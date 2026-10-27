# INF601 - Advanced Programming in Python
# Samuel Hart
# Mini Project 6

from django import forms

from .models import Book, Reading


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
