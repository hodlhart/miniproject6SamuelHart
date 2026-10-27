# INF601 - Advanced Programming in Python
# Samuel Hart
# Mini Project 6

from dataclasses import dataclass
from datetime import datetime

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import IntegerField, Sum, Value
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .decorators import parent_required
from .forms import CardForm, LogReadingForm, ReaderCreationForm
from .models import Book, Card, Purchase, Reading, annotate_chapter_balance


@dataclass(frozen=True)
class StatementLine:
    """One dated change to a reader's chapter balance."""

    when: datetime
    description: str
    change: int


def _reader_balance(reader):
    """Return one reader's derived chapter balance."""
    return annotate_chapter_balance(
        get_user_model().objects.filter(pk=reader.pk)
    ).get().balance


def _get_active_reader(reader_id):
    """Return an active reader, or 404 so a hidden reader leaves the site."""
    return get_object_or_404(get_user_model(), pk=reader_id, is_active=True)


def register(request):
    """Create a reader account with Django's UserCreationForm."""
    if request.method == "POST":
        form = ReaderCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            messages.success(
                request,
                f"Account {user.username} created. Log in to start reading.",
            )
            return redirect("library:login")
    else:
        form = ReaderCreationForm()
    return render(request, "library/register.html", {"form": form})


def index(request):
    """Render each active reader's balance and every card currently for sale."""
    # The parent owns the inventory and signs in through the admin; the other
    # accounts are the readers, so staff accounts are left off the family page.
    # Hidden readers are inactive, never deleted, and disappear from this list.
    readers = annotate_chapter_balance(
        get_user_model()
        .objects.filter(is_staff=False, is_active=True)
        .order_by("username")
    )
    cards = Card.objects.filter(for_sale=True).order_by("name", "set_name")
    return render(request, "library/index.html", {"readers": readers, "cards": cards})


def wallet(request, reader_id):
    """Render one reader's readings and purchases as a statement with one total."""
    reader = _get_active_reader(reader_id)
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
    balance = _reader_balance(reader)
    return render(
        request,
        "library/wallet.html",
        {"reader": reader, "lines": lines, "balance": balance},
    )


def log_reading(request, reader_id):
    """Record a reading for one reader, optionally creating a new book first."""
    reader = _get_active_reader(reader_id)
    if request.method == "POST":
        form = LogReadingForm(request.POST, reader=reader)
        if form.is_valid():
            reading = form.save()
            unit = "chapter" if reading.chapters == 1 else "chapters"
            messages.success(
                request,
                f"Logged {reading.chapters} {unit} of {reading.book.title}.",
            )
            return redirect("library:wallet", reader_id=reader.pk)
    else:
        form = LogReadingForm(reader=reader)
    return render(
        request,
        "library/log_reading.html",
        {"reader": reader, "form": form},
    )


def reader_shop(request, reader_id):
    """Show one reader's balance and the cards on offer with buy controls."""
    reader = _get_active_reader(reader_id)
    cards = Card.objects.filter(for_sale=True).order_by("name", "set_name")
    return render(
        request,
        "library/reader_shop.html",
        {"reader": reader, "balance": _reader_balance(reader), "cards": cards},
    )


@require_POST
def buy_card(request, reader_id, card_id):
    """Sell a for-sale card to one reader, refusing an unaffordable purchase."""
    reader = _get_active_reader(reader_id)
    # BEGIN IMMEDIATE is configured on the database, so entering this block
    # takes SQLite's write lock before the balance is read. No other purchase
    # can commit between the check and the insert below.
    with transaction.atomic():
        card = get_object_or_404(Card, pk=card_id)
        if Purchase.objects.filter(card=card).exists():
            messages.error(request, f"{card.name} has already been bought.")
            return redirect("library:reader_shop", reader_id=reader.pk)
        if not card.for_sale:
            messages.error(request, f"{card.name} is not for sale.")
            return redirect("library:reader_shop", reader_id=reader.pk)
        balance = _reader_balance(reader)
        if balance < card.price_chapters:
            messages.error(
                request,
                f"{reader.username} cannot afford {card.name}: it costs "
                f"{card.price_chapters} chapters and the balance is {balance}.",
            )
            return redirect("library:reader_shop", reader_id=reader.pk)
        Purchase.objects.create(
            user=reader,
            card=card,
            chapters_spent=card.price_chapters,
        )
        card.for_sale = False
        card.save(update_fields=["for_sale"])
    messages.success(
        request,
        f"Bought {card.name} for {card.price_chapters} chapters.",
    )
    return redirect("library:my_cards", reader_id=reader.pk)


def books(request, reader_id):
    """Render one reader's books with the chapters read from each."""
    reader = _get_active_reader(reader_id)
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
    reader = _get_active_reader(reader_id)
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


@parent_required
def manage_cards(request):
    """List every card for a parent and apply remove or put-back actions."""
    if request.method == "POST":
        card_id = request.POST.get("card_id")
        if not card_id:
            messages.error(request, "No card was selected.")
            return redirect("library:manage_cards")
        card = get_object_or_404(Card, pk=card_id)
        action = request.POST.get("action")
        if action == "remove":
            card.for_sale = False
            card.save(update_fields=["for_sale"])
            messages.success(request, f"{card.name} removed from sale.")
        elif action == "restore":
            card.for_sale = True
            card.save(update_fields=["for_sale"])
            messages.success(request, f"{card.name} put back on sale.")
        else:
            messages.error(request, "Unknown card action.")
        return redirect("library:manage_cards")
    cards = Card.objects.order_by("name", "set_name")
    return render(request, "library/manage_cards.html", {"cards": cards})


@parent_required
def manage_card_new(request):
    """Add a card to the inventory with the price the parent types."""
    if request.method == "POST":
        form = CardForm(request.POST)
        if form.is_valid():
            card = form.save()
            messages.success(request, f"Added {card.name} to the inventory.")
            return redirect("library:manage_cards")
    else:
        form = CardForm()
    return render(request, "library/manage_card_new.html", {"form": form})
