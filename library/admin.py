# INF601 - Advanced Programming in Python
# Samuel Hart
# Mini Project 6

from django.contrib import admin
from django.db.models import Count

from .models import Book, Card, Purchase, Reading


@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    """Admin for books, showing the owning reader and the reading log size."""

    list_display = ("title", "owner", "reading_count")
    list_filter = ("owner",)
    search_fields = ("title", "owner__username")
    ordering = ("title",)
    list_select_related = ("owner",)

    def get_queryset(self, request):
        """Return books with owner and reading count fetched by the changelist query."""
        queryset = super().get_queryset(request)
        return queryset.select_related("owner").annotate(reading_count=Count("readings"))

    @admin.display(description="Readings", ordering="reading_count")
    def reading_count(self, book):
        """Return how many reading entries this book has."""
        return book.reading_count


@admin.register(Reading)
class ReadingAdmin(admin.ModelAdmin):
    """Admin for reading entries, ordered newest first."""

    list_display = ("book", "owner", "chapters", "logged_at")
    list_filter = ("book__owner", "logged_at")
    search_fields = ("book__title", "book__owner__username")
    ordering = ("-logged_at",)
    list_select_related = ("book", "book__owner")

    @admin.display(description="Reader", ordering="book__owner__username")
    def owner(self, reading):
        """Return the reader whose book this entry belongs to."""
        return reading.book.owner


@admin.register(Card)
class CardAdmin(admin.ModelAdmin):
    """Admin for the card inventory, with price and sale state visible."""

    list_display = (
        "name",
        "set_name",
        "number",
        "rarity",
        "tier",
        "price_chapters",
        "for_sale",
    )
    list_filter = ("tier", "for_sale", "set_name")
    search_fields = ("name", "set_name", "tcgdex_id")
    ordering = ("name", "set_name")


@admin.register(Purchase)
class PurchaseAdmin(admin.ModelAdmin):
    """Admin for purchases, ordered newest first with buyer and card joined."""

    list_display = ("card", "user", "chapters_spent", "purchased_at")
    list_filter = ("user", "purchased_at")
    search_fields = ("card__name", "user__username")
    ordering = ("-purchased_at",)
    list_select_related = ("card", "user")
