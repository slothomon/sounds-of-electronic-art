# Structured data

The build inserts JSON-LD automatically. The markup mirrors visible content;
missing optional values are omitted rather than invented.

## Homepage

The homepage contains a graph with:

- `WebSite`
- `WebPage`
- `RadioSeries`

The series identifies `sounds of electronic art`, Radio Blau, the team and the
public profiles configured in `content/site.json`.

## Upcoming broadcast

Source (`content/upcoming-broadcasts.json`):

```json
{
  "id": "broadcast-2026-10-24",
  "date": "2026-10-24T21:00:00",
  "episode_number": 102,
  "title_de": "Credit 00",
  "title_en": "Credit 00",
  "details_de": "Drei Stunden elektronische Musik. Live auf Radio Blau.",
  "details_en": "Three hours of electronic music, live on Radio Blau."
}
```

Generated JSON-LD contains a `RadioEpisode` with optional `episodeNumber`, a
`BroadcastEvent`, `RadioBroadcastService`, and a reference to the
`RadioSeries`.

## Upcoming event

Source (`content/upcoming-events.json`):

```json
{
  "date": "2026-09-12T20:00:00",
  "end": "2026-09-13T02:00:00",
  "title_de": "sofea night",
  "title_en": "sofea night",
  "details_de": "Eine Nacht mit dem sofea-Team und Gästen.",
  "details_en": "A night with the sofea team and guests.",
  "location": "Conne Island, Leipzig",
  "links": [
    {
      "label_de": "Details",
      "label_en": "Details",
      "url": "https://example.org/event",
      "primary": true
    }
  ]
}
```

Generated JSON-LD uses `MusicEvent`, `Place`, `EventScheduled`,
`OfflineEventAttendanceMode`, the visible description, image and external
links.

## Archived broadcast

Source enrichment (`content/episodes.json`):

```json
{
  "episode_id": "2026-03-14-neele",
  "date": "2026-03-14",
  "episode_number": 98,
  "title_de": "Neele",
  "title_en": "Neele",
  "audio_url": "https://soundcloud.com/sounds-of-electronic-art/neele-2026-03-14",
  "details_de": "Mitschnitt aus der 98. Sendung.",
  "details_en": "Recording from the 98th broadcast."
}
```

`episode_id` is the stable local identity and is used for the detail URL and
internal references. It is not a Schema.org property. `audio_url` remains the
current playback source.

Generated JSON-LD contains `RadioEpisode`, optional `episodeNumber`,
`AudioObject`, duration where available, image and a `RadioSeries` reference.

## Validation

`scripts/validate_site.py --public` parses every JSON-LD block and requires the
Schema.org context on the homepage and all detail pages. Use Google's Rich
Results Test for `MusicEvent` pages and Schema.org Validator for the radio
vocabulary. Correct structured data does not guarantee a rich result.
