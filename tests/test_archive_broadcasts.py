#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import tempfile
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "archive_broadcasts.py"
spec = importlib.util.spec_from_file_location("archive_broadcasts", SCRIPT)
module = importlib.util.module_from_spec(spec)
assert spec.loader
spec.loader.exec_module(module)
BERLIN = ZoneInfo("Europe/Berlin")


def write(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def fixture(root: Path, episodes=None, upcoming=None, numbers=None):
    write(root / "content" / "episodes.json", episodes or [])
    write(root / "content" / "upcoming-broadcasts.json", upcoming or [])
    write(root / "content" / "episode-numbers.json", numbers or [])


def test_expired_broadcast_moves_without_audio():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        fixture(
            root,
            episodes=[{"date": "2026-08-15", "title_de": "Old", "title_en": "Old", "audio_url": "https://example.test/audio", "episode_id": "2026-08-15-old"}],
            numbers=[{"date": "2026-08-15", "episode_number": 100}],
            upcoming=[
                {
                    "date": "2026-08-29T21:00:00",
                    "episode_number": 101,
                    "title_de": "Heckintosh",
                    "title_en": "Heckintosh",
                    "details_de": "Ankündigung",
                    "details_en": "Announcement",
                    "image": "/assets/heckintosh.png",
                    "id": "broadcast-2026-08-29",
                },
                {
                    "date": "2026-10-24T21:00:00",
                    "episode_number": 102,
                    "title_de": "Credit 00",
                    "title_en": "Credit 00",
                },
            ],
        )
        count = module.migrate(root, datetime(2026, 8, 30, 2, 0, tzinfo=BERLIN))
        assert count == 1
        episodes = read(root / "content" / "episodes.json")
        archived = episodes[0]
        assert archived["episode_number"] == 101
        assert archived["episode_id"] == "2026-08-29-heckintosh"
        assert archived["announcement_de"] == "Ankündigung"
        assert archived["announcement_en"] == "Announcement"
        assert "details_de" not in archived
        assert "audio_url" not in archived
        assert [row["episode_number"] for row in read(root / "content" / "episode-numbers.json")][:2] == [101, 100]
        assert [row["episode_number"] for row in read(root / "content" / "upcoming-broadcasts.json")] == [102]


def test_existing_audio_is_preserved():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        fixture(
            root,
            episodes=[
                {
                    "date": "2026-08-29",
                    "episode_number": 101,
                    "title_de": "Heckintosh",
                    "title_en": "Heckintosh",
                    "audio_url": "https://soundcloud.com/example/heckintosh",
                    "episode_id": "2026-08-29-heckintosh",
                }
            ],
            numbers=[{"date": "2026-08-29", "episode_number": 101}],
            upcoming=[
                {
                    "date": "2026-08-29T21:00:00",
                    "episode_number": 101,
                    "title_de": "Heckintosh",
                    "title_en": "Heckintosh",
                    "details_de": "Neue Beschreibung",
                }
            ],
        )
        module.migrate(root, datetime(2026, 8, 30, 2, 0, tzinfo=BERLIN))
        archived = read(root / "content" / "episodes.json")[0]
        assert archived["audio_url"] == "https://soundcloud.com/example/heckintosh"
        assert archived["announcement_de"] == "Neue Beschreibung"


def test_automatic_number_assignment_and_idempotence():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        fixture(
            root,
            numbers=[{"date": "2026-08-15", "episode_number": 100}],
            upcoming=[
                {
                    "date": "2026-08-29T21:00:00",
                    "title_de": "Heckintosh",
                    "title_en": "Heckintosh",
                }
            ],
        )
        now = datetime(2026, 8, 30, 2, 0, tzinfo=BERLIN)
        assert module.migrate(root, now) == 1
        before = (root / "content" / "episodes.json").read_bytes()
        assert read(root / "content" / "episodes.json")[0]["episode_number"] == 101
        assert module.migrate(root, now) == 0
        assert (root / "content" / "episodes.json").read_bytes() == before


def test_dry_run_does_not_write():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        fixture(
            root,
            numbers=[{"date": "2026-08-15", "episode_number": 100}],
            upcoming=[{"date": "2026-08-29T21:00:00", "episode_number": 101, "title_de": "Heckintosh", "title_en": "Heckintosh"}],
        )
        original = (root / "content" / "upcoming-broadcasts.json").read_bytes()
        assert module.migrate(root, datetime(2026, 8, 30, 2, 0, tzinfo=BERLIN), dry_run=True) == 1
        assert (root / "content" / "upcoming-broadcasts.json").read_bytes() == original
        assert read(root / "content" / "episodes.json") == []


if __name__ == "__main__":
    tests = [
        test_expired_broadcast_moves_without_audio,
        test_existing_audio_is_preserved,
        test_automatic_number_assignment_and_idempotence,
        test_dry_run_does_not_write,
    ]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
