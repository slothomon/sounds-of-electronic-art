from __future__ import annotations

import unittest
from datetime import datetime, timezone

from scripts import build


class CalendarTitleNotesTests(unittest.TestCase):
    def setUp(self):
        self.site = {
            "name": "sounds of electronic art",
            "radio": {"stream_url": "https://www.radioblau.de/stream/"},
        }
        self.item = {
            "id": "broadcast-2026-10-24",
            "type": "broadcast",
            "date": "2026-10-24T21:00:00",
            "episode_number": 102,
            "title_de": "Credit 00",
            "details_de": "Drei Stunden elektronische Musik. Live auf Radio Blau.",
        }
        self.event_url = "https://sofea.radio/termine/broadcast-2026-10-24/"

    def event_lines(self):
        return build.calendar_event_lines(
            self.item,
            self.site,
            self.event_url,
            datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
        )

    def test_calendar_title_uses_short_sofea_name(self):
        self.assertEqual(build.calendar_title(self.item, self.site), "sofea #102 - Credit 00")

    def test_calendar_title_without_guest(self):
        item = dict(self.item, title_de="sounds of electronic art")
        self.assertEqual(build.calendar_title(item, self.site), "sofea #102")

    def test_legacy_prefixed_title_is_not_duplicated(self):
        item = dict(self.item, title_de="sofea #102 - Credit 00")
        self.assertEqual(build.calendar_title(item, self.site), "sofea #102 - Credit 00")

    def test_livestream_url_is_on_line_after_label(self):
        description = next(line for line in self.event_lines() if line.startswith("DESCRIPTION:"))
        self.assertIn(
            r"\n\n-----\n\nLivestream:\nhttps://www.radioblau.de/stream/\n\nRadio Blau",
            description,
        )

    def test_vevent_url_stays_on_sofea(self):
        self.assertIn(f"URL:{self.event_url}", self.event_lines())


if __name__ == "__main__":
    unittest.main()
