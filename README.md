# sounds of electronic art — GitHub Pages site

Dependency-light static website for the `sounds of electronic art` radio show,
published at [sofea.radio](https://sofea.radio/).

## Features

- responsive orange design with dark and Solarized-Light-inspired themes;
- German default interface with an English switch;
- separate Pages CMS editors for upcoming broadcasts, events, Hören, episode numbering and archive enrichment;
- one to five editorially selected recordings with a click-to-load SoundCloud player;
- searchable, paginated and statically generated broadcast archive;
- canonical episode numbering by broadcast date, including multiple sets from the same broadcast;
- automatic numbering of future broadcasts after the latest confirmed episode;
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
content/episode-numbers.json           Canonical broadcast date → episode number mapping
content/upcoming-broadcasts.json       Upcoming radio broadcasts
content/upcoming-events.json           Upcoming events
content/episodes.json                  Local archive enrichment and overrides
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

## Local workflow

Before starting local work, first update the checkout. This is especially
important because Pages CMS and the scheduled SoundCloud refresh can create
commits while another computer is not being used.

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

Install the normal build dependencies once:

```cmd
py -m pip install -r requirements.txt
```

Run the same complete source/build/output check used by GitHub Actions:

```cmd
py scripts\check.py
```

The build normally uses the public URL from `content/site.json`. That is fine
for a normal visual preview on `localhost:8000`; the generated site still works
locally because the production domain has no path prefix.

`SITE_URL` is an optional build-time override for canonical URLs, sitemap URLs,
calendar URLs and deployments below a path prefix. `scripts/check.py` does not
currently parse a `--site-url` command-line option, so set the environment
variable instead when an override is actually needed.

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

## Content model

### Upcoming broadcasts

Edit `content/upcoming-broadcasts.json` directly or through Pages CMS.

```json
{
  "date": "2026-08-29T21:00:00",
  "title_de": "Heckintosh",
  "title_en": "Heckintosh",
  "details_de": "Drei Stunden elektronische Musik. Live auf Radio Blau.",
  "details_en": "Three hours of electronic music. Live on Radio Blau.",
  "links": []
}
```

Times are Leipzig wall-clock time without a UTC offset. Broadcasts default to
three hours.

Future broadcast numbers normally do **not** need to be maintained manually.
The build starts after the highest confirmed value in
`content/episode-numbers.json` and assigns numbers to future broadcasts in
chronological order. Adding an extra future broadcast therefore shifts the
numbers of later future broadcasts automatically.

An explicit `episode_number` on an upcoming broadcast remains available as an
advanced override, but should normally be left empty.

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

`content/episode-numbers.json` is the canonical historical numbering table. It
is also editable through **Sendungsnummern** in Pages CMS.

```json
[
  {
    "date": "2026-08-15",
    "episode_number": 100
  },
  {
    "date": "2026-07-04",
    "episode_number": 99
  }
]
```

Use one entry per actually broadcast episode. File order is irrelevant. Episode
numbers must be unique and continuous from `1` through the current highest
number.

The mapping is date-based: every archived SoundCloud set with the same broadcast
date receives the same `episode_number`. This is intentional because one radio
broadcast can contain multiple separately uploaded sets.

After a broadcast has actually happened, add its final date and number here.
Future entries in `content/upcoming-broadcasts.json` are then renumbered from the
new highest confirmed episode on the next build.

An explicit `episode_number` in `content/episodes.json` still takes precedence
and is intended only for deliberate exceptions.

### Archive enrichment and identity

SoundCloud supplies the automatically refreshed base metadata. Local editorial
content in `content/episodes.json` is merged by `episode_id` first. The source
ID, SoundCloud URL and date/title are compatibility fallbacks for older entries.

```json
{
  "episode_id": "2025-11-22-werner-benzo",
  "date": "2025-11-22",
  "updated_at": "2026-08-04",
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

For a new recording to appear automatically in the website archive:

1. make the SoundCloud track public;
2. add it to the **Sendungen** playlist;
3. make sure the SoundCloud metadata exposes the correct broadcast date;
4. preferably set the final SoundCloud artwork before the first archive refresh;
5. run **GitHub Actions → Refresh SoundCloud archive → Run workflow**.

The manual action runs the same strict updater as the scheduled refresh. If the
cache or artwork changes, the workflow commits `content/archive-cache.json` and
`assets/images/episodes/`, rebases onto the latest `main`, pushes the result and
then explicitly dispatches the Pages deployment.

The workflow also runs automatically once per day. Running it manually is only
needed when a new or corrected recording should appear immediately.

A new archive item does not need a matching manual `content/episodes.json`
entry unless editorial text, tracklists, artwork or another override is wanted.
If its date exists in `content/episode-numbers.json`, its episode number is
applied automatically during the site build.

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

- `pages.yml` runs `scripts/check.py` and deploys the result.
- `quality.yml` runs the same check for pull requests.
- `refresh-archive.yml` runs daily and can also be started manually as
  **Refresh SoundCloud archive**. It updates SoundCloud metadata/artwork,
  commits changes and explicitly dispatches `pages.yml` because a push made by
  `GITHUB_TOKEN` does not trigger another workflow automatically.

## Pages CMS

See [`docs/pages-cms.md`](docs/pages-cms.md). The CMS provides editors for
upcoming broadcasts/events, the Hören selection, canonical episode numbers and
archive enrichment.

Each editor should use an individual GitHub account with repository access; do
not share one account.

## Licensing

The website software is licensed under the [MIT License](LICENSE). Editorial
content, branding, artwork, audio and third-party media are excluded; see
[`CONTENT-LICENSE.md`](CONTENT-LICENSE.md).
