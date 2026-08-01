# sounds of electronic art — GitHub Pages site

A dependency-light static website for the sounds of electronic art radio show.

## Included

- Responsive orange design
- German default interface with English language switch
- Dark theme and a Solarized-Light-inspired light theme
- Multiple upcoming broadcasts and events
- Five selectable SoundCloud recordings with an in-page player
- Statically generated and searchable broadcast archive
- Automatic SoundCloud archive refresh during deployment and once per day
- RSS feed, sitemap, robots.txt and custom 404 page
- Automatic deployment with GitHub Actions and GitHub Pages
- No analytics, cookies or external web fonts

## Edit general content

General information, team, links and the SoundCloud recording list are in:

```text
content/site.json
```

The `mixes` array controls the recordings in the **Hören / Listen** section.

## Add broadcasts and events to “Upcoming”

Upcoming items are maintained in:

```text
content/episodes.json
```

Every object with

```json
"status": "upcoming"
```

is rendered in the Upcoming section. Entries are automatically sorted by date, so the file can contain one, two or more upcoming items.

### Broadcast example

```json
{
  "date": "2026-08-29T21:00:00+02:00",
  "end": "2026-08-30T00:00:00+02:00",
  "type": "broadcast",
  "title_de": "sounds of electronic art",
  "title_en": "sounds of electronic art",
  "status": "upcoming",
  "summary_de": "Drei Stunden elektronische Musik und Gespräche live auf Radio Blau.",
  "summary_en": "Three hours of electronic music and conversation live on Radio Blau.",
  "audio_url": null
}
```

For broadcasts, no extra livestream or schedule button is added; the permanent livestream remains in the main navigation. If `end` is omitted, a duration of three hours is assumed.

### Event example

Add another object to the same JSON array:

```json
{
  "date": "2026-09-12T20:00:00+02:00",
  "end": "2026-09-13T02:00:00+02:00",
  "type": "event",
  "title_de": "sofea night",
  "title_en": "sofea night",
  "status": "upcoming",
  "summary_de": "Eine Nacht mit dem sofea-Team und Gästen.",
  "summary_en": "A night with the sofea team and guests.",
  "location_de": "Conne Island, Leipzig",
  "location_en": "Conne Island, Leipzig",
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

Supported optional fields:

- `end`: end date and time; otherwise 3 hours for broadcasts and 2 hours for events
- `duration_hours`: alternative duration when `end` is omitted
- `type`: `broadcast` or `event`
- `label_de` / `label_en`: custom category label above the title
- `location`, or separate `location_de` / `location_en`
- `links`: any number of buttons with bilingual labels, URL and optional `primary: true`

A standard `.ics` calendar file is generated automatically for every upcoming item. It can be opened by Apple Calendar, Outlook, Thunderbird and most mobile calendar apps without depending on a Google account. Upcoming times are interpreted in the `Europe/Berlin` timezone; the displayed time uses whole hours only.

Check the JSON syntax after editing:

```cmd
python -m json.tool content\episodes.json > nul
```

## In-page details and track lists

The title of every upcoming item and archived broadcast opens a responsive in-page detail dialog. The URL hash changes while the dialog is open, so the current detail view can be copied and shared directly. On mobile devices the dialog is displayed as a full-width bottom sheet.

Optional detail fields can be added to an upcoming item or a past broadcast in `content/episodes.json`:

```json
{
  "details_de": "Längerer Beschreibungstext mit Hintergrundinformationen.",
  "details_en": "Longer description with background information.",
  "image": "assets/images/my-event.jpg",
  "image_alt_de": "Flyer der Veranstaltung",
  "image_alt_en": "Event flyer",
  "lineup": [
    {"name": "96kbps", "url": "https://soundcloud.com/skile"},
    "easy.miner",
    "fumé"
  ],
  "tracklist": [
    {"time": "00:00", "artist": "Artist", "title": "Track"},
    "Another Artist — Another Track"
  ]
}
```

For an archived SoundCloud broadcast, keep an object in `content/episodes.json` with the same `audio_url` as the cached entry. The build merges the local detail fields into the automatically refreshed archive cache, so track lists and editorial text are not overwritten by the daily SoundCloud update.

## Static broadcast archive

The archive is generated from:

```text
https://soundcloud.com/sounds-of-electronic-art/sets/sendungen
```

`scripts/update_archive.py` reads the playlist through `yt-dlp`, cleans titles, dates, descriptions and URLs, and writes the result to:

```text
content/archive-cache.json
```

`scripts/build.py` then renders the cache into static HTML and `public/archive.json`. The public page does not need to query SoundCloud when a visitor opens it.

The GitHub Actions workflow refreshes the cache:

- on every push to `main`
- when manually started
- once per day

When the playlist changes, GitHub Actions commits the refreshed cache as `github-actions[bot]`.

## Build and preview locally

A normal website build only needs Python:

```cmd
cd /d M:\dev\sofea-github-pages
python scripts\build.py
python -m http.server 8000 --directory public
```

Open:

```text
http://localhost:8000
```

Updating the SoundCloud archive locally is optional. Install the additional dependency once:

```cmd
python -m pip install -r requirements-archive.txt
python scripts\update_archive.py
```

GitHub Actions performs the archive update automatically during deployment.

## Deploy to GitHub Pages

1. Push the repository to `main`.
2. Open **Settings > Pages**.
3. Select **GitHub Actions** as the source.
4. Wait for the **Deploy GitHub Pages** workflow.

Do not edit files inside `public` directly. They are regenerated by `scripts/build.py`.

## Impressum und Datenschutz

Die Betreiberangaben werden zentral in `content/legal.json` gepflegt:

```json
{
  "operator_name": "Vorname Nachname",
  "street_address": "Musterstraße 1",
  "postal_city": "01234 Musterstadt",
  "country": "Deutschland"
}
```

Beim Build entstehen daraus:

- `public/impressum.html`
- `public/datenschutz.html`

Die Vorlagen enthalten bewusst keine E-Mail-Adresse und keine Telefonnummer. Vor der Veröffentlichung müssen die Platzhalter in `content/legal.json` ersetzt werden.

Das Radio-Blau-Logo im Footer ist mit `https://www.radioblau.de/` verlinkt. Die Grafik unter `assets/images/radioblau-logo.png` ist die unveränderte bereitgestellte Originaldatei.
