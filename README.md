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

```bash
python manage.py migrate
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
already had, and what it could not reach.

## Create the parent account

`seed-demo` creates the parent with an unusable password on purpose, so no credential
is ever written to a file in this repository. Set one yourself:

```bash
python manage.py changepassword parent
```

The parent signs in at `/accounts/login/` with that username and password, and reaches
the Django admin at `/admin/` and the management pages.

## Run the development server

```bash
python manage.py runserver
```

Then open http://127.0.0.1:8000/.

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
only the type, so the artwork can rotate freely.

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

The project runs with `DEBUG = True` and `ALLOWED_HOSTS` limited to localhost, which is
right for development and wrong for a public address. To serve it from a host:

- add the hostname to `ALLOWED_HOSTS`, keeping `127.0.0.1` and `localhost` for local work
- add the site's `https://` origin to `CSRF_TRUSTED_ORIGINS`
- set `SECURE_PROXY_SSL_HEADER` if a proxy terminates TLS in front of Django
- set `DEBUG = False`, and run with `runserver 0.0.0.0:8000 --insecure` or serve static
  files properly, because `runserver` stops serving them once `DEBUG` is off
- replace `SECRET_KEY` with a value that is not in this repository

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
