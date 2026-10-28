# INF601 - Advanced Programming in Python
# Samuel Hart
# Mini Project 6

import re
from dataclasses import dataclass
from datetime import datetime

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.contrib.auth.hashers import check_password, make_password
from django.db import IntegrityError, transaction
from django.db.models import IntegerField, Sum, Value
from django.db.models.functions import Coalesce
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST, require_safe

from .artcache import cache_remote_art, cached_art_url
from .decorators import parent_required
from .energy import build_energy_grid, build_registration_grid
from .forms import (
    CardForm,
    EnergyRegistrationForm,
    EnergyResetForm,
    EnergySequenceForm,
    LoginForm,
    LogReadingForm,
    PickBookForm,
    UsernameForm,
)
from .lookups import (
    LookupUnavailable,
    card_initial_from_record,
    fetch_tcgdex_card,
    search_open_library,
    search_tcgdex,
)
from .models import Book, Card, Profile, Purchase, Reading, annotate_chapter_balance

ART_NAME_RE = re.compile(r"^[0-9a-f]{64}\.(?:jpg|jpeg|png|webp|gif|img)$")
ART_CONTENT_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".gif": "image/gif",
    ".img": "application/octet-stream",
}
MAX_ENERGY_FAILURES = 5


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


def _reading_message(reading):
    """Return the success message for a newly logged reading."""
    unit = "chapter" if reading.chapters == 1 else "chapters"
    return f"Logged {reading.chapters} {unit} of {reading.book.title}."


def register(request):
    """Create a reader account with a three-energy login order."""
    if request.method == "POST":
        form = EnergyRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            messages.success(
                request,
                f"Account {user.username} created. Log in with your energy order.",
            )
            return redirect("library:login")
    else:
        form = EnergyRegistrationForm()
    return render(
        request,
        "library/register.html",
        {"form": form, "energy_tiles": build_registration_grid()},
    )


def _safe_next(request, next_url):
    """Return next_url when it is local, otherwise the login redirect."""
    if next_url and url_has_allowed_host_and_scheme(
        next_url, {request.get_host()}, require_https=request.is_secure()
    ):
        return next_url
    return settings.LOGIN_REDIRECT_URL


def login_view(request):
    """Log in a parent with a password or a reader with three energy types."""
    next_url = request.POST.get("next") or request.GET.get("next", "")
    stage = "identify"
    identify_form = UsernameForm()
    energy_form = None
    energy_tiles = None
    password_form = None
    username = ""

    if request.method == "POST":
        action = request.POST.get("action", "")
        username = (request.POST.get("username") or "").strip()

        if action == "identify":
            identify_form = UsernameForm(request.POST)
            if identify_form.is_valid():
                user = get_user_model().objects.filter(
                    username=username, is_active=True
                ).first()
                if user is None:
                    messages.error(request, "No active account with that name.")
                elif user.is_staff:
                    stage = "password"
                    password_form = LoginForm(
                        request, initial={"username": username}
                    )
                else:
                    profile = Profile.objects.filter(user=user).first()
                    if profile is None:
                        messages.error(
                            request,
                            "This reader has no energy order yet. "
                            "Ask a parent to set one.",
                        )
                    elif profile.failed_attempts >= MAX_ENERGY_FAILURES:
                        messages.error(
                            request,
                            "Too many tries. Ask a parent to reset your energy order.",
                        )
                    else:
                        stage = "energy"
                        energy_form = EnergySequenceForm()
                        energy_tiles = build_energy_grid(
                            [
                                profile.first_type,
                                profile.second_type,
                                profile.third_type,
                            ]
                        )
        elif action == "password":
            stage = "password"
            password_form = LoginForm(request, data=request.POST)
            if password_form.is_valid():
                login(request, password_form.get_user())
                return redirect(_safe_next(request, next_url))
            messages.error(request, "That username and password did not match.")
        elif action == "energy":
            user = get_user_model().objects.filter(
                username=username, is_active=True
            ).first()
            profile = Profile.objects.filter(user=user).first() if user else None
            if user is None or profile is None:
                messages.error(request, "That reader could not be found.")
            elif profile.failed_attempts >= MAX_ENERGY_FAILURES:
                messages.error(
                    request,
                    "Too many tries. Ask a parent to reset your energy order.",
                )
            else:
                energy_form = EnergySequenceForm(request.POST)
                if energy_form.is_valid():
                    payload = ":".join([
                        energy_form.cleaned_data["first_type"],
                        energy_form.cleaned_data["second_type"],
                        energy_form.cleaned_data["third_type"],
                    ])
                    if check_password(payload, profile.energy_hash):
                        profile.failed_attempts = 0
                        profile.save(update_fields=["failed_attempts"])
                        login(
                            request,
                            user,
                            backend="django.contrib.auth.backends.ModelBackend",
                        )
                        return redirect(_safe_next(request, next_url))
                    profile.failed_attempts += 1
                    profile.save(update_fields=["failed_attempts"])
                    messages.error(request, "That order did not match. Try again.")
                else:
                    messages.error(request, "Choose three different energy types.")
                if profile.failed_attempts >= MAX_ENERGY_FAILURES:
                    stage = "identify"
                    messages.error(
                        request,
                        "Too many tries. Ask a parent to reset your energy order.",
                    )
                else:
                    stage = "energy"
                    energy_form = EnergySequenceForm()
                    energy_tiles = build_energy_grid(
                        [
                            profile.first_type,
                            profile.second_type,
                            profile.third_type,
                        ]
                    )

    return render(
        request,
        "library/login.html",
        {
            "stage": stage,
            "identify_form": identify_form,
            "energy_form": energy_form,
            "energy_tiles": energy_tiles,
            "password_form": password_form,
            "username": username,
            "next": next_url,
        },
    )


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
    """Record a reading, offering Open Library matches for a new title."""
    reader = _get_active_reader(reader_id)
    owned_books = reader.books.order_by("title")
    lookup_results = None
    lookup_title = ""
    lookup_chapters = None
    lookup_error = None

    if request.method == "POST":
        action = request.POST.get("action", "log")
        if action == "pick":
            pick_form = PickBookForm(request.POST, reader=reader)
            if pick_form.is_valid():
                reading = pick_form.save()
                messages.success(request, _reading_message(reading))
                return redirect("library:wallet", reader_id=reader.pk)
            messages.error(request, "That book could not be logged. Try again.")
            form = LogReadingForm(reader=reader)
        else:
            form = LogReadingForm(request.POST, reader=reader)
            if form.is_valid():
                new_title = (form.cleaned_data.get("new_title") or "").strip()
                if new_title and form.owned_book() is None:
                    lookup_title = new_title
                    lookup_chapters = form.cleaned_data["chapters"]
                    try:
                        lookup_results = search_open_library(new_title)
                    except LookupUnavailable:
                        lookup_error = (
                            "Open Library could not be reached. "
                            "You can still log the book without a cover."
                        )
                    for result in lookup_results or []:
                        cache_remote_art(result["cover_url"])
                        result["cached_cover_url"] = cached_art_url(
                            result["cover_url"]
                        )
                else:
                    reading = form.save()
                    messages.success(request, _reading_message(reading))
                    return redirect("library:wallet", reader_id=reader.pk)
    else:
        form = LogReadingForm(reader=reader)

    return render(
        request,
        "library/log_reading.html",
        {
            "reader": reader,
            "form": form,
            "owned_books": owned_books,
            "lookup_results": lookup_results,
            "lookup_title": lookup_title,
            "lookup_chapters": lookup_chapters,
            "lookup_error": lookup_error,
        },
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


@require_safe
def serve_art(request, name):
    """Serve one cached artwork file with a long-lived cache header."""
    if not ART_NAME_RE.fullmatch(name):
        raise Http404
    path = settings.ART_CACHE_ROOT / name
    if not path.is_file():
        raise Http404
    suffix = "." + name.rsplit(".", 1)[-1]
    content_type = ART_CONTENT_TYPES.get(suffix, "application/octet-stream")
    response = FileResponse(path.open("rb"), content_type=content_type)
    response["Cache-Control"] = "public, max-age=31536000, immutable"
    return response


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
def manage_readers(request):
    """List readers and the parent's forms for resetting energy orders."""
    readers = get_user_model().objects.filter(
        is_staff=False, is_active=True
    ).order_by("username")
    rows = []
    for reader in readers:
        profile = Profile.objects.filter(user=reader).first()
        initial = None
        if profile:
            initial = {
                "first_type": profile.first_type,
                "second_type": profile.second_type,
                "third_type": profile.third_type,
            }
        rows.append({
            "reader": reader,
            "profile": profile,
            "form": EnergyResetForm(initial=initial),
            "locked": bool(
                profile and profile.failed_attempts >= MAX_ENERGY_FAILURES
            ),
        })
    return render(request, "library/manage_readers.html", {"rows": rows})


@parent_required
@require_POST
def reset_energy(request, reader_id):
    """Let a parent set a new energy order and clear the failure count."""
    reader = get_object_or_404(
        get_user_model(), pk=reader_id, is_staff=False, is_active=True
    )
    form = EnergyResetForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Choose three different energy types.")
        return redirect("library:manage_readers")
    first = form.cleaned_data["first_type"]
    second = form.cleaned_data["second_type"]
    third = form.cleaned_data["third_type"]
    profile = Profile.objects.filter(user=reader).first()
    if profile is None:
        profile = Profile(user=reader)
    profile.first_type = first
    profile.second_type = second
    profile.third_type = third
    profile.energy_hash = make_password(f"{first}:{second}:{third}")
    profile.failed_attempts = 0
    profile.save()
    messages.success(request, f"Energy order reset for {reader.username}.")
    return redirect("library:manage_readers")


@parent_required
def manage_card_new(request):
    """Add a card by hand or from a TCGdex lookup, keeping the typed price."""
    query = request.GET.get("q", "").strip()
    tcgdex_id = request.GET.get("tcgdex_id", "").strip()
    results = []
    selected = None
    lookup_error = None

    if request.method == "POST":
        form = CardForm(request.POST)
        if form.is_valid():
            try:
                with transaction.atomic():
                    card = form.save()
            except IntegrityError:
                messages.error(request, "This card is already in the inventory.")
            else:
                if card.image_url:
                    cache_remote_art(card.image_url)
                messages.success(request, f"Added {card.name} to the inventory.")
                return redirect("library:manage_cards")
    else:
        initial = {}
        if tcgdex_id:
            try:
                selected = fetch_tcgdex_card(tcgdex_id)
            except LookupUnavailable:
                lookup_error = "TCGdex could not be reached. Try again."
            if selected:
                initial = card_initial_from_record(selected)
            else:
                messages.error(request, "TCGdex has no card with that id.")
        form = CardForm(initial=initial)
        if query:
            try:
                results = search_tcgdex(query)
            except LookupUnavailable:
                lookup_error = "TCGdex could not be reached. Try again."
            for result in results:
                cache_remote_art(result["image_url"])
                result["cached_image_url"] = cached_art_url(result["image_url"])

    return render(
        request,
        "library/manage_card_new.html",
        {
            "form": form,
            "query": query,
            "results": results,
            "selected": selected,
            "lookup_error": lookup_error,
        },
    )
