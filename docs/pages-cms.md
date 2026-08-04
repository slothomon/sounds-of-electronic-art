# Pages CMS editorial workflow

Pages CMS edits the JSON files in this GitHub repository directly. It does not
introduce a second database or a shared password.

## Accounts and access

Each editor should use an individual GitHub account. Add the two or three
editors as collaborators under:

```text
Repository → Settings → Collaborators → Add people
```

Use two-factor authentication or passkeys. Do not create a shared editorial
GitHub account: individual accounts preserve attribution and can be revoked
separately.

## One-time setup

1. Open `app.pagescms.org`.
2. Sign in with your own GitHub account.
3. Install the Pages CMS GitHub App.
4. Choose **Only select repositories**.
5. Select `slothomon/sounds-of-electronic-art`.
6. Open the repository and branch `main`.

Pages CMS automatically reads `.pages.yml` from the repository root.

## Content areas

The CMS intentionally exposes three focused editors:

- **Demnächst – Sendungen** → `content/upcoming-broadcasts.json`
- **Demnächst – Veranstaltungen** → `content/upcoming-events.json`
- **Sendungsarchiv** → `content/episodes.json`

### Upcoming broadcasts

Available fields:

- local start date/time;
- optional episode number;
- German and English title;
- German and English full text;
- optional artwork;
- optional external buttons/links.

The website creates the shorter homepage excerpt automatically. Broadcasts
default to three hours and `Radio Blau, Leipzig`.

### Upcoming events

Available fields:

- local start and optional end date/time;
- German and English title;
- German and English full text;
- one visible location field;
- optional flyer/artwork;
- optional external buttons/links.

### Archive enrichment

The SoundCloud cache supplies the basic metadata and locally cached artwork.
The archive editor adds only the editorial fields that the site owns:

- date and optional episode number;
- German and English title;
- exact SoundCloud URL used as the merge key;
- optional full editorial text;
- optional artwork override;
- music presentations;
- tracklist;
- optional `updated_at` for meaningful content changes.

Music presentations and tracklist rows are object lists. Use the URL field for
Discogs, Bandcamp, label or artist links.

## Dates and time zones

Upcoming times are saved as Leipzig wall-clock time without a UTC suffix:

```text
2026-08-29T21:00:00
```

The build applies `Europe/Berlin`, including summer and winter time. Archive
dates use `YYYY-MM-DD`.

## Images

Uploaded images are stored in:

```text
assets/images/uploads/
```

Cached SoundCloud artwork is stored in:

```text
assets/images/episodes/
```

An explicit CMS artwork wins over automatically cached SoundCloud artwork.
Custom `social_image` values are an advanced manual option and must be PNG.

## Publishing and validation

Saving in Pages CMS creates a normal Git commit. GitHub Actions then runs the
same command used locally:

```cmd
py scripts\check.py
```

If validation fails, inspect the Actions log before making further edits. The
source JSON remains versioned and can be restored from Git history.
