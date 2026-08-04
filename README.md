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
content/episodes.json       Upcoming entries and local archive enrichment
content/archive-cache.json  Cached SoundCloud playlist metadata
content/legal.json          Operator details for legal pages
docs/                       Search Console and structured-data notes
scripts/build.py             Static-site generator
scripts/update_archive.py    SoundCloud archive updater
scripts/validate_site.py     Generated-site validation
templates/                  HTML templates
```

Do not edit `public/` directly. It is deleted and rebuilt by
`scripts/build.py` and is ignored by Git.

## Edit general content

General information, team members, links and the recordings shown under
**Hören / Listen** are maintained in:

```text
content/site.json
```

The build displays the first five objects in the `mixes` array.

## Add broadcasts and events to Upcoming

Upcoming items are maintained in:

```text
content/episodes.json
```

Every future object with `"status": "upcoming"` is rendered and sorted by
start date. Expired items are excluded automatically during the next build.

### Broadcast example

```json
{
  "date": "2026-08-29T21:00:00+02:00",
  "end": "2026-08-30T00:00:00+02:00",
  "type": "broadcast",
  "title_de": "sofea #100 - tba",
  "title_en": "sofea #100 - tba",
  "status": "upcoming",
  "summary_de": "Drei Stunden elektronische Musik. Live auf Radio Blau.",
  "summary_en": "Three hours of electronic music. Live on Radio Blau.",
  "audio_url": null
}
```

If `end` is omitted, broadcasts default to three hours and events to two
hours. `duration_hours` can override that default.

### Event example

```json
{
  "date": "2026-09-12T20:00:00+02:00",
  "end": "2026-09-13T02:00:00+02:00",
  "type": "event",
  "status": "upcoming",
  "title_de": "sofea night",
  "title_en": "sofea night",
  "summary_de": "Eine Nacht mit dem sofea-Team und Gästen.",
  "summary_en": "A night with the sofea team and guests.",
  "details_de": "Hier kann ein längerer Beschreibungstext stehen.",
  "details_en": "A longer event description can be placed here.",
  "location_de": "Conne Island, Leipzig",
  "location_en": "Conne Island, Leipzig",
  "image": "assets/images/sofea-night.jpg",
  "image_alt_de": "Flyer der sofea night",
  "image_alt_en": "sofea night flyer",
  "lineup": [
    {"name": "96kbps", "url": "https://soundcloud.com/skile"},
    {"name": "easy.miner", "url": "https://soundcloud.com/easy_miner"},
    {"name": "fumé", "url": "https://soundcloud.com/fume"}
  ],
  "links": [
    {
      "label_de": "Veranstaltungsdetails",
      "label_en": "Event details",
      "url": "https://example.org/event",
      "primary": true
    }
  ],
  "audio_url": null
}
```

Supported optional fields include:

- `slug`: stable custom URL segment;
- `label_de` / `label_en`: category shown above the title;
- `location`, or separate `location_de` / `location_en`;
- `details_de` / `details_en`: longer text; blank lines create paragraphs;
- `image` or `image_url`, plus localized alt text;
- `lineup`: strings or objects with `name`, optional `url` and optional
  `schema_type` (for example `Person`, `MusicGroup` or `PerformingGroup`);
- optional structured venue fields: `venue_name`, `street_address`,
  `postal_code`, `address_locality`, `address_region` and `address_country`;
- `music_presentations`: records or tracks introduced during the editorial part
  of the programme; strings or objects with `artist`, `title`, optional `label`,
  `year`, `url` and localized `note_de` / `note_en`;
- `tracklist`: strings or objects with `artist`, `title`, optional `time`,
  `label` and `url`;
- `social_image`: optional custom Open Graph image; otherwise the build creates
  an individual branded 1200 × 630 pixel card automatically;
- `links`: additional buttons with labels, URL and optional `primary: true`;
- `updated_at`: optional `YYYY-MM-DD` date for the sitemap.

The build generates:

```text
/termine/YYYY-MM-DD-slug/
/calendar/YYYY-MM-DD-slug.ics
/calendar.ics
```

`/calendar.ics` contains all future entries and is linked through the
**Kalender abonnieren** control. Its stable subscription address is:

```text
webcal://sofea.radio/calendar.ics
```

The HTTPS fallback is `https://sofea.radio/calendar.ics`. Individual `.ics`
files remain available for one-off imports. Calendar notes contain the
Radio Blau DAB+/FM frequencies and the stream URL in a consistent footer.

## Enrich an archived broadcast

The SoundCloud cache supplies title, date, description and audio URL. Add a
non-upcoming object to `content/episodes.json` with the exact same `audio_url`
to add longer text, an image, lineup or tracklist without modifying the cache:

```json
{
  "date": "2026-03-14",
  "status": "past",
  "title_de": "Neele",
  "title_en": "Neele",
  "summary_de": "Mitschnitt des Sets aus der 98. Sendung im März 2026.",
  "summary_en": "Recording from the 98th broadcast.",
  "details_de": "Weitere Informationen zur Sendung.",
  "details_en": "Additional information about the broadcast.",
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

It writes cleaned metadata to `content/archive-cache.json`. The public website
uses that committed cache and does not have to query the playlist in a
visitor's browser.

The **Refresh SoundCloud archive** workflow runs daily and can also be started
manually. It commits the cache only when it changes. That commit then triggers
the independent **Deploy GitHub Pages** workflow.

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

## GitHub Actions

- `.github/workflows/deploy-pages.yml` validates, builds and deploys the site
  on pushes to `main`. Pull requests run the build and validation but do not
  deploy.
- `.github/workflows/refresh-archive.yml` is the only workflow with repository
  write access and only updates `content/archive-cache.json`.
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
