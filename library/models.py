# INF601 - Advanced Programming in Python
# Samuel Hart
# Mini Project 6

from django.conf import settings
from django.db import models
from django.db.models import F, IntegerField, OuterRef, Subquery, Sum, Value
from django.db.models.functions import Coalesce, Lower

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
