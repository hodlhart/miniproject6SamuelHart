# INF601 - Advanced Programming in Python
# Samuel Hart
# Mini Project 6

from django.conf import settings
from django.db import models
from django.db.models import F, IntegerField, OuterRef, Subquery, Sum, Value
from django.db.models.functions import Coalesce, Lower

from .artcache import cached_art_url
from .energy import ENERGY_TYPES
from .lookups import build_cover_url


class Book(models.Model):
    """A book that belongs to one reader."""

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="books",
    )
    title = models.CharField(max_length=200)
    # The numeric Open Library cover id, not a URL. The address is built from
    # it when needed, so the stored value stays independent of the cover host.
    cover_id = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        # One reader cannot hold "Wings of Fire" and "wings of fire" as two
        # books. The constraint compares the folded title, so case, and the
        # owner together decide identity at the database level.
        constraints = [
            models.UniqueConstraint(
                Lower("title"),
                "owner",
                name="library_book_unique_title_per_owner",
            ),
        ]

    @property
    def cover_url(self):
        """Return the Open Library cover address for this book, or None."""
        return build_cover_url(self.cover_id)

    @property
    def cached_cover_url(self):
        """Return the local URL for this book's cached cover, or None."""
        return cached_art_url(self.cover_url)

    def __str__(self):
        """Return the title with its reader, so admin rows are distinguishable."""
        return f"{self.title} ({self.owner})"


class Reading(models.Model):
    """Chapters read from one book on one occasion."""

    book = models.ForeignKey(
        Book,
        on_delete=models.CASCADE,
        related_name="readings",
    )
    chapters = models.PositiveSmallIntegerField()
    logged_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        # A log entry of zero chapters would earn credit for nothing, so the
        # floor is enforced by the database rather than by a form alone.
        constraints = [
            models.CheckConstraint(
                condition=models.Q(chapters__gte=1),
                name="library_reading_chapters_at_least_one",
            ),
        ]

    def __str__(self):
        """Return the chapter count and book title for this log entry."""
        return f"{self.chapters} chapters from {self.book.title}"


class Card(models.Model):
    """A physical Pokemon card held in the family's inventory."""

    class Tier(models.TextChoices):
        """Printing tiers. A tier suggests a price, it does not set one."""

        NORMAL = "normal", "Normal"
        EX = "ex", "EX"
        FULL_ART = "full_art", "Full art"

    name = models.CharField(max_length=200)
    set_name = models.CharField(max_length=200)
    number = models.CharField(max_length=20)
    rarity = models.CharField(max_length=50)
    price_chapters = models.PositiveSmallIntegerField()
    tier = models.CharField(
        max_length=20,
        choices=Tier.choices,
        default=Tier.NORMAL,
    )
    image_url = models.URLField(blank=True)
    for_sale = models.BooleanField(default=True)
    # Nullable unique columns accept unlimited nulls, so the catalogue id is
    # declared non-null as well as unique.
    tcgdex_id = models.CharField(max_length=100, unique=True)

    @property
    def cached_image_url(self):
        """Return the local URL for this card's cached artwork, or None."""
        return cached_art_url(self.image_url)

    def __str__(self):
        """Return the card name and set, which identify it to the family."""
        return f"{self.name} ({self.set_name})"


class Purchase(models.Model):
    """A card bought with chapters, frozen at the price charged that day."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="purchases",
    )
    card = models.OneToOneField(
        Card,
        on_delete=models.PROTECT,
        related_name="purchase",
    )
    # A snapshot, not a lookup of Card.price_chapters. Re-pricing the card later
    # leaves this number alone, so history and balances stay correct.
    chapters_spent = models.PositiveSmallIntegerField()
    purchased_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        """Return the card and buyer for this purchase."""
        return f"{self.card.name} bought by {self.user}"


class Profile(models.Model):
    """The ordered energy types a reader uses to log in."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile",
    )
    # The types are kept for two jobs only: building the nine-type login grid
    # and prefilling a parent's reset form. The credential check uses the salted
    # energy_hash below, never these fields.
    first_type = models.CharField(max_length=20, choices=ENERGY_TYPES)
    second_type = models.CharField(max_length=20, choices=ENERGY_TYPES)
    third_type = models.CharField(max_length=20, choices=ENERGY_TYPES)
    energy_hash = models.CharField(max_length=128)
    failed_attempts = models.PositiveSmallIntegerField(default=0)

    def __str__(self):
        """Return the reader and their first energy type."""
        return f"{self.user} ({self.first_type})"


def annotate_chapter_balance(users):
    """Annotate a user queryset with chapters read, spent and the difference.

    The balance is computed from the two totals on every call. Nothing is
    stored, so it cannot drift out of step with the readings and purchases.
    The subqueries keep the two independent totals apart; summing across both
    relations in one join would multiply the rows and overstate each total.
    """
    read = (
        Reading.objects.filter(book__owner=OuterRef("pk"))
        .order_by()
        .values("book__owner")
        .annotate(total=Sum("chapters"))
        .values("total")
    )
    spent = (
        Purchase.objects.filter(user=OuterRef("pk"))
        .order_by()
        .values("user")
        .annotate(total=Sum("chapters_spent"))
        .values("total")
    )
    zero = Value(0, output_field=IntegerField())
    annotated = users.annotate(
        chapters_read=Coalesce(Subquery(read, output_field=IntegerField()), zero),
        chapters_spent=Coalesce(Subquery(spent, output_field=IntegerField()), zero),
    )
    return annotated.annotate(balance=F("chapters_read") - F("chapters_spent"))
