#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import tempfile
from pathlib import Path

from PIL import Image

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "build.py"
spec = importlib.util.spec_from_file_location("build", SCRIPT)
module = importlib.util.module_from_spec(spec)
assert spec.loader
spec.loader.exec_module(module)


def test_archive_text_priority():
    base = {
        "announcement_de": "Ankündigung",
        "summary_de": "Kurzfassung",
        "soundcloud_description": "SoundCloud komplett",
        "post_text_de": "Nachtext",
    }
    assert module.content_text(base, "de") == "Nachtext"

    without_post = dict(base)
    without_post.pop("post_text_de")
    assert module.content_text(without_post, "de") == "SoundCloud komplett"

    legacy = dict(without_post)
    legacy["details_de"] = "Manueller Alttext"
    assert module.content_text(legacy, "de") == "Manueller Alttext"

    announcement_only = {"announcement_de": "Ankündigung", "announcement_en": "Announcement"}
    assert module.content_text(announcement_only, "de") == "Ankündigung"
    assert module.content_text(announcement_only, "en") == "Announcement"


def test_markdown_links_are_safe_and_cards_stay_clean():
    value = "Danke!\n\nSoundcloud:\n[Profil](https://soundcloud.com/example)"
    rendered = module.text_paragraphs(value)
    assert 'href="https://soundcloud.com/example"' in rendered
    assert "[Profil](" not in rendered
    assert module.card_excerpt(value, 180) == "Danke!"


def test_soundcloud_mentions_are_linked_without_matching_email_addresses():
    value = (
        "Mixing Session mit @thomas-heinrich und @taask77. "
        "Kontakt: radio@example.com. "
        "[Profil @resident](https://soundcloud.com/resident)"
    )
    rendered = module.text_paragraphs(value)
    assert 'href="https://soundcloud.com/thomas-heinrich"' in rendered
    assert 'href="https://soundcloud.com/taask77"' in rendered
    assert "@thomas-heinrich ↗</a>" in rendered
    assert "@taask77 ↗</a>" in rendered
    assert "radio@example.com" in rendered
    assert 'href="https://soundcloud.com/example"' not in rendered
    assert rendered.count('href="https://soundcloud.com/resident"') == 1


def test_social_card_uses_current_hero_artwork():
    site = {
        "name": "sounds of electronic art",
        "description_de": "Elektronische Musik, Radio und Klubkultur aus Leipzig.",
    }
    with tempfile.TemporaryDirectory() as tmp:
        target = Path(tmp) / "social-card.png"
        module.write_social_card("site", {}, site, target)
        with Image.open(target) as card:
            assert card.size == module.SOCIAL_CARD_SIZE
            hero = module.social_card_hero()
            x, y = module.SOCIAL_CARD_HERO_POSITION
            centre = module.SOCIAL_CARD_HERO_SIZE // 2
            assert card.getpixel((x + centre, y + centre)) == hero.getpixel((centre, centre))


def test_detail_description_falls_back_after_url_filtering():
    item = {"soundcloud_description": "https://example.com"}
    site = {
        "name": "sounds of electronic art",
        "description_de": "Elektronische Musik, Radio und Klubkultur aus Leipzig.",
    }
    assert module.detail_description(item, site) == site["description_de"]


def test_soundcloud_tracklist_is_extracted_from_description():
    value = (
        "Ein kurzer Hinweis.\n\n"
        "Tracklist:\n\n"
        "Swayzak - Annadub\n"
        "Delano Smith, Brian Kage - Keep 'em Movin'\n\n"
        "Danke fürs Zuhören."
    )
    prose, tracks = module.extract_soundcloud_tracklist(value)
    assert prose == "Ein kurzer Hinweis.\n\nDanke fürs Zuhören."
    assert tracks == [
        {"artist": "Swayzak", "title": "Annadub"},
        {"artist": "Delano Smith, Brian Kage", "title": "Keep 'em Movin'"},
    ]


def test_archive_load_structures_tracklist_only_description():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "content").mkdir()
        cache = {
            "episodes": [{
                "episode_id": "2026-08-15-sofea-100-96kbps-komplette-sendung",
                "date": "2026-08-15",
                "title": "sofea 100 - 96kbps (komplette Sendung)",
                "summary": "Tracklist:",
                "description": "Tracklist:\n\nArtist A - Title A\nArtist B - Title B",
                "audio_url": "https://soundcloud.com/example/episode-100",
            }]
        }
        (root / "content" / "archive-cache.json").write_text(
            json.dumps(cache), encoding="utf-8"
        )
        previous_root = module.ROOT
        previous_artwork_dir = module.EPISODE_ARTWORK_DIR
        try:
            module.ROOT = root
            module.EPISODE_ARTWORK_DIR = root / "assets" / "images" / "episodes"
            episode = module.load_archive([])[0]
        finally:
            module.ROOT = previous_root
            module.EPISODE_ARTWORK_DIR = previous_artwork_dir

    assert episode["title_de"] == "96kbps (komplette Sendung)"
    assert episode["soundcloud_description"] == ""
    assert episode["summary_de"] == ""
    assert episode["tracklist"] == [
        {"artist": "Artist A", "title": "Title A"},
        {"artist": "Artist B", "title": "Title B"},
    ]


def test_archive_title_cleanup_preserves_non_date_parentheses():
    assert (
        module.clean_archive_title(
            "sofea #100 - 96kbps (komplette Sendung) (2026-08-15)"
        )
        == "96kbps (komplette Sendung)"
    )


def test_archive_detail_header_includes_episode_number():
    html = module.archive_detail_inner(
        {
            "date": "2026-08-15",
            "episode_number": 100,
            "title_de": "96kbps (komplette Sendung)",
            "title_en": "96kbps (complete broadcast)",
        },
        {"name": "sounds of electronic art"},
        "",
        "h2",
        "episode-100-heading",
    )
    assert 'data-de="Sendung #100"' in html
    assert 'data-en="Broadcast #100"' in html


if __name__ == "__main__":
    test_archive_text_priority()
    print("PASS test_archive_text_priority")
    test_markdown_links_are_safe_and_cards_stay_clean()
    print("PASS test_markdown_links_are_safe_and_cards_stay_clean")
    test_detail_description_falls_back_after_url_filtering()
    print("PASS test_detail_description_falls_back_after_url_filtering")
