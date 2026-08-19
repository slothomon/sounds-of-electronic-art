from __future__ import annotations

import unittest
from datetime import datetime, timezone

from scripts import build


class CalendarNotesLayoutTests(unittest.TestCase):
    def setUp(self):
        self.site = {
            "name": "sounds of electronic art",
            "radio": {"stream_url": "https://www.radioblau.de/stream/"},
        }
        self.item = {
            "id": "broadcast-2026-08-29",
            "type": "broadcast",
            "date": "2026-08-29T21:00:00",
            "episode_number": 101,
            "title_de": "Heckintosh",
            "details_de": "Drei Stunden elektronische Musik. Live auf Radio Blau.",
        }
        self.event_url = "https://sofea.radio/termine/broadcast-2026-08-29/"

    def event_lines(self):
        return build.calendar_event_lines(
            self.item,
            self.site,
            self.event_url,
            datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
        )

    def test_vevent_url_stays_on_sofea_detail_page(self):
        lines = self.event_lines()
        self.assertIn(f"URL:{self.event_url}", lines)
        self.assertNotIn("URL:https://www.radioblau.de/stream/", lines)
        self.assertFalse(any(line.startswith("X-SOFEA-EVENT-URL:") for line in lines))

    def test_livestream_is_first_item_after_separator(self):
        description = next(line for line in self.event_lines() if line.startswith("DESCRIPTION:"))
        expected = (
            r"\n\n-----\n\nLivestream: https://www.radioblau.de/stream/"
            r"\n\nRadio Blau erreicht ihr auf DAB+"
        )
        self.assertIn(expected, description)

    def test_livestream_url_is_not_split_by_ical_folding(self):
        description = next(line for line in self.event_lines() if line.startswith("DESCRIPTION:"))
        folded = build.fold_ical_line(description)
        url = "https://www.radioblau.de/stream/"
        self.assertTrue(any(url in physical_line for physical_line in folded))
        self.assertFalse(any("https://" in physical_line and url not in physical_line for physical_line in folded))


if __name__ == "__main__":
    unittest.main()
