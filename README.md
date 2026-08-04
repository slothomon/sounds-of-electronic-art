# sounds of electronic art — GitHub Pages site

Dependency-light static website for the `sounds of electronic art` radio show,
published at [sofea.radio](https://sofea.radio/).

## Features

- responsive orange design with dark and Solarized-Light-inspired themes;
- German default interface with an English switch;
- separate Pages CMS editors for upcoming broadcasts, events, Hören and archive enrichment;
- one to five editorially selected recordings with a click-to-load SoundCloud player;
- searchable, paginated and statically generated broadcast archive;
- crawlable broadcast/event detail pages with progressive-enhancement dialogs;
- stable local episode IDs independent of SoundCloud permalinks;
- responsive local episode artwork;
- individual social cards and structured data;
- RSS, sitemap, subscribable calendar, robots.txt and a custom 404 page;
- source/build/output validation in local development and GitHub Actions.

SoundCloud is contacted only after a visitor explicitly loads the player. The
site content, archive index, descriptions and cached artwork are generated
locally and remain readable without a SoundCloud request. Audio playback still
uses SoundCloud as its current source.

## Repository structure

```text
.github/workflows/pages.yml            Build and deploy GitHub Pages
.github/workflows/quality.yml          Pull-request validation
.github/workflows/refresh-archive.yml  Daily/manual SoundCloud refresh
.pages.yml                             Pages CMS form configuration
assets/                                CSS, JavaScript, logos and source images
content/site.json                      General site configuration
content/listen.json                    Ordered Hören selection by episode ID
content/upcoming-broadcasts.json       Upcoming radio broadcasts
content/upcoming-events.json           Upcoming events
content/episodes.json                  Local archive enrichment
content/archive-cache.json             Cached SoundCloud playlist metadata
content/legal.json                     Legal-page operator details
docs/pages-cms.md                      Editorial workflow
docs/search-console-setup.md           Google Search Console setup
docs/structured-data.md                Implemented structured data
scripts/build.py                       Static-site generator
scripts/check.py                       Validate → build → validate
scripts/update_archive.py              SoundCloud metadata/artwork updater
scripts/validate_site.py               Source and generated-site validator
templates/                              HTML templates
```

Do not edit `public/`; it is rebuilt and ignored by Git.

## Local quality check

Install the normal build dependencies once:

```cmd
py -m pip install -r requirements.txt
```

Then run the same complete check used by GitHub Actions:

```cmd
py scripts\check.py
```

For production canonical URLs during a local check:

```cmd
py scripts\check.py --site-url https://sofea.radio
```

Preview the result:

```cmd
py -m http.server 8000 --directory public
```

## Content model

### Upcoming broadcasts

Edit `content/upcoming-broadcasts.json` directly or through Pages CMS.

```json
{
  "date": "2026-08-29T21:00:00",
  "episode_number": 100,
  "title_de": "sofea #100 – tba",
  "title_en": "sofea #100 – tba",
  "details_de": "Drei Stunden elektronische Musik. Live auf Radio Blau.",
  "details_en": "Three hours of electronic music, live on Radio Blau.",
  "image": "assets/images/uploads/example.jpg",
  "links": []
}
```

Times are Leipzig wall-clock time without a UTC offset. Broadcasts default to
three hours.

### Upcoming events

Edit `content/upcoming-events.json`.

```json
{
  "date": "2026-09-12T20:00:00",
  "end": "2026-09-13T02:00:00",
  "title_de": "sofea night",
  "title_en": "sofea night",
  "details_de": "Eine Nacht mit dem sofea-Team und Gästen.",
  "details_en": "A night with the sofea team and guests.",
  "location": "Conne Island, Leipzig",
  "image": "assets/images/uploads/sofea-night.jpg",
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

Events without `end` default to two hours.

### Archive enrichment and identity

SoundCloud supplies the automatically refreshed base metadata. Local editorial
content in `content/episodes.json` is merged by `episode_id` first. The source
ID, SoundCloud URL and date/title are only compatibility fallbacks for older
entries.

```json
{
  "episode_id": "2025-11-22-werner-benzo",
  "date": "2025-11-22",
  "updated_at": "2026-08-04",
  "episode_number": 96,
  "title_de": "Werner Benzo (Komplette Sendung)",
  "title_en": "Werner Benzo (Complete broadcast)",
  "audio_url": "https://soundcloud.com/sounds-of-electronic-art/werner-benzo-komplette-sendung",
  "details_de": "Komplette Sendung mit Interview und Musik von Werner Benzo.",
  "details_en": "Complete broadcast featuring an interview and music by Werner Benzo.",
  "music_presentations": [
    {
      "artist": "Headache",
      "title": "Nineteen Sixty Five",
      "url": "https://www.discogs.com/master/example"
    }
  ],
  "tracklist": [
    {
      "time": "00:00",
      "artist": "Artist",
      "title": "Track title"
    }
  ]
}
```

An explicit `episode_id` is recommended for locally edited entries. The format
is lowercase letters, digits and hyphens. If it is absent, the build derives a
fallback from date and title, for example `2025-11-22-werner-benzo`. Once an ID
is referenced by `content/listen.json`, keep it stable.

`episode_number` is optional. When supplied, it is used in the visible label,
social card, archive export and Schema.org `episodeNumber` value.

`social_image` is an optional advanced field and must point to a PNG. Without
it, the build creates an individual PNG social card.

## Hören / Listen

The homepage selection is stored separately in `content/listen.json` and can be
edited through **Hören – Auswahl** in Pages CMS.

```json
[
  {
    "episode_id": "2026-03-14-neele",
    "label": "Neele"
  }
]
```

The list order controls the homepage order. Keep one to five entries. `label`
is only used to make the CMS list readable; the public title, description,
duration and playback URL are resolved from the archive by `episode_id`.

## Episode artwork

The archive updater stores SoundCloud artwork under:

```text
assets/images/episodes/YYYY-MM-DD-title.jpg
```

A manually uploaded `image` takes precedence. During the site build, local
artwork is additionally rendered as responsive WebP variants for smaller
screens. Generated variants live only in `public/`.

Refresh metadata/artwork locally only when needed:

```cmd
py -m pip install -r requirements-archive.txt
py scripts\update_archive.py
```

A successful refresh writes `episode_id` and `soundcloud_id` into the local
cache. Existing IDs are preserved across SoundCloud title or permalink changes
whenever the source ID remains available.

## GitHub Actions

- `pages.yml` runs `scripts/check.py` and deploys the result.
- `quality.yml` runs the same check for pull requests.
- `refresh-archive.yml` updates metadata/artwork, commits changes and explicitly
  dispatches `pages.yml` because a push made by `GITHUB_TOKEN` does not trigger
  another workflow automatically.

## Pages CMS

See [`docs/pages-cms.md`](docs/pages-cms.md). Each editor should use an
individual GitHub account with repository access; do not share one account.

## Licensing

The website software is licensed under the [MIT License](LICENSE). Editorial
content, branding, artwork, audio and third-party media are excluded; see
[`CONTENT-LICENSE.md`](CONTENT-LICENSE.md).
