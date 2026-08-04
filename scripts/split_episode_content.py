#!/usr/bin/env python3
"""Split the legacy mixed episodes array into three focused Pages CMS files."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "content"
SOURCE = CONTENT / "episodes.json"
BROADCASTS = CONTENT / "upcoming-broadcasts.json"
EVENTS = CONTENT / "upcoming-events.json"


def read_list(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, list):
        raise ValueError(f"{path.relative_to(ROOT)} must contain a JSON array")
    return [dict(item) for item in value if isinstance(item, dict)]


def local_wall_clock(value: Any) -> str:
    """Keep the entered Leipzig wall-clock time and remove its UTC offset."""
    text = str(value or "").strip()
    if not text:
        return ""
    match = re.match(r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2})(?::(\d{2}))?", text)
    if not match:
        return text
    return f"{match.group(1)}:{match.group(2) or '00'}"


def clean_archive_title(value: Any) -> str:
    title = " ".join(str(value or "").split())
    title = re.sub(r"\s*\(\s*20\d{2}[-_.]\d{1,2}[-_.]\d{1,2}\s*\)\s*$", "", title)
    title = re.sub(r"\s+20\d{2}[-_.]\d{1,2}[-_.]\d{1,2}\s*$", "", title)
    return title.strip()


def text_value(item: dict[str, Any], language: str) -> str:
    value = item.get(f"details_{language}") or item.get(f"summary_{language}") or ""
    if not value and language == "en":
        value = item.get("details_de") or item.get("summary_de") or ""
    return str(value).strip()


def compact_links(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    rows = []
    for entry in value:
        if not isinstance(entry, dict) or not entry.get("url"):
            continue
        row = {
            "label_de": str(entry.get("label_de") or entry.get("label") or "Details"),
            "label_en": str(entry.get("label_en") or entry.get("label") or entry.get("label_de") or "Details"),
            "url": str(entry["url"]),
        }
        if entry.get("primary"):
            row["primary"] = True
        rows.append(row)
    return rows


def migrate_broadcast(item: dict[str, Any]) -> dict[str, Any]:
    row: dict[str, Any] = {
        "date": local_wall_clock(item.get("date")),
        "title_de": str(item.get("title_de") or item.get("title") or "").strip(),
        "title_en": str(item.get("title_en") or item.get("title_de") or item.get("title") or "").strip(),
        "details_de": text_value(item, "de"),
        "details_en": text_value(item, "en"),
    }
    if item.get("image"):
        row["image"] = item["image"]
    links = compact_links(item.get("links"))
    if links:
        row["links"] = links
    return {key: value for key, value in row.items() if value not in (None, "", [])}


def migrate_event(item: dict[str, Any]) -> dict[str, Any]:
    row = migrate_broadcast(item)
    end = local_wall_clock(item.get("end"))
    if end:
        row["end"] = end
    location = (
        item.get("location")
        or item.get("location_de")
        or item.get("venue_name")
        or ""
    )
    if location:
        row["location"] = str(location).strip()
    return row


def migrate_archive(item: dict[str, Any]) -> dict[str, Any]:
    title_de = clean_archive_title(item.get("title_de") or item.get("title") or "")
    title_en = clean_archive_title(item.get("title_en") or title_de)
    row: dict[str, Any] = {
        "date": str(item.get("date") or "")[:10],
        "title_de": title_de,
        "title_en": title_en or title_de,
        "audio_url": str(item.get("audio_url") or "").strip(),
    }
    for key in ("updated_at", "image"):
        if item.get(key):
            row[key] = item[key]
    details_de = text_value(item, "de")
    details_en = text_value(item, "en")
    if details_de:
        row["details_de"] = details_de
    if details_en:
        row["details_en"] = details_en
    for key in ("music_presentations", "tracklist"):
        if isinstance(item.get(key), list) and item[key]:
            row[key] = item[key]
    return {key: value for key, value in row.items() if value not in (None, "", [])}


def identity(item: dict[str, Any]) -> str:
    return str(item.get("audio_url") or f"{item.get('date')}|{item.get('title_de')}").rstrip("/")


def merge_unique(existing: list[dict[str, Any]], incoming: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result = list(existing)
    positions = {identity(item): index for index, item in enumerate(result)}
    for item in incoming:
        key = identity(item)
        if key in positions:
            result[positions[key]] = item
        else:
            positions[key] = len(result)
            result.append(item)
    return result


def write_json(path: Path, value: list[dict[str, Any]]) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="Write the split files. Without this option only show a preview.")
    args = parser.parse_args()

    legacy = read_list(SOURCE)
    existing_broadcasts = read_list(BROADCASTS)
    existing_events = read_list(EVENTS)

    broadcasts = []
    events = []
    archive = []
    for item in legacy:
        if item.get("status") == "upcoming":
            if str(item.get("type") or "broadcast").lower() == "event":
                events.append(migrate_event(item))
            else:
                broadcasts.append(migrate_broadcast(item))
        else:
            # Local archive enrichment is only useful when it can be matched to
            # a SoundCloud recording. Old schedule-only placeholders are omitted.
            if item.get("audio_url"):
                archive.append(migrate_archive(item))

    broadcasts = merge_unique(existing_broadcasts, broadcasts)
    events = merge_unique(existing_events, events)

    print(f"Archive entries: {len(archive)}")
    print(f"Upcoming broadcasts: {len(broadcasts)}")
    print(f"Upcoming events: {len(events)}")
    print("Upcoming times will be stored without a UTC offset, e.g. 2026-08-29T21:00:00.")

    if not args.write:
        print("Dry run only. Run again with --write to update the files.")
        return

    write_json(SOURCE, archive)
    write_json(BROADCASTS, broadcasts)
    write_json(EVENTS, events)
    print("Wrote content/episodes.json, content/upcoming-broadcasts.json and content/upcoming-events.json.")


if __name__ == "__main__":
    main()
