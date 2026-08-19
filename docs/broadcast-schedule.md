# Broadcast schedule automation

Regular `sounds of electronic art` broadcasts are maintained by `scripts/update_schedule.py`.

The schedule is configured in `content/site.json` under `broadcast_schedule`:

- `anchor`: first regular slot managed by the automation. The current anchor is 2026-08-29 21:00, episode #101.
- `first_episode_number`: episode number belonging to the anchor.
- `interval_weeks`: regular cadence, currently 8 weeks.
- `horizon_months`: how far the generated calendar is kept populated, currently 12 months.
- `skip_dates`: regular slot dates that are cancelled completely.
- `date_overrides`: regular slot dates that move to another local date/time while keeping their stable ID and episode number.

Unknown guests use `sounds of electronic art` as the editorial title. Do not use `tba`. Once a guest is known, replace `title_de` / `title_en` with the guest or editorial title. The calendar title is assembled automatically as `sounds of electronic art #NUMBER – GUEST`; without a guest it is simply `sounds of electronic art #NUMBER`.

## Cancellation

To cancel the regular slot on 2027-02-13:

```json
"skip_dates": [
  "2027-02-13"
]
```

## Rescheduling

To move the same slot to 2027-02-20 at 21:00 while keeping its identity and episode number:

```json
"date_overrides": {
  "2027-02-13": "2027-02-20T21:00:00"
}
```

Do not put the same slot in both `skip_dates` and `date_overrides`.
