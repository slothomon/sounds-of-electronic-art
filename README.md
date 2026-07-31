# sounds of electronic art — GitHub Pages site

A dependency-light static site for the sounds of electronic art radio show.

## Included

- Responsive one-page design
- German default interface with an English language switch
- Orange, rose/lavender and contrast colour palettes
- Light/dark theme switch
- Next-show card and calendar link
- Ten featured SoundCloud recordings with an in-page player
- Broadcast archive loaded from the SoundCloud playlist `Sendungen`
- Searchable local fallback archive
- RSS feed, sitemap, robots.txt and custom 404 page
- Automatic deployment with GitHub Actions and GitHub Pages
- No analytics or external web fonts

## SoundCloud playlist archive

The archive source is configured in:

```text
content/site.json
```

```json
"archive_playlist_url": "https://soundcloud.com/sounds-of-electronic-art/sets/sendungen"
```

At runtime the page uses the official SoundCloud Widget API to read all tracks from that playlist. Adding or removing a track in the playlist therefore updates the website archive without a new Git commit.

The page derives the broadcast date from the track title, description or URL when it finds one of these forms:

```text
2026-03-14
14.03.2026
14. März 2026
```

When no broadcast date can be found, the SoundCloud publication date is used.

Browser privacy extensions can block SoundCloud. In that case the locally stored fallback from `content/episodes.json` remains visible.

## Local fallback and next transmission

The next transmission and fallback archive are stored in:

```text
content/episodes.json
```

A record uses this structure:

```json
{
  "date": "2026-03-14T21:00:00+01:00",
  "title_de": "Neele",
  "title_en": "Neele",
  "status": "past",
  "summary_de": "Mitschnitt des Sets aus der 98. Sendung im März 2026.",
  "summary_en": "Recording of Neele's set from the 98th show in March 2026.",
  "audio_url": "https://soundcloud.com/sounds-of-electronic-art/neele-2026-03-14"
}
```

The former `guests` field is no longer needed. Guest names should be part of the title.

Field notes:

- `date`: ISO 8601 date including the Leipzig UTC offset
- `title_de` / `title_en`: title in both languages
- `status`: `upcoming` for a future transmission, otherwise `past`
- `summary_de` / `summary_en`: short description
- `audio_url`: recording URL or `null`

Check the JSON syntax with:

```cmd
python -m json.tool content\episodes.json > nul
```

## Featured recordings

The ten cards in the **Hören** section are maintained in the `mixes` array in:

```text
content/site.json
```

## Preview locally on Windows

```cmd
cd /d M:\dev\sofea-github-pages
python scripts\build.py
python -m http.server 8000 --directory public
```

Open:

```text
http://localhost:8000
```

## Deploy to GitHub Pages

```cmd
git status
git add .
git commit -m "Update website"
git push
```

The included GitHub Actions workflow rebuilds and deploys the `public` directory. Do not edit files inside `public` directly.
