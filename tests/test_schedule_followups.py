from __future__ import annotations

import importlib.util
import unittest
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


update_schedule = load_module("update_schedule_followup", ROOT / "scripts" / "update_schedule.py")
build = load_module("build_followup", ROOT / "scripts" / "build.py")


class ScheduleFollowupTests(unittest.TestCase):
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
                "date_overrides": [],
            },
        }

    def now(self):
        return datetime(2026, 8, 20, 12, 0, tzinfo=update_schedule.BERLIN_TZ)

    def test_cancelled_slot_does_not_consume_episode_number(self):
        site = self.site()
        site["broadcast_schedule"]["skip_dates"] = ["2027-02-13"]
        rows = update_schedule.maintain_schedule(site, [], self.now())
        april = next(row for row in rows if row["date"][:10] == "2027-04-10")
        self.assertEqual(april["episode_number"], 104)

    def test_pages_cms_override_list_keeps_identity_and_number(self):
        site = self.site()
        site["broadcast_schedule"]["date_overrides"] = [
            {"date": "2027-02-13", "new_date": "2027-02-20T21:00:00"}
        ]
        rows = update_schedule.maintain_schedule(site, [], self.now())
        row = next(row for row in rows if row["episode_number"] == 104)
        self.assertEqual(row["id"], "broadcast-2027-02-13")
        self.assertEqual(row["date"], "2027-02-20T21:00:00")

    def test_calendar_folding_keeps_short_https_url_whole(self):
        url = "https://www.radioblau.de/stream/"
        line = "DESCRIPTION:" + ("Langer Standardtext " * 8) + r"\nLiveStream:\n" + url
        folded = build.fold_ical_line(line)
        self.assertTrue(any(url in physical_line for physical_line in folded))
        self.assertFalse(any("https://" in physical_line and url not in physical_line for physical_line in folded))
        self.assertTrue(all(len(physical_line.encode("utf-8")) <= 73 for physical_line in folded))
        unfolded = folded[0] + "".join(
            physical_line[1:] if physical_line.startswith(" ") else physical_line
            for physical_line in folded[1:]
        )
        self.assertEqual(unfolded, line)


if __name__ == "__main__":
    unittest.main()
