#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import unicodedata
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

BERLIN_TZ = ZoneInfo("Europe/Berlin")
DEFAULT_BROADCAST_HOURS = 3
ARCHIVE_FIELDS = (
    "title_de",
    "title_en",
    "details_de",
    "details_en",
    "image",
    "social_image",
    "links",
    "music_presentations",
    "tracklist",
)


def slugify(value: object) -> str:
    text = str(value or "").lower()
    for source, target in {"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"}.items():
        text = text.replace(source, target)
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")[:80] or "sendung"


def parse_local(value: object) -> datetime:
    parsed = datetime.fromisoformat(str(value))
    # The project treats the wall-clock value in upcoming JSON as Leipzig time.
    return parsed.replace(tzinfo=BERLIN_TZ)


def broadcast_end(item: dict) -> datetime:
    start = parse_local(item["date"])
    if item.get("end"):
        return parse_local(item["end"])
    return start + timedelta(hours=DEFAULT_BROADCAST_HOURS)


def episode_number_value(value: object) -> int | None:
    if value in (None, ""):
        return None
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def read_json_list(path: Path) -> list[dict]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, list):
        raise ValueError(f"{path} must contain a top-level JSON array")
    if not all(isinstance(item, dict) for item in value):
        raise ValueError(f"{path} must contain JSON objects only")
    return value


def write_json_list(path: Path, value: list[dict]) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def archive_match_key(item: dict) -> tuple[str, str]:
    date_value = str(item.get("date") or "")[:10]
    title = str(item.get("title_de") or item.get("title") or "")
    return date_value, slugify(title)


def archive_episode_id(item: dict) -> str:
    date_value, title_slug = archive_match_key(item)
    return f"{date_value or 'undated'}-{title_slug}"


def canonical_number_maps(rows: list[dict]) -> tuple[dict[str, int], dict[int, str]]:
    by_date: dict[str, int] = {}
    by_number: dict[int, str] = {}
    for index, row in enumerate(rows, start=1):
        date_value = str(row.get("date") or "")[:10]
        number = episode_number_value(row.get("episode_number"))
        if not date_value or number is None:
            raise ValueError(f"episode-numbers.json entry {index} is missing date or episode_number")
        if date_value in by_date and by_date[date_value] != number:
            raise ValueError(f"duplicate canonical date with conflicting numbers: {date_value}")
        if number in by_number and by_number[number] != date_value:
            raise ValueError(f"duplicate canonical episode number #{number}")
        by_date[date_value] = number
        by_number[number] = date_value
    return by_date, by_number


def assign_upcoming_numbers(
    broadcasts: list[dict],
    canonical_by_date: dict[str, int],
    canonical_by_number: dict[int, str],
) -> dict[int, int]:
    used_numbers = dict(canonical_by_number)
    next_number = max(used_numbers, default=0) + 1
    assignments: dict[int, int] = {}

    ordered = sorted(enumerate(broadcasts), key=lambda pair: parse_local(pair[1]["date"]))
    for original_index, item in ordered:
        date_value = parse_local(item["date"]).date().isoformat()
        explicit = episode_number_value(item.get("episode_number"))
        canonical = canonical_by_date.get(date_value)

        if canonical is not None:
            if explicit is not None and explicit != canonical:
                raise ValueError(
                    f"broadcast {date_value} uses episode_number #{explicit}, "
                    f"but canonical data says #{canonical}"
                )
            number = canonical
        elif explicit is not None:
            conflicting_date = used_numbers.get(explicit)
            if conflicting_date and conflicting_date != date_value:
                raise ValueError(
                    f"broadcast {date_value} reuses episode_number #{explicit} "
                    f"already assigned to {conflicting_date}"
                )
            number = explicit
        else:
            while next_number in used_numbers:
                next_number += 1
            number = next_number

        assignments[original_index] = number
        used_numbers[number] = date_value
        next_number = max(next_number, number + 1)

    return assignments


def archive_from_broadcast(item: dict, number: int) -> dict:
    date_value = parse_local(item["date"]).date().isoformat()
    title_de = str(item.get("title_de") or "").strip()
    title_en = str(item.get("title_en") or title_de).strip()
    if not title_de:
        raise ValueError(f"broadcast {date_value} is missing title_de")

    archived: dict = {
        "date": date_value,
        "episode_number": number,
        "title_de": title_de,
        "title_en": title_en,
        "episode_id": f"{date_value}-{slugify(title_de)}",
    }
    for key in ARCHIVE_FIELDS:
        if key in {"title_de", "title_en"}:
            continue
        value = item.get(key)
        if value not in (None, "", []):
            archived[key] = value
    # audio_url is intentionally not copied or synthesized. It is added later
    # only when a real recording exists in the SoundCloud archive/cache.
    return archived


def merge_archived_metadata(existing: dict, incoming: dict) -> bool:
    """Fill missing editorial fields while preserving existing archive data/audio."""
    changed = False
    for key, value in incoming.items():
        if key == "audio_url":
            continue
        if existing.get(key) in (None, "", []):
            existing[key] = value
            changed = True
    return changed


def resolve_now(value: str | None) -> datetime:
    if not value:
        return datetime.now(BERLIN_TZ)
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=BERLIN_TZ)
    return parsed.astimezone(BERLIN_TZ)


def migrate(root: Path, now: datetime, dry_run: bool = False) -> int:
    content = root / "content"
    upcoming_path = content / "upcoming-broadcasts.json"
    episodes_path = content / "episodes.json"
    numbers_path = content / "episode-numbers.json"

    broadcasts = read_json_list(upcoming_path)
    episodes = read_json_list(episodes_path)
    numbers = read_json_list(numbers_path)

    canonical_by_date, canonical_by_number = canonical_number_maps(numbers)
    assignments = assign_upcoming_numbers(broadcasts, canonical_by_date, canonical_by_number)

    archive_by_id = {str(item.get("episode_id") or archive_episode_id(item)): item for item in episodes}
    archive_by_key = {archive_match_key(item): item for item in episodes}

    remaining: list[dict] = []
    archived_count = 0
    changed = False

    for index, broadcast in enumerate(broadcasts):
        if broadcast_end(broadcast) > now:
            remaining.append(broadcast)
            continue

        number = assignments[index]
        incoming = archive_from_broadcast(broadcast, number)
        identity = incoming["episode_id"]
        key = archive_match_key(incoming)
        existing = archive_by_id.get(identity) or archive_by_key.get(key)

        if existing is None:
            episodes.append(incoming)
            archive_by_id[identity] = incoming
            archive_by_key[key] = incoming
            changed = True
        else:
            changed = merge_archived_metadata(existing, incoming) or changed
            existing_number = episode_number_value(existing.get("episode_number"))
            if existing_number is not None and existing_number != number:
                raise ValueError(
                    f"archive entry {identity} has episode_number #{existing_number}, expected #{number}"
                )

        date_value = incoming["date"]
        canonical = canonical_by_date.get(date_value)
        if canonical is not None and canonical != number:
            raise ValueError(
                f"canonical date {date_value} has episode_number #{canonical}, expected #{number}"
            )
        conflicting_date = canonical_by_number.get(number)
        if conflicting_date and conflicting_date != date_value:
            raise ValueError(
                f"episode_number #{number} is already assigned to {conflicting_date}, not {date_value}"
            )
        if canonical is None:
            row = {"date": date_value, "episode_number": number}
            numbers.append(row)
            canonical_by_date[date_value] = number
            canonical_by_number[number] = date_value
            changed = True

        archived_count += 1
        changed = True  # Removal from upcoming-broadcasts.json.
        print(f"Archived broadcast #{number}: {date_value} - {incoming['title_de']}")

    if not archived_count:
        print("No completed broadcasts to archive.")
        return 0

    episodes.sort(
        key=lambda item: (str(item.get("date") or "")[:10], episode_number_value(item.get("episode_number")) or 0),
        reverse=True,
    )
    numbers.sort(key=lambda item: episode_number_value(item.get("episode_number")) or 0, reverse=True)
    remaining.sort(key=lambda item: parse_local(item["date"]))

    if dry_run:
        print(f"Dry run: would archive {archived_count} broadcast(s); no files written.")
        return archived_count

    if changed:
        write_json_list(episodes_path, episodes)
        write_json_list(numbers_path, numbers)
        write_json_list(upcoming_path, remaining)
        print(f"Archived {archived_count} broadcast(s).")
    return archived_count


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Move completed SOFEA broadcasts from upcoming data into the permanent archive."
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="Repository root (default: parent directory of scripts/).",
    )
    parser.add_argument(
        "--now",
        help="Override current time for testing (ISO 8601; naive values are Europe/Berlin).",
    )
    parser.add_argument("--dry-run", action="store_true", help="Report changes without writing files.")
    args = parser.parse_args()

    try:
        migrate(args.root.resolve(), resolve_now(args.now), args.dry_run)
    except (OSError, json.JSONDecodeError, ValueError) as error:
        print(f"ERROR: {error}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
