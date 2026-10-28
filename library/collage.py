# INF601 - Advanced Programming in Python
# Samuel Hart
# Mini Project 6

"""Choose deterministic cached artwork for the page background collage."""

import hashlib

from django.contrib.auth import get_user_model
from django.utils import timezone

from .artcache import cached_art_url
from .energy import ENERGY_TYPES, energy_print_urls, load_energy_deck
from .lookups import build_cover_url
from .models import Book, Card, Profile, Purchase

MAX_TILES = 12
TOP_UP_THRESHOLD = 6
COVERS_PER_READER = 2


def _cached_urls(remote_urls):
    """Return local URLs for remote artwork already in the cache."""
    return [url for url in (cached_art_url(u) for u in remote_urls) if url]


def _tile_key(seed, url):
    """Return a deterministic ordering key for one artwork URL."""
    return hashlib.sha256(f"{seed}:{url}".encode()).hexdigest()


def _global_candidates():
    """Return every card plus a small sample of each reader's covers."""
    candidates = _cached_urls(
        Card.objects.exclude(image_url="").values_list("image_url", flat=True)
    )
    reader_ids = get_user_model().objects.filter(
        is_staff=False, is_active=True
    ).values_list("id", flat=True)
    for reader_id in reader_ids:
        cover_ids = (
            Book.objects.filter(owner_id=reader_id)
            .exclude(cover_id=None)
            .values_list("cover_id", flat=True)
        )
        covers = _cached_urls(build_cover_url(cover_id) for cover_id in cover_ids)
        candidates.extend(covers[:COVERS_PER_READER])
    return candidates


def _reader_candidates(reader_id):
    """Return a reader's books and owned cards, topped up from for-sale cards."""
    reader = get_user_model().objects.filter(pk=reader_id, is_active=True).first()
    if reader is None:
        return []
    cover_ids = (
        Book.objects.filter(owner=reader)
        .exclude(cover_id=None)
        .values_list("cover_id", flat=True)
    )
    candidates = _cached_urls(build_cover_url(cover_id) for cover_id in cover_ids)
    candidates.extend(
        _cached_urls(
            Purchase.objects.filter(user=reader).values_list(
                "card__image_url", flat=True
            )
        )
    )
    candidates = list(dict.fromkeys(candidates))
    if len(candidates) < TOP_UP_THRESHOLD:
        candidates.extend(
            _cached_urls(
                Card.objects.filter(for_sale=True).values_list(
                    "image_url", flat=True
                )
            )
        )
    return candidates


def _energy_fill(reader_id, needed, seed):
    """Return cached energy tiles, favourite types first, then any type."""
    profile = Profile.objects.filter(user_id=reader_id).first()
    favourite = []
    if profile:
        favourite = [
            profile.first_type,
            profile.second_type,
            profile.third_type,
        ]
    deck = load_energy_deck()
    favourite_urls = []
    for code in favourite:
        favourite_urls.extend(energy_print_urls(code, deck))
    other_urls = []
    for code, _ in ENERGY_TYPES:
        if code not in favourite:
            other_urls.extend(energy_print_urls(code, deck))
    favourite_urls = list(dict.fromkeys(favourite_urls))
    other_urls = list(dict.fromkeys(other_urls))
    favourite_urls.sort(key=lambda url: _tile_key(seed, url))
    other_urls.sort(key=lambda url: _tile_key(seed, url))
    return (favourite_urls + other_urls)[:needed]


def build_wallpaper(reader_id):
    """Return up to twelve cached artwork URLs seeded by reader and day."""
    seed = f"{reader_id}:{timezone.localdate().toordinal()}"
    if reader_id:
        own = list(dict.fromkeys(_reader_candidates(reader_id)))
        own.sort(key=lambda url: _tile_key(seed, url))
        own = own[:MAX_TILES]
        if len(own) < MAX_TILES:
            own.extend(_energy_fill(reader_id, MAX_TILES - len(own), seed))
        return own[:MAX_TILES]
    candidates = list(dict.fromkeys(_global_candidates()))
    candidates.sort(key=lambda url: _tile_key(seed, url))
    return candidates[:MAX_TILES]
