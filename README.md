# sounds of electronic art — GitHub Pages site

A dependency-light static website for the `sounds of electronic art` radio
show, published at <https://sofea.radio/>.

## Included

- responsive orange design;
- German default interface with an English language switch;
- dark theme and a Solarized-Light-inspired light theme;
- multiple upcoming broadcasts and events;
- five selectable SoundCloud recordings with a click-to-load in-page player;
- statically generated and searchable broadcast archive with pagination;
- crawlable detail pages for broadcasts and upcoming events;
- progressive enhancement: detail links open in a dialog on the homepage but
  remain normal URLs for new tabs, no-JavaScript use and search engines;
- RSS feed, sitemap, subscribable calendar, `robots.txt` and a custom 404 page;
- separate GitHub Actions workflows for deployment and archive refresh;
- automatically generated social cards for every broadcast and event;
- no first-party analytics, advertising tracking or external web fonts.

The SoundCloud iframe is not created until a visitor explicitly loads the player.
After that click, the third-party embed may make requests to SoundCloud; see the
generated privacy notice for details.

## Repository structure

```text
assets/                     CSS, JavaScript, logos and images
content/site.json           General website, team and recording data
content/upcoming-broadcasts.json  Upcoming radio broadcasts
content/upcoming-events.json      Upcoming events
content/episodes.json             Local archive enrichment
content/archive-cache.json        Cached SoundCloud playlist metadata
content/legal.json          Operator details for legal pages
docs/                       Search Console, Pages CMS and structured-data notes
scripts/build.py             Static-site generator
scripts/update_archive.py    SoundCloud archive and artwork updater
scripts/normalize_episode_lists.py  One-time Pages CMS data normalizer
.pages.yml                    Pages CMS editor schema
scripts/validate_site.py     Generated-site validation
templates/                  HTML templates
```

Do not edit `public/` directly. It is deleted and rebuilt by
`scripts/build.py` and is ignored by Git.

## Edit content with Pages CMS

The repository includes a focused `.pages.yml` configuration with three
separate editors: **Demnächst – Sendungen**, **Demnächst – Veranstaltungen**
and **Sendungsarchiv**. Each editor only exposes fields relevant to that content
type.

Each editor should use an individual GitHub account; do not share one account.
The complete one-time setup and editorial workflow are documented in:

```text
docs/pages-cms.md
```

Before opening a file that still contains string-only music presentations or
tracklist rows, run the included normalizer once:

```cmd
py scripts\normalize_episode_lists.py
py scripts\normalize_episode_lists.py --write
```

## Edit general content

General information, team members, links and the recordings shown under
**Hören / Listen** are maintained in:

```text
content/site.json
```

The build displays the first five objects in the `mixes` array.

## Add broadcasts and events to Demnächst

Pages CMS stores future content in two separate files:

```text
content/upcoming-broadcasts.json
content/upcoming-events.json
```

Times are stored as Leipzig wall-clock time **without a UTC offset**, for
example `2026-08-29T21:00:00`. This prevents the CMS from displaying 19:00
when 21:00 was entered. The build applies the `Europe/Berlin` timezone and
therefore handles summer and winter time correctly.

There is only one editorial text per language: `details_de` and `details_en`.
The homepage creates a short excerpt automatically; the detail view shows the
complete text.

### Broadcast example

```json
{
  "date": "2026-08-29T21:00:00",
  "title_de": "sofea #100 - tba",
  "title_en": "sofea #100 - tba",
  "details_de": "Drei Stunden elektronische Musik. Live auf Radio Blau.",
  "details_en": "Three hours of electronic music. Live on Radio Blau.",
  "image": "/assets/images/uploads/sofea-100.jpg",
  "links": []
}
```

Broadcasts default to three hours.

### Event example

```json
{
  "date": "2026-09-12T20:00:00",
  "end": "2026-09-13T02:00:00",
  "title_de": "sofea night",
  "title_en": "sofea night",
  "details_de": "Eine Nacht mit dem sofea-Team und Gästen.",
  "details_en": "A night with the sofea team and guests.",
  "location": "Conne Island, Leipzig",
  "image": "/assets/images/uploads/sofea-night.jpg",
  "links": [
    {
      "label_de": "Veranstaltungsdetails",
      "label_en": "Event details",
      "url": "https://example.org/event",
      "primary": true
    }
  ]
}
```

The build generates crawlable detail pages, individual calendar files and the
subscribable calendar at `https://sofea.radio/calendar.ics`.

### One-time migration from the former mixed file

Preview the split:

```cmd
py scripts\split_episode_content.py
```

Then write the three focused files:

```cmd
py scripts\split_episode_content.py --write
```

The migration keeps the entered local hour and removes timezone suffixes from
future dates. It also moves former `summary_*` values into the single
`details_*` text fields.

## Enrich an archived broadcast

The SoundCloud cache supplies title, date, description, audio URL and artwork.
Add an object to `content/episodes.json` with the exact same `audio_url` to add
editorial text, music presentations or a tracklist without modifying the cache:

```json
{
  "date": "2026-03-14",
  "title_de": "Neele",
  "title_en": "Neele",
  "details_de": "Mitschnitt des Sets aus der 98. Sendung im März 2026.",
  "details_en": "Recording from the 98th broadcast.",
  "audio_url": "https://soundcloud.com/sounds-of-electronic-art/neele-2026-03-14",
  "music_presentations": [
    "Artist A — Release without a link",
    {
      "artist": "Artist B",
      "title": "Album or track title",
      "label": "Example Records",
      "year": 2026,
      "url": "https://www.discogs.com/master/example",
      "note_de": "Kurzer redaktioneller Hinweis.",
      "note_en": "Short editorial note."
    }
  ],
  "tracklist": [
    {"time": "00:00", "artist": "Artist B", "title": "Track One"}
  ]
}
```

Each archive entry receives a page below `/sendungen/`. Homepage titles open
these pages in the existing modal/dialog interface; opening a title in a new
tab uses the standalone page. `music_presentations` appears as a separate
**Musikvorstellungen** section before the line-up and tracklist. Use simple
strings when no external source is needed, or objects with `artist`, `title`
and `url` for Discogs, Bandcamp or label links. The exact `audio_url` is the
stable key used to merge these local additions with the SoundCloud cache.

Every detail page receives an individual branded social card under
`public/assets/images/social/`. Set `social_image` to a local path or absolute
URL only when a hand-designed card should override the generated one.

## Static SoundCloud archive

`scripts/update_archive.py` reads this playlist through `yt-dlp`:

```text
https://soundcloud.com/sounds-of-electronic-art/sets/sendungen
```

It writes cleaned metadata to `content/archive-cache.json` and caches the
corresponding SoundCloud artwork under:

```text
assets/images/episodes/YYYY-MM-DD-title.jpg
```

The public website therefore uses committed metadata and local images instead
of requesting artwork from SoundCloud in a visitor's browser. A manually
provided `.jpg`, `.jpeg`, `.png` or `.webp` with the same date/title filename
is retained and takes precedence. An explicit `image` value in
`content/episodes.json` takes precedence over both.

The **Refresh SoundCloud archive** workflow runs daily and can also be started
manually. It commits the cache and newly discovered artwork only when something
changes. That commit then triggers the independent **Deploy GitHub Pages**
workflow. Existing custom artwork is not overwritten by the normal scheduled
run.

## Build and preview locally

### Windows

Install the build dependencies once (Pillow for social cards and the Windows time-zone fallback):

```cmd
cd /d M:\dev\sofea-github-pages
py -m pip install -r requirements.txt
```

Then build and preview:

```cmd
py scripts\build.py
py scripts\validate_site.py public
py -m http.server 8000 --directory public
```

Open <http://localhost:8000> and stop the server with `Ctrl+C`.

### Linux or macOS

```bash
python3 -m pip install -r requirements.txt
python3 scripts/build.py
python3 scripts/validate_site.py public
python3 -m http.server 8000 --directory public
```

The Windows-only `tzdata` dependency is skipped automatically on systems that
provide the IANA time-zone database themselves. Pillow generates the per-page
social cards during every build.

### Refresh the archive locally (optional)

```cmd
py -m pip install -r requirements-archive.txt
py scripts\update_archive.py --strict
py scripts\build.py
```

Useful artwork options:

```cmd
py scripts\update_archive.py --no-artwork
py scripts\update_archive.py --refresh-artwork
```

`--refresh-artwork` deliberately replaces matching automatic files. Keep it
off when the same filename contains a hand-selected image.

## GitHub Actions

- `.github/workflows/deploy-pages.yml` validates, builds and deploys the site
  on pushes to `main`. Pull requests run the build and validation but do not
  deploy.
- `.github/workflows/refresh-archive.yml` is the only workflow with repository
  write access and only updates `content/archive-cache.json` and local SoundCloud artwork.
- `.github/dependabot.yml` checks the Python and GitHub Actions dependencies
  monthly.

GitHub Pages must use **GitHub Actions** as its publishing source.

## Search engine setup

The build generates real detail URLs, canonical tags, an expanded sitemap and
an RSS feed whose items point to local detail pages.

Google Search Console still requires a one-time account and DNS verification.
Follow:

```text
docs/search-console-setup.md
```

The build inserts JSON-LD structured data automatically:

- the homepage describes the website and `RadioSeries`;
- broadcast pages use `RadioEpisode` and, when audio exists, `AudioObject`;
- public event pages use `MusicEvent`;
- scheduled radio broadcasts include a `BroadcastEvent`.

Implementation details and optional content fields are documented in:

```text
docs/structured-data-templates.md
```

## Legal pages

Operator details are maintained centrally in `content/legal.json`. Review them
before each public release. The build creates:

- `public/impressum.html`
- `public/datenschutz.html`

The Radio Blau logo remains the supplied original file and links to
<https://www.radioblau.de/>.

## Licensing

The website software is available under the MIT License in [`LICENSE`](LICENSE).
Editorial content, branding, audio, artwork, photographs and third-party media
are excluded; see [`CONTENT-LICENSE.md`](CONTENT-LICENSE.md).
