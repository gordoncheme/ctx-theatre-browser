# CTX Live Theatre Productions
  Video Demo:  <https://youtu.be/kmROSknHBv8>

  Description: The CTX Live Theatre Productions program allows a user to maintain a store of production events, and review/ search them on demand.

## Overview

CTX Live Theatre Productions is a command-line program that collects, stores, and displays theatre productions from the CTX Live Theatre website. Although CTX provides a public RSS feed, it only lists upcoming productions. This project expands on that feed by scraping each production’s webpage for more complete show details and then storing everything in a JSON file for long-term use.

The program has a menu-driven interface that lets the user synchronize new productions from the web, view all saved productions, search by title, see only future productions, and add productions manually. I chose this project because I enjoy local theatre and wanted a simple personal tool to browse shows in one place. I plan to deploy this somehow so I can actually use it.

---

## Data Model

Each production is stored as a Python dictionary containing:

- **slug** (unique key)
- **title**
- **url**
- **category** (usually "Productions" or "Manual")
- **date_text** (raw date string from HTML)
- **start_date** and **end_date** in ISO format
- **days_of_week**
- **venue_name** and **venue_address**
- **rss_description** (plain-text)
- **rss_description_html** (raw HTML)
- **html_synopsis**

All productions are saved inside a JSON file (`events.json`) where each key is the slug. This prevents duplicate entries and allows easy updates when syncing.

---

## Functionality

### 1. Syncing the RSS Feed
The program uses the `requests` library to download CTX’s RSS feed. Each item in the feed contains a title, link, category, and HTML description. Only items in the “Productions” category are processed. For each production, the script fetches the associated HTML page.

### 2. HTML Parsing
HTML parsing is done using regular expressions because the CTX pages have a predictable structure. The program extracts:
- date range from the `<h3>` block
- venue information from the `<address>` block
- the first paragraph after `<h3>` as the synopsis

A helper function cleans HTML into plain text.

If the main date header does not include a year, the script searches the page for a full date range and uses that instead.

### 3. Storage
Each production is stored or updated in `events.json`. Slugs come from the URL, and manual entries generate their own slug. This allows the user to add older shows that no longer appear in the RSS feed.

### 4. Searching and Filtering
The program supports:
- listing all productions
- showing only future productions
- searching titles for a keyword

Searches are case-insensitive. Future productions are those whose end date is today or later.

### 5. Manual Additions
The user may add a production manually by entering all required details. This makes the program useful even when the RSS feed does not show older productions.

---

## Testing

The file `test_project.py` includes small tests for:
- slug extraction
- HTML cleanup
- date-range parsing
- venue parsing
- slug uniqueness for manual entries

These tests help ensure that the core parsing logic behaves correctly.

---

## Libraries

The only third-party library required is:

- `requests` – for downloading RSS and HTML pages

All other modules come from Python’s standard library.

---

## Conclusion

The program meets all the goals I had when starting: it collects CTX theatre production information, stores it for later browsing, and gives me simple tools to filter and search the list. It also handles manual entries, making it possible to maintain a personal history of shows beyond what the RSS feed provides.

