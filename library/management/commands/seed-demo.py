# INF601 - Advanced Programming in Python
# Samuel Hart
# Mini Project 6

from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from library.artcache import cached_art_name
from library.avatars import search_avatar_candidates
from library.lookups import LookupUnavailable
from library.models import Book, Card, Profile, Purchase, Reading

PARENT_USERNAME = "parent"
PARENT_EMAIL = "parent@example.com"

READERS = {
    "maya": ("fire", "water", "grass"),
    "leo": ("lightning", "psychic", "fighting"),
    "zoe": ("darkness", "metal", "fairy"),
}

# Each reader gets a different, easily recognised Pokemon portrait. The
# artwork is found and cached through the same helper the registration page
# uses, so the picker shows cards from the first run.
PORTRAITS = {
    "maya": "Pikachu",
    "leo": "Charizard",
    "zoe": "Gengar",
}

BOOKS = {
    "maya": (
        ("The One and Only Ivan", 12656488, (3, 4)),
        ("The Wild Robot", 7443301, (2, 3)),
    ),
    "leo": (
        ("The Hobbit", 14627509, (10, 12)),
        ("Wonder", 8223160, (8, 10)),
    ),
    "zoe": (
        ("Dog Man", 7894142, (4, 5)),
        ("The One and Only Bob", 10108500, (6, 7)),
    ),
}

CARDS = (
    (
        "Charizard ex", "Obsidian Flames", "125", "Double rare", 20,
        Card.Tier.EX, True, "sv03-125",
        "https://assets.tcgdex.net/en/sv/sv03/125/low.webp",
    ),
    (
        "Pikachu", "Base Set", "58", "Common", 5,
        Card.Tier.NORMAL, False, "base1-58",
        "https://assets.tcgdex.net/en/base/base1/58/low.webp",
    ),
    (
        "Mew ex", "151", "151", "Double rare", 30,
        Card.Tier.FULL_ART, False, "sv03.5-151",
        "https://assets.tcgdex.net/en/sv/sv03.5/151/low.webp",
    ),
    (
        "Snorlax", "151", "143", "Uncommon", 3,
        Card.Tier.NORMAL, False, "sv03.5-143",
        "https://assets.tcgdex.net/en/sv/sv03.5/143/low.webp",
    ),
    (
        "Bulbasaur", "Base Set", "44", "Common", 4,
        Card.Tier.NORMAL, True, "base1-44",
        "https://assets.tcgdex.net/en/base/base1/44/low.webp",
    ),
    (
        "Squirtle", "Base Set", "63", "Common", 6,
        Card.Tier.NORMAL, True, "base1-63",
        "https://assets.tcgdex.net/en/base/base1/63/low.webp",
    ),
    (
        "Charmander", "Base Set", "46", "Common", 5,
        Card.Tier.NORMAL, True, "base1-46",
        "https://assets.tcgdex.net/en/base/base1/46/low.webp",
    ),
    (
        "Umbreon VMAX", "Evolving Skies", "215", "Secret Rare", 40,
        Card.Tier.FULL_ART, True, "swsh7-215",
        "https://assets.tcgdex.net/en/swsh/swsh7/215/low.webp",
    ),
)

PURCHASES = (
    ("maya", "Pikachu", 5),
    ("leo", "Mew ex", 30),
)


class Command(BaseCommand):
    """Seed a demo family, fetching a card portrait for each reader."""

    help = (
        "Seed a believable demo family into an empty database. Each reader "
        "gets a portrait, so this command needs network access to TCGdex."
    )

    def add_arguments(self, parser):
        """Add the --force flag."""
        parser.add_argument(
            "--force",
            action="store_true",
            help=(
                "Delete existing readers, purchases and cards, then seed again."
            ),
        )

    def handle(self, *args, **options):
        """Seed the demo family and report created and skipped rows."""
        force = options["force"]
        user_model = get_user_model()
        existing = user_model.objects.filter(is_staff=False)
        if existing.exists() and not force:
            names = ", ".join(
                existing.order_by("username").values_list("username", flat=True)
            )
            raise CommandError(
                f"This database already has readers: {names}.\n"
                "Refusing to seed again. --force would delete every non-staff "
                "user (with their books, readings, purchases and profiles), "
                "every purchase, and every card in the inventory, then seed "
                "the demo again. Staff accounts are left alone."
            )

        counts = {
            "parent": 0,
            "readers": 0,
            "books": 0,
            "readings": 0,
            "cards": 0,
            "purchases": 0,
        }
        skipped = []
        self.portraits = {}

        with transaction.atomic():
            if force:
                Purchase.objects.all().delete()
                Card.objects.all().delete()
                user_model.objects.filter(is_staff=False).delete()

            if self._seed_parent():
                counts["parent"] = 1
            else:
                skipped.append(f"parent {PARENT_USERNAME!r} (already exists)")

            cards = self._seed_cards(counts)
            readers = self._seed_readers(counts)

            for username, books in BOOKS.items():
                reader = readers[username]
                for title, cover_id, chapter_counts in books:
                    book = Book.objects.create(
                        owner=reader,
                        title=title,
                        cover_id=cover_id,
                    )
                    counts["books"] += 1
                    for chapters in chapter_counts:
                        Reading.objects.create(book=book, chapters=chapters)
                        counts["readings"] += 1

            for username, card_name, chapters_spent in PURCHASES:
                Purchase.objects.create(
                    user=readers[username],
                    card=cards[card_name],
                    chapters_spent=chapters_spent,
                )
                counts["purchases"] += 1

        self._print_report(counts, skipped)
        self._warn_missing_art()

    def _seed_parent(self):
        """Return True when the demo parent was created, False when reused."""
        user_model = get_user_model()
        parent = user_model.objects.filter(username=PARENT_USERNAME).first()
        if parent is not None:
            if not parent.is_staff:
                raise CommandError(
                    f"A non-staff user named {PARENT_USERNAME!r} exists. "
                    "Use --force to replace the demo data."
                )
            return False
        user_model.objects.create_superuser(
            username=PARENT_USERNAME,
            email=PARENT_EMAIL,
            password=None,
        )
        return True

    def _seed_readers(self, counts):
        """Create the three readers with Profiles and portraits, by name."""
        readers = {}
        for username, energy_types in READERS.items():
            user = get_user_model().objects.create_user(username=username)
            user.set_unusable_password()
            user.save(update_fields=["password"])
            first, second, third = energy_types
            profile = Profile.objects.create(
                user=user,
                first_type=first,
                second_type=second,
                third_type=third,
                energy_hash=make_password(f"{first}:{second}:{third}"),
            )
            self._choose_portrait(username, profile)
            readers[username] = user
            counts["readers"] += 1
        return readers

    def _choose_portrait(self, username, profile):
        """Find card art for this reader's Pokemon and store the first match."""
        pokemon = PORTRAITS[username]
        try:
            candidates = search_avatar_candidates(pokemon)
        except LookupUnavailable as exc:
            raise CommandError(
                f"TCGdex could not be reached while choosing a portrait for "
                f"{username!r} ({pokemon}). Seeding needs the network for "
                "portraits."
            ) from exc
        if not candidates:
            raise CommandError(
                f"TCGdex returned no card art for {pokemon} ({username})."
            )
        # Searches often list promo prints first; the plain-name card is the
        # one a child recognises, so prefer it when the search offers it.
        candidate = next(
            (item for item in candidates if item["name"] == pokemon),
            candidates[0],
        )
        profile.avatar_url = candidate["remote_url"]
        profile.save(update_fields=["avatar_url"])
        self.portraits[username] = candidate

    def _seed_cards(self, counts):
        """Create the demo cards and return them by name."""
        cards = {}
        for card_data in CARDS:
            (
                name,
                set_name,
                number,
                rarity,
                price,
                tier,
                for_sale,
                tcgdex_id,
                image_url,
            ) = card_data
            card = Card.objects.create(
                name=name,
                set_name=set_name,
                number=number,
                rarity=rarity,
                price_chapters=price,
                tier=tier,
                for_sale=for_sale,
                tcgdex_id=tcgdex_id,
                image_url=image_url,
            )
            cards[name] = card
            counts["cards"] += 1
        return cards

    def _print_report(self, counts, skipped):
        """Print the seeded rows and the skipped items."""
        if counts["parent"]:
            self.stdout.write(
                f'Created parent "{PARENT_USERNAME}" with an unusable password. '
                f"Run `python manage.py changepassword {PARENT_USERNAME}` "
                "to sign in."
            )
        else:
            self.stdout.write(f'Reused parent "{PARENT_USERNAME}".')
        for username, energy_types in READERS.items():
            self.stdout.write(
                f'Created reader "{username}" with energy order '
                f"{', '.join(energy_types)}."
            )
            portrait = self.portraits[username]
            self.stdout.write(
                f'  Portrait: {portrait["name"]} '
                f'({portrait["id"]}, {portrait["size"]} bytes).'
            )
        self.stdout.write(
            f"Created {counts['books']} books, {counts['readings']} readings, "
            f"{counts['cards']} cards and {counts['purchases']} purchases."
        )
        if skipped:
            self.stdout.write("Skipped: " + "; ".join(skipped) + ".")
        else:
            self.stdout.write("Skipped: nothing.")

    def _warn_missing_art(self):
        """Tell the user when seeded artwork is not in the cache yet."""
        missing = 0
        for card in Card.objects.exclude(image_url=""):
            if cached_art_name(card.image_url) is None:
                missing += 1
        for book in Book.objects.exclude(cover_id=None):
            if cached_art_name(book.cover_url) is None:
                missing += 1
        if missing:
            self.stdout.write(
                f"Artwork not cached yet: {missing} files. "
                "Run `python manage.py cache-art` before viewing covers and cards."
            )
        else:
            self.stdout.write("All seeded artwork is already cached.")
