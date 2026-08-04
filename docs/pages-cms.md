# Pages CMS editorial workflow

Pages CMS edits the JSON files in this GitHub repository directly. There is no
separate content database and every change remains visible in Git history.

## Editors

Use one personal GitHub account per editor. Add the two or three editors as
repository collaborators and enable 2FA or passkeys. Do not create a shared
editor account.

## Content areas

The Pages CMS sidebar contains three focused editors:

1. **Demnächst – Sendungen** → `content/upcoming-broadcasts.json`
2. **Demnächst – Veranstaltungen** → `content/upcoming-events.json`
3. **Sendungsarchiv** → `content/episodes.json`

This separation is deliberate: Pages CMS cannot filter one top-level JSON array
into several field-specific editors. Separate files keep the forms short and
avoid showing venue, tracklist or archive fields where they are irrelevant.

### Demnächst – Sendungen

Fields:

- start date and time;
- German and English title;
- one German and English text;
- optional artwork;
- optional external buttons.

Broadcasts default to three hours. The homepage automatically shortens the text;
the detail page displays it in full.

### Demnächst – Veranstaltungen

Fields:

- start and optional end;
- German and English title;
- one German and English text;
- one venue/location field;
- optional flyer;
- optional external buttons.

### Sendungsarchiv

Fields:

- broadcast date and optional update date;
- German and English title;
- exact SoundCloud URL;
- optional German and English editorial text;
- optional local artwork;
- music presentations;
- tracklist.

If the editorial text is empty, the SoundCloud description remains the fallback.
The archive list shows an automatic excerpt and the detail page shows the full
text.

## Correct local time

Future dates are stored without a timezone suffix:

```json
"date": "2026-08-29T21:00:00"
```

Pages CMS therefore displays 21:00 instead of converting the value to 19:00.
The build interprets the value as `Europe/Berlin`, including CET/CEST changes.
Do not manually add `Z`, `+01:00` or `+02:00` to future dates in the new files.

## One-time migration

The former `content/episodes.json` mixed archive entries and upcoming items.
First preview the migration:

```cmd
py scripts\split_episode_content.py
```

Then write the split files:

```cmd
py scripts\split_episode_content.py --write
```

The script:

- keeps archive enrichment in `content/episodes.json`;
- moves future broadcasts to `content/upcoming-broadcasts.json`;
- moves future events to `content/upcoming-events.json`;
- keeps the entered local clock time while removing the UTC offset;
- replaces the old summary/detail duplication with one `details_*` text field;
- removes redundant trailing dates from local archive titles.

Review the diff before committing:

```cmd
git diff -- content
```

## Opening Pages CMS

1. Open `https://app.pagescms.org/`.
2. Sign in with your personal GitHub account.
3. Install the Pages CMS GitHub App.
4. Select **Only select repositories**.
5. Authorize only `slothomon/sounds-of-electronic-art`.
6. Open the repository and branch `main`.
7. Choose one of the three content areas.

After changing `.pages.yml`, Pages CMS may retain its cached configuration for a
few minutes. Reload the repository view after the new commit is on `main`.

## Before publishing locally

```cmd
py scripts\validate_site.py --source
py scripts\build.py
py scripts\validate_site.py --public
```

Pages CMS itself writes commits to GitHub. GitHub Actions then performs the same
validation before deploying the site.
