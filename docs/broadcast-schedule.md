# Broadcast schedule automation

Regular `sounds of electronic art` broadcasts are maintained by `scripts/update_schedule.py`.

The authoritative schedule configuration lives in `content/broadcast-schedule.json` and is editable in Pages CMS under **Sendungsplanung**.

- `anchor`: first regular slot managed by the automation. Current anchor: 2026-08-29 21:00, episode #101.
- `first_episode_number`: episode number belonging to the anchor.
- `interval_weeks`: regular cadence, currently 8 weeks.
- `horizon_months`: how far the generated calendar is kept populated, currently 12 months.
- `skip_dates`: regular slot dates that are cancelled completely.
- `date_overrides`: regular slot dates that move to another local date/time while keeping their stable ID and episode number.

Unknown guests use `sounds of electronic art` as the editorial title. Do not use `tba`. Once a guest is known, replace `title_de` / `title_en` with the guest or editorial title. The calendar title is assembled automatically as `sounds of electronic art #NUMBER – GUEST`; without a guest it is simply `sounds of electronic art #NUMBER`.

## Cancellation

In Pages CMS, open **Sendungsplanung → Ausfallende Sendungen** and add the regular date, for example `2027-02-13`.

A cancelled slot does **not** consume an episode number. If #103 is followed by a cancelled regular slot, the next broadcast is #104.

Equivalent JSON:

```json
"skip_dates": [
  "2027-02-13"
]
```

## Rescheduling

In Pages CMS, open **Sendungsplanung → Verschobene Sendungen** and add the regular slot plus its new local date/time.

Example: move the regular slot from 2027-02-13 to 2027-02-20 21:00 while keeping its identity and episode number:

```json
"date_overrides": [
  {
    "date": "2027-02-13",
    "new_date": "2027-02-20T21:00:00"
  }
]
```

Do not put the same slot in both `skip_dates` and `date_overrides`.

## Calendar notes

The iCalendar output folds long lines according to the existing byte limit while keeping ordinary HTTP(S) URLs on a single physical folded line when possible. This avoids clients treating the livestream URL as a truncated link when the preceding description is long.
