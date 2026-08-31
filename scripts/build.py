#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import html
import json
import os
import re
import unicodedata
import shutil
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from PIL import Image, ImageDraw, ImageFont
from urllib.parse import quote, urlparse

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "public"
EPISODE_ARTWORK_DIR = ROOT / "assets" / "images" / "episodes"
ARTWORK_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp")
RESPONSIVE_ARTWORK_WIDTHS = (320, 640, 960, 1280)
RESPONSIVE_ARTWORK_DIR = Path("assets/images/generated/episodes")
MONTHS_DE = ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September", "Oktober", "November", "Dezember"]
MONTHS_EN = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
WEEKDAYS_DE = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]
WEEKDAYS_EN = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
BERLIN_TZ = ZoneInfo("Europe/Berlin")


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def read_json_list(path: Path) -> list[dict]:
    """Read an optional top-level JSON array."""
    if not path.exists():
        return []
    value = read_json(path)
    if not isinstance(value, list):
        raise ValueError(f"{path.relative_to(ROOT)} must contain a top-level JSON array")
    return [item for item in value if isinstance(item, dict)]


def asset_bundle_version(paths: list[Path]) -> str:
    """Return a stable short fingerprint for browser-cached CSS/JS assets."""
    digest = hashlib.sha256()
    for path in paths:
        digest.update(path.relative_to(ROOT).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()[:12]


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def slugify(value: str) -> str:
    text = str(value or "").lower()
    for source, target in {"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"}.items():
        text = text.replace(source, target)
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")[:80] or "sendung"


MARKDOWN_LINK_RE = re.compile(r"\[([^\]\n]+)\]\((https?://[^\s)]+)\)")
PLAIN_URL_RE = re.compile(r"https?://\S+", re.IGNORECASE)


def plain_editorial_text(value: object) -> str:
    """Return prose suitable for cards/meta descriptions without raw link markup."""
    rows: list[str] = []
    for raw_line in str(value or "").replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        line = raw_line.strip()
        if not line or line.casefold() in {"soundcloud", "soundcloud:"}:
            continue
        if MARKDOWN_LINK_RE.fullmatch(line) or PLAIN_URL_RE.fullmatch(line):
            continue
        line = MARKDOWN_LINK_RE.sub(lambda match: match.group(1), line)
        rows.append(line)
    return " ".join(" ".join(rows).split())


def card_excerpt(value: str, limit: int = 100) -> str:
    """Return a compact card excerpt while preserving the full detail text."""
    normalized = plain_editorial_text(value)
    if len(normalized) <= limit:
        return normalized
    shortened = normalized[: limit + 1].rsplit(" ", 1)[0].rstrip(" .,;:–—-")
    return (shortened or normalized[:limit].rstrip()) + "…"

def content_text(item: dict, language: str = "de") -> str:
    """Resolve archive prose by editorial priority.

    Priority: post-show text -> legacy manual details -> SoundCloud description
    -> legacy SoundCloud summary -> announcement. English falls back to German
    within each editorial layer.
    """
    fallback_language = "de" if language == "en" else None

    for field in ("post_text", "details"):
        value = str(item.get(f"{field}_{language}") or "").strip()
        if not value and fallback_language:
            value = str(item.get(f"{field}_{fallback_language}") or "").strip()
        if value:
            return value

    soundcloud = str(
        item.get(f"soundcloud_description_{language}")
        or item.get("soundcloud_description")
        or item.get(f"summary_{language}")
        or item.get("summary")
        or ""
    ).strip()
    if soundcloud:
        return soundcloud

    announcement = str(item.get(f"announcement_{language}") or "").strip()
    if not announcement and fallback_language:
        announcement = str(item.get(f"announcement_{fallback_language}") or "").strip()
    return announcement

def episode_number_value(item: dict) -> int | None:
    """Return an upcoming broadcast episode number as an integer when present."""
    value = item.get("episode_number")
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None

def upcoming_label(item: dict, language: str = "de") -> str:
    """Return the visible label without storing removed label_* fields on broadcasts."""
    item_type = str(item.get("type") or "broadcast").lower()
    if item_type == "broadcast":
        number = episode_number_value(item)
        base = "Sendung" if language == "de" else "Broadcast"
        return f"{base} #{number}" if number is not None else base
    fallback = "Veranstaltung" if language == "de" else "Event"
    return str(item.get(f"label_{language}") or fallback)


EPISODE_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{2,95}$")


def derived_episode_id(item: dict) -> str:
    """Build a deterministic local identifier without depending on a source URL."""
    date_part = str(item.get("date") or "")[:10] or "undated"
    title = clean_archive_title(item.get("title_de") or item.get("title") or "sendung")
    return f"{date_part}-{slugify(title)}"


def episode_id_value(item: dict) -> str:
    """Return an explicit local ID or the deterministic compatibility fallback."""
    explicit = str(item.get("episode_id") or "").strip().lower()
    return explicit if EPISODE_ID_RE.fullmatch(explicit) else derived_episode_id(item)


def episode_label(item: dict, language: str = "de") -> str:
    number = episode_number_value(item)
    if number is None:
        return "Sendung" if language == "de" else "Broadcast"
    return f"Sendung #{number}" if language == "de" else f"Broadcast #{number}"


def duration_label(item: dict) -> str:
    """Return a human-readable duration from cache metadata."""
    duration_ms = item.get("duration_ms")
    try:
        if duration_ms not in (None, ""):
            total_seconds = max(0, round(float(duration_ms) / 1000))
            hours, remainder = divmod(total_seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            return f"{hours}:{minutes:02d}:{seconds:02d}" if hours else f"{minutes}:{seconds:02d}"
    except (TypeError, ValueError):
        pass
    return str(item.get("duration") or "").strip()


def featured_audio_items(selection: list[dict], archive: list[dict]) -> list[dict]:
    """Resolve the editorial Hören selection by local episode ID."""
    if not selection:
        raise ValueError("content/listen.json must contain at least one entry")
    archive_by_id = {episode_id_value(item): item for item in archive}
    resolved: list[dict] = []
    missing: list[str] = []
    unavailable: list[str] = []
    for row in selection[:5]:
        episode_id = str(row.get("episode_id") or "").strip().lower()
        if not episode_id:
            continue
        item = archive_by_id.get(episode_id)
        if item is None:
            missing.append(episode_id)
            continue
        audio_url = str(item.get("audio_url") or "").strip()
        if not audio_url:
            unavailable.append(episode_id)
            continue
        title_de = clean_archive_title(item.get("title_de") or item.get("title") or "")
        title_en = clean_archive_title(item.get("title_en") or title_de)
        resolved.append({
            "episode_id": episode_id,
            "title_de": title_de,
            "title_en": title_en,
            "subtitle_de": content_text(item, "de"),
            "subtitle_en": content_text(item, "en"),
            "duration": duration_label(item),
            "url": audio_url,
        })
    if missing:
        raise ValueError(
            "episode_id values from content/listen.json not found in the archive: " + ", ".join(missing)
        )
    if unavailable:
        raise ValueError(
            "episode_id values from content/listen.json have no audio_url: " + ", ".join(unavailable)
        )
    if not resolved:
        raise ValueError("content/listen.json did not resolve to any archive entries")
    return resolved

def clean_archive_title(value: object) -> str:
    """Remove a redundant trailing SoundCloud date while preserving other notes."""
    title = " ".join(str(value or "").split())
    title = re.sub(r"\s*\(\s*(20\d{2})[-_.](\d{1,2})[-_.](\d{1,2})\s*\)\s*$", "", title)
    title = re.sub(r"\s+(20\d{2})[-_.](\d{1,2})[-_.](\d{1,2})\s*$", "", title)
    return title.strip()


def parse_date(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def parse_upcoming_date(value: str) -> datetime:
    """Interpret upcoming dates as local Leipzig time.

    The wall-clock time is authoritative, so an accidentally stale CET/CEST
    offset in the JSON cannot shift a downloaded calendar event by one hour.
    """
    parsed = datetime.fromisoformat(value)
    return parsed.replace(tzinfo=BERLIN_TZ)


def render(template: str, values: dict[str, str]) -> str:
    for key, value in values.items():
        template = template.replace("{{ " + key + " }}", value)
    unresolved = sorted(set(re.findall(r"\{\{\s*[A-Za-z0-9_]+\s*\}\}", template)))
    if unresolved:
        raise ValueError("Unresolved template placeholders: " + ", ".join(unresolved))
    return template


def soundcloud_embed(url: str) -> str:
    return (
        "https://w.soundcloud.com/player/?url=" + quote(url, safe="")
        + "&color=%23ef9a55&auto_play=false&hide_related=true"
        + "&show_comments=true&show_user=true&show_reposts=true&show_playcount=true&show_teaser=false"
    )


def date_long(value: datetime, language: str) -> str:
    if language == "de":
        return f"{WEEKDAYS_DE[value.weekday()]}, {value.day}. {MONTHS_DE[value.month - 1]} {value.year}"
    return f"{WEEKDAYS_EN[value.weekday()]}, {value.day} {MONTHS_EN[value.month - 1]} {value.year}"


def hour_range_clock(start: datetime, end: datetime, language: str = "de") -> str:
    """Return a compact clock range using an en dash without spaces.

    The visible form is ``21:00–00:00``. Keeping the whole range compact
    follows the preferred German notation and avoids ambiguous wrapping.
    """
    return f"{start.strftime('%H:%M')}–{end.strftime('%H:%M')}"


def broadcast_guest_title(item: dict, site: dict, language: str = "de") -> str:
    """Return only the editorial guest/title part of a broadcast title."""
    title = str(item.get(f"title_{language}") or item.get("title_de") or "").strip()
    if not title:
        return ""
    site_name = str(site.get("name") or "sounds of electronic art").strip()
    short_name = str(site.get("short_name") or "sofea").strip()
    names = [name for name in (site_name, short_name) if name]
    if names:
        prefix = "|".join(re.escape(name) for name in sorted(names, key=len, reverse=True))
        match = re.match(rf"^(?:{prefix})\s*#\s*\d+\s*[-–—:]\s*(.+)$", title, flags=re.IGNORECASE)
        if match:
            title = match.group(1).strip()
        elif re.match(rf"^(?:{prefix})\s*#\s*\d+\s*$", title, flags=re.IGNORECASE):
            return ""
    folded = title.casefold().strip(" .")
    placeholders = {"tba", "t.b.a", "to be announced", site_name.casefold(), short_name.casefold()}
    return "" if folded in placeholders else title

def calendar_title(item: dict, site: dict) -> str:
    item_type = str(item.get("type") or "broadcast").lower()
    if item_type != "broadcast":
        return str(item.get("title_de") or site.get("name") or "sofea").strip()

    number = item.get("episode_number")
    base = f"sofea #{number}" if number not in (None, "") else "sofea"
    guest = str(item.get("title_de") or "").strip()

    if not guest or guest.casefold() in {"sounds of electronic art", "sofea", "tba"}:
        return base

    legacy = re.match(
        r"^\s*(?:sounds of electronic art|sofea)\s*#?\s*\d+\s*[-–—:]\s*(.+?)\s*$",
        guest,
        flags=re.IGNORECASE,
    )
    if legacy:
        guest = legacy.group(1).strip()

    return f"{base} - {guest}" if guest else base

def calendar_filename(item: dict, site: dict) -> str:
    stable_id = str(item.get("id") or "").strip()
    if stable_id:
        return f"{slugify(stable_id)}.ics"
    start = parse_upcoming_date(item["date"])
    return f"{start.strftime('%Y-%m-%d')}-{slugify(calendar_title(item, site))}.ics"


def ical_escape(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace("\r\n", "\\n")
        .replace("\n", "\\n")
        .replace(";", "\\;")
        .replace(",", "\\,")
    )


def fold_ical_line(line: str, limit: int = 73) -> list[str]:
    """Fold iCalendar lines without splitting UTF-8 or short HTTP(S) URLs."""
    if limit < 4:
        raise ValueError("iCalendar fold limit must be at least 4 bytes")

    url_pattern = re.compile(r"https?://[A-Za-z0-9._~:/?#\[\]@!$&'()*+,;=%-]+")
    lines: list[str] = []
    current = ""
    current_bytes = 0
    index = 0

    while index < len(line):
        url_match = url_pattern.match(line, index)
        if url_match:
            token = url_match.group(0)
            token_bytes = len(token.encode("utf-8"))
            # Keep ordinary URLs on one physical iCalendar line. If the URL
            # itself is longer than a continuation line, fall back to normal
            # UTF-8-safe character folding below.
            if token_bytes <= limit - 1:
                if current and current_bytes + token_bytes > limit:
                    lines.append(current)
                    current = " " + token
                    current_bytes = 1 + token_bytes
                else:
                    current += token
                    current_bytes += token_bytes
                index = url_match.end()
                continue

        char = line[index]
        char_bytes = len(char.encode("utf-8"))
        if current and current_bytes + char_bytes > limit:
            lines.append(current)
            current = " " + char
            current_bytes = 1 + char_bytes
        else:
            current += char
            current_bytes += char_bytes
        index += 1

    lines.append(current)
    return lines


def calendar_event_lines(item: dict, site: dict, event_url: str, dtstamp: str) -> list[str]:
    start = parse_upcoming_date(item["date"])
    end = upcoming_end(item)
    item_type = str(item.get("type") or "broadcast").lower()
    title = calendar_title(item, site)
    summary = content_text(item, "de")
    default_location = "Radio Blau, Leipzig" if item_type == "broadcast" else ""
    location = str(item.get("location_de") or item.get("location") or default_location)
    stable_id = str(item.get("id") or "").strip()
    uid_source = stable_id or f"{start.isoformat()}|{title}"
    uid = hashlib.sha1(uid_source.encode("utf-8")).hexdigest()[:24] + "@sofea.radio"
    raw_lines = [
        "BEGIN:VEVENT",
        f"UID:{uid}",
        f"DTSTAMP:{dtstamp}",
        f"DTSTART:{start.astimezone(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        f"DTEND:{end.astimezone(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        f"SUMMARY:{ical_escape(title)}",
    ]

    stream_url = str(
        site.get("radio", {}).get("stream_url") or "https://www.radioblau.de/stream/"
    ).strip()
    calendar_footer = (
        "-----\n\n"
        "Livestream:\n"
        f"{stream_url}\n\n"
        "Radio Blau erreicht ihr auf DAB+, sowie\n"
        "UKW 99,2 MHz, 94,4 MHz & 89,2 MHz"
    )
    description = f"{summary}\n\n{calendar_footer}" if summary else calendar_footer
    raw_lines.append(f"DESCRIPTION:{ical_escape(description)}")
    if location:
        raw_lines.append(f"LOCATION:{ical_escape(location)}")

    # Keep the canonical SOFEA event/detail page as the VEVENT URL. The
    # livestream remains a separate, visible link in DESCRIPTION.
    raw_lines.extend([
        f"URL:{ical_escape(event_url)}",
        "STATUS:CONFIRMED",
        "TRANSP:OPAQUE",
        "END:VEVENT",
    ])
    return raw_lines

def calendar_event_content(item: dict, site: dict, event_url: str) -> str:
    dtstamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    raw_lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//sounds of electronic art//sofea.radio//DE",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        *calendar_event_lines(item, site, event_url, dtstamp),
        "END:VCALENDAR",
    ]
    folded = [part for line in raw_lines for part in fold_ical_line(line)]
    return "\r\n".join(folded) + "\r\n"


def calendar_feed_content(items: list[dict], site: dict, canonical_url: str) -> str:
    dtstamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    raw_lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//sounds of electronic art//sofea.radio//DE",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:sounds of electronic art",
        "X-WR-TIMEZONE:Europe/Berlin",
        "X-APPLE-CALENDAR-COLOR:#EF9A55",
        "REFRESH-INTERVAL;VALUE=DURATION:PT12H",
        "X-PUBLISHED-TTL:PT12H",
    ]
    for item in sorted(items, key=lambda entry: parse_upcoming_date(str(entry["date"]))):
        detail_url = absolute_site_url(canonical_url, detail_relative_path("upcoming", item, site))
        raw_lines.extend(calendar_event_lines(item, site, detail_url, dtstamp))
    raw_lines.append("END:VCALENDAR")
    folded = [part for line in raw_lines for part in fold_ical_line(line)]
    return "\r\n".join(folded) + "\r\n"

def upcoming_end(item: dict) -> datetime:
    start = parse_upcoming_date(str(item["date"]))
    item_type = str(item.get("type") or "broadcast").lower()
    default_hours = 3 if item_type == "broadcast" else 2
    return parse_upcoming_date(str(item["end"])) if item.get("end") else start + timedelta(hours=default_hours)

def detail_identifier(kind: str, item: dict, site: dict) -> str:
    title = str(item.get("title_de") or item.get("title") or site["name"])
    if kind == "upcoming":
        stable_id = str(item.get("id") or "").strip()
        if stable_id:
            return f"detail-upcoming-{slugify(stable_id)}"
        date_part = parse_upcoming_date(str(item["date"])).strftime("%Y-%m-%d")
        seed = f"{item.get('date')}|{title}"
    else:
        date_part = parse_date(str(item["date"])).strftime("%Y-%m-%d")
        seed = str(item.get("audio_url") or f"{item.get('date')}|{title}")
    digest = hashlib.sha1(seed.encode("utf-8")).hexdigest()[:8]
    return f"detail-{kind}-{date_part}-{slugify(title)}-{digest}"


def detail_relative_path(kind: str, item: dict, site: dict) -> str:
    title = str(item.get("title_de") or item.get("title") or site["name"])
    title_for_slug = re.sub(r"\s*\(\d{4}-\d{2}-\d{2}\)\s*$", "", title).strip()
    custom_slug = str(item.get("slug") or "").strip()
    if kind == "upcoming":
        stable_id = str(item.get("id") or "").strip()
        if stable_id:
            return f"termine/{slugify(stable_id)}/"
        date_part = parse_upcoming_date(str(item["date"])).strftime("%Y-%m-%d")
        folder = "termine"
    else:
        date_part = parse_date(str(item["date"])).strftime("%Y-%m-%d")
        folder = "sendungen"
    slug = slugify(custom_slug or title_for_slug)
    return f"{folder}/{date_part}-{slug}/"

def site_href(base_path: str, relative_path: str = "") -> str:
    root = (base_path.rstrip("/") + "/") if base_path else "/"
    return root + relative_path.lstrip("/")


def absolute_site_url(canonical_url: str, relative_path: str = "") -> str:
    return canonical_url.rstrip("/") + "/" + relative_path.lstrip("/")


def meta_excerpt(value: object, limit: int = 160) -> str:
    normalized = " ".join(str(value or "").split())
    if len(normalized) <= limit:
        return normalized
    shortened = normalized[: limit + 1].rsplit(" ", 1)[0].rstrip(" .,;:–—-")
    return (shortened or normalized[:limit].rstrip()) + "…"


def json_ld_script(data: dict) -> str:
    payload = json.dumps(data, ensure_ascii=False, indent=2).replace("</", "<\\/")
    return f'<script type="application/ld+json">\n{payload}\n</script>'


def series_id(canonical_url: str) -> str:
    return canonical_url.rstrip("/") + "/#radio-series"


def series_schema(site: dict, canonical_url: str, compact: bool = False) -> dict:
    schema: dict = {
        "@type": "RadioSeries",
        "@id": series_id(canonical_url),
        "name": site["name"],
        "alternateName": site.get("short_name") or "sofea",
        "url": canonical_url.rstrip("/") + "/",
    }
    if compact:
        return schema
    schema.update({
        "description": site.get("description_de") or site["name"],
        "inLanguage": "de",
        "productionCompany": {
            "@type": "Organization",
            "name": site.get("radio", {}).get("name") or "Radio Blau",
            "url": site.get("radio", {}).get("url") or "https://www.radioblau.de/",
        },
        "sameAs": [
            str(link["url"])
            for link in site.get("social", [])
            if isinstance(link, dict) and link.get("url")
        ],
        "creator": [
            {
                "@type": "Person",
                "name": str(member.get("name") or member.get("alias") or ""),
                **({"alternateName": str(member["alias"])} if member.get("alias") else {}),
                **({"sameAs": str(member["alias_url"])} if member.get("alias_url") else {}),
            }
            for member in site.get("team", [])
            if isinstance(member, dict) and (member.get("name") or member.get("alias"))
        ],
    })
    return {key: value for key, value in schema.items() if value not in (None, "", [])}


def homepage_structured_data(site: dict, canonical_url: str) -> str:
    root_url = canonical_url.rstrip("/") + "/"
    website_id = root_url + "#website"
    webpage_id = root_url + "#webpage"
    data = {
        "@context": "https://schema.org",
        "@graph": [
            {
                "@type": "WebSite",
                "@id": website_id,
                "url": root_url,
                "name": site["name"],
                "alternateName": site.get("short_name") or "sofea",
                "description": site.get("description_de") or site["name"],
                "inLanguage": ["de", "en"],
            },
            {
                "@type": "WebPage",
                "@id": webpage_id,
                "url": root_url,
                "name": site["name"],
                "description": site.get("description_de") or site["name"],
                "isPartOf": {"@id": website_id},
                "mainEntity": {"@id": series_id(canonical_url)},
                "inLanguage": "de",
            },
            series_schema(site, canonical_url),
        ],
    }
    return json_ld_script(data)


def iso_duration_from_seconds(total_seconds: int) -> str:
    total_seconds = max(0, int(total_seconds))
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    parts = "PT"
    if hours:
        parts += f"{hours}H"
    if minutes:
        parts += f"{minutes}M"
    if seconds or parts == "PT":
        parts += f"{seconds}S"
    return parts


def item_audio_duration(item: dict, site: dict | None = None) -> str:
    duration_ms = item.get("duration_ms")
    try:
        if duration_ms not in (None, ""):
            return iso_duration_from_seconds(round(float(duration_ms) / 1000))
    except (TypeError, ValueError):
        pass
    raw = str(item.get("duration") or "").strip()
    if raw.startswith("P"):
        return raw
    if re.fullmatch(r"\d{1,2}:\d{2}(?::\d{2})?", raw):
        values = [int(part) for part in raw.split(":")]
        if len(values) == 2:
            minutes, seconds = values
            return iso_duration_from_seconds(minutes * 60 + seconds)
        hours, minutes, seconds = values
        return iso_duration_from_seconds(hours * 3600 + minutes * 60 + seconds)
    return ""

def upcoming_structured_data(item: dict, site: dict, canonical_url: str, detail_url: str) -> str:
    start = parse_upcoming_date(str(item["date"]))
    end = upcoming_end(item)
    item_type = str(item.get("type") or "broadcast").lower()
    title = str(item.get("title_de") or site["name"] or "")
    description = detail_description(item, site)
    image = detail_social_image(item, site, canonical_url, "upcoming")
    if item_type == "event":
        event: dict = {
            "@context": "https://schema.org",
            "@type": "MusicEvent",
            "@id": detail_url.rstrip("/") + "/#event",
            "url": detail_url,
            "name": title,
            "description": description,
            "startDate": start.isoformat(),
            "endDate": end.isoformat(),
            "eventStatus": "https://schema.org/EventScheduled",
            "eventAttendanceMode": "https://schema.org/OfflineEventAttendanceMode",
            "inLanguage": "de",
            "organizer": {
                "@type": "Organization",
                "name": site["name"],
                "url": canonical_url.rstrip("/") + "/",
            },
            "image": [image],
        }
        location = str(item.get("location") or "").strip()
        if location:
            event["location"] = {"@type": "Place", "name": location}
        external_urls = [
            str(link["url"])
            for link in item.get("links", [])
            if isinstance(link, dict) and link.get("url")
        ]
        if external_urls:
            event["sameAs"] = external_urls
        return json_ld_script(event)

    episode_node: dict = {
        "@type": "RadioEpisode",
        "@id": detail_url.rstrip("/") + "/#episode",
        "url": detail_url,
        "name": title,
        "description": description,
        "datePublished": start.date().isoformat(),
        "inLanguage": "de",
        "partOfSeries": {"@id": series_id(canonical_url)},
        "publication": {
            "@type": "BroadcastEvent",
            "isLiveBroadcast": True,
            "startDate": start.isoformat(),
            "endDate": end.isoformat(),
            "publishedOn": {
                "@type": "RadioBroadcastService",
                "name": site.get("radio", {}).get("name") or "Radio Blau",
                "url": site.get("radio", {}).get("url") or "https://www.radioblau.de/",
            },
        },
        "image": image,
    }
    number = episode_number_value(item)
    if number is not None:
        episode_node["episodeNumber"] = number
    data = {
        "@context": "https://schema.org",
        "@graph": [episode_node, series_schema(site, canonical_url, compact=True)],
    }
    return json_ld_script(data)

def archive_structured_data(item: dict, site: dict, canonical_url: str, detail_url: str) -> str:
    value = parse_date(str(item["date"]))
    title = str(item.get("title_de") or item.get("title") or site["name"] or "")
    episode: dict = {
        "@type": "RadioEpisode",
        "@id": detail_url.rstrip("/") + "/#episode",
        "url": detail_url,
        "name": title,
        "description": detail_description(item, site),
        "datePublished": value.date().isoformat(),
        "inLanguage": "de",
        "partOfSeries": {"@id": series_id(canonical_url)},
        "image": detail_social_image(item, site, canonical_url, "episode"),
    }
    number = episode_number_value(item)
    if number is not None:
        episode["episodeNumber"] = number
    audio_url = str(item.get("audio_url") or "").strip()
    if audio_url:
        audio: dict = {
            "@type": "AudioObject",
            "@id": detail_url.rstrip("/") + "/#audio",
            "name": title,
            "url": audio_url,
            "embedUrl": soundcloud_embed(audio_url),
        }
        duration = item_audio_duration(item)
        if duration:
            audio["duration"] = duration
        episode["associatedMedia"] = audio
    data = {
        "@context": "https://schema.org",
        "@graph": [episode, series_schema(site, canonical_url, compact=True)],
    }
    return json_ld_script(data)

SOCIAL_CARD_SIZE = (1200, 630)


def social_card_relative_path(kind: str, item: dict, site: dict) -> str:
    detail_path = detail_relative_path(kind, item, site).strip("/").replace("/", "-")
    return f"assets/images/social/{detail_path}.png"


def _font_candidates(bold: bool) -> list[Path]:
    if os.name == "nt":
        windows = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"
        names = ["segoeuib.ttf", "arialbd.ttf"] if bold else ["segoeui.ttf", "arial.ttf"]
        return [windows / name for name in names]
    return [
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        Path("/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/dejavu/DejaVuSans.ttf"),
        Path("/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Arial.ttf"),
    ]


def social_font(size: int, bold: bool = False):
    for candidate in _font_candidates(bold):
        if candidate.is_file():
            return ImageFont.truetype(str(candidate), size=size)
    return ImageFont.load_default(size=size)


def wrap_social_text(draw: ImageDraw.ImageDraw, value: str, font, max_width: int, max_lines: int) -> list[str]:
    words = " ".join(value.split()).split()
    if not words:
        return []
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = word if not current else f"{current} {word}"
        if draw.textbbox((0, 0), candidate, font=font)[2] <= max_width:
            current = candidate
            continue
        if current:
            lines.append(current)
        current = word
        if len(lines) == max_lines:
            break
    if current and len(lines) < max_lines:
        lines.append(current)
    consumed = " ".join(lines)
    normalized = " ".join(value.split())
    if consumed != normalized and lines:
        last = lines[-1]
        while last and draw.textbbox((0, 0), last + "…", font=font)[2] > max_width:
            last = last[:-1].rstrip()
        lines[-1] = (last or "") + "…"
    return lines


def social_card_date(kind: str, item: dict) -> str:
    value = parse_upcoming_date(str(item["date"])) if kind == "upcoming" else parse_date(str(item["date"])).astimezone(BERLIN_TZ)
    return f"{value.day}. {MONTHS_DE[value.month - 1]} {value.year}"


def write_social_card(kind: str, item: dict, site: dict, target: Path) -> None:
    image = Image.new("RGB", SOCIAL_CARD_SIZE, "#171412")
    draw = ImageDraw.Draw(image)
    orange = "#ef9a55"
    peach = "#f2b27e"
    ink = "#f7f0e9"
    muted = "#c6b5a8"
    draw.rounded_rectangle((32, 32, 1168, 598), radius=34, fill="#211b18", outline="#54463e", width=2)
    draw.rectangle((32, 32, 58, 598), fill=orange)

    brand_font = social_font(54, bold=True)
    small_font = social_font(24, bold=True)
    meta_font = social_font(30)
    url_font = social_font(24, bold=True)

    draw.text((96, 78), "sofea", font=brand_font, fill=peach)
    draw.text((98, 142), "sounds of electronic art", font=small_font, fill=orange)

    item_type = str(item.get("type") or "broadcast").lower() if kind == "upcoming" else "broadcast"
    label = "VERANSTALTUNG" if item_type == "event" else "SENDUNG"
    number = episode_number_value(item)
    if number is not None and item_type == "broadcast":
        label += f" #{number}"
    if kind == "upcoming":
        label += " · DEMNÄCHST"
    draw.text((96, 215), label, font=small_font, fill=orange)

    title = str(item.get("title_de") or item.get("title") or site["name"])
    title_size = 72 if len(title) <= 30 else 60 if len(title) <= 55 else 50
    title_font = social_font(title_size, bold=True)
    title_lines = wrap_social_text(draw, title, title_font, 760, 3)
    y = 260
    line_height = int(title_size * 1.12)
    for line in title_lines:
        draw.text((96, y), line, font=title_font, fill=ink)
        y += line_height

    date_text = social_card_date(kind, item)
    location = str(item.get("location") or ("Radio Blau, Leipzig" if item_type == "broadcast" else "")).strip()
    meta = date_text + (f" · {location}" if location else "")
    draw.text((96, 518), meta, font=meta_font, fill=muted)
    draw.text((900, 550), "www.sofea.radio", font=url_font, fill=peach)

    target.parent.mkdir(parents=True, exist_ok=True)
    image.save(target, format="PNG", optimize=True)

def write_social_cards(upcoming: list[dict], archive: list[dict], site: dict) -> None:
    for kind, items in (("upcoming", upcoming), ("episode", archive)):
        for item in items:
            if item.get("social_image"):
                continue
            target = PUBLIC / social_card_relative_path(kind, item, site)
            write_social_card(kind, item, site, target)

def detail_social_image(item: dict, site: dict, canonical_url: str, kind: str) -> str:
    raw = str(item.get("social_image") or "").strip()
    if raw:
        path = urlparse(raw).path if raw.startswith(("https://", "http://")) else raw
        if Path(path).suffix.lower() != ".png":
            raise ValueError(f"social_image must be a PNG file: {raw}")
        if raw.startswith(("https://", "http://")):
            return raw
        return absolute_site_url(canonical_url, raw)
    return absolute_site_url(canonical_url, social_card_relative_path(kind, item, site))

def detail_description(item: dict, site: dict) -> str:
    value = content_text(item, "de") or site.get("description_de") or site["name"]
    return meta_excerpt(plain_editorial_text(value), 160)

def detail_page_title(kind: str, item: dict, site: dict) -> str:
    title = str(item.get("title_de") or item.get("title") or site["name"])
    value = parse_upcoming_date(str(item["date"])) if kind == "upcoming" else parse_date(str(item["date"]))
    if kind == "upcoming":
        return f"{title} – {value.day}. {MONTHS_DE[value.month - 1]} {value.year} | {site['name']}"
    return f"{title} – Sendung vom {value.day}. {MONTHS_DE[value.month - 1]} {value.year} | {site['name']}"


def detail_navigation(
    items: list[dict],
    index: int,
    kind: str,
    site: dict,
    base_path: str,
) -> str:
    links: list[str] = []
    labels = [
        (index - 1, "← Neuer", "← Newer") if kind == "episode" else (index - 1, "← Früher", "← Earlier"),
        (index + 1, "Älter →", "Older →") if kind == "episode" else (index + 1, "Später →", "Later →"),
    ]
    for target, label_de, label_en in labels:
        if target < 0 or target >= len(items):
            continue
        entry = items[target]
        path = detail_relative_path(kind, entry, site)
        title_de = str(entry.get("title_de") or entry.get("title") or site["name"])
        title_en = str(entry.get("title_en") or title_de)
        links.append(
            f'<a href="{esc(site_href(base_path, path))}" data-bilingual '
            f'data-de="{esc(label_de + ": " + title_de)}" data-en="{esc(label_en + ": " + title_en)}">'
            f'{esc(label_de + ": " + title_de)}</a>'
        )
    return f'<nav class="detail-neighbours" aria-label="Weitere Einträge">{"".join(links)}</nav>' if links else ""


def asset_href(value: object, base_path: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    if raw.startswith(("https://", "http://", "data:")):
        return raw
    return f"{base_path}/{raw.lstrip('/')}"


def inline_editorial_html(value: object) -> str:
    """Escape prose while allowing simple Markdown-style http(s) links."""
    raw = str(value or "")
    chunks: list[str] = []
    cursor = 0
    for match in MARKDOWN_LINK_RE.finditer(raw):
        chunks.append(esc(raw[cursor:match.start()]))
        chunks.append(
            f'<a href="{esc(match.group(2))}" target="_blank" rel="noopener noreferrer">'
            f'{esc(match.group(1))} ↗</a>'
        )
        cursor = match.end()
    chunks.append(esc(raw[cursor:]))
    return "".join(chunks)


def text_paragraphs(value: object) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    paragraphs = []
    for paragraph in raw.replace("\r\n", "\n").split("\n\n"):
        paragraph = paragraph.strip()
        if paragraph:
            rendered_lines = [inline_editorial_html(line) for line in paragraph.split("\n")]
            paragraphs.append(f"<p>{'<br>'.join(rendered_lines)}</p>")
    return "".join(paragraphs)


def localized_prose(item: dict, field: str) -> str:
    de_value = item.get(f"{field}_de") or item.get(field) or ""
    en_value = item.get(f"{field}_en") or item.get(field) or de_value
    if not de_value and not en_value:
        return ""
    return (
        f'<div class="detail-prose" data-language-panel="de">{text_paragraphs(de_value)}</div>'
        f'<div class="detail-prose" data-language-panel="en" hidden>{text_paragraphs(en_value)}</div>'
    )

def localized_collection(item: dict, field: str) -> tuple[list, list]:
    shared = item.get(field) if isinstance(item.get(field), list) else []
    de_value = item.get(f"{field}_de") if isinstance(item.get(f"{field}_de"), list) else shared
    en_value = item.get(f"{field}_en") if isinstance(item.get(f"{field}_en"), list) else shared
    return list(de_value or []), list(en_value or de_value or [])

def lineup_items(values: list) -> str:
    rows = []
    for value in values:
        if isinstance(value, dict):
            label = str(value.get("name") or value.get("artist") or value.get("label") or "").strip()
            url = str(value.get("url") or "").strip()
        else:
            label = str(value).strip()
            url = ""
        if not label:
            continue
        content = esc(label)
        if url:
            content = f'<a href="{esc(url)}" target="_blank" rel="noopener noreferrer">{content} ↗</a>'
        rows.append(f"<li>{content}</li>")
    return "".join(rows)



def tracklist_items(values: list) -> str:
    rows = []
    for value in values:
        if isinstance(value, dict):
            artist = str(value.get("artist") or "").strip()
            title = str(value.get("title") or value.get("name") or "").strip()
            timecode = str(value.get("time") or value.get("timecode") or "").strip()
            label = str(value.get("label") or "").strip()
            url = str(value.get("url") or "").strip()
            main = " – ".join(part for part in [artist, title] if part) or label
            if label and main != label:
                main += f" ({label})"
        else:
            main = str(value).strip().replace(" — ", " – ").replace(" - ", " – ")
            timecode = ""
            url = ""
        if not main:
            continue
        content = esc(main)
        if url:
            content = f'<a href="{esc(url)}" target="_blank" rel="noopener noreferrer">{content} ↗</a>'
        time_html = f'<span class="detail-track-time">{esc(timecode)}</span>' if timecode else ""
        rows.append(f"<li><span>{content}</span>{time_html}</li>")
    return "".join(rows)


def music_presentation_items(values: list, language: str) -> str:
    rows: list[str] = []
    for value in values:
        if isinstance(value, dict):
            artist = str(value.get("artist") or value.get("name") or "").strip()
            title = str(value.get("title") or value.get("release") or "").strip()
            label = str(value.get("label") or "").strip()
            year = str(value.get("year") or "").strip()
            url = str(value.get("url") or "").strip()
            note = str(
                value.get(f"note_{language}")
                or value.get(f"description_{language}")
                or value.get("note")
                or value.get("description")
                or ""
            ).strip()
            main = " – ".join(part for part in [artist, title] if part) or label
            meta = " · ".join(part for part in [label, year] if part)
        else:
            main = str(value).strip()
            meta = ""
            note = ""
            url = ""
        if not main:
            continue
        title_html = esc(main)
        if url:
            title_html = f'<a href="{esc(url)}" target="_blank" rel="noopener noreferrer">{title_html} ↗</a>'
        meta_html = f'<span class="detail-presentation-meta">{esc(meta)}</span>' if meta else ""
        note_html = f'<p>{esc(note)}</p>' if note else ""
        rows.append(
            '<li><div class="detail-presentation-heading">'
            f'<strong>{title_html}</strong>{meta_html}</div>{note_html}</li>'
        )
    return "".join(rows)


def music_presentations_section(item: dict) -> str:
    de_values, en_values = localized_collection(item, "music_presentations")
    de_rows = music_presentation_items(de_values, "de")
    en_rows = music_presentation_items(en_values, "en")
    if not de_rows and not en_rows:
        return ""
    return (
        '<section class="detail-section">'
        '<h3 data-bilingual data-de="Musikvorstellungen" data-en="Featured music">Musikvorstellungen</h3>'
        f'<ul class="detail-presentations" data-language-panel="de">{de_rows}</ul>'
        f'<ul class="detail-presentations" data-language-panel="en" hidden>{en_rows}</ul>'
        '</section>'
    )

def tracklist_section(item: dict) -> str:
    values = item.get("tracklist") if isinstance(item.get("tracklist"), list) else []
    rows = tracklist_items(values)
    if not rows:
        return ""
    return (
        '<section class="detail-section">'
        '<h3 data-bilingual data-de="Tracklist" data-en="Track list">Tracklist</h3>'
        f'<ol class="detail-tracklist">{rows}</ol>'
        '</section>'
    )

def detail_collection_section(
    item: dict,
    field: str,
    heading_de: str,
    heading_en: str,
    ordered: bool = False,
) -> str:
    de_values, en_values = localized_collection(item, field)
    renderer = tracklist_items if ordered else lineup_items
    de_rows = renderer(de_values)
    en_rows = renderer(en_values)
    if not de_rows and not en_rows:
        return ""
    tag = "ol" if ordered else "ul"
    class_name = "detail-tracklist" if ordered else "detail-lineup"
    return (
        '<section class="detail-section">'
        f'<h3 data-bilingual data-de="{esc(heading_de)}" data-en="{esc(heading_en)}">{esc(heading_de)}</h3>'
        f'<{tag} class="{class_name}" data-language-panel="de">{de_rows}</{tag}>'
        f'<{tag} class="{class_name}" data-language-panel="en" hidden>{en_rows}</{tag}>'
        '</section>'
    )



def detail_prose(item: dict) -> str:
    de_value = content_text(item, "de")
    en_value = content_text(item, "en")
    if not de_value and not en_value:
        return ""
    return (
        f'<div class="detail-prose" data-language-panel="de">{text_paragraphs(de_value)}</div>'
        f'<div class="detail-prose" data-language-panel="en" hidden>{text_paragraphs(en_value)}</div>'
    )


def local_asset_path(value: object) -> Path | None:
    raw = str(value or "").strip()
    if not raw or raw.startswith(("https://", "http://", "data:")):
        return None
    candidate = (ROOT / raw.lstrip("/")).resolve()
    try:
        candidate.relative_to(ROOT.resolve())
    except ValueError:
        return None
    return candidate if candidate.is_file() else None


def responsive_artwork_name(item: dict) -> str:
    source = detail_image_source(item)
    digest = hashlib.sha1(source.encode("utf-8")).hexdigest()[:8]
    return f"{episode_artwork_stem(item)}-{digest}"


def responsive_artwork_variants(item: dict) -> tuple[list[tuple[str, int]], tuple[int, int] | None]:
    source = local_asset_path(detail_image_source(item))
    if source is None:
        return [], None
    try:
        with Image.open(source) as original:
            width, height = original.size
    except (OSError, ValueError):
        return [], None
    widths = [value for value in RESPONSIVE_ARTWORK_WIDTHS if value < width]
    if not widths or widths[-1] != width:
        widths.append(width)
    base_name = responsive_artwork_name(item)
    return [
        ((RESPONSIVE_ARTWORK_DIR / f"{base_name}-{target_width}.webp").as_posix(), target_width)
        for target_width in widths
    ], (width, height)


def write_responsive_artwork(item: dict) -> None:
    source = local_asset_path(detail_image_source(item))
    variants, _ = responsive_artwork_variants(item)
    if source is None or not variants:
        return
    try:
        with Image.open(source) as original:
            image = original.convert("RGB")
            for relative_path, target_width in variants:
                target = PUBLIC / relative_path
                target.parent.mkdir(parents=True, exist_ok=True)
                if target_width == image.width:
                    resized = image
                else:
                    target_height = max(1, round(image.height * target_width / image.width))
                    resized = image.resize((target_width, target_height), Image.Resampling.LANCZOS)
                resized.save(target, format="WEBP", quality=84, method=6)
    except (OSError, ValueError) as error:
        print(f"WARNING: Could not generate responsive artwork for {source}: {error}")


def write_responsive_artworks(items: list[dict]) -> None:
    seen: set[str] = set()
    for item in items:
        source = detail_image_source(item)
        if not source:
            continue
        key = responsive_artwork_name(item)
        if key in seen:
            continue
        seen.add(key)
        write_responsive_artwork(item)


def episode_artwork_stem(item: dict) -> str:
    date_part = str(item.get("date") or "")[:10] or "undated"
    title = str(item.get("title_de") or item.get("title") or "sendung")
    return f"{date_part}-{slugify(title)}"


def local_episode_artwork(item: dict) -> str:
    for extension in ARTWORK_EXTENSIONS:
        candidate = EPISODE_ARTWORK_DIR / f"{episode_artwork_stem(item)}{extension}"
        if candidate.is_file():
            return candidate.relative_to(ROOT).as_posix()
    return ""


def detail_image_source(item: dict) -> str:
    explicit = str(item.get("image") or "").strip()
    return explicit or local_episode_artwork(item)

def detail_intro(header_html: str, image_html: str, summary_html: str) -> str:
    if not image_html:
        return header_html + summary_html
    return (
        '<div class="detail-intro detail-intro-with-artwork">'
        f'{image_html}'
        f'<div class="detail-intro-copy">{header_html}{summary_html}</div>'
        '</div>'
    )


def detail_image(item: dict, base_path: str, title_de: str, title_en: str) -> str:
    source = detail_image_source(item)
    src = asset_href(source, base_path)
    if not src:
        return ""
    alt_de = title_de
    alt_en = title_en
    variants, dimensions = responsive_artwork_variants(item)
    srcset = ""
    if variants:
        srcset_value = ", ".join(f"{asset_href(path, base_path)} {width}w" for path, width in variants)
        srcset = (
            f' srcset="{esc(srcset_value)}" '
            'sizes="(max-width: 720px) min(62vw, 240px), (max-width: 980px) 42vw, 420px"'
        )
    size_attributes = ""
    if dimensions:
        size_attributes = f' width="{dimensions[0]}" height="{dimensions[1]}"'
    return (
        '<figure class="detail-image detail-artwork">'
        f'<picture><img src="{esc(src)}"{srcset}{size_attributes} alt="{esc(alt_de)}" '
        'loading="lazy" decoding="async" '
        f'data-alt-de="{esc(alt_de)}" data-alt-en="{esc(alt_en)}"></picture>'
        '</figure>'
    )

def external_action_links(item: dict) -> list[str]:
    links = item.get("links") if isinstance(item.get("links"), list) else []
    actions = []
    for link in links:
        if not isinstance(link, dict) or not link.get("url"):
            continue
        label_de = str(link.get("label_de") or link.get("label") or "Details")
        label_en = str(link.get("label_en") or link.get("label") or label_de)
        class_name = "button button-primary" if link.get("primary") else "button"
        actions.append(
            f'<a class="{class_name}" href="{esc(link["url"])}" target="_blank" '
            f'rel="noopener noreferrer" data-bilingual data-de="{esc(label_de)}" '
            f'data-en="{esc(label_en)}">{esc(label_de)}</a>'
        )
    return actions


def upcoming_detail_inner(
    item: dict,
    site: dict,
    base_path: str,
    heading_tag: str,
    heading_id: str,
) -> str:
    start = parse_upcoming_date(str(item["date"]))
    end = upcoming_end(item)
    item_type = str(item.get("type") or "broadcast").lower()
    title_de = str(item.get("title_de") or site["name"])
    title_en = str(item.get("title_en") or title_de)
    label_de = upcoming_label(item, "de")
    label_en = upcoming_label(item, "en")
    default_location = "Radio Blau, Leipzig" if item_type == "broadcast" else ""
    location = str(item.get("location") or default_location).strip()
    date_de = date_long(start, "de")
    date_en = date_long(start, "en")
    time_value = hour_range_clock(start, end)

    meta = [
        f'<time datetime="{esc(start.isoformat())}" data-bilingual data-de="{esc(date_de)}" data-en="{esc(date_en)}">{esc(date_de)}</time>',
        f'<span>{esc(time_value)}</span>',
    ]
    if location:
        meta.append(f'<span>{esc(location)}</span>')

    actions = external_action_links(item)
    action_html = f'<div class="detail-actions">{"".join(actions)}</div>' if actions else ""

    header_html = (
        '<header class="detail-header">'
        f'<p class="eyebrow" data-bilingual data-de="{esc(label_de)}" data-en="{esc(label_en)}">{esc(label_de)}</p>'
        f'<{heading_tag} id="{esc(heading_id)}" data-bilingual data-de="{esc(title_de)}" '
        f'data-en="{esc(title_en)}">{esc(title_de)}</{heading_tag}>'
        f'<div class="detail-meta">{"".join(meta)}</div>'
        '</header>'
    )
    image_html = detail_image(item, base_path, title_de, title_en)
    return (
        f'{detail_intro(header_html, image_html, "")}'
        f'{detail_prose(item)}'
        f'{action_html}'
    )

def upcoming_detail_dialog(
    item: dict,
    site: dict,
    base_path: str,
    detail_url: str,
) -> str:
    dialog_id = detail_identifier("upcoming", item, site)
    heading_id = f"{dialog_id}-heading"
    title_de = str(item.get("title_de") or site["name"])
    page_title = f"{title_de} | {site['name']}"
    inner = upcoming_detail_inner(item, site, base_path, "h2", heading_id)
    return (
        f'<dialog class="detail-dialog" id="{esc(dialog_id)}" data-detail-dialog '
        f'data-detail-url="{esc(detail_url)}" data-page-title="{esc(page_title)}" '
        f'aria-labelledby="{esc(heading_id)}">'
        '<article class="detail-dialog-shell">'
        '<button class="detail-close" type="button" data-detail-close '
        'data-label-de="Details schließen" data-label-en="Close details" aria-label="Details schließen">×</button>'
        f'{inner}'
        '</article></dialog>'
    )

def upcoming_detail_page(
    item: dict,
    site: dict,
    base_path: str,
) -> str:
    heading_id = "detail-page-heading"
    inner = upcoming_detail_inner(item, site, base_path, "h1", heading_id)
    return f'<article class="detail-page-card" aria-labelledby="{heading_id}">{inner}</article>'

def archive_detail_inner(
    item: dict,
    site: dict,
    base_path: str,
    heading_tag: str,
    heading_id: str,
) -> str:
    value = parse_date(str(item["date"]))
    title_de = clean_archive_title(item["title_de"])
    title_en = clean_archive_title(item.get("title_en") or title_de)
    visible_item = dict(item)
    visible_item["details_de"] = content_text(item, "de")
    visible_item["details_en"] = content_text(item, "en")
    date_de = f"{value.day:02d}. {MONTHS_DE[value.month - 1]} {value.year}"
    date_en = f"{value.day:02d} {MONTHS_EN[value.month - 1]} {value.year}"
    summary_html = ""
    actions = external_action_links(item)
    audio_url = str(item.get("audio_url") or "").strip()
    if audio_url:
        actions.insert(
            0,
            f'<a class="button button-primary" href="{esc(audio_url)}" target="_blank" '
            'rel="noopener noreferrer" data-bilingual data-de="Auf SoundCloud anhören ↗" '
            'data-en="Listen on SoundCloud ↗">Auf SoundCloud anhören ↗</a>',
        )
    action_html = f'<div class="detail-actions">{"".join(actions)}</div>' if actions else ""
    header_html = (
        '<header class="detail-header">'
        '<p class="eyebrow" data-bilingual data-de="Sendung" data-en="Broadcast">Sendung</p>'
        f'<{heading_tag} id="{esc(heading_id)}" data-bilingual data-de="{esc(title_de)}" '
        f'data-en="{esc(title_en)}">{esc(title_de)}</{heading_tag}>'
        '<div class="detail-meta">'
        f'<time datetime="{esc(item["date"])}" data-bilingual data-de="{esc(date_de)}" '
        f'data-en="{esc(date_en)}">{esc(date_de)}</time>'
        '</div></header>'
    )
    image_html = detail_image(item, base_path, title_de, title_en)
    return (
        f'{detail_intro(header_html, image_html, summary_html)}'
        f'{localized_prose(visible_item, "details")}'
        f'{music_presentations_section(item)}'
        f'{detail_collection_section(item, "lineup", "Mitwirkende", "Contributors")}'
        f'{detail_collection_section(item, "tracklist", "Tracklist", "Track list", ordered=True)}'
        f'{action_html}'
    )

def archive_detail_dialog(item: dict, site: dict, base_path: str, detail_url: str) -> str:
    dialog_id = detail_identifier("episode", item, site)
    heading_id = f"{dialog_id}-heading"
    title_de = str(item["title_de"])
    page_title = f"{title_de} | {site['name']}"
    inner = archive_detail_inner(item, site, base_path, "h2", heading_id)
    return (
        f'<dialog class="detail-dialog" id="{esc(dialog_id)}" data-detail-dialog '
        f'data-detail-url="{esc(detail_url)}" data-page-title="{esc(page_title)}" '
        f'aria-labelledby="{esc(heading_id)}">'
        '<article class="detail-dialog-shell">'
        '<button class="detail-close" type="button" data-detail-close '
        'data-label-de="Details schließen" data-label-en="Close details" aria-label="Details schließen">×</button>'
        f'{inner}'
        '</article></dialog>'
    )

def archive_detail_page(item: dict, site: dict, base_path: str) -> str:
    heading_id = "detail-page-heading"
    inner = archive_detail_inner(item, site, base_path, "h1", heading_id)
    return f'<article class="detail-page-card" aria-labelledby="{heading_id}">{inner}</article>'

def upcoming_rows(items: list[dict], site: dict, base_path: str) -> tuple[str, str]:
    if not items:
        return (
            '<p class="upcoming-empty" data-bilingual '
            'data-de="Aktuell sind keine Termine eingetragen." '
            'data-en="No upcoming dates are currently listed.">'
            'Aktuell sind keine Termine eingetragen.</p>',
            "",
        )

    rows: list[str] = []
    dialogs: list[str] = []
    for item in sorted(items, key=lambda entry: parse_upcoming_date(str(entry["date"]))):
        start = parse_upcoming_date(str(item["date"]))
        item_type = str(item.get("type") or "broadcast").lower()
        end = upcoming_end(item)
        title_de = str(item.get("title_de") or site["name"])
        title_en = str(item.get("title_en") or title_de)
        card_summary_de = card_excerpt(content_text(item, "de"))
        card_summary_en = card_excerpt(content_text(item, "en"))
        label_de = upcoming_label(item, "de")
        label_en = upcoming_label(item, "en")
        default_location = "Radio Blau, Leipzig" if item_type == "broadcast" else ""
        location = str(item.get("location") or default_location).strip()
        dialog_id = detail_identifier("upcoming", item, site)
        relative_path = detail_relative_path("upcoming", item, site)
        detail_url = site_href(base_path, relative_path)
        absolute_detail_url = detail_url
        calendar_href = site_href(base_path, f"calendar/{calendar_filename(item, site)}")

        summary_html = ""
        if card_summary_de or card_summary_en:
            summary_html = (
                f'<p class="upcoming-summary" data-bilingual data-de="{esc(card_summary_de)}" '
                f'data-en="{esc(card_summary_en)}">{esc(card_summary_de)}</p>'
            )

        date_de = date_long(start, "de")
        date_en = date_long(start, "en")
        clock_range = hour_range_clock(start, end)
        footer_parts = [
            (
                f'<time class="upcoming-date" datetime="{esc(start.isoformat())}" data-upcoming-date '
                f'data-date-de="{esc(date_de)}" data-date-en="{esc(date_en)}" data-bilingual '
                f'data-de="{esc(date_de)}" data-en="{esc(date_en)}">{esc(date_de)}</time>'
            ),
            f'<span>{esc(clock_range)}</span>',
        ]
        if location:
            footer_parts.append(f'<span>{esc(location)}</span>')
        footer_html = '<span class="upcoming-footer-separator" aria-hidden="true">·</span>'.join(footer_parts)

        calendar_button = (
            f'<a class="button calendar-button upcoming-calendar-button" href="{esc(calendar_href)}" '
            'type="text/calendar">'
            '<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">'
            '<path d="M7 3v3M17 3v3M4.5 9h15M5 5.5h14a1 1 0 0 1 1 1V20H4V6.5a1 1 0 0 1 1-1Z"/>'
            '<path d="m9 14 2 2 4-4"/></svg>'
            '<span data-bilingual data-de="Termin speichern" data-en="Save event">Termin speichern</span></a>'
        )

        rows.append(
            f'<article class="upcoming-card upcoming-card-{esc(item_type)}" data-detail-id="{esc(dialog_id)}">'
            '<div class="date-panel">'
            f'<span class="upcoming-day">{start.day}</span>'
            f'<span class="upcoming-month" data-bilingual data-de="{esc(MONTHS_DE[start.month - 1])}" '
            f'data-en="{esc(MONTHS_EN[start.month - 1])}">{esc(MONTHS_DE[start.month - 1])}</span>'
            f'<span class="upcoming-year">{start.year}</span>'
            '</div>'
            '<div class="upcoming-copy">'
            '<div class="upcoming-card-header">'
            f'<p class="eyebrow" data-bilingual data-de="{esc(label_de)}" '
            f'data-en="{esc(label_en)}">{esc(label_de)}</p>'
            f'{calendar_button}'
            '</div>'
            '<div class="upcoming-card-body">'
            f'<h3><a class="upcoming-title-link detail-title-link" href="{esc(detail_url)}" '
            f'data-detail-link data-detail-id="{esc(dialog_id)}" data-bilingual '
            f'data-de="{esc(title_de)}" data-en="{esc(title_en)}">{esc(title_de)}</a></h3>'
            f'{summary_html}'
            '</div>'
            f'<footer class="upcoming-card-footer">{footer_html}</footer>'
            '</div></article>'
        )
        dialogs.append(upcoming_detail_dialog(item, site, base_path, absolute_detail_url))
    return "".join(rows), "".join(dialogs)

def archive_match_key(item: dict) -> tuple[str, str]:
    date_value = str(item.get("date") or "")[:10]
    title = str(item.get("title_de") or item.get("title") or "")
    return date_value, slugify(clean_archive_title(title))


def load_archive(episodes: list[dict]) -> list[dict]:
    """Merge local editorial data with the source cache.

    Local ``episode_id`` is the canonical identity. SoundCloud ID, URL and
    date/title matching remain compatibility fallbacks for older content.
    """
    local_entries = [
        item
        for item in episodes
        if item.get("date") and (item.get("title_de") or item.get("title"))
    ]
    local_by_id = {episode_id_value(item): item for item in local_entries}
    local_by_source_id = {
        str(item.get("soundcloud_id") or "").strip(): item
        for item in local_entries
        if item.get("soundcloud_id")
    }
    local_by_url = {
        str(item["audio_url"]).rstrip("/"): item
        for item in local_entries
        if item.get("audio_url")
    }
    local_by_key = {archive_match_key(item): item for item in local_entries}
    result: list[dict] = []
    seen_ids: set[str] = set()

    cache_path = ROOT / "content" / "archive-cache.json"
    try:
        cache = read_json(cache_path)
        cached_episodes = cache.get("episodes", [])
        if isinstance(cached_episodes, list):
            for item in cached_episodes:
                if not isinstance(item, dict):
                    continue
                if not item.get("date") or not item.get("title") or not item.get("audio_url"):
                    continue
                base = {
                    "date": str(item["date"]),
                    "episode_id": str(item.get("episode_id") or "").strip(),
                    "title_de": clean_archive_title(item["title"]),
                    "title_en": clean_archive_title(item["title"]),
                    "summary_de": str(item.get("summary") or ""),
                    "summary_en": str(item.get("summary") or ""),
                    "soundcloud_description": str(item.get("description") or ""),
                    "audio_url": str(item["audio_url"]),
                    "soundcloud_id": str(item.get("soundcloud_id") or "").strip(),
                    "duration_ms": item.get("duration_ms"),
                    "image": str(item.get("image") or ""),
                    "artwork_url": str(item.get("artwork_url") or ""),
                }
                cached_identity = episode_id_value(base)
                normalised_url = base["audio_url"].rstrip("/")
                override = (
                    local_by_id.get(cached_identity)
                    or local_by_source_id.get(base["soundcloud_id"])
                    or local_by_url.get(normalised_url)
                    or local_by_key.get(archive_match_key(base))
                )
                if override:
                    for key, value in override.items():
                        if key in {"date", "audio_url", "soundcloud_id"}:
                            continue
                        base[key] = value
                base["episode_id"] = episode_id_value(base)
                base["title_de"] = clean_archive_title(base.get("title_de"))
                base["title_en"] = clean_archive_title(base.get("title_en") or base["title_de"])
                if not base.get("image"):
                    base["image"] = local_episode_artwork(base)
                result.append(base)
                seen_ids.add(base["episode_id"])
    except (OSError, json.JSONDecodeError, AttributeError, TypeError, ValueError):
        result = []

    for item in local_entries:
        identity = episode_id_value(item)
        if identity in seen_ids:
            continue
        local_item = dict(item)
        local_item["episode_id"] = identity
        local_item["title_de"] = clean_archive_title(local_item.get("title_de") or "")
        local_item["title_en"] = clean_archive_title(local_item.get("title_en") or local_item["title_de"])
        if not local_item.get("image"):
            local_item["image"] = local_episode_artwork(local_item)
        result.append(local_item)
        seen_ids.add(identity)

    return sorted(result, key=lambda item: parse_date(str(item["date"])), reverse=True)

def flatten_search_values(value: object) -> list[str]:
    if isinstance(value, dict):
        rows: list[str] = []
        for nested in value.values():
            rows.extend(flatten_search_values(nested))
        return rows
    if isinstance(value, list):
        rows = []
        for nested in value:
            rows.extend(flatten_search_values(nested))
        return rows
    return [str(value)] if value not in (None, "") else []


def episode_rows(archive: list[dict], site: dict, base_path: str) -> tuple[str, str]:
    rows: list[str] = []
    dialogs: list[str] = []
    for item in archive:
        value = parse_date(str(item["date"]))
        date_de = f"{value.day:02d}. {MONTHS_DE[value.month - 1]} {value.year}"
        date_en = f"{value.day:02d} {MONTHS_EN[value.month - 1][:3]} {value.year}"
        title_de = clean_archive_title(item["title_de"])
        title_en = clean_archive_title(item.get("title_en") or title_de)
        summary_de = content_text(item, "de")
        summary_en = content_text(item, "en")
        card_summary_de = card_excerpt(summary_de, 180)
        card_summary_en = card_excerpt(summary_en, 180)
        search_text = " ".join(
            [str(item["date"]), date_de, date_en, title_de, title_en, summary_de, summary_en]
            + flatten_search_values(item.get("music_presentations"))
            + flatten_search_values(item.get("tracklist"))
        ).casefold()
        summary_html = ""
        if card_summary_de or card_summary_en:
            summary_html = (
                f'<p data-bilingual data-de="{esc(card_summary_de)}" data-en="{esc(card_summary_en)}">{esc(card_summary_de)}</p>'
            )
        episode_id = f"episode-{episode_id_value(item)}"
        dialog_id = detail_identifier("episode", item, site)
        relative_path = detail_relative_path("episode", item, site)
        detail_url = site_href(base_path, relative_path)
        audio_url = str(item.get("audio_url") or "").strip()
        audio_link = (
            f'<a class="episode-link" href="{esc(audio_url)}" target="_blank" '
            'rel="noopener noreferrer" data-i18n="play_recording">Aufnahme abspielen ↗</a>'
            if audio_url
            else ""
        )
        rows.append(
            f'<article class="episode" id="{esc(episode_id)}" data-episode '
            f'data-detail-id="{esc(dialog_id)}" data-search="{esc(search_text)}">'
            f'<time class="episode-date" datetime="{esc(item["date"])}" data-bilingual '
            f'data-de="{esc(date_de)}" data-en="{esc(date_en)}">{esc(date_de)}</time>'
            '<div class="episode-copy"><div class="episode-title-row">'
            f'<h3><a class="episode-title-link detail-title-link" href="{esc(detail_url)}" data-detail-link '
            f'data-detail-id="{esc(dialog_id)}" data-bilingual data-de="{esc(title_de)}" '
            f'data-en="{esc(title_en)}">{esc(title_de)}</a></h3></div>'
            f'{summary_html}</div>'
            f'{audio_link}'
            '</article>'
        )
        dialogs.append(archive_detail_dialog(item, site, base_path, detail_url))
    return "".join(rows), "".join(dialogs)

def legal_pages_content(legal: dict[str, str]) -> dict[str, str]:
    name = esc(legal["operator_name"])
    street = esc(legal["street_address"])
    postal_city = esc(legal["postal_city"])
    country = esc(legal.get("country") or "Deutschland")
    address = (
        f'<address class="legal-address"><strong>{name}</strong><br>'
        f'{street}<br>{postal_city}<br>{country}</address>'
    )

    imprint = f'''
<section class="section legal-section">
  <div class="shell legal-shell">
    <div data-language-panel="de">
      <p class="eyebrow">Rechtliche Hinweise</p>
      <h1 class="legal-title">Impressum</h1>
      <div class="legal-card">
        <h2>Angaben gemäß § 18 Abs. 1 Medienstaatsvertrag</h2>
        <p>Anbieter und Betreiber dieser Website:</p>
        {address}
      </div>
      <p class="legal-note">Stand: Juli 2026</p>
    </div>
    <div data-language-panel="en" hidden>
      <p class="eyebrow">Legal information</p>
      <h1 class="legal-title">Legal notice</h1>
      <div class="legal-card">
        <h2>Information pursuant to section 18(1) of the German Interstate Media Treaty</h2>
        <p>Provider and operator of this website:</p>
        {address}
      </div>
      <p class="legal-note">Last updated: July 2026. The German version is authoritative.</p>
    </div>
  </div>
</section>'''

    privacy = f'''
<section class="section legal-section">
  <div class="shell legal-shell">
    <div data-language-panel="de">
      <p class="eyebrow">Rechtliche Hinweise</p>
      <h1 class="legal-title">Datenschutz&shy;erklärung</h1>

      <div class="legal-card legal-prose">
        <h2>1. Verantwortlicher</h2>
        <p>Verantwortlich für die Datenverarbeitung auf dieser Website ist:</p>
        {address}
        <p>Datenschutzanfragen können postalisch an diese Anschrift gerichtet werden.</p>

        <h2>2. Hosting über GitHub Pages</h2>
        <p>Diese Website wird über GitHub Pages bereitgestellt, einen Dienst der GitHub, Inc. Beim Aufruf einer GitHub-Pages-Website wird die IP-Adresse des zugreifenden Geräts nach Angaben von GitHub zu Sicherheitszwecken protokolliert und gespeichert. Weitere technische Nutzungsdaten können durch GitHub verarbeitet werden.</p>
        <p><a href="https://docs.github.com/en/site-policy/privacy-policies/github-general-privacy-statement">Datenschutzhinweise von GitHub ↗</a></p>

        <h2>3. Lokale Einstellungen</h2>
        <p>Die Website speichert die gewählte Sprache und das helle oder dunkle Farbschema im lokalen Speicher des Browsers. Diese Angaben dienen ausschließlich dazu, die gewählten Anzeigeeinstellungen bei späteren Besuchen beizubehalten. Sie werden nicht zur Reichweitenmessung oder zur Erstellung von Nutzerprofilen verwendet.</p>

        <h2 id="soundcloud">4. Eingebettete Inhalte von SoundCloud</h2>
        <p>Im Bereich „Hören“ wird zunächst nur eine lokal bereitgestellte Vorschau angezeigt. Erst wenn die Schaltfläche „SoundCloud-Player laden“ betätigt wird, erstellt der Browser eine direkte Verbindung zu SoundCloud und lädt den externen Audioplayer. Dabei können insbesondere die IP-Adresse, Browser- und Geräteinformationen, die aufgerufene Seite sowie Nutzungsinformationen an SoundCloud übermittelt werden. SoundCloud weist darauf hin, dass bei eingebetteten Playern Nutzungsdaten zu Analysezwecken erhoben und Cookies oder vergleichbare Technologien eingesetzt werden können.</p>
        <p><a href="https://help.soundcloud.com/hc/en-us/articles/360004066174-General-Data-Protection-Regulation-GDPR">Datenschutzhinweise zu eingebetteten SoundCloud-Playern ↗</a></p>

        <h2>5. Externe Links</h2>
        <p>Diese Website enthält Links zu externen Angeboten, insbesondere SoundCloud, Instagram und Radio Blau. Erst beim Anklicken eines solchen Links wird die jeweilige externe Website aufgerufen. Für die dortige Datenverarbeitung ist der jeweilige Anbieter verantwortlich.</p>

        <h2>6. Eigene Reichweitenmessung und Kontaktformulare</h2>
        <p>Diese Website verwendet keine eigene Webanalyse, kein eigenes Tracking, keine Werbenetzwerke und kein Kontaktformular. Es werden keine Newsletter angeboten.</p>

        <h2>7. Rechte betroffener Personen</h2>
        <p>Im Rahmen der gesetzlichen Voraussetzungen bestehen insbesondere Rechte auf Auskunft, Berichtigung, Löschung, Einschränkung der Verarbeitung, Datenübertragbarkeit und Widerspruch. Außerdem besteht das Recht, sich bei einer Datenschutzaufsichtsbehörde zu beschweren.</p>

        <h2>8. Aktualisierung</h2>
        <p>Diese Datenschutzerklärung wird angepasst, wenn sich die eingesetzten Dienste oder die rechtlichen Anforderungen ändern.</p>
      </div>
      <p class="legal-note">Stand: Juli 2026</p>
    </div>

    <div data-language-panel="en" hidden>
      <p class="eyebrow">Legal information</p>
      <h1 class="legal-title">Privacy notice</h1>

      <div class="legal-card legal-prose">
        <h2>1. Controller</h2>
        <p>The controller responsible for processing personal data on this website is:</p>
        {address}
        <p>Privacy enquiries may be sent to this postal address.</p>

        <h2>2. Hosting through GitHub Pages</h2>
        <p>This website is hosted through GitHub Pages, a service provided by GitHub, Inc. GitHub states that the IP address of a device visiting a GitHub Pages site is logged and stored for security purposes. GitHub may process additional technical usage information.</p>
        <p><a href="https://docs.github.com/en/site-policy/privacy-policies/github-general-privacy-statement">GitHub General Privacy Statement ↗</a></p>

        <h2>3. Local preferences</h2>
        <p>The website stores the selected language and light or dark colour scheme in the browser's local storage. These values are used only to restore the selected display preferences. They are not used for audience measurement or profiling.</p>

        <h2 id="soundcloud-en">4. Embedded SoundCloud content</h2>
        <p>The “Listen” section initially shows only a locally provided preview. A direct connection to SoundCloud is established only after the “Load SoundCloud player” button is selected. At that point, the external audio player is loaded and may transmit the IP address, browser and device information, the referring page and usage information. SoundCloud states that embedded players may collect usage information for analytics and may use cookies or similar technologies.</p>
        <p><a href="https://help.soundcloud.com/hc/en-us/articles/360004066174-General-Data-Protection-Regulation-GDPR">SoundCloud information for embedded players ↗</a></p>

        <h2>5. External links</h2>
        <p>This website links to external services, particularly SoundCloud, Instagram and Radio Blau. The external website is contacted only after a link is selected. The respective provider is responsible for processing data on that service.</p>

        <h2>6. Analytics and contact forms</h2>
        <p>This website does not operate its own analytics, tracking, advertising networks, contact forms or newsletter.</p>

        <h2>7. Data subject rights</h2>
        <p>Subject to the applicable legal requirements, data subjects may have rights of access, rectification, erasure, restriction, data portability and objection. They may also lodge a complaint with a data protection supervisory authority.</p>

        <h2>8. Updates</h2>
        <p>This privacy notice will be updated when the services used by this website or the applicable legal requirements change.</p>
      </div>
      <p class="legal-note">Last updated: July 2026. The German version is authoritative.</p>
    </div>
  </div>
</section>'''

    return {"impressum": imprint, "datenschutz": privacy}

def episode_numbers_by_date(entries: list[dict]) -> dict[str, int]:
    """Return the canonical episode number for each broadcast date."""
    numbers_by_date: dict[str, int] = {}
    dates_by_number: dict[int, str] = {}
    for index, item in enumerate(entries, start=1):
        date_value = str(item.get("date") or "").strip()
        number = episode_number_value(item)
        try:
            parsed_date = datetime.fromisoformat(date_value).date().isoformat()
        except ValueError as exc:
            raise ValueError(
                f"content/episode-numbers.json entry {index} has an invalid date: {date_value!r}"
            ) from exc
        if parsed_date != date_value:
            raise ValueError(
                f"content/episode-numbers.json entry {index} date must use YYYY-MM-DD: {date_value!r}"
            )
        if number is None:
            raise ValueError(
                f"content/episode-numbers.json entry {index} has an invalid episode_number"
            )
        if date_value in numbers_by_date:
            raise ValueError(f"Duplicate episode-number date: {date_value}")
        if number in dates_by_number:
            raise ValueError(
                f"Duplicate episode_number {number}: {dates_by_number[number]} and {date_value}"
            )
        numbers_by_date[date_value] = number
        dates_by_number[number] = date_value

    if dates_by_number:
        expected = set(range(1, max(dates_by_number) + 1))
        missing = sorted(expected.difference(dates_by_number))
        if missing:
            raise ValueError(
                "Missing episode_number values: " + ", ".join(str(number) for number in missing)
            )
    return numbers_by_date


def apply_archive_episode_numbers(items: list[dict], numbers_by_date: dict[str, int]) -> None:
    """Apply the date-based number unless an archive item explicitly overrides it."""
    for item in items:
        if episode_number_value(item) is not None:
            continue
        number = numbers_by_date.get(str(item.get("date") or "")[:10])
        if number is not None:
            item["episode_number"] = number


def assign_upcoming_episode_numbers(items: list[dict], numbers_by_date: dict[str, int]) -> None:
    """Number future broadcasts chronologically after the latest confirmed episode."""
    next_number = max(numbers_by_date.values(), default=0) + 1
    for item in sorted(items, key=lambda entry: parse_upcoming_date(str(entry["date"]))):
        explicit = episode_number_value(item)
        if explicit is not None:
            next_number = max(next_number, explicit + 1)
            continue
        known = numbers_by_date.get(str(item.get("date") or "")[:10])
        if known is not None:
            item["episode_number"] = known
            next_number = max(next_number, known + 1)
            continue
        item["episode_number"] = next_number
        next_number += 1


def main() -> None:
    site = read_json(ROOT / "content" / "site.json")
    legal = read_json(ROOT / "content" / "legal.json")
    listen_entries = read_json_list(ROOT / "content" / "listen.json")
    archive_entries = read_json_list(ROOT / "content" / "episodes.json")
    episode_number_entries = read_json_list(ROOT / "content" / "episode-numbers.json")
    broadcast_entries = read_json_list(ROOT / "content" / "upcoming-broadcasts.json")
    event_entries = read_json_list(ROOT / "content" / "upcoming-events.json")
    for item in broadcast_entries:
        item["type"] = "broadcast"
    for item in event_entries:
        item["type"] = "event"

    # Publish the exact editorial SOFEA broadcast windows for the client-side
    # LIVE state. The local Leipzig wall clock is authoritative and is
    # converted to UTC here so browsers do not need timezone assumptions.
    live_broadcast_windows = [
        {
            "start": (
                parse_upcoming_date(str(item["date"]))
                .astimezone(timezone.utc)
                .isoformat()
                .replace("+00:00", "Z")
            ),
            "end": (
                upcoming_end(item)
                .astimezone(timezone.utc)
                .isoformat()
                .replace("+00:00", "Z")
            ),
        }
        for item in broadcast_entries
        if item.get("date")
    ]
    numbers_by_date = episode_numbers_by_date(episode_number_entries)
    archive = load_archive(archive_entries)
    apply_archive_episode_numbers(archive, numbers_by_date)

    pages_url = str(os.environ.get("SITE_URL") or site.get("url") or "http://localhost:8000").rstrip("/")
    parsed = urlparse(pages_url)
    base_path = parsed.path.rstrip("/")
    canonical_url = pages_url + "/"
    home_href = site_href(base_path)

    now_utc = datetime.now(timezone.utc)
    future_broadcasts = [
        item
        for item in broadcast_entries
        if upcoming_end(item).astimezone(timezone.utc) > now_utc
    ]
    assign_upcoming_episode_numbers(future_broadcasts, numbers_by_date)
    future_events = [
        item
        for item in event_entries
        if upcoming_end(item).astimezone(timezone.utc) > now_utc
    ]
    upcoming = sorted(
        future_broadcasts + future_events,
        key=lambda item: parse_upcoming_date(str(item["date"])),
    )

    team_rows = []
    for member in site["team"]:
        alias_url = member.get("alias_url")
        if alias_url:
            alias = (
                f'<a class="artist-link" href="{esc(alias_url)}" target="_blank" '
                f'rel="noopener noreferrer">{esc(member["alias"])} ↗</a>'
            )
        else:
            alias = f'<span>{esc(member["alias"])}</span>'
        team_rows.append(f'<div class="team-member"><span>{esc(member["name"])}</span>{alias}</div>')
    team_html = "".join(team_rows)
    social_html = "".join(
        f'<a href="{esc(link["url"])}" target="_blank" rel="noopener noreferrer">{esc(link["label"])}</a>'
        for link in site["social"]
    )

    featured_mixes = featured_audio_items(listen_entries, archive)
    mix_rows = []
    for index, mix in enumerate(featured_mixes):
        duration = f'<span class="mix-duration">{esc(mix["duration"])}</span>' if mix.get("duration") else ""
        mix_rows.append(
            f'<button class="mix-item" type="button" role="listitem" data-mix-index="{index}" '
            f'data-title="{esc(mix["title_de"])}" data-title-en="{esc(mix["title_en"])}" '
            f'data-subtitle-de="{esc(mix["subtitle_de"])}" data-subtitle-en="{esc(mix["subtitle_en"])}" '
            f'data-url="{esc(mix["url"])}" data-embed="{esc(soundcloud_embed(mix["url"]))}" '
            f'aria-pressed="{"true" if index == 0 else "false"}" aria-expanded="false" '
            'aria-controls="recording-player-panel">'
            f'<span class="mix-copy"><strong data-mix-title>{esc(mix["title_de"])}</strong>'
            f'<span data-mix-subtitle>{esc(mix["subtitle_de"])}</span></span>'
            f'<span class="mix-item-meta">{duration}'
            '<svg class="mix-chevron" viewBox="0 0 20 20" aria-hidden="true" focusable="false">'
            '<path d="m6 8 4 4 4-4"/></svg></span></button>'
        )

    first_mix = featured_mixes[0]
    archive_playlist_url = site.get(
        "archive_playlist_url",
        "https://soundcloud.com/sounds-of-electronic-art/sets/sendungen",
    )
    logo_svg = (ROOT / "assets" / "icons" / "logo.svg").read_text(encoding="utf-8")
    template = (ROOT / "templates" / "index.html").read_text(encoding="utf-8")
    asset_version = asset_bundle_version([
        ROOT / "assets" / "css" / "site.css",
        ROOT / "assets" / "css" / "mobile-hero.css",
        ROOT / "assets" / "js" / "site.js",
    ])
    hero_preload_urls = {
        "dark": site_href(base_path, "assets/images/branding/sofea-hero-dark.webp"),
        "light": site_href(base_path, "assets/images/branding/sofea-hero-light.webp"),
    }
    upcoming_html, upcoming_dialogs = upcoming_rows(upcoming[:3], site, base_path)
    episodes_html, episode_dialogs = episode_rows(archive, site, base_path)
    default_social_image = absolute_site_url(canonical_url, "assets/images/sofea-social-card-v3.png")

    common_values = {
        "base_path": esc(base_path),
        "home_href": esc(home_href),
        "logo_svg": logo_svg,
        "radio_stream_url": esc(site["radio"]["stream_url"]),
        "radio_home_url": "https://www.radioblau.de/",
        "social_html": social_html,
        "social_image_url": esc(default_social_image),
        "structured_data_html": "",
        "build_year": str(datetime.now().year),
        "calendar_feed_href": esc(site_href(base_path, "calendar.ics")),
        "calendar_webcal_url": esc(re.sub(r"^https?://", "webcal://", canonical_url) + "calendar.ics"),
        "asset_version": asset_version,
        "hero_preload_urls_json": json.dumps(hero_preload_urls, ensure_ascii=False),
    }
    values = common_values | {
        "page_title": esc("sounds of electronic art – elektronische musik & klubkultur"),
        "description": esc(site["description_de"]),
        "canonical_url": esc(canonical_url),
        "structured_data_html": homepage_structured_data(site, canonical_url),
        "upcoming_html": upcoming_html,
        "mixes_html": "".join(mix_rows),
        "first_mix_title": esc(first_mix["title_de"]),
        "first_mix_subtitle_de": esc(first_mix["subtitle_de"]),
        "first_mix_url": esc(first_mix["url"]),
        "first_mix_embed": esc(soundcloud_embed(first_mix["url"])),
        "team_html": team_html,
        "episodes_html": episodes_html,
        "detail_dialogs_html": upcoming_dialogs + episode_dialogs,
        "archive_playlist_url": esc(archive_playlist_url),
    }

    if PUBLIC.exists():
        shutil.rmtree(PUBLIC)
    PUBLIC.mkdir(parents=True)
    (PUBLIC / "live-broadcasts.json").write_text(
        json.dumps({"broadcasts": live_broadcast_windows}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    shutil.copytree(ROOT / "assets", PUBLIC / "assets")
    write_responsive_artworks(upcoming + archive)
    write_social_cards(upcoming, archive, site)
    (PUBLIC / "calendar.ics").write_text(
        calendar_feed_content(upcoming, site, canonical_url),
        encoding="utf-8",
        newline="",
    )

    calendar_dir = PUBLIC / "calendar"
    calendar_dir.mkdir(parents=True, exist_ok=True)
    for item in upcoming:
        filename = calendar_filename(item, site)
        detail_url = absolute_site_url(canonical_url, detail_relative_path("upcoming", item, site))
        (calendar_dir / filename).write_text(
            calendar_event_content(item, site, detail_url),
            encoding="utf-8",
            newline="",
        )

    (PUBLIC / "index.html").write_text(render(template, values), encoding="utf-8")

    legal_template = (ROOT / "templates" / "legal.html").read_text(encoding="utf-8")
    legal_contents = legal_pages_content(legal)
    legal_pages = {
        "impressum.html": {
            "page_title": "Impressum / Legal notice — sounds of electronic art",
            "description": "Impressum und Anbieterkennzeichnung von sounds of electronic art.",
            "canonical_url": canonical_url + "impressum.html",
            "legal_content": legal_contents["impressum"],
        },
        "datenschutz.html": {
            "page_title": "Datenschutz / Privacy — sounds of electronic art",
            "description": "Datenschutzerklärung von sounds of electronic art.",
            "canonical_url": canonical_url + "datenschutz.html",
            "legal_content": legal_contents["datenschutz"],
        },
    }
    for filename, page_values in legal_pages.items():
        current_values = common_values | {
            key: esc(value) if key != "legal_content" else value
            for key, value in page_values.items()
        }
        (PUBLIC / filename).write_text(render(legal_template, current_values), encoding="utf-8")

    detail_template = (ROOT / "templates" / "detail.html").read_text(encoding="utf-8")
    for index, item in enumerate(upcoming):
        relative_path = detail_relative_path("upcoming", item, site)
        output_dir = PUBLIC / relative_path
        output_dir.mkdir(parents=True, exist_ok=True)
        canonical_detail_url = absolute_site_url(canonical_url, relative_path)
        item_type = str(item.get("type") or "broadcast").lower()
        detail_values = common_values | {
            "page_title": esc(detail_page_title("upcoming", item, site)),
            "description": esc(detail_description(item, site)),
            "canonical_url": esc(canonical_detail_url),
            "social_image_url": esc(detail_social_image(item, site, canonical_url, "upcoming")),
            "social_image_alt": esc(str(item.get("title_de") or site["name"])),
            "og_type": "article" if item_type == "broadcast" else "website",
            "structured_data_html": upcoming_structured_data(item, site, canonical_url, canonical_detail_url),
            "detail_back_href": esc(site_href(base_path, "#upcoming")),
            "detail_back_de": "← Zurück zu Demnächst",
            "detail_back_en": "← Back to upcoming",
            "detail_content": upcoming_detail_page(item, site, base_path),
            "detail_navigation": detail_navigation(upcoming, index, "upcoming", site, base_path),
        }
        (output_dir / "index.html").write_text(render(detail_template, detail_values), encoding="utf-8")

    for index, item in enumerate(archive):
        relative_path = detail_relative_path("episode", item, site)
        output_dir = PUBLIC / relative_path
        output_dir.mkdir(parents=True, exist_ok=True)
        canonical_detail_url = absolute_site_url(canonical_url, relative_path)
        detail_values = common_values | {
            "page_title": esc(detail_page_title("episode", item, site)),
            "description": esc(detail_description(item, site)),
            "canonical_url": esc(canonical_detail_url),
            "social_image_url": esc(detail_social_image(item, site, canonical_url, "episode")),
            "social_image_alt": esc(str(item.get("title_de") or site["name"])),
            "og_type": "article",
            "structured_data_html": archive_structured_data(item, site, canonical_url, canonical_detail_url),
            "detail_back_href": esc(site_href(base_path, "#archive")),
            "detail_back_de": "← Zurück zum Sendungsarchiv",
            "detail_back_en": "← Back to the broadcast archive",
            "detail_content": archive_detail_page(item, site, base_path),
            "detail_navigation": detail_navigation(archive, index, "episode", site, base_path),
        }
        (output_dir / "index.html").write_text(render(detail_template, detail_values), encoding="utf-8")

    archive_export = {
        "source": archive_playlist_url,
        "count": len(archive),
        "episodes": [
            {
                "episode_id": episode_id_value(item),
                "date": item["date"],
                "episode_number": episode_number_value(item),
                "title": item["title_de"],
                "summary": content_text(item, "de"),
                "url": absolute_site_url(canonical_url, detail_relative_path("episode", item, site)),
                "audio_url": str(item.get("audio_url") or ""),
                "music_presentations": item.get("music_presentations") or [],
                "tracklist": item.get("tracklist") or [],
            }
            for item in archive
        ],
    }
    (PUBLIC / "archive.json").write_text(
        json.dumps(archive_export, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    feed_items = []
    for item in archive[:50]:
        value = parse_date(str(item["date"]))
        detail_url = absolute_site_url(canonical_url, detail_relative_path("episode", item, site))
        feed_items.append(
            "<item>"
            f"<title>{esc(item['title_de'])}</title>"
            f"<description>{esc(content_text(item, 'de'))}</description>"
            f"<link>{esc(detail_url)}</link>"
            f"<pubDate>{format_datetime(value)}</pubDate>"
            f"<guid isPermaLink=\"true\">{esc(detail_url)}</guid>"
            "</item>"
        )
    feed = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom"><channel>'
        f'<title>{esc(site["name"])}</title>'
        f'<link>{esc(canonical_url)}</link>'
        f'<atom:link href="{esc(canonical_url + "feed.xml")}" rel="self" type="application/rss+xml" />'
        f'<description>{esc(site["description_de"])}</description>'
        '<language>de-DE</language>'
        f'<lastBuildDate>{format_datetime(datetime.now(timezone.utc))}</lastBuildDate>'
        + "".join(feed_items)
        + "</channel></rss>"
    )
    (PUBLIC / "feed.xml").write_text(feed, encoding="utf-8")

    sitemap_entries: list[tuple[str, str | None]] = [
        (canonical_url, None),
        (canonical_url + "impressum.html", None),
        (canonical_url + "datenschutz.html", None),
    ]
    for item in upcoming:
        lastmod = str(item.get("updated_at") or "")[:10] or None
        sitemap_entries.append(
            (absolute_site_url(canonical_url, detail_relative_path("upcoming", item, site)), lastmod)
        )
    cache_lastmod: str | None = None
    try:
        cache_value = read_json(ROOT / "content" / "archive-cache.json")
        cache_lastmod = str(cache_value.get("updated_at") or "")[:10] or None
    except (OSError, json.JSONDecodeError, AttributeError, TypeError):
        cache_lastmod = None
    for item in archive:
        lastmod = str(item.get("updated_at") or "")[:10] or cache_lastmod
        sitemap_entries.append(
            (absolute_site_url(canonical_url, detail_relative_path("episode", item, site)), lastmod)
        )

    sitemap_lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
    seen_urls: set[str] = set()
    for location, lastmod in sitemap_entries:
        if location in seen_urls:
            continue
        seen_urls.add(location)
        sitemap_lines.append("  <url>")
        sitemap_lines.append(f"    <loc>{esc(location)}</loc>")
        if lastmod and re.fullmatch(r"\d{4}-\d{2}-\d{2}", lastmod):
            sitemap_lines.append(f"    <lastmod>{esc(lastmod)}</lastmod>")
        sitemap_lines.append("  </url>")
    sitemap_lines.append("</urlset>")
    (PUBLIC / "sitemap.xml").write_text("\n".join(sitemap_lines) + "\n", encoding="utf-8")
    (PUBLIC / "robots.txt").write_text(
        f"User-agent: *\nAllow: /\nSitemap: {canonical_url}sitemap.xml\n",
        encoding="utf-8",
    )
    (PUBLIC / ".nojekyll").write_text("", encoding="utf-8")
    not_found_template = (ROOT / "templates" / "404.html").read_text(encoding="utf-8")
    (PUBLIC / "404.html").write_text(render(not_found_template, common_values), encoding="utf-8")
    print(
        f"Built {PUBLIC} for {pages_url}: {len(upcoming)} upcoming items, "
        f"{len(archive)} broadcasts and {len(sitemap_entries)} sitemap entries"
    )

if __name__ == "__main__":
    main()
