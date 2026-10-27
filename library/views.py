# INF601 - Advanced Programming in Python
# Samuel Hart
# Mini Project 6

from dataclasses import dataclass
from datetime import datetime

from django.contrib.auth import get_user_model
from django.db.models import IntegerField, Sum, Value
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404, render

from .models import Book, Card, Purchase, Reading, annotate_chapter_balance


@dataclass(frozen=True)
class StatementLine:
    """One dated change to a reader's chapter balance."""

    when: datetime
    description: str
    change: int


def index(request):
    """Render each reader's balance alongside every card currently for sale."""
    # The parent owns the inventory and signs in through the admin; the other
    # accounts are the readers, so staff accounts are left off the family page.
    readers = annotate_chapter_balance(
        get_user_model().objects.filter(is_staff=False).order_by("username")
    )
    cards = Card.objects.filter(for_sale=True).order_by("name", "set_name")
    return render(request, "library/index.html", {"readers": readers, "cards": cards})


def wallet(request, reader_id):
    """Render one reader's readings and purchases as a statement with one total."""
    reader = get_object_or_404(get_user_model(), pk=reader_id)
    readings = Reading.objects.filter(book__owner=reader).select_related("book")
    purchases = Purchase.objects.filter(user=reader).select_related("card")
    lines = [
        StatementLine(
            when=reading.logged_at,
            description=f"Read {reading.chapters} chapters of {reading.book.title}",
            change=reading.chapters,
        )
        for reading in readings
    ]
    lines.extend(
        StatementLine(
            when=purchase.purchased_at,
            description=f"Bought {purchase.card.name}",
            change=-purchase.chapters_spent,
        )
        for purchase in purchases
    )
    lines.sort(key=lambda line: line.when, reverse=True)
    # The footer total is the annotated balance, the same figure the home page
    # shows, rather than a second sum that could drift from it.
    balance = annotate_chapter_balance(
        get_user_model().objects.filter(pk=reader.pk)
    ).get().balance
    return render(
        request,
        "library/wallet.html",
        {"reader": reader, "lines": lines, "balance": balance},
    )


def books(request, reader_id):
    """Render one reader's books with the chapters read from each."""
    reader = get_object_or_404(get_user_model(), pk=reader_id)
    reader_books = (
        Book.objects.filter(owner=reader)
        .annotate(
            chapters_read=Coalesce(
                Sum("readings__chapters"), Value(0), output_field=IntegerField()
            )
        )
        .order_by("title")
    )
    return render(
        request,
        "library/books.html",
        {"reader": reader, "books": reader_books},
    )


def shop(request):
    """Render every card currently for sale."""
    cards = Card.objects.filter(for_sale=True).order_by("name", "set_name")
    return render(request, "library/shop.html", {"cards": cards})


def my_cards(request, reader_id):
    """Render the cards one reader already owns, newest purchase first."""
    reader = get_object_or_404(get_user_model(), pk=reader_id)
    purchases = (
        Purchase.objects.filter(user=reader)
        .select_related("card")
        .order_by("-purchased_at")
    )
    return render(
        request,
        "library/my_cards.html",
        {"reader": reader, "purchases": purchases},
    )
