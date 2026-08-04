#!/usr/bin/env python3
"""Normalize legacy string lists in content/episodes.json for Pages CMS.

Pages CMS can edit repeatable object fields reliably when each list item has the
same shape. Older sofea entries may use plain strings in music_presentations or
tracklist. This script converts those strings to objects while preserving all
other data.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PATH = ROOT / "content" / "episodes.json"
SEPARATOR = re.compile(r"\s+[—–-]\s+")


def split_credit(value: str) -> tuple[str, str]:
    parts = SEPARATOR.split(value.strip(), maxsplit=1)
    if len(parts) == 2:
        return parts[0].strip(), parts[1].strip()
    return "", value.strip()


def normalize_item(item: Any) -> tuple[Any, bool]:
    if not isinstance(item, str):
        return item, False
    artist, title = split_credit(item)
    normalized: dict[str, str] = {"title": title}
    if artist:
        normalized = {"artist": artist, "title": title}
    return normalized, True


def normalize_episode(episode: dict[str, Any]) -> int:
    changed = 0
    for field in ("music_presentations", "tracklist"):
        values = episode.get(field)
        if not isinstance(values, list):
            continue
        normalized = []
        for item in values:
            new_item, did_change = normalize_item(item)
            normalized.append(new_item)
            changed += int(did_change)
        episode[field] = normalized
    return changed


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Convert legacy string list items in episodes.json to object items."
    )
    parser.add_argument("path", nargs="?", type=Path, default=DEFAULT_PATH)
    parser.add_argument(
        "--write",
        action="store_true",
        help="Write the normalized JSON back to disk. Without this flag only report changes.",
    )
    args = parser.parse_args()

    path = args.path.resolve()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        print(f"ERROR: Could not read {path}: {error}")
        return 1
    if not isinstance(data, list):
        print(f"ERROR: {path} must contain a top-level JSON array")
        return 1

    changed = 0
    for episode in data:
        if isinstance(episode, dict):
            changed += normalize_episode(episode)

    if not changed:
        print("No legacy string entries found; episodes.json is already Pages-CMS-friendly.")
        return 0

    if not args.write:
        print(
            f"Would convert {changed} string list item(s). "
            "Run again with --write after committing or backing up the file."
        )
        return 0

    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    try:
        display_path = path.relative_to(ROOT)
    except ValueError:
        display_path = path
    print(f"Converted {changed} string list item(s) in {display_path}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
