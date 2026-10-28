# INF601 - Advanced Programming in Python
# Samuel Hart
# Mini Project 6

"""The energy deck: cached prints, the manifest, and the login/register grids."""

import json
import os
import random
import tempfile

from django.conf import settings
from django.urls import reverse

from .artcache import cache_remote_art, local_name_for_url
from .lookups import (
    LookupUnavailable,
    build_tcgdex_image_url,
    fetch_tcgdex_card,
    search_tcgdex,
)

ENERGY_TYPES = (
    ("grass", "Grass"),
    ("fire", "Fire"),
    ("water", "Water"),
    ("lightning", "Lightning"),
    ("psychic", "Psychic"),
    ("fighting", "Fighting"),
    ("darkness", "Darkness"),
    ("metal", "Metal"),
    ("fairy", "Fairy"),
    ("dragon", "Dragon"),
)
ENERGY_TYPE_LABELS = dict(ENERGY_TYPES)
PRINTS_PER_TYPE = 5
DECK_MANIFEST = "energy-deck.json"


def deck_manifest_path():
    """Return the manifest path inside the gitignored cache folder."""
    return settings.ART_CACHE_ROOT / DECK_MANIFEST


def load_energy_deck():
    """Return the cached energy file names grouped by type."""
    try:
        with deck_manifest_path().open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return {}
    if not isinstance(data, dict):
        return {}
    deck = {}
    for code, names in data.items():
        if code not in ENERGY_TYPE_LABELS or not isinstance(names, list):
            continue
        deck[code] = [name for name in names if isinstance(name, str)]
    return deck


def _write_energy_deck(deck):
    """Write the energy manifest atomically inside the cache folder."""
    settings.ART_CACHE_ROOT.mkdir(parents=True, exist_ok=True)
    path = deck_manifest_path()
    with tempfile.NamedTemporaryFile(
        dir=settings.ART_CACHE_ROOT,
        mode="w",
        encoding="utf-8",
        delete=False,
    ) as handle:
        json.dump(deck, handle, indent=2, sort_keys=True)
        temp_name = handle.name
    os.replace(temp_name, path)


def _existing_names(names):
    """Return the listed file names that still exist on disk."""
    return [
        name for name in names if (settings.ART_CACHE_ROOT / name).is_file()
    ]


def cache_energy_deck():
    """Cache up to five artwork prints per energy type and return counts."""
    deck = load_energy_deck()
    fetched = 0
    already = 0
    missing = 0
    result = {}

    for code, label in ENERGY_TYPES:
        names = _existing_names(deck.get(code, []))[:PRINTS_PER_TYPE]
        already += len(names)
        if len(names) >= PRINTS_PER_TYPE:
            result[code] = names
            continue

        seen = set(names)
        try:
            rows = search_tcgdex(f"{label} energy", limit=None)
        except LookupUnavailable:
            rows = []
        for row in rows:
            if len(names) >= PRINTS_PER_TYPE:
                break
            if not row.get("image_url"):
                continue
            # The search row already carries the card's name. Reject a special
            # before spending a record request on it.
            if row.get("name") != f"{label} Energy":
                continue
            try:
                record = fetch_tcgdex_card(row["id"])
            except LookupUnavailable:
                continue
            if record is None:
                continue
            # Both tests must pass. A special energy carries rules text, so it
            # has an effect key; the record name check repeats the row's name
            # against the authoritative record.
            if "effect" in record:
                continue
            if record.get("name") != f"{label} Energy":
                continue
            url = build_tcgdex_image_url(record.get("image"))
            if not url:
                continue
            name = local_name_for_url(url)
            if name in seen:
                continue
            if (settings.ART_CACHE_ROOT / name).is_file():
                already += 1
            else:
                name = cache_remote_art(url)
                if not name:
                    continue
                fetched += 1
            seen.add(name)
            names.append(name)
        if names:
            result[code] = names
            if len(names) < PRINTS_PER_TYPE:
                missing += PRINTS_PER_TYPE - len(names)

    _write_energy_deck(result)
    return {"fetched": fetched, "already": already, "missing": missing}


def energy_print_urls(type_code, deck=None):
    """Return the cached app URLs for one energy type's prints."""
    if deck is None:
        deck = load_energy_deck()
    urls = []
    for name in deck.get(type_code, []):
        if (settings.ART_CACHE_ROOT / name).is_file():
            urls.append(reverse("library:art", args=[name]))
    return urls


def available_energy_types(deck=None):
    """Return the energy types that have at least one cached print."""
    if deck is None:
        deck = load_energy_deck()
    return [
        (code, label)
        for code, label in ENERGY_TYPES
        if energy_print_urls(code, deck)
    ]


def build_energy_grid(required_types, deck=None, size=9):
    """Return distinct energy tiles for available types, including required ones."""
    if deck is None:
        deck = load_energy_deck()
    available = [code for code, _ in available_energy_types(deck)]
    required = list(
        dict.fromkeys(code for code in required_types if code in available)
    )
    pool = [code for code in available if code not in required]
    extra = random.sample(pool, min(size - len(required), len(pool)))
    codes = required + extra
    random.shuffle(codes)

    tiles = []
    for code in codes:
        urls = energy_print_urls(code, deck)
        tiles.append({
            "code": code,
            "label": ENERGY_TYPE_LABELS[code],
            "image_url": random.choice(urls),
        })
    return tiles


def build_registration_grid(deck=None):
    """Return one tile per available energy type for the registration picker."""
    if deck is None:
        deck = load_energy_deck()
    tiles = []
    for code, label in available_energy_types(deck):
        urls = energy_print_urls(code, deck)
        tiles.append({
            "code": code,
            "label": label,
            "image_url": random.choice(urls),
        })
    random.shuffle(tiles)
    return tiles
