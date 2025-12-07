import pytest
from datetime import date

from project import (
    slug_from_url,
    html_to_text,
    parse_date_range,
    get_venue_info,
    make_manual_slug,
)


def test_slug_from_url():
    url = "https://ctxlivetheatre.com/productions/20260116-songs-for-a-new-world-by-waco-civic-theat/"
    assert slug_from_url(url) == "20260116-songs-for-a-new-world-by-waco-civic-theat"


def test_html_to_text():
    html_input = "<p>Hello <strong>World</strong>!</p>"
    assert html_to_text(html_input) == "Hello World!"


def test_parse_date_range():
    text = "Jan. 16 - Jan. 24, 2026 Fridays-Saturdays"
    start, end, days = parse_date_range(text)
    assert start == "2026-01-16"
    assert end == "2026-01-24"
    assert days == "Fridays-Saturdays"


def test_get_venue_info():
    html = """
        <address>
            <strong>Waco Civic Theatre</strong><br>
            1517 Lake Air Drive<br>
            Waco, TX 76717
        </address>
    """
    name, addr = get_venue_info(html)
    assert name == "Waco Civic Theatre"
    assert "1517 Lake Air Drive" in addr
    assert "Waco" in addr


def test_make_manual_slug_uniqueness():
    existing = {"2025-11-21-rex-dexter-of-mars"}
    slug = make_manual_slug("Rex Dexter of Mars", "2025-11-21", existing)
    assert slug != "2025-11-21-rex-dexter-of-mars"
    assert slug.startswith("2025-11-21-rex-dexter-of-mars")

