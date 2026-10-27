# INF601 - Advanced Programming in Python
# Samuel Hart
# Mini Project 6

from django.contrib.auth import get_user_model
from django.shortcuts import render

from .models import Card, annotate_chapter_balance


def index(request):
    """Render each reader's balance alongside every card currently for sale."""
    # The parent owns the inventory and signs in through the admin; the other
    # accounts are the readers, so staff accounts are left off the family page.
    readers = annotate_chapter_balance(
        get_user_model().objects.filter(is_staff=False).order_by("username")
    )
    cards = Card.objects.filter(for_sale=True).order_by("name", "set_name")
    return render(request, "library/index.html", {"readers": readers, "cards": cards})
