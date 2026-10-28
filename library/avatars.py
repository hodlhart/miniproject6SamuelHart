# INF601 - Advanced Programming in Python
# Samuel Hart
# Mini Project 6

"""Choose card art for a reader's portrait, using the existing cache."""

from django.conf import settings
from django.urls import reverse

from .artcache import cache_remote_art
from .lookups import search_tcgdex

STARTER_POKEMON = (
    "Pikachu",
    "Charizard",
    "Bulbasaur",
    "Squirtle",
    "Charmander",
    "Eevee",
    "Snorlax",
    "Mewtwo",
    "Gengar",
    "Dragonite",
    "Lucario",
    "Gardevoir",
)
AVATAR_CANDIDATES = 5


def search_avatar_candidates(query, limit=AVATAR_CANDIDATES):
    """Return up to five cards with cached artwork for a name."""
    rows = search_tcgdex(query, limit=None)
    candidates = []
    for row in rows:
        if len(candidates) >= limit:
            break
        remote_url = row.get("image_url")
        if not remote_url:
            continue
        local_name = cache_remote_art(remote_url)
        if not local_name:
            continue
        try:
            size = (settings.ART_CACHE_ROOT / local_name).stat().st_size
        except OSError:
            continue
        candidates.append({
            "id": row.get("id", ""),
            "name": row.get("name", ""),
            "remote_url": remote_url,
            "local_url": reverse("library:art", args=[local_name]),
            "size": size,
        })
    return candidates
