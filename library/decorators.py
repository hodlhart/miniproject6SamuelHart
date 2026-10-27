# INF601 - Advanced Programming in Python
# Samuel Hart
# Mini Project 6

import functools

from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied


def parent_required(view_func):
    """Allow staff only: anonymous users log in, other signed-in users get 403."""

    # A plain decorator, not a decorator factory. The only valid use is
    # @parent_required. Writing @parent_required() raises TypeError at import
    # time instead of returning a view that could run without these checks.
    @functools.wraps(view_func)
    def wrapper(request, *args, **kwargs):
        """Run the parent checks, then call the wrapped view."""
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path())
        if not request.user.is_staff:
            raise PermissionDenied
        return view_func(request, *args, **kwargs)

    return wrapper
