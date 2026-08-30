#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "update_archive.py"
spec = importlib.util.spec_from_file_location("update_archive", SCRIPT)
module = importlib.util.module_from_spec(spec)
assert spec.loader
spec.loader.exec_module(module)


def test_sound_description_and_summary():
    value = (
        "Danke für den Abend.\n"
        "Viel Freude beim Nachhören!\n\n"
        "Soundcloud:\n"
        "[example](https://soundcloud.com/example)\n"
    )
    description = module.sound_description({"description": value})
    assert description == value.rstrip()
    assert module.sound_summary(description) == "Danke für den Abend."


def test_normalise_sounds_keeps_full_description():
    value = "Erste Zeile.\n\nZweite Zeile."
    cache = module.normalise_sounds(
        [{
            "id": "1",
            "title": "Test 2026-08-29",
            "description": value,
            "permalink_url": "https://soundcloud.com/example/test",
            "duration": 1000,
        }],
        "https://soundcloud.com/example/sets/test",
    )
    episode = cache["episodes"][0]
    assert episode["summary"] == "Erste Zeile."
    assert episode["description"] == value


if __name__ == "__main__":
    test_sound_description_and_summary()
    print("PASS test_sound_description_and_summary")
    test_normalise_sounds_keeps_full_description()
    print("PASS test_normalise_sounds_keeps_full_description")
