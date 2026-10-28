# INF601 - Advanced Programming in Python
# Samuel Hart
# Mini Project 6

"""Catalogue lookups for Open Library and TCGdex, both without API keys."""

import json
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

OPEN_LIBRARY_SEARCH = "https://openlibrary.org/search.json"
OPEN_LIBRARY_COVER = "https://covers.openlibrary.org/b/id/{cover_id}-M.jpg"
TCGDEX_CARDS = "https://api.tcgdex.net/v2/en/cards"
TCGDEX_SEARCH_LIMIT = 12
REQUEST_TIMEOUT = 10
USER_AGENT = "PagesForPokemon/1.0 (family reading app)"


class LookupUnavailable(Exception):
    """Raised when a catalogue service cannot be reached or understood."""


def build_cover_url(cover_id):
    """Return the Open Library cover address for a numeric id, or None."""
    if not cover_id:
        return None
    return OPEN_LIBRARY_COVER.format(cover_id=cover_id)


def build_tcgdex_image_url(image):
    """Return the low-resolution artwork URL for a bare TCGdex image path."""
    if not image:
        return None
    return f"{image}/low.webp"


def _fetch_json(url):
    """Fetch one JSON document, leaving HTTP errors for the caller."""
    request = Request(
        url,
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
    )
    try:
        with urlopen(request, timeout=REQUEST_TIMEOUT) as response:
            return json.load(response)
    except HTTPError:
        # Re-raised so callers can tell a 404 from a service failure.
        raise
    except (URLError, OSError, ValueError) as exc:
        raise LookupUnavailable(f"Could not reach the catalogue: {exc}") from exc


def search_open_library(title):
    """Return up to five Open Library matches for a title."""
    params = urlencode({
        "q": title,
        "limit": 5,
        "fields": "key,title,author_name,first_publish_year,cover_i",
    })
    try:
        data = _fetch_json(f"{OPEN_LIBRARY_SEARCH}?{params}")
    except HTTPError as exc:
        raise LookupUnavailable(f"Open Library returned {exc.code}") from exc
    if not isinstance(data, dict):
        raise LookupUnavailable("Open Library returned an unexpected response.")

    results = []
    for doc in data.get("docs", []):
        cover_id = doc.get("cover_i")
        try:
            cover_id = int(cover_id) if cover_id is not None else None
        except (TypeError, ValueError):
            cover_id = None
        authors = doc.get("author_name") or []
        if isinstance(authors, str):
            authors = [authors]
        results.append({
            "title": doc.get("title") or title,
            "author": ", ".join(authors) if authors else "Unknown author",
            "year": doc.get("first_publish_year"),
            "cover_id": cover_id,
            "cover_url": build_cover_url(cover_id),
        })
    return results


def search_tcgdex(name, limit=TCGDEX_SEARCH_LIMIT):
    """Return TCGdex matches for a card name, all when limit is None."""
    params = urlencode({"name": name})
    try:
        data = _fetch_json(f"{TCGDEX_CARDS}?{params}")
    except HTTPError as exc:
        raise LookupUnavailable(f"TCGdex returned {exc.code}") from exc
    if not isinstance(data, list):
        raise LookupUnavailable("TCGdex returned an unexpected response.")

    results = []
    rows = data if limit is None else data[:limit]
    for row in rows:
        results.append({
            "id": row.get("id", ""),
            "local_id": row.get("localId", ""),
            "name": row.get("name", ""),
            "image_url": build_tcgdex_image_url(row.get("image")),
        })
    return results


def fetch_tcgdex_card(card_id):
    """Return one TCGdex card record, or None when the id is unknown."""
    url = f"{TCGDEX_CARDS}/{quote(card_id, safe='')}"
    try:
        data = _fetch_json(url)
    except HTTPError as exc:
        if exc.code == 404:
            return None
        raise LookupUnavailable(f"TCGdex returned {exc.code}") from exc
    if not isinstance(data, dict):
        raise LookupUnavailable("TCGdex returned an unexpected response.")
    return data


def card_initial_from_record(record):
    """Return CardForm initial values from one TCGdex record."""
    set_data = record.get("set") or {}
    rarity = record.get("rarity")
    if rarity in (None, "", "None"):
        rarity = ""
    return {
        "name": record.get("name", ""),
        "set_name": set_data.get("name") or set_data.get("id", ""),
        "number": record.get("localId", ""),
        "rarity": rarity,
        "image_url": build_tcgdex_image_url(record.get("image")) or "",
        "catalogue_id": record.get("id", ""),
    }
