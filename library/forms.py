# INF601 - Advanced Programming in Python
# Samuel Hart
# Mini Project 6

from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.utils.text import slugify

from .models import Book, Card, Reading


class LoginForm(AuthenticationForm):
    """Django's authentication form with Bootstrap classes on its inputs."""

    username = forms.CharField(
        label="Username",
        widget=forms.TextInput(attrs={"class": "form-control", "autofocus": True}),
    )
    password = forms.CharField(
        label="Password",
        widget=forms.PasswordInput(attrs={"class": "form-control"}),
    )


class ReaderCreationForm(UserCreationForm):
    """Django's user creation form, restricted to an ordinary reader account."""

    def __init__(self, *args, **kwargs):
        """Add Bootstrap classes to the username and password inputs."""
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-control"

    def save(self, commit=True):
        """Create an active, non-staff, non-superuser reader account."""
        user = super().save(commit=False)
        user.is_staff = False
        user.is_superuser = False
        user.is_active = True
        if commit:
            user.save()
        return user


def build_tcgdex_id(set_name, number):
    """Return a stable catalogue id built from a card's set name and number."""
    suffix = f"-{slugify(number)}"
    stem = slugify(set_name)[: 100 - len(suffix)]
    return f"{stem}{suffix}"


class CardForm(forms.ModelForm):
    """Add a card, keeping the price the parent types rather than a tier default."""

    class Meta:
        model = Card
        fields = [
            "name",
            "set_name",
            "number",
            "rarity",
            "price_chapters",
            "tier",
            "image_url",
            "for_sale",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "set_name": forms.TextInput(attrs={"class": "form-control"}),
            "number": forms.TextInput(attrs={"class": "form-control"}),
            "rarity": forms.TextInput(attrs={"class": "form-control"}),
            "price_chapters": forms.NumberInput(attrs={"class": "form-control"}),
            "tier": forms.Select(attrs={"class": "form-select"}),
            "image_url": forms.URLInput(attrs={"class": "form-control"}),
            "for_sale": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }
        help_texts = {
            "tier": (
                "Suggests 1 chapter for Normal, 5 for EX and 10 for Full art. "
                "The price you type is the price kept."
            ),
        }

    def clean(self):
        """Refuse a second card with the same set and number."""
        cleaned_data = super().clean()
        set_name = cleaned_data.get("set_name")
        number = cleaned_data.get("number")
        if set_name and number:
            tcgdex_id = build_tcgdex_id(set_name, number)
            existing = Card.objects.filter(tcgdex_id=tcgdex_id)
            if self.instance.pk:
                existing = existing.exclude(pk=self.instance.pk)
            if existing.exists():
                raise forms.ValidationError(
                    "A card from this set with this number already exists."
                )
        return cleaned_data

    def save(self, commit=True):
        """Fill the catalogue id before saving the new card."""
        card = super().save(commit=False)
        card.tcgdex_id = build_tcgdex_id(card.set_name, card.number)
        if commit:
            card.save()
        return card


class LogReadingForm(forms.ModelForm):
    """Record chapters read, choosing an owned book or naming a new one."""

    book = forms.ModelChoiceField(
        queryset=Book.objects.none(),
        required=False,
        empty_label="Select a book",
    )
    chapters = forms.IntegerField(
        min_value=1,
        max_value=32767,
        error_messages={"min_value": "Enter at least 1 chapter."},
        widget=forms.NumberInput(attrs={"class": "form-control"}),
    )
    new_title = forms.CharField(
        max_length=200,
        required=False,
        label="Or a new book title",
        help_text="Used only when no book is selected above.",
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )

    class Meta:
        model = Reading
        fields = ["book", "chapters"]

    def __init__(self, *args, reader, **kwargs):
        """Limit the book choices to books this reader owns."""
        super().__init__(*args, **kwargs)
        self.reader = reader
        self.fields["book"].queryset = reader.books.order_by("title")
        self.fields["book"].widget.attrs["class"] = "form-select"

    def clean(self):
        """Require exactly one book source: an existing book or a new title."""
        cleaned_data = super().clean()
        book = cleaned_data.get("book")
        new_title = (cleaned_data.get("new_title") or "").strip()
        if not book and not new_title:
            raise forms.ValidationError("Choose a book or enter a new title.")
        if book and new_title:
            raise forms.ValidationError(
                "Choose an existing book or enter a new title, not both."
            )
        cleaned_data["new_title"] = new_title
        return cleaned_data

    def save(self, commit=True):
        """Create the named book first, then return the reading for it."""
        reading = super().save(commit=False)
        new_title = self.cleaned_data["new_title"]
        if new_title:
            # A case-insensitive match is the same book, so reuse it rather than
            # letting the unique constraint reject a duplicate casing.
            reading.book = (
                Book.objects.filter(owner=self.reader, title__iexact=new_title).first()
                or Book.objects.create(owner=self.reader, title=new_title)
            )
        if commit:
            reading.save()
        return reading
