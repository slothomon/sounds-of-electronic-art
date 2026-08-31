# sounds of electronic art — GitHub Pages site

Dependency-light static website for the `sounds of electronic art` radio show,
published at [sofea.radio](https://sofea.radio/).

## Features

- responsive orange design with dark and Solarized-Light-inspired themes;
- German default interface with an English switch;
- Pages CMS editors for upcoming broadcasts, events, Hören, episode numbering,
  archive enrichment and the recurring broadcast schedule;
- automatic maintenance of the regular eight-week broadcast schedule, including
  cancellations and rescheduled slots with stable IDs and episode numbers;
- automatic rollover of completed broadcasts from **Demnächst** into the
  permanent local archive, independently of SoundCloud availability;
- schedule-aware livestream state: the Radio Blau link changes to a highlighted
  `LIVE` control only while a SOFEA broadcast is actually scheduled;
- local `Heute` / `Morgen` (`Today` / `Tomorrow`) labels for imminent broadcasts;
- one to five editorially selected recordings with a click-to-load SoundCloud
  player;
- searchable, paginated and statically generated broadcast archive;
- canonical episode numbering by broadcast date, including multiple sets from
  the same broadcast;
- crawlable broadcast/event detail pages with progressive-enhancement dialogs;
- stable local episode IDs independent of SoundCloud permalinks;
- responsive local episode artwork;
- individual social cards, canonical metadata and structured data;
- RSS, sitemap, subscribable calendar, robots.txt and a custom 404 page;
- content-fingerprinted CSS/JavaScript URLs and early preload of the active hero
  artwork;
- source/build/output validation plus unit tests in local development and CI.

SoundCloud is contacted only after a visitor explicitly loads the player. The
site content, archive index, descriptions and cached artwork are generated
locally and remain readable without a SoundCloud request. Audio playback still
uses SoundCloud as its current source.

## Repository structure

```text
.github/workflows/pages.yml            Build, test and deploy GitHub Pages
.github/workflows/quality.yml          Pull-request validation and unit tests
.github/workflows/refresh-archive.yml  Daily/manual archive + schedule maintenance
.pages.yml                             Pages CMS form configuration
assets/                                CSS, JavaScript, logos and source images
content/site.json                      General site configuration
content/listen.json                    Ordered Hören selection by episode ID
content/episode-numbers.json           Canonical broadcast date → episode number mapping
content/broadcast-schedule.json        Recurring broadcast schedule configuration
content/upcoming-broadcasts.json       Materialized upcoming radio broadcasts
content/upcoming-events.json           Upcoming events
content/episodes.json                  Permanent local archive enrichment and overrides
content/archive-cache.json             Cached SoundCloud playlist metadata
content/legal.json                     Legal-page operator details
docs/broadcast-schedule.md             Schedule automation and exceptions
docs/pages-cms.md                      Editorial workflow
docs/search-console-setup.md           Google Search Console setup
docs/structured-data.md                Implemented structured data
scripts/archive_broadcasts.py          Move completed broadcasts into the local archive
scripts/build.py                       Static-site generator
scripts/check.py                       Validate → build → validate
scripts/update_archive.py              SoundCloud metadata/artwork updater
scripts/update_schedule.py             Maintain the recurring future schedule
scripts/validate_site.py               Source and generated-site validator
tests/                                 Unit/regression tests
templates/                              HTML templates
requirements.txt                       Build dependencies
requirements-dev.txt                   Build + test dependencies
requirements-archive.txt               Build + SoundCloud updater dependencies
```

Do not edit `public/`; it is rebuilt and ignored by Git. In particular,
`public/live-broadcasts.json` is generated from the editorial broadcast data and
is overwritten by every build.

## Local workflow

Before starting local work, first update the checkout. This is especially
important because Pages CMS and the scheduled archive refresh can create commits
while another computer is not being used.

```cmd
git status
git pull --ff-only
```

If there are uncommitted local changes, stash them before pulling and restore
them afterwards:

```cmd
git stash push -u -m "local work"
git pull --ff-only
git stash pop
```

If local commits already exist while `origin/main` has moved forward, rebase
them before pushing:

```cmd
git fetch origin
git rebase origin/main
```

## Local quality check and preview

For development, install the build and test dependencies once:

```cmd
py -m pip install -r requirements-dev.txt
```

Run the source/build/output validation:

```cmd
py scripts\check.py
```

Run the unit/regression tests:

```cmd
py -m pytest -q
```

The GitHub Pages and pull-request workflows run both checks before accepting or
deploying a code change.

The build normally uses the public URL from `content/site.json`. That is fine
for a normal visual preview on `localhost:8000`; the generated site still works
locally because the production domain has no path prefix.

`SITE_URL` is an optional build-time override for canonical URLs, sitemap URLs,
calendar URLs and deployments below a path prefix. `scripts/check.py` does not
parse a `--site-url` command-line option, so set the environment variable
instead when an override is actually needed.

PowerShell example:

```powershell
$env:SITE_URL = "http://localhost:8000"
py scripts\check.py
Remove-Item Env:SITE_URL
```

Start the local server from the repository root:

```cmd
py -m http.server 8000 --directory public
```

Then open <http://localhost:8000/>.

## Broadcast lifecycle

The regular SOFEA schedule is configured in
`content/broadcast-schedule.json`. `scripts/update_schedule.py` materializes the
future slots into `content/upcoming-broadcasts.json` and keeps the configured
planning horizon populated.

Regular entries receive a stable ID based on their original slot, for example
`broadcast-2026-10-24`. A rescheduled broadcast keeps that ID and its episode
number. A cancelled regular slot is removed and does not consume an episode
number. See [`docs/broadcast-schedule.md`](docs/broadcast-schedule.md) for the
exception workflow.

The daily **Refresh SoundCloud archive** workflow performs the lifecycle in this
order:

1. `scripts/archive_broadcasts.py` moves broadcasts whose three-hour window has
   ended from `content/upcoming-broadcasts.json` into `content/episodes.json`;
2. it records the final date/episode-number mapping in
   `content/episode-numbers.json` if necessary;
3. `scripts/update_archive.py` refreshes SoundCloud metadata and artwork;
4. `scripts/update_schedule.py` replenishes the future broadcast horizon;
5. the resulting source data is validated, committed when changed and the Pages
   deployment is triggered.

This means a completed broadcast can already exist as an archive page before a
recording is available on SoundCloud. Playback is exposed only when a real
recording can be matched; the archive script never invents an `audio_url`.

The generated `live-broadcasts.json` converts the same Leipzig editorial times
to UTC. The browser uses it only for the schedule-aware LIVE indicator; it does
not probe the Radio Blau stream.

## Content model

### Upcoming broadcasts

Regular broadcasts are normally created by `scripts/update_schedule.py`. Use
**Demnächst – Sendungen** in Pages CMS to add or refine the guest/editorial
title, announcement text, artwork and links. Use **Sendungsplanung** for a
cancelled or rescheduled regular slot instead of manually moving/deleting the
managed entry.

A materialized regular entry looks like this:

```json
{
  "date": "2026-10-24T21:00:00",
  "episode_number": 102,
  "title_de": "Credit 00",
  "title_en": "Credit 00",
  "details_de": "The man, the myth, the legend.",
  "details_en": "The man, the myth, the legend.",
  "links": [],
  "id": "broadcast-2026-10-24"
}
```

Times are Leipzig wall-clock time without a UTC offset. The validator rejects
invalid or ambiguous daylight-saving transition times. Broadcasts without an
explicit `end` use the fixed three-hour SOFEA duration.

The schedule automation preserves editorial changes on managed future entries.
A separate, non-regular broadcast may still be added manually; an explicit
`episode_number` remains available as an advanced override but should not be
needed for normal regular slots.

### Upcoming events

Edit `content/upcoming-events.json` directly or through Pages CMS.

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

### Episode numbering

`content/episode-numbers.json` is the canonical historical numbering table and
is editable through **Sendungsnummern** in Pages CMS.

```json
[
  {
    "date": "2026-08-29",
    "episode_number": 101
  },
  {
    "date": "2026-07-04",
    "episode_number": 100
  }
]
```

Use one entry per actually broadcast episode. File order is irrelevant. Episode
numbers must be unique and continuous from `1` through the current highest
number.

The mapping is date-based: every archived SoundCloud set with the same broadcast
date receives the same `episode_number`. This is intentional because one radio
broadcast can contain multiple separately uploaded sets.

For normal scheduled broadcasts, `scripts/archive_broadcasts.py` writes the
canonical row automatically when the broadcast ends. Manual editing is mainly
for historical data or deliberate corrections. An explicit `episode_number` in
`content/episodes.json` still takes precedence and is intended only for
exceptions.

### Archive enrichment and identity

Completed broadcasts are first represented locally in `content/episodes.json`.
SoundCloud supplies additional automatically refreshed metadata when a recording
becomes available. Local editorial content is merged by `episode_id` first; the
source ID, SoundCloud URL and date/title are compatibility fallbacks for older
entries.

```json
{
  "episode_id": "2025-11-22-werner-benzo",
  "date": "2025-11-22",
  "updated_at": "2026-08-04",
  "title_de": "Werner Benzo (Komplette Sendung)",
  "title_en": "Werner Benzo (Complete broadcast)",
  "audio_url": "https://soundcloud.com/sounds-of-electronic-art/werner-benzo-komplette-sendung",
  "post_text_de": "Komplette Sendung mit Interview und Musik von Werner Benzo.",
  "post_text_en": "Complete broadcast featuring an interview and music by Werner Benzo.",
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

Visible archive prose uses this priority:

1. `post_text_de` / `post_text_en`;
2. legacy `details_de` / `details_en`;
3. full SoundCloud description;
4. archived announcement text.

Normally the episode number comes from `content/episode-numbers.json`. An
explicit `episode_number` in an archive entry is only an override. When a number
is present after merging, it is used in the visible label, social card, archive
export and Schema.org `episodeNumber` value.

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

## SoundCloud archive refresh

The archive source is the public SoundCloud playlist:

```text
https://soundcloud.com/sounds-of-electronic-art/sets/sendungen
```

For a new recording to gain playback on the website:

1. make the SoundCloud track public;
2. add it to the **Sendungen** playlist;
3. make sure the SoundCloud metadata exposes the correct broadcast date;
4. preferably set the final SoundCloud artwork before the first refresh;
5. run **GitHub Actions → Refresh SoundCloud archive → Run workflow** if the
   daily refresh should not be awaited.

The manual action runs the same lifecycle as the scheduled daily refresh. The
SoundCloud updater deliberately retains the existing cache if a transient
refresh fails, unless it is invoked locally with `--strict`.

If metadata/artwork or schedule/archive data changes, the workflow commits
`content/archive-cache.json`, `content/episodes.json`,
`content/episode-numbers.json`, `content/upcoming-broadcasts.json` and episode
artwork as needed, rebases onto the latest `main`, pushes the result and then
explicitly dispatches the Pages deployment.

A recording does not require a manually created archive row: the completed
broadcast is normally already present in `content/episodes.json`, and the build
merges the SoundCloud recording into it. Older SoundCloud-only material can
still be represented from the cache without a local enrichment row.

### Refreshing locally

Install the additional updater dependencies once:

```cmd
py -m pip install -r requirements-archive.txt
```

Then run:

```cmd
py scripts\update_archive.py
```

The normal updater preserves an already cached local artwork file. If the
SoundCloud artwork of an existing archived track changes later, force an
artwork refresh locally and review the resulting diff before committing:

```cmd
py scripts\update_archive.py --refresh-artwork
```

A successful refresh writes/preserves `episode_id` and `soundcloud_id` in the
cache. Existing IDs are preserved across SoundCloud title or permalink changes
whenever the source ID remains available.

## Episode artwork

Automatic SoundCloud artwork is stored under:

```text
assets/images/episodes/YYYY-MM-DD-title.jpg
```

A manually configured local `image` takes precedence. During the site build,
local artwork is additionally rendered as responsive WebP variants for smaller
screens. Generated variants live only in `public/`.

The source validator can report `orphaned episode artwork` as a warning. These
warnings do not fail the build. Review them manually: stale duplicate artwork
may be removed once the current archive entry references the canonical file.

## GitHub Actions

- `pages.yml` installs the development requirements, runs the unit tests,
  executes `scripts/check.py` and deploys the generated `public/` directory.
- `quality.yml` runs the same tests and validation for pull requests and manual
  quality checks.
- `refresh-archive.yml` runs daily and can also be started manually as
  **Refresh SoundCloud archive**. It archives completed broadcasts, refreshes
  SoundCloud metadata/artwork, replenishes the future schedule, validates the
  resulting source data, commits changes and explicitly dispatches `pages.yml`
  because a push made by `GITHUB_TOKEN` does not trigger another workflow
  automatically.

## Pages CMS

See [`docs/pages-cms.md`](docs/pages-cms.md). The CMS provides editors for
upcoming broadcasts/events, the Hören selection, canonical episode numbers,
archive enrichment and recurring broadcast planning.

Each editor should use an individual GitHub account with repository access; do
not share one account.

## Licensing

The website software is licensed under the [MIT License](LICENSE). Editorial
content, branding, artwork, audio and third-party media are excluded; see
[`CONTENT-LICENSE.md`](CONTENT-LICENSE.md).
