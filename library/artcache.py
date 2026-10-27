# INF601 - Advanced Programming in Python
# Samuel Hart
# Mini Project 6

"""Fetch remote artwork once into a gitignored folder and serve it locally."""

import hashlib
import os
import tempfile
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from django.conf import settings
from django.urls import reverse

USER_AGENT = "PagesForPokemon/1.0 (family reading app)"
REQUEST_TIMEOUT = 10
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".gif"}


def _extension_for(url):
    """Return a safe image suffix for a remote URL."""
    suffix = Path(urlparse(url).path).suffix.lower()
    return suffix if suffix in IMAGE_SUFFIXES else ".img"


def local_name_for_url(url):
    """Return the cache file name derived from the source URL."""
    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()
    return f"{digest}{_extension_for(url)}"


def cache_remote_art(url):
    """Fetch one remote image into the cache and return its local name."""
    if not url:
        return None
    name = local_name_for_url(url)
    path = settings.ART_CACHE_ROOT / name
    if path.is_file():
        return name

    temp_name = None
    try:
        settings.ART_CACHE_ROOT.mkdir(parents=True, exist_ok=True)
        request = Request(url, headers={"User-Agent": USER_AGENT})
        with urlopen(request, timeout=REQUEST_TIMEOUT) as response:
            if not response.headers.get_content_type().startswith("image/"):
                return None
            data = response.read()
        if not data:
            return None
        with tempfile.NamedTemporaryFile(
            dir=settings.ART_CACHE_ROOT, delete=False
        ) as handle:
            handle.write(data)
            temp_name = handle.name
        os.replace(temp_name, path)
    except (HTTPError, URLError, OSError, ValueError):
        if temp_name:
            try:
                os.unlink(temp_name)
            except OSError:
                pass
        return None
    return name


def cached_art_name(url):
    """Return the local name when this artwork is cached, or None."""
    if not url:
        return None
    name = local_name_for_url(url)
    return name if (settings.ART_CACHE_ROOT / name).is_file() else None


def cached_art_url(url):
    """Return the app URL for cached artwork, or None when it is missing."""
    name = cached_art_name(url)
    if not name:
        return None
    return reverse("library:art", args=[name])
