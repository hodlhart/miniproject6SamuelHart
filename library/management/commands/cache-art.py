# INF601 - Advanced Programming in Python
# Samuel Hart
# Mini Project 6

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from library.artcache import cache_remote_art, local_name_for_url
from library.energy import ENERGY_TYPES, cache_energy_deck
from library.lookups import build_cover_url
from library.models import Book, Card


class Command(BaseCommand):
    """Fetch card, cover, and energy artwork into the local cache."""

    help = (
        "Fetch card, book cover, and energy artwork into the local cache. "
        "Fails when the energy deck has no print for a type."
    )

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
            f"Cards and covers: Fetched: {fetched} | Already cached: {already} | "
            f"Could not fetch: {failed}"
        )
        energy = cache_energy_deck()
        self.stdout.write(
            f"Energy deck: Fetched: {energy['fetched']} | "
            f"Already cached: {energy['already']} | "
            f"Missing prints: {energy['missing']}"
        )
        self.stdout.flush()
        if energy["types_without_prints"]:
            missing = ", ".join(energy["types_without_prints"])
            if len(energy["types_without_prints"]) == len(ENERGY_TYPES):
                headline = "Energy deck is empty"
            else:
                headline = "Energy deck incomplete"
            cause = ""
            if energy["errors"]:
                cause = " Lookup failed: " + "; ".join(energy["errors"]) + "."
            raise CommandError(
                f"{headline}: no cached print for {missing}.{cause} "
                "The login grid still works with labelled tiles."
            )
