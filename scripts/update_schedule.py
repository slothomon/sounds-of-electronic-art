#!/usr/bin/env python3
from __future__ import annotations

import calendar
import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
SITE_PATH = ROOT / "content" / "site.json"
UPCOMING_PATH = ROOT / "content" / "upcoming-broadcasts.json"
BERLIN_TZ = ZoneInfo("Europe/Berlin")


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json_if_changed(path: Path, value) -> bool:
    rendered = json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    if path.exists() and path.read_text(encoding="utf-8") == rendered:
        return False
    path.write_text(rendered, encoding="utf-8")
    return True


def parse_local(value: str) -> datetime:
    parsed = datetime.fromisoformat(str(value))
    if parsed.tzinfo is not None:
        raise ValueError(f"broadcast schedule dates must be local Leipzig time without an offset: {value}")
    return parsed.replace(tzinfo=BERLIN_TZ)


def add_months(value: datetime, months: int) -> datetime:
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return value.replace(year=year, month=month, day=day)


def normalize_editorial_title(value: object, site_name: str, short_name: str) -> str:
    title = " ".join(str(value or "").split())
    if not title:
        return site_name
    names = [name for name in (site_name, short_name) if name]
    if names:
        prefix = "|".join(re.escape(name) for name in sorted(names, key=len, reverse=True))
        match = re.match(rf"^(?:{prefix})\s*#\s*\d+\s*[-–—:]\s*(.+)$", title, flags=re.IGNORECASE)
        if match:
            title = match.group(1).strip()
        elif re.match(rf"^(?:{prefix})\s*#\s*\d+\s*$", title, flags=re.IGNORECASE):
            return site_name
    folded = title.casefold().strip(" .")
    if folded in {"tba", "t.b.a", "to be announced"}:
        return site_name
    return title


def regular_slot_id(slot: datetime) -> str:
    return f"broadcast-{slot.date().isoformat()}"


def is_regular_slot_date(candidate, anchor, interval_days: int) -> bool:
    delta = (candidate - anchor.date()).days
    return delta >= 0 and delta % interval_days == 0


def maintain_schedule(site: dict, existing: list[dict], now: datetime | None = None) -> list[dict]:
    config = site.get("broadcast_schedule")
    if not isinstance(config, dict):
        raise ValueError("content/site.json is missing broadcast_schedule configuration")

    anchor = parse_local(str(config["anchor"]))
    first_episode_number = int(config["first_episode_number"])
    interval_weeks = int(config.get("interval_weeks", 8))
    horizon_months = int(config.get("horizon_months", 12))
    if interval_weeks <= 0 or horizon_months <= 0:
        raise ValueError("broadcast_schedule interval_weeks and horizon_months must be positive")

    skip_dates = {str(value) for value in config.get("skip_dates", [])}
    overrides = config.get("date_overrides", {}) or {}
    if not isinstance(overrides, dict):
        raise ValueError("broadcast_schedule.date_overrides must be an object")
    overlap = skip_dates.intersection(overrides)
    if overlap:
        raise ValueError("a broadcast slot cannot be both skipped and overridden: " + ", ".join(sorted(overlap)))

    now = now or datetime.now(BERLIN_TZ)
    if now.tzinfo is None:
        now = now.replace(tzinfo=BERLIN_TZ)
    else:
        now = now.astimezone(BERLIN_TZ)
    horizon = add_months(now, horizon_months)
    interval = timedelta(weeks=interval_weeks)
    interval_days = interval.days
    site_name = str(site.get("name") or "sounds of electronic art")
    short_name = str(site.get("short_name") or "sofea")
    default_de = str(config.get("details_de") or "Drei Stunden elektronische Musik. Live auf Radio Blau.")
    default_en = str(config.get("details_en") or "Three hours of electronic music. Live on Radio Blau.")

    by_id = {str(entry.get("id")): entry for entry in existing if isinstance(entry, dict) and entry.get("id")}
    by_date = {str(entry.get("date")): entry for entry in existing if isinstance(entry, dict) and entry.get("date")}
    consumed: set[int] = set()
    result: list[dict] = []
    managed_ids: set[str] = set()

    slot = anchor
    index = 0
    while slot <= horizon:
        slot_key = slot.date().isoformat()
        stable_id = regular_slot_id(slot)
        managed_ids.add(stable_id)
        episode_number = first_episode_number + index
        actual = parse_local(str(overrides[slot_key])) if slot_key in overrides else slot
        if slot_key not in skip_dates and actual + timedelta(hours=3) > now:
            current = by_id.get(stable_id) or by_date.get(slot.replace(tzinfo=None).isoformat(timespec="seconds"))
            if current is None:
                current = by_date.get(actual.replace(tzinfo=None).isoformat(timespec="seconds"))
            entry = dict(current or {})
            if current is not None:
                consumed.add(id(current))
            entry["id"] = stable_id
            entry["date"] = actual.replace(tzinfo=None).isoformat(timespec="seconds")
            entry["episode_number"] = episode_number
            entry["title_de"] = normalize_editorial_title(entry.get("title_de"), site_name, short_name)
            entry["title_en"] = normalize_editorial_title(entry.get("title_en"), site_name, short_name)
            entry["details_de"] = str(entry.get("details_de") or default_de)
            entry["details_en"] = str(entry.get("details_en") or default_en)
            entry.pop("label_de", None)
            entry.pop("label_en", None)
            result.append(entry)
        slot += interval
        index += 1

    skipped_ids = {f"broadcast-{value}" for value in skip_dates}
    for entry in existing:
        if not isinstance(entry, dict) or id(entry) in consumed:
            continue
        entry_id = str(entry.get("id") or "")
        date_value = str(entry.get("date") or "")
        date_key = date_value[:10]
        if entry_id in skipped_ids or (not entry_id and date_key in skip_dates):
            continue
        if entry_id.startswith("broadcast-"):
            try:
                slot_date = datetime.fromisoformat(entry_id.removeprefix("broadcast-")).date()
            except ValueError:
                slot_date = None
            if slot_date is not None and is_regular_slot_date(slot_date, anchor, interval_days):
                if entry_id not in managed_ids or parse_local(date_value) + timedelta(hours=3) <= now:
                    continue
        result.append(dict(entry))

    result.sort(key=lambda entry: parse_local(str(entry["date"])))
    return result


def main() -> int:
    site = read_json(SITE_PATH)
    existing = read_json(UPCOMING_PATH)
    if not isinstance(existing, list):
        raise ValueError("content/upcoming-broadcasts.json must contain a top-level JSON array")
    updated = maintain_schedule(site, existing)
    changed = write_json_if_changed(UPCOMING_PATH, updated)
    if changed:
        print(f"Updated {UPCOMING_PATH.relative_to(ROOT)} with {len(updated)} upcoming broadcast(s).")
    else:
        print(f"{UPCOMING_PATH.relative_to(ROOT)} is already up to date ({len(updated)} broadcast(s)).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
