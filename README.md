# sounds of electronic art — GitHub Pages site

A dependency-light static website for the `sounds of electronic art` radio
show, published at <https://sofea.radio/>.

## Features

- responsive orange design with dark and Solarized-Light-inspired themes;
- German default interface and English language switch;
- separate upcoming broadcasts and events;
- five editorially selected recordings whose metadata is derived from the
  SoundCloud archive cache;
- click-to-load SoundCloud player with a mobile inline accordion;
- static, searchable and paginated broadcast archive;
- crawlable detail pages that open as dialogs on the homepage;
- tracklists and music presentations with optional external links;
- local SoundCloud artwork cache plus responsive WebP variants;
- individual PNG social cards, JSON-LD, RSS, sitemap and calendar feeds;
- Pages CMS configuration for two or three editors;
- source/build/output validation shared by local development and GitHub Actions;
- no first-party analytics, advertising tracking or external web fonts.

The SoundCloud iframe is created only after a visitor explicitly loads the
player. See the generated privacy notice for the resulting third-party request.

## Repository structure

```text
.github/workflows/pages.yml            Build and deploy GitHub Pages
.github/workflows/quality.yml          Validate pull requests
.github/workflows/refresh-archive.yml  Refresh SoundCloud metadata and artwork
.pages.yml                             Pages CMS schema
assets/                                CSS, JavaScript, logos and source images
content/site.json                      General site configuration
content/upcoming-broadcasts.json       Future radio broadcasts
content/upcoming-events.json           Future public events
content/episodes.json                  Editorial archive enrichment
content/archive-cache.json             Cached SoundCloud playlist metadata
content/legal.json                     Legal-page operator data
docs/pages-cms.md                      Editorial setup and workflow
docs/search-console-setup.md           Google Search Console setup
docs/structured-data.md                Generated Schema.org data
scripts/build.py                       Static-site generator
scripts/check.py                       Source → build → output quality command
scripts/update_archive.py              SoundCloud metadata/artwork updater
scripts/validate_site.py               Source and generated-site validator
templates/                              HTML templates
```

Do not edit `public/`. It is generated and ignored by Git.

## Edit content with Pages CMS

Use an individual GitHub account for every editor. The repository contains three
focused CMS areas:

- **Demnächst – Sendungen**
- **Demnächst – Veranstaltungen**
- **Sendungsarchiv**

The one-time setup and field descriptions are documented in
[`docs/pages-cms.md`](docs/pages-cms.md).

## Featured recordings under Hören

`content/site.json` stores only the SoundCloud URLs selected for the five
featured recordings:

```json
{
  "featured_audio_urls": [
    "https://soundcloud.com/sounds-of-electronic-art/neele-2026-03-14"
  ]
}
```

Title, description and duration are resolved from `archive-cache.json` and
`episodes.json`. This avoids maintaining duplicate metadata in `site.json`.
Use one to five unique URLs that are present in the archive.

## Upcoming broadcasts

Edit `content/upcoming-broadcasts.json` or use Pages CMS:

```json
{
  "date": "2026-08-29T21:00:00",
  "episode_number": 100,
  "title_de": "sofea #100 – tba",
  "title_en": "sofea #100 – tba",
  "details_de": "Drei Stunden elektronische Musik. Live auf Radio Blau.",
  "details_en": "Three hours of electronic music. Live on Radio Blau.",
  "image": "/assets/images/uploads/sofea-100.png",
  "links": []
}
```

Upcoming times are Leipzig wall-clock time without a UTC suffix. The build
applies `Europe/Berlin`. Broadcasts default to three hours and the location
`Radio Blau, Leipzig`.

There is one full text per language. The homepage creates its excerpt
automatically; the detail page displays the complete text.

## Upcoming events

Edit `content/upcoming-events.json`:

```json
{
  "date": "2026-09-12T20:00:00",
  "end": "2026-09-13T02:00:00",
  "title_de": "sofea night",
  "title_en": "sofea night",
  "details_de": "Eine Nacht mit dem sofea-Team und Gästen.",
  "details_en": "A night with the sofea team and guests.",
  "location": "Conne Island, Leipzig",
  "image": "/assets/images/uploads/sofea-night.png",
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

An event without `end` defaults to two hours.

## Enrich an archived broadcast

The SoundCloud cache supplies date, title, description, duration, audio URL and
artwork. Add an object to `content/episodes.json` with the exact same
`audio_url` to attach local editorial data:

```json
{
  "date": "2026-03-14",
  "episode_number": 98,
  "updated_at": "2026-08-04",
  "title_de": "Neele",
  "title_en": "Neele",
  "audio_url": "https://soundcloud.com/sounds-of-electronic-art/neele-2026-03-14",
  "details_de": "Mitschnitt des Sets aus der 98. Sendung im März 2026.",
  "details_en": "Recording from the 98th broadcast.",
  "music_presentations": [
    {
      "artist": "Artist",
      "title": "Release",
      "url": "https://www.discogs.com/"
    }
  ],
  "tracklist": [
    {
      "time": "00:00",
      "artist": "Artist",
      "title": "Track"
    }
  ]
}
```

`episode_number` is optional and is used for Schema.org `episodeNumber`, labels
and generated social cards. `updated_at` should change only after meaningful
editorial changes.

## Artwork and social images

The archive updater stores SoundCloud artwork under:

```text
assets/images/episodes/YYYY-MM-DD-title.jpg
```

A local file named for the same date/title is retained and takes precedence.
An explicit `image` value in the content file wins over the automatic cache.
During the build, local artwork receives 480, 800 and 1200 pixel WebP variants
used through `srcset`.

Each detail page also receives a generated PNG social card. A manual override is
possible through the advanced field `social_image`, but it must point to a PNG.

## Static SoundCloud archive

Install updater dependencies and refresh locally only when needed:

```cmd
py -m pip install -r requirements-archive.txt
py scripts\update_archive.py --strict
```

Useful options:

```cmd
py scripts\update_archive.py --no-artwork
py scripts\update_archive.py --refresh-artwork
```

The daily **Refresh SoundCloud archive** workflow commits changed cache/artwork
and explicitly dispatches the independent Pages deployment. A temporary
SoundCloud error does not replace the last working cache.

## Build and validate locally

### Windows

```cmd
cd /d M:\dev\sofea-github-pages
py -m pip install -r requirements.txt
py scripts\check.py
py -m http.server 8000 --directory public
```

Open <http://localhost:8000> and stop the server with `Ctrl+C`.

### Linux or macOS

```bash
python3 -m pip install -r requirements.txt
python3 scripts/check.py
python3 -m http.server 8000 --directory public
```

`check.py` runs source validation, the build and generated-site validation. The
same command is used by the deployment and pull-request workflows, preventing
local/CI command drift.

## GitHub Actions and Dependabot

- `pages.yml` builds and deploys pushes to `main`.
- `quality.yml` performs the full check for pull requests.
- `refresh-archive.yml` is the only workflow with repository write permission;
  it refreshes archive metadata/artwork and dispatches `pages.yml` after a
  changed commit.
- Dependabot groups all Python updates into one monthly PR and all GitHub
  Actions updates into one monthly PR.

GitHub Pages must use **GitHub Actions** as its publishing source.

## SEO and structured data

The build creates canonical detail pages, sitemap entries, local RSS links,
unique social cards and JSON-LD for:

- `WebSite`, `WebPage` and `RadioSeries` on the homepage;
- `RadioEpisode`, `BroadcastEvent` and `RadioBroadcastService` for upcoming
  broadcasts;
- `MusicEvent` for events;
- `RadioEpisode` and `AudioObject` for archived recordings.

See [`docs/structured-data.md`](docs/structured-data.md) and
[`docs/search-console-setup.md`](docs/search-console-setup.md).

## Legal pages and licensing

Operator details are in `content/legal.json`. The build creates Impressum and
privacy pages. The supplied Radio Blau logo links to the station homepage.

The website software is MIT-licensed. Editorial content, branding, audio,
artwork, photographs and third-party media are excluded; see
[`CONTENT-LICENSE.md`](CONTENT-LICENSE.md).
