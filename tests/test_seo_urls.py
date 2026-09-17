from __future__ import annotations

import importlib.util
import json
import shutil
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

ROOT = Path(__file__).resolve().parents[1]


def load_script(name):
    spec = importlib.util.spec_from_file_location(f"seo_{name}", ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


build = load_script("build")
archiver = load_script("archive_broadcasts")
site = json.loads((ROOT / "content/site.json").read_text(encoding="utf-8"))


def test_archive_address_survives_title_and_date_corrections():
    item = {"episode_id": "2020-01-01-original", "date": "2020-01-01", "title_de": "Original"}
    original = build.detail_relative_path("episode", item, site)
    item.update(title_de="Corrected title", date="2020-01-02")
    assert build.detail_relative_path("episode", item, site) == original


def test_existing_url_exceptions_remain_published():
    items = build.load_archive(build.read_json_list(ROOT / "content/episodes.json"))
    paths = {item["episode_id"]: build.detail_relative_path("episode", item, site) for item in items}
    assert paths["2026-08-15-sofea-100-96kbps-komplette-sendung"] == "sendungen/2026-08-15-96kbps-komplette-sendung/"
    assert paths["2023-10-06-scherbert"] == "sendungen/2023-06-10-scherbert/"


def test_fallback_is_specific_and_only_promises_existing_audio():
    item = {"date": "2020-01-01", "title_de": "Guest", "episode_number": 50}
    summary = build.detail_description(item, site)
    assert "Guest" not in summary and "#50" in summary and "1. Januar 2020" in summary
    assert "Mitschnitt" not in summary and "SoundCloud" not in summary
    item["audio_url"] = "https://soundcloud.com/example/recording"
    assert build.archive_summary(item, site) == (
        "sounds of electronic art (sofea) – Mitschnitt der Sendung #50 "
        "vom 1. Januar 2020 auf Radio Blau."
    )
    assert build.archive_summary(item, site, "en") == (
        "sounds of electronic art (sofea) – Recording of episode #50 "
        "from 1 January 2020 on Radio Blau."
    )
    item["post_text_de"] = "An existing editorial description."
    assert build.detail_description(item, site) == item["post_text_de"]


def test_sitemap_uses_only_valid_entry_dates():
    assert build.sitemap_lastmod({}) is None
    assert build.sitemap_lastmod({"updated_at": "2026-02-30"}) is None
    assert build.sitemap_lastmod({"updated_at": "2026-09-17T08:00:00Z"}) == "2026-09-17"


def test_archiving_preserves_rescheduled_id_and_merges_aliases():
    item = {"id": "broadcast-2026-10-24", "date": "2026-10-25T21:00:00", "title_de": "Guest", "title_en": "Guest"}
    archived = archiver.archive_from_broadcast(item, 102)
    assert archived["redirect_from"] == ["termine/broadcast-2026-10-24/"]
    existing = {"redirect_from": ["termine/another-old-address/"], "post_text_de": "Keep me"}
    assert archiver.merge_archived_metadata(existing, archived)
    assert existing["redirect_from"] == ["termine/another-old-address/", "termine/broadcast-2026-10-24/"]
    assert existing["post_text_de"] == "Keep me"
    assert not archiver.merge_archived_metadata(existing, archived)


def test_redirects_reject_conflicts_and_unsafe_paths(tmp_path, monkeypatch):
    monkeypatch.setattr(build, "PUBLIC", tmp_path)
    (tmp_path / "sendungen/episode-one").mkdir(parents=True)
    (tmp_path / "sendungen/episode-one/index.html").write_text("target", encoding="utf-8")
    base = {"episode_id": "episode-one", "redirect_from": ["../escape/"]}
    with pytest.raises(ValueError, match="Invalid redirect path"):
        build.write_archive_redirects([base], site, site["url"])
    base["redirect_from"] = ["sendungen/episode-one/"]
    with pytest.raises(ValueError, match="itself"):
        build.write_archive_redirects([base], site, site["url"])
    base["redirect_from"] = ["termine/old/"]
    other = {"episode_id": "episode-two", "redirect_from": ["termine/old/"]}
    with pytest.raises(ValueError, match="Conflicting"):
        build.write_archive_redirects([base, other], site, site["url"])


def test_announcement_survives_until_archiving_then_redirects(tmp_path, monkeypatch):
    root = tmp_path / "site"
    shutil.copytree(ROOT, root, ignore=shutil.ignore_patterns(".git", "public", "__pycache__", ".pytest_cache"))
    monkeypatch.setattr(build, "ROOT", root)
    monkeypatch.setattr(build, "PUBLIC", root / "public")
    monkeypatch.setattr(build, "EPISODE_ARTWORK_DIR", root / "assets/images/episodes")
    monkeypatch.setattr(build, "write_responsive_artworks", lambda *args: None)
    monkeypatch.setattr(build, "write_social_cards", lambda *args: None)
    monkeypatch.delenv("SITE_URL", raising=False)

    class AfterBroadcast(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 10, 25, 2, tzinfo=ZoneInfo("Europe/Berlin")).astimezone(tz)

    monkeypatch.setattr(build, "datetime", AfterBroadcast)
    build.main()
    announcement = root / "public/termine/broadcast-2026-10-24/index.html"
    assert announcement.is_file()
    assert 'http-equiv="refresh"' not in announcement.read_text(encoding="utf-8")
    assert 'href="/termine/broadcast-2026-10-24/"' not in (root / "public/index.html").read_text(encoding="utf-8")

    assert archiver.migrate(root, AfterBroadcast.now()) == 1
    build.main()
    target = "https://sofea.radio/sendungen/2026-10-24-credit-00/"
    assert f'content="0; url={target}"' in announcement.read_text(encoding="utf-8")
    assert f'rel="canonical" href="{target}"' in announcement.read_text(encoding="utf-8")
    sitemap = (root / "public/sitemap.xml").read_text(encoding="utf-8")
    assert target in sitemap
    assert "/termine/broadcast-2026-10-24/" not in sitemap
