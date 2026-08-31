# Pages CMS editorial workflow

Pages CMS reads `.pages.yml` and edits the repository files directly. Open
`https://app.pagescms.org`, sign in with your own GitHub account, install the
Pages CMS GitHub App for this repository only, and select branch `main`.

The Content menu contains six focused editors:

1. **Demnächst – Sendungen** → `content/upcoming-broadcasts.json`
2. **Demnächst – Veranstaltungen** → `content/upcoming-events.json`
3. **Hören – Auswahl** → `content/listen.json`
4. **Sendungsnummern** → `content/episode-numbers.json`
5. **Sendungsarchiv** → `content/episodes.json`
6. **Sendungsplanung** → `content/broadcast-schedule.json`

## Hören – Auswahl

The list order is the order shown on the homepage. Keep one to five entries.
Each row contains:

- `label`: only a readable CMS label;
- `episode_id`: the stable internal ID of an archive entry.

The visible title, text, duration and audio link are taken from the archive.
The CMS label is deliberately ignored by the site build, so it cannot create
conflicting public metadata.

The corresponding ID is shown in the **Sendungsarchiv** editor. Existing entries
without an explicit ID use the deterministic fallback `YYYY-MM-DD-title`. Once
an ID is used by the Hören selection, do not change it.

## Editorial rules

- Enter upcoming times as Leipzig local time. Pages CMS stores them without a
  UTC offset, for example `2026-08-29T21:00:00`.
- Use `details_de` and `details_en` as the single full text. The homepage and
  archive list automatically create excerpts.
- Use one `location` field for events. Broadcasts automatically use
  `Radio Blau, Leipzig`.
- Regular future broadcasts normally receive `episode_number` from the schedule
  automation. Set it manually only for a deliberate override or non-regular
  broadcast.
- `episode_id` is the internal archive identity. `audio_url` is the playback
  source and no longer the primary key used by the website.
- Music presentations and tracklist rows are objects and require `title`.
- Uploaded content images may be JPG, PNG or WebP.
- An advanced manually entered `social_image` must be PNG; it is intentionally
  not exposed in the compact CMS forms.

For regular schedule exceptions, use **Sendungsplanung** rather than deleting
or moving a managed row under **Demnächst – Sendungen**. A cancelled slot does
not consume a sendungsnummer; a rescheduled slot keeps its stable ID and number.
See [`broadcast-schedule.md`](broadcast-schedule.md).

Before publishing a larger edit, run locally:

```cmd
py scripts\check.py
py -m pytest -q
```

Every saved change remains attributable to the editor's own GitHub account.

## Archive text priority

Completed broadcasts are archived independently of SoundCloud by the scheduled
archive workflow. It moves the ended broadcast into `content/episodes.json` and
records its canonical date/number before the SoundCloud refresh runs. The
visible archive text uses this priority: manual post-show text, legacy manual
archive text, SoundCloud description, then announcement text. The SoundCloud
cache stores both a short summary and the complete description.
