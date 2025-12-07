##Comments

##Global Variable Declaration

##Functions (roughly in call order)

import json
from pydoc import cli
import re
from urllib.parse import urlparse
import xml.etree.ElementTree as ET
import html
from datetime import date
import requests
import sys

# ---------- Helpers for storing data ----------

def slug_from_url(url):
    """
    Extract slug from a CTX production URL.
    Example:
      https://.../productions/20260116-songs-for-a-new-world-by-waco-civic-theat/
      -> 20260116-songs-for-a-new-world-by-waco-civic-theat

    """
    path = urlparse(url).path  # e.g. "/productions/20260116-songs-for-a-new-world-by-waco-civic-theat/"
    return path.rstrip("/").split("/")[-1]


def load_store(path):
    """
    Load existing events from JSON file.
    If file doesn't exist or is bad, return empty dict.

    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError:
        return {}


def save_store(path, data):
    """
    Save events dict to JSON file.

    """
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

#----------- Other Helpers --------

def html_to_text(raw_html):
    """
    Convert HTML or HTML-escaped text to plain text.
    - Unescapes entities like &lt; and &amp;rsquo;
    - Strips HTML tags
    - Collapses extra whitespace

    """
    if not raw_html:
        return ""

    # First unescape entities (&lt;p&gt; -> <p>, &amp;rsquo; -> ’, etc.)
    unescaped = html.unescape(raw_html)

    # Remove HTML tags like <p>, <strong>, etc.
    no_tags = re.sub(r"<.*?>", "", unescaped)

    # Collapse whitespace
    return " ".join(no_tags.split())


def fetch_text(url, fallback_path=None):
    """
    Try to GET text from a URL.
    If it fails and fallback_path is provided, load from that file instead.

    """
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        return resp.text
    except Exception as e:
        print(f"Warning: could not fetch {url}: {e}")
        if fallback_path:
            print(f"Falling back to local file: {fallback_path}")
            with open(fallback_path, "r", encoding="utf-8") as f:
                return f.read()
        # No fallback, re-raise or return empty
        raise

def make_manual_slug(title, start_date, existing_slugs):
    """
    Create a slug from start_date and title, like:
      '2025-11-21-rex-dexter-of-mars'
    Ensure it's unique within existing_slugs.

    """
    base = f"{start_date}-{title.lower()}"
    # Replace non-alphanumeric with hyphens
    base = re.sub(r"[^a-z0-9]+", "-", base)
    base = base.strip("-")
    if not base:
        base = "manual-production"

    slug = base
    counter = 2
    while slug in existing_slugs:
        slug = f"{base}-{counter}"
        counter += 1

    return slug


def prompt_date(prompt):
    """
    Prompt the user for a date in YYYY-MM-DD format.
    Repeats until valid.

    """
    while True:
        text = input(prompt).strip()
        try:
            d = date.fromisoformat(text)  # raises ValueError if bad
            return d.isoformat()          # store as 'YYYY-MM-DD'
        except ValueError:
            print("Invalid date. Please use YYYY-MM-DD (e.g., 2025-11-21).")


def add_manual_event(events, store_path):
    """
    Interactively add a production manually.
    Updates the events dict and writes to events.json.

    """
    print("\n=== Add a manual production ===")

    # Required fields
    title = ""
    while not title:
        title = input("Title (required): ").strip()
        if not title:
            print("Title is required.")

    # URL optional (for older shows you might not have one)
    url = input("URL (optional, press Enter if none): ").strip()

    print("Enter the production dates:")
    start_date = prompt_date("  Start date (YYYY-MM-DD): ")
    end_date = prompt_date("  End date   (YYYY-MM-DD): ")

    days_of_week = input("Days of week (optional, e.g., 'Fridays-Saturdays'): ").strip()

    venue_name = input("Venue name (optional): ").strip()
    venue_address = input("Venue address (optional): ").strip()

    short_desc = input("Short description (optional): ").strip()

    # Determine slug
    existing_slugs = set(events.keys())
    if url:
        slug = slug_from_url(url)
    else:
        slug = make_manual_slug(title, start_date, existing_slugs)

    # Warn if overwriting
    if slug in events:
        print(f"\nWarning: A production with slug '{slug}' already exists.")
        overwrite = input("Overwrite it? [y/N]: ").strip().lower()
        if overwrite != "y":
            print("Aborted adding manual production.\n")
            return

    # Build date_text
    date_text = f"{start_date} - {end_date}"

    record = {
        "slug": slug,
        "url": url,
        "title": title,
        "category": "Manual",          # distinguish from RSS 'Productions'
        "date_text": date_text,
        "start_date": start_date,
        "end_date": end_date,
        "days_of_week": days_of_week,
        "venue_name": venue_name,
        "venue_address": venue_address,
        "rss_description_html": "",    # no HTML source for manual entries
        "rss_description": short_desc,
        "html_synopsis": short_desc,
    }

    events[slug] = record
    save_store(store_path, events)

    print(f"\nAdded/updated manual production with slug '{slug}'.\n")


def run_sync_only():
    """
    Helper to run sync and exit.
    """
    print("Running sync-only mode...")
    sync_events("events.json")
    print("Sync-only complete.")

# ---------- RSS parsing ----------

def parse_rss_items(xml_text):
    """
    Parse the RSS XML and return a list of items.
    Each item is a dict with title, link, and category.

    """
    root = ET.fromstring(xml_text)
    channel = root.find("channel")
    items = []

    for item in channel.findall("item"):
        title = item.findtext("title", "").strip()
        link = item.findtext("link", "").strip()
        category = item.findtext("category", "").strip()
        description = item.findtext("description", "").strip()

        items.append({
            "title": title,
            "link": link,
            "category": category,
            "description": description
        })

    return items

# ---------- Production page HTML parsing ----------

def get_date_text_from_production_page(html):
    """
    Extract the date text from the first <h3>...</h3> block
    on a CTX production page.

    """
    # Find <h3> ... </h3>, including newlines
    match = re.search(r"<h3>(.*?)</h3>", html, re.DOTALL | re.IGNORECASE)
    if not match:
        return ""

    h3_content = match.group(1)

    # Replace <br> with a space
    h3_content = re.sub(r"<br\s*/?>", " ", h3_content)

    # Remove any remaining HTML tags, like <small>...</small>
    h3_content = re.sub(r"<.*?>", "", h3_content)

    # Collapse whitespace
    date_text = " ".join(h3_content.split())
    return date_text

def find_full_date_text_in_html(html):
    """
    Look for a full date range with a year anywhere in the HTML, like:
      'November 21 - November 22, 2025'
      or
      'November 21 - 22, 2025'
    Returns the matched string, or "" if none found.

    """

    # Pattern 1: Month day - Month day, Year
    m = re.search(r"([A-Za-z]+\s+\d{1,2})\s*-\s*([A-Za-z]+\s+\d{1,2}),\s*(\d{4})", html)
    if m:
        return m.group(0)

    # Pattern 2: Month day - day, Year (same month)
    m = re.search(r"([A-Za-z]+\s+\d{1,2})\s*-\s*(\d{1,2}),\s*(\d{4})", html)
    if m:
        # Expand the second date with the same month
        month_day1, day2, year = m.groups()
        # month_day1 is e.g. "November 21"
        month = month_day1.split()[0]
        full = f"{month_day1} - {month} {day2}, {year}"
        return full

    return ""


def get_first_paragraph(html):
    h3_match = re.search(r"<h3>.*?</h3>", html, re.DOTALL)
    if not h3_match:
        return ""

    rest = html[h3_match.end():]

    p_match = re.search(r"<p>(.*?)</p>", rest, re.DOTALL)
    if not p_match:
        return ""

    paragraph_html = p_match.group(1)
    paragraph_text = re.sub(r"<.*?>", "", paragraph_html)
    return " ".join(paragraph_text.split())

def get_venue_info(html):
    """
    Extracts the venue name and address from the <address> block.
    Returns (venue_name, venue_address).
    If not found, returns ("", "").

    """

    # Find the <address>...</address> block
    match = re.search(r"<address>(.*?)</address>", html, re.DOTALL | re.IGNORECASE)
    if not match:
        return "", ""

    address_block = match.group(1)

    # Extract venue name (inside <strong> ... </strong>)
    name_match = re.search(r"<strong>(.*?)</strong>", address_block, re.DOTALL | re.IGNORECASE)
    if name_match:
        raw_name = name_match.group(1)
        # Strip any tags inside (e.g., <a href="...">Aurora Arts Theatre</a>)
        venue_name = re.sub(r"<.*?>", "", raw_name)
        venue_name = " ".join(venue_name.split())
    else:
        venue_name = ""

    # Remove the <strong>...</strong> block from the address_block
    remainder = re.sub(r"<strong>.*?</strong>", "", address_block, flags=re.DOTALL | re.IGNORECASE)

    # Strip HTML tags from remainder to get the address text
    remainder = re.sub(r"<.*?>", "", remainder)
    venue_address = " ".join(remainder.split())

    return venue_name, venue_address


#------------ parse date range ------------

MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4,
    "may": 5, "jun": 6, "jul": 7, "aug": 8,
    "sep": 9, "sept": 9, "oct": 10, "nov": 11, "dec": 12
}


def parse_date_range(date_text):
    """
    Parse strings like:
      'Jan. 16 - Jan. 24, 2026 Fridays-Saturdays'
    into:
      start_date = '2026-01-16'
      end_date   = '2026-01-24'
      days_of_week = 'Fridays-Saturdays'

    If parsing fails, returns ("", "", "").

    """
    # Capture: "Jan. 16 - Jan. 24, 2026" + the rest
    pattern = r"([A-Za-z\.]+\s+\d{1,2})\s*-\s*([A-Za-z\.]+\s+\d{1,2}),\s*(\d{4})(.*)"
    m = re.match(pattern, date_text)
    if not m:
        return "", "", ""

    start_md, end_md, year_str, rest = m.groups()
    year = int(year_str)

    def parse_md(md):
        # md looks like "Jan. 16" or "January 16"
        parts = md.split()
        if len(parts) != 2:
            return ""

        month_token = parts[0].rstrip(".")   # "Jan." -> "Jan"
        day_str = parts[1].rstrip(",")       # "16," -> "16"

        month_key = month_token[:3].lower()  # "Jan" -> "jan"
        if month_key not in MONTHS:
            return ""

        month = MONTHS[month_key]
        day = int(day_str)

        return date(year, month, day).isoformat()  # 'YYYY-MM-DD'

    start_date = parse_md(start_md)
    end_date = parse_md(end_md)
    days_of_week = rest.strip()  # whatever comes after the year

    return start_date, end_date, days_of_week

# ---------- main actions -----------

#Sync Events

def sync_events(store_path="events.json"):
    """
    Sync productions from the RSS + HTML pages into the events.json store.
    Returns the updated events dictionary.
    
    """
    events = load_store(store_path)

    RSS_URL = "https://ctxlivetheatre.com/rss/all/"
    rss_xml = fetch_text(RSS_URL, fallback_path="sample_feed.xml")
    rss_items = parse_rss_items(rss_xml)

    for item in rss_items:
        if item["category"] != "Productions":
            continue

        url = item["link"]
        slug = slug_from_url(url)

        production_html = fetch_text(url, fallback_path="sample_production_page.html")

        date_text = get_date_text_from_production_page(production_html)
        start_date, end_date, days_of_week = parse_date_range(date_text)

        # Fallback if h3 didn’t have a year / didn’t parse
        if not start_date or not end_date:
            full_date_text = find_full_date_text_in_html(production_html)
            if full_date_text:
                # You may not have days_of_week here; that’s OK
                start_date, end_date, _ = parse_date_range(full_date_text)
                # Keep days_of_week from h3 if you want, or leave blank
                if not date_text:
                    date_text = full_date_text


        venue_name, venue_address = get_venue_info(production_html)

        record = {
            "slug": slug,
            "url": url,
            "title": item["title"],
            "category": item["category"],
            "date_text": date_text,
            "start_date": start_date,
            "end_date": end_date,
            "days_of_week": days_of_week,
            "venue_name": venue_name,
            "venue_address": venue_address,
            "rss_description_html": item["description"],
            "rss_description": html_to_text(item["description"]),
            "html_synopsis": get_first_paragraph(production_html),
        }

        events[slug] = record
        print(f"Updated: {slug} → {item['title']}")

    save_store(store_path, events)
    print(f"\nSaved {len(events)} productions.")
    return events


#List Events

def list_all_events(events):
    print("\n=== All Productions ===\n")
    for slug, event in events.items():
        print(event["title"])
        print(f"  {event['start_date']} → {event['end_date']} ({event['days_of_week']})")
        print(f"  Venue: {event['venue_name']}")
        print(f"  URL: {event['url']}")
        print()

#Search Events

def search_events(events, keyword):
    """
    Search productions by title OR RSS description (case-insensitive).
    Results are sorted by start_date.
    """
    if not keyword:
        print("\nNo keyword entered.\n")
        return

    keyword_lower = keyword.lower()
    matches = []

    for event in events.values():
        if keyword_lower in event["title"].lower():   # <-- title only
            matches.append(event)

    if not matches:
        print(f"\nNo productions found for '{keyword}'.\n")
        return

    matches.sort(key=lambda e: e.get("start_date") or "")

    print(f"\n=== Search results for '{keyword}' ===\n")
    for event in matches:
        print(event["title"])
        print(f"  {event['start_date']} → {event['end_date']} ({event['days_of_week']})")
        print(f"  Venue: {event['venue_name']}")
        print(f"  URL: {event['url']}")
        print()

#Show Future Productions

def show_future_productions(events):
    """
    Show productions whose end_date is today or later.
    This includes shows that are currently running or upcoming.
    """
    today = date.today()
    matches = []

    for event in events.values():
        end_str = event.get("end_date") or ""
        if not end_str:
            continue  # skip events without an end_date

        try:
            end = date.fromisoformat(end_str)
        except ValueError:
            continue  # skip bad data

        if end >= today:
            matches.append(event)

    if not matches:
        print("\nNo future productions found.\n")
        return

    print(f"\n=== Future productions (end date >= {today.isoformat()}) ===\n")

    # Sort by start_date if available
    matches.sort(key=lambda e: (e.get("start_date") or ""))

    for event in matches:
        title = event["title"]
        start = event.get("start_date") or "?"
        end = event.get("end_date") or "?"
        days = event.get("days_of_week") or ""
        venue = event.get("venue_name") or ""

        print(event["title"])
        print(f"  {event['start_date']} → {event['end_date']} ({event['days_of_week']})")
        print(f"  Venue: {event['venue_name']}")
        print(f"  URL: {event['url']}")
        print()


##Main function

def main():
    store_path = "events.json"
    events = load_store(store_path)

    if len(sys.argv) > 1 and sys.argv[1] == "--sync-only":
        run_sync_only()
    else:

        while True:
            print("\n====== CTX Theatre Browser ======")
            print("1. Sync productions (update from web)")
            print("2. List all productions")
            print("3. Show future productions")
            print("4. Search productions (title)")
            print("5. Add a production manually")
            print("6. Quit")

            choice = input("Choose an option: ").strip()

            if choice == "1":
                events = sync_events(store_path)

            elif choice == "2":
                list_all_events(events)

            elif choice == "3":
                show_future_productions(events)

            elif choice == "4":
                keyword = input("Input keyword: ").strip()
                if keyword:
                    search_events(events, keyword)
                else:
                    print("No keyword entered.\n")

            elif choice == "5":
                add_manual_event(events, store_path)
                # reload from disk in case you want fresh state
                events = load_store(store_path)

            elif choice == "6":
                print("Goodbye!")
                break

            else:
                print("Invalid choice. Please enter 1–6.")


##Call Main Function


if __name__ == "__main__":
    main()





