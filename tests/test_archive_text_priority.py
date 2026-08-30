#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
from pathlib import Path

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


if __name__ == "__main__":
    test_archive_text_priority()
    print("PASS test_archive_text_priority")
    test_markdown_links_are_safe_and_cards_stay_clean()
    print("PASS test_markdown_links_are_safe_and_cards_stay_clean")
