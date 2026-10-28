# INF601 - Advanced Programming in Python
# Samuel Hart
# Mini Project 6

from django import template

from ..models import Profile

register = template.Library()


@register.inclusion_tag("library/_avatar.html")
def reader_avatar(user, name=None):
    """Render a reader's mini card picture, or the plain default."""
    profile = Profile.objects.filter(user=user).first() if user else None
    label = name or getattr(user, "username", "")
    return {
        "avatar_url": profile.cached_avatar_url if profile else None,
        "name": label,
        "initial": label[:1],
    }
