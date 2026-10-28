# INF601 - Advanced Programming in Python
# Samuel Hart
# Mini Project 6

import functools

from django.contrib import messages
from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied
from django.urls import reverse


def parent_required(view_func):
    """Allow staff only, redirecting guests and refusing other users with 403."""

    # A plain decorator, not a decorator factory. The only valid use is
    # @parent_required. Writing @parent_required() raises TypeError at import
    # time instead of returning a view that could run without these checks.
    @functools.wraps(view_func)
    def wrapper(request, *args, **kwargs):
        """Run the parent checks, then call the wrapped view."""
        if not request.user.is_authenticated:
            messages.info(request, "Sign in as a parent to continue.")
            return redirect_to_login(request.get_full_path())
        if not request.user.is_staff:
            raise PermissionDenied("Parent access only.")
        return view_func(request, *args, **kwargs)

    return wrapper


def reader_required(view_func):
    """Require the signed-in reader to own the page; staff may view any reader."""

    @functools.wraps(view_func)
    def wrapper(request, *args, **kwargs):
        """Check reader ownership, then call the wrapped reader view."""
        reader_id = kwargs.get("reader_id")
        if reader_id is None:
            raise ValueError("reader_required needs a reader_id URL argument")
        if not request.user.is_authenticated:
            messages.info(request, "Sign in to open that page.")
            # A POST cannot be replayed by a login redirect, so a signed-out
            # buyer returns to the shop where the Buy button lives.
            if request.method == "POST":
                next_url = reverse("library:reader_shop", args=[reader_id])
            else:
                next_url = request.get_full_path()
            return redirect_to_login(next_url)
        if request.user.is_staff:
            return view_func(request, *args, **kwargs)
        if request.user.pk != reader_id:
            raise PermissionDenied("This page belongs to another reader.")
        return view_func(request, *args, **kwargs)

    return wrapper


def family_required(view_func):
    """Allow any signed-in reader or parent, redirecting guests with a message."""

    @functools.wraps(view_func)
    def wrapper(request, *args, **kwargs):
        """Check sign-in, then call the wrapped view."""
        if not request.user.is_authenticated:
            messages.info(request, "Sign in to see the family inventory.")
            return redirect_to_login(request.get_full_path())
        return view_func(request, *args, **kwargs)

    return wrapper
