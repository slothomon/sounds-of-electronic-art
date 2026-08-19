from __future__ import annotations

import importlib.util
import unittest
from datetime import datetime
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "update_schedule.py"
spec = importlib.util.spec_from_file_location("update_schedule", MODULE_PATH)
update_schedule = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(update_schedule)


class BroadcastScheduleTests(unittest.TestCase):
    def site(self):
        return {
            "name": "sounds of electronic art",
            "short_name": "sofea",
            "broadcast_schedule": {
                "anchor": "2026-08-29T21:00:00",
                "first_episode_number": 101,
                "interval_weeks": 8,
                "horizon_months": 12,
                "skip_dates": [],
                "date_overrides": {},
            },
        }

    def now(self):
        return datetime(2026, 8, 20, 12, 0, tzinfo=update_schedule.BERLIN_TZ)

    def test_regular_slots_start_with_episode_101(self):
        rows = update_schedule.maintain_schedule(self.site(), [], self.now())
        self.assertEqual(
            [(row["date"][:10], row["episode_number"]) for row in rows],
            [
                ("2026-08-29", 101),
                ("2026-10-24", 102),
                ("2026-12-19", 103),
                ("2027-02-13", 104),
                ("2027-04-10", 105),
                ("2027-06-05", 106),
                ("2027-07-31", 107),
            ],
        )

    def test_legacy_tba_is_normalized(self):
        existing = [{
            "date": "2026-08-29T21:00:00",
            "title_de": "sofea #100 - tba",
            "title_en": "sofea #100 - tba",
            "details_de": "Drei Stunden elektronische Musik. Live auf Radio Blau",
            "details_en": "Three hours of electronic music. Live on Radio Blau.",
        }]
        row = update_schedule.maintain_schedule(self.site(), existing, self.now())[0]
        self.assertEqual(row["id"], "broadcast-2026-08-29")
        self.assertEqual(row["episode_number"], 101)
        self.assertEqual(row["title_de"], "sounds of electronic art")
        self.assertNotIn("label_de", row)
        self.assertNotIn("label_en", row)

    def test_guest_fields_are_preserved(self):
        existing = [{
            "date": "2026-08-29T21:00:00",
            "title_de": "Heckintosh",
            "title_en": "Heckintosh",
            "details_de": "Custom",
            "details_en": "Custom EN",
            "links": [{"label": "Info", "url": "https://example.com"}],
        }]
        row = update_schedule.maintain_schedule(self.site(), existing, self.now())[0]
        self.assertEqual(row["title_de"], "Heckintosh")
        self.assertEqual(row["details_de"], "Custom")
        self.assertEqual(row["links"][0]["label"], "Info")

    def test_skip_date_removes_regular_slot(self):
        site = self.site()
        site["broadcast_schedule"]["skip_dates"] = ["2027-02-13"]
        rows = update_schedule.maintain_schedule(site, [], self.now())
        self.assertNotIn("2027-02-13", [row["date"][:10] for row in rows])
        next_regular = next(row for row in rows if row["date"][:10] == "2027-04-10")
        self.assertEqual(next_regular["episode_number"], 104)

    def test_override_keeps_slot_identity_and_number(self):
        site = self.site()
        site["broadcast_schedule"]["date_overrides"] = {
            "2027-02-13": "2027-02-20T21:00:00"
        }
        rows = update_schedule.maintain_schedule(site, [], self.now())
        row = next(row for row in rows if row["episode_number"] == 104)
        self.assertEqual(row["id"], "broadcast-2027-02-13")
        self.assertEqual(row["date"], "2027-02-20T21:00:00")


if __name__ == "__main__":
    unittest.main()
