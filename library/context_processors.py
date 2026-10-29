# INF601 - Advanced Programming in Python
# Samuel Hart
# Mini Project 6

from pathlib import Path

from django.conf import settings

from .collage import build_wallpaper


def wallpaper(request):
    """Add cached collage tiles for the current library page."""
    match = request.resolver_match
    if match is None or match.namespace != "library":
        return {}
    reader_id = match.kwargs.get("reader_id")
    return {"wallpaper_tiles": build_wallpaper(int(reader_id) if reader_id else 0)}

def static_version(request):
    """Return the app stylesheet's modification time, so a change is never served stale."""
    stylesheet = Path(settings.BASE_DIR) / "static" / "app.css"
    try:
        return {"STATIC_VERSION": int(stylesheet.stat().st_mtime)}
    except OSError:
        return {"STATIC_VERSION": 0}
