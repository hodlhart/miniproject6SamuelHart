# Pages for Pokemon

A family reading tracker built with Django. Children earn chapters by reading books,
then spend those chapters on Pokemon cards from their parents' collection.

The app grew out of a real household problem. Two parents own a stock of physical
Pokemon cards, and their children wanted them. Reading became the currency, which
turned an argument about screen time into a reason to finish a chapter.

## How it works

Every child has an account with a stock of chapters. A chapter is earned by logging a
reading against a book they own, and it is spent by buying a card. Cards cost what the
parent sets, and the family uses 1 chapter for a normal card, 5 for an EX, and 10 for
full art.

The wallet is a statement, not a single number. Every reading adds a line and every
purchase subtracts one, with a running total at the bottom, so a child can see where
their chapters came from and where they went.

## Requirements

- Python 3.12 or newer. This project was built and tested on 3.13.15.
- `uv` for the environment and package installation.
- Network access the first time you seed the demo or fetch artwork.

Four direct dependencies, all pinned in `requirements.txt`: Django 6.1.2,
django-debug-toolbar 8.0.0, asgiref and sqlparse. Bootstrap 5.3.3 is vendored into
`static/vendor/`, so the site renders with no CDN and no network at runtime.

## Install

```bash
uv venv --python 3.13
source .venv/bin/activate
uv pip install pip
uv pip install -r requirements.txt
```

## Initialize the database

The migrations are committed, so a fresh clone only has to apply them. The first two
commands are the ones the course asks to see documented:

```bash
python manage.py makemigrations
python manage.py migrate
```

`makemigrations` reports "No changes detected" on a fresh clone, because the migration
files are already in the repository. It is listed because it is the command you run after
changing a model, and it must be run before `migrate` picks the change up.

Then fill the database with the demo household:

```bash
python manage.py seed-demo
```

`seed-demo` creates a demo household: a parent account, three readers each with their
own energy order and portrait, six books with Open Library covers, twelve readings,
eight cards and two purchases. It needs network access the first time, because it looks
up a portrait for each reader. Run it again and it refuses, naming what `--force` would
delete.

Then cache the artwork locally:

```bash
python manage.py cache-art
```

This fetches every card image, book cover and energy print into `media/art-cache/`,
which is gitignored. It is safe to run repeatedly and reports what it fetched, what it
already had, and what it could not reach. The login does not depend on that folder:
with an empty cache the energy grid shows nine labelled tiles instead of card art,
so a reader can still sign in. If a type ends up with no cached print, `cache-art`
names the missing types and the lookup error, and exits non-zero.

## Create the parent account

The course lists `createsuperuser` as one of the commands to document, and it works here:

```bash
python manage.py createsuperuser
```

There is a shortcut, because `seed-demo` already creates a staff account named `parent`
with an unusable password. To give that account a password instead of making another one:

```bash
python manage.py changepassword parent
```

Either route gives you a parent login. A staff account never appears in the reader list,
because the front page shows non-staff accounts only, so the parent is not offered as a
reader to sign in as.

The parent signs in at `/accounts/login/` with that username and password, and reaches
the Django admin at `/admin/` and the management pages.

## Run the development server

```bash
python manage.py runserver --insecure
```

Then open http://127.0.0.1:8000/.

The `--insecure` flag is needed because `DEBUG` is off. Django only serves static
files itself when `DEBUG` is on, and with it off the stylesheet and the vendored
Bootstrap return 404, which leaves the app readable but unstyled. The flag serves
them without turning `DEBUG` back on for everything else.

## The pages

| Path | What it does |
| --- | --- |
| `/` | Who is reading. A guest sees the reader tiles and picks a name |
| `/accounts/register/` | Create a reader account by choosing three energy types and a portrait |
| `/accounts/login/` | Sign in. Readers tap three energy cards, parents use a password |
| `/readers/<id>/` | A reader's own page: balance, recent activity, and the ways onward |
| `/readers/<id>/log/` | Log chapters against a book they own, or look up a new title |
| `/readers/<id>/books/` | The books they have read, with covers |
| `/readers/<id>/cards/` | The cards they have bought |
| `/readers/<id>/shop/` | The cards on sale, with a confirmation modal |
| `/cards/` | The whole inventory |
| `/progress/` | The family's reading over time, in chapters only |
| `/manage/cards/` | Parent only. The inventory, add a card, list or unlist |
| `/manage/readers/` | Parent only. Reset a reader's energy order or their portrait |
| `/admin/` | Django admin, with all four models styled for real entry |

## Signing in

A reader does not have a password. They have three energy types in a fixed order, and
they sign in by tapping them on a grid of nine energy cards. The grid holds nine
different types, not just their three, so someone watching the screen cannot read the
answer off it, and it reshuffles on every attempt. The individual card does not matter,
only the type, so the artwork can rotate freely. Tiles use cached prints when they are
present and show the type name otherwise, so the grid works on a fresh clone before any
artwork has been fetched.

The check happens on the server against a hashed sequence. Five wrong tries and the
reader is asked to fetch a parent, who can reset the order from `/manage/readers/`.

Readers can only open their own pages. A parent can open any of them. Anyone not signed
in is sent to the login page and returned to where they were afterward.

## Two things this app does on purpose

**Logging the same reading twice is allowed.** This is a family app on a home network
with no password on the reader side, and the trust model is deliberate. The parent sees
the statement and can correct anything that looks wrong. Adding a guard would have
turned a five second task into a two step one for the people who use it every day.

**A purchase records the price it was bought at.** Re-pricing a card later does not
rewrite what a child already spent, so last month's statement stays true.

## Where the data lives

SQLite, in `db.sqlite3`, which is gitignored. Artwork is cached under `media/art-cache/`,
also gitignored. No card image, book cover or energy print is committed to this
repository: the app fetches them at runtime from TCGdex and Open Library, and the
artwork remains the property of its owners. That keeps the repository free of
copyrighted images and keeps the app working offline once the cache is warm.

## Deploying elsewhere

The committed defaults are safe for local work: `DEBUG` is off, and only
`127.0.0.1` and `localhost` are accepted. A deployment supplies its own values
through the environment, so no hostname or secret is committed:

- `DJANGO_SECRET_KEY`: a fresh key from Django's own generator:

  ```bash
  python -c "from django.core.management.utils import get_random_secret_key as g; print(g())"
  ```

  The old key remains in git history and is worthless; do not reuse it.
- `DJANGO_DEBUG`: leave unset (off) on a server, or set `1` for local debugging.
- `DJANGO_ALLOWED_HOSTS`: comma-separated hostnames, for example the public
  hostname plus `127.0.0.1,localhost`.
- `DJANGO_CSRF_TRUSTED_ORIGINS`: comma-separated origins with their scheme,
  for example the site's `https://` origin plus `http://127.0.0.1,http://localhost`.

TLS terminates at a proxy, which sets `X-Forwarded-Proto`; `SECURE_PROXY_SSL_HEADER`
tells Django to trust it, so HTTPS form submissions pass the CSRF origin check.
With `DEBUG` off, `runserver` does not serve static files, so the deployment
command is `python manage.py runserver 0.0.0.0:8000 --insecure` (or a real
static file server in front of it).

## AI Usage

### What the AI wrote

The application code was written by Claude Code working from prompts I wrote for each
step: the project scaffold and four models, the templates and Bootstrap integration, the
forms and the purchase confirmation modal, the authentication, the Open Library and
TCGdex lookups, the artwork cache, the page background collage, the energy grid login,
the family progress page, the reader portraits, and the seed command.

### What I chose, specified, and verified

The product decisions were mine, and several of them changed the code after the fact.
The currency is chapters rather than minutes, cards cost 1, 5 and 10 chapters by tier,
and the wallet shows a statement with one total rather than a balance on its own. I
rejected a rename of the shop blueprint to "bank". I asked for times in local time rather
than UTC, which meant keeping `USE_TZ` on and setting the zone rather than turning
conversion off. I asked for the Change column and a single Total instead of separate
change and balance columns. I chose the card back palette for the styling. When a
suggestion would have hidden a page element behind a hover, I asked for it to be visible,
because the app runs on tablets.

I also set the trust model: no duplicate-reading guard, no daily cap, no confirmation on
logging. That is a deliberate tradeoff for a family app and it is described above.

Later decisions came from using the app rather than planning it. The landing page had a
full width blue Log reading bar above an account card that filled a third of the row,
leaving the rest empty, so I had that area split into two columns grouped by purpose:
who the reader is on the left, what they do on the right. Filling the gap with a button
alone would have left a tall void, so the recent books went into that column too. I asked
for a chapter stepper beside each recent book, one chapter per tap, committed by the Log
button. The energy grid on the login page had to stop scrolling, so it now uses five
columns instead of three, which is the layout registration already had. I asked for the
thumbnail treatment on the parent's card list and for the book covers to be true
thumbnails rather than full size images.

Verification was mine throughout. I ran the app in a browser after every step and
clicked through it, which is how several problems surfaced: a Buy button that silently
returned to the same page without saying anything, reader pages that answered to
anyone who typed the address, and a landing page whose most common action was two taps
away. I checked database constraints by attempting the violations rather than reading
the code, confirmed the seeded balances against the rows by hand, and checked that the
site renders with the network off once the artwork cache is warm.

### What I changed in the AI-generated code

I removed the duplicate Log in link from the navigation bar for signed-out visitors,
because the landing page already offers the parent login directly under the reader
names. My first attempt broke every page: I deleted four lines including the `{% endif %}`
that closed the staff section of the navbar, which left the template tag unclosed and
turned the site into a 500 error. That was repaired by restoring the two structural lines
and keeping only the removal I intended. The change is at commit `5ccbf96`.

I also removed the camera capture feature from the plan after testing showed the
recognized text from a clean card image did not include the collector number at all,
which was the whole basis for identifying a card from a photograph.

My second change was to the stylesheet loading. While working on the styling I kept
changing `app.css` and reloading to see no difference, because the browser was reusing the
copy it already had: the link tag named the file with no version, so from the browser's
point of view the address never changed. A version parameter fixes it, and the honest
version of that is the file's own modification time rather than something arbitrary, so the
address changes exactly when the file does and not otherwise.

I wrote it in `library/context_processors.py`, since a Django template cannot read
`settings` directly and a context processor is the supported way to hand a value to every
page:

```python
def static_version(request):
    """Return the app stylesheet's modification time, so a change is never served stale."""
    stylesheet = Path(settings.BASE_DIR) / "static" / "app.css"
    try:
        return {"STATIC_VERSION": int(stylesheet.stat().st_mtime)}
    except OSError:
        return {"STATIC_VERSION": 0}
```

I registered it in `TEMPLATES` beside the wallpaper processor, and changed one line of
`base.html` to append `?v={{ STATIC_VERSION }}` to the stylesheet address. I left the
Bootstrap link alone, because that file never changes.

This matters beyond my own convenience. A visitor's first load on a deployed host would
otherwise be able to render a stale stylesheet against new HTML, which looks like a broken
layout rather than a caching problem.
