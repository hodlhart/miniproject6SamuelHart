# Pages for Pokemon: project rules

A Django app for one family. Kids earn chapters by reading books and spend them on physical
Pokemon cards their parents already own. This is a real app used at home, not a demonstration.

## What must be true

- **A balance is derived, never stored.** Total chapters read minus total chapters spent,
  computed when needed. There is no balance column anywhere in the schema.
- **A purchase records the price actually charged at the time.** Re-pricing a card later must
  never rewrite what a kid already paid.
- **Two books for the same kid whose titles differ only in case are the same book.**
  "Wings of Fire" and "wings of fire" must not both exist for one reader.
- **A card's catalogue id is unique and never null.** A nullable unique column is not a
  guarantee, because the database accepts any number of nulls in it.
- **Readers sign in with three energy types in order, not a password.** A kid picks their name
  from the list, then taps their three types on a grid of nine energy cards. The order is the
  secret; the individual card is not, so any print of a type counts and the grid reshuffles on
  every visit. Only the parent account has a username and password.
- **The same reading may be logged twice.** That is accepted rather than guarded. Do not add a
  duplicate check, a per-day cap, or a confirmation step.
- **A parent owns the card inventory and sets each card's price directly.** The tier suggests a
  price; it does not determine one. Normal, EX and full art start at 1, 5 and 10 chapters.
- **Removing a reader hides them rather than deleting them**, so their reading history and the
  cards they already own survive.
- **A reading records how many chapters were read, not which chapter.**
- **Times shown to the family are local.** Times are stored as UTC and rendered in
  America/Chicago. A chapter logged at 7pm must not display tomorrow's date.

## Out of scope

- No API keys. The card and book catalogues need none.
- Registration is open to the family. A reader builds their own account by choosing three energy
  types and a portrait. The management pages stay behind the parent password.
- Card artwork is never committed to the repository. It is referenced by URL and cached at run
  time into a gitignored folder.

## Style

- PEP 8, lines at most 100 characters, no em dashes, no trailing whitespace.
- A one-line docstring on every hand-written function and class.
- Comments explain why, not what. Docstrings describe what a thing is.
- Every hand-written `.py` file begins with:

```
# INF601 - Advanced Programming in Python
# Samuel Hart
# Mini Project 6
```

## Workflow

- **Do not commit.** The human commits. Leave every change staged or unstaged for review.
- **Do not edit** `.gitignore`, `requirements.txt`, or anything inside `.venv/`.
- Nothing may be tracked inside `media/`, `staticfiles/`, or any other gitignored directory.
- When a requirement here is ambiguous or contradicts the current code, stop and ask rather
  than choosing silently.
