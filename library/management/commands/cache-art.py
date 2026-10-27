# INF601 - Advanced Programming in Python
# Samuel Hart
# Mini Project 6

from django.conf import settings
from django.core.management.base import BaseCommand

from library.artcache import cache_remote_art, local_name_for_url
from library.lookups import build_cover_url
from library.models import Book, Card


class Command(BaseCommand):
    """Fetch every card image and book cover into the local artwork cache."""

    help = "Fetch card and book artwork into the local cache."

    def handle(self, *args, **options):
        """Fetch missing artwork and report fetched, cached and failed counts."""
        urls = list(
            Card.objects.exclude(image_url="").values_list("image_url", flat=True)
        )
        urls.extend(
            build_cover_url(cover_id)
            for cover_id in Book.objects.exclude(cover_id=None).values_list(
                "cover_id", flat=True
            )
        )
        unique_urls = list(dict.fromkeys(url for url in urls if url))

        fetched = 0
        already = 0
        failed = 0
        for url in unique_urls:
            name = local_name_for_url(url)
            if (settings.ART_CACHE_ROOT / name).is_file():
                already += 1
                continue
            if cache_remote_art(url):
                fetched += 1
            else:
                failed += 1

        self.stdout.write(
            f"Fetched: {fetched} | Already cached: {already} | "
            f"Could not fetch: {failed}"
        )
