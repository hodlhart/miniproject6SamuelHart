# INF601 - Advanced Programming in Python
# Samuel Hart
# Mini Project 6

from .collage import build_wallpaper


def wallpaper(request):
    """Add cached collage tiles for the current library page."""
    match = request.resolver_match
    if match is None or match.namespace != "library":
        return {}
    reader_id = match.kwargs.get("reader_id")
    return {"wallpaper_tiles": build_wallpaper(int(reader_id) if reader_id else 0)}
