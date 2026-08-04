#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import html
import json
import os
import re
import shutil
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from PIL import Image, ImageDraw, ImageFont, ImageOps
from urllib.parse import quote, urlparse

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "public"
EPISODE_ARTWORK_DIR = ROOT / "assets" / "images" / "episodes"
ARTWORK_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp")
RESPONSIVE_ARTWORK_WIDTHS = (480, 800, 1200)
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


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def slugify(value: str) -> str:
    value = value.lower()
    replacements = {"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"}
    for source, target in replacements.items():
        value = value.replace(source, target)
    value = "".join(char if char.isalnum() else "-" for char in value)
    return "-".join(part for part in value.split("-") if part)[:80] or "sendung"


def card_excerpt(value: str, limit: int = 100) -> str:
    """Return a compact card excerpt while preserving the full detail text."""
    normalized = " ".join(str(value or "").split())
    if len(normalized) <= limit:
        return normalized
    shortened = normalized[: limit + 1].rsplit(" ", 1)[0].rstrip(" .,;:–—-")
    return (shortened or normalized[:limit].rstrip()) + "…"


def content_text(item: dict, language: str = "de") -> str:
    """Return the single editorial text used for cards and detail pages.

    ``details_*`` is the current field. ``summary_*`` remains a compatibility
    fallback for older entries and the imported SoundCloud cache.
    """
    primary = str(item.get(f"details_{language}") or item.get(f"summary_{language}") or "").strip()
    if primary:
        return primary
    if language == "en":
        return str(item.get("details_de") or item.get("summary_de") or "").strip()
    return str(item.get("summary") or "").strip()


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


def calendar_filename(item: dict, site: dict) -> str:
    start = parse_upcoming_date(item["date"])
    title = str(item.get("title_de") or site["name"])
    return f"{start.strftime('%Y-%m-%d')}-{slugify(title)}.ics"


def ical_escape(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace("\r\n", "\\n")
        .replace("\n", "\\n")
        .replace(";", "\\;")
        .replace(",", "\\,")
    )


def fold_ical_line(line: str, limit: int = 73) -> list[str]:
    """Fold iCalendar lines without splitting UTF-8 characters."""
    lines: list[str] = []
    current = ""
    current_bytes = 0
    for char in line:
        char_bytes = len(char.encode("utf-8"))
        if current and current_bytes + char_bytes > limit:
            lines.append(current)
            current = " " + char
            current_bytes = 1 + char_bytes
        else:
            current += char
            current_bytes += char_bytes
    lines.append(current)
    return lines


def calendar_event_lines(item: dict, site: dict, event_url: str, dtstamp: str) -> list[str]:
    start = parse_upcoming_date(str(item["date"]))
    end = upcoming_end(item)
    item_type = str(item.get("type") or "broadcast").lower()
    title = str(item.get("title_de") or site["name"])
    summary = content_text(item, "de")
    default_location = "Radio Blau, Leipzig" if item_type == "broadcast" else ""
    location = str(item.get("location") or default_location)

    uid_source = f"{start.isoformat()}|{title}"
    uid = hashlib.sha1(uid_source.encode("utf-8")).hexdigest()[:24] + "@sofea.radio"
    raw_lines = [
        "BEGIN:VEVENT",
        f"UID:{uid}",
        f"DTSTAMP:{dtstamp}",
        f"DTSTART:{start.astimezone(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        f"DTEND:{end.astimezone(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        f"SUMMARY:{ical_escape(title)}",
    ]
    stream_url = str(site.get("radio", {}).get("stream_url") or "https://www.radioblau.de/stream/")
    calendar_footer = (
        "-----\n\n"
        "Radio Blau erreicht ihr auf DAB+, sowie\n"
        "UKW 99,2 MHz, 94,4 MHz & 89,2 MHz\n\n"
        "LiveStream:\n"
        f"{stream_url}"
    )
    description = f"{summary}\n\n{calendar_footer}" if summary else calendar_footer
    raw_lines.append(f"DESCRIPTION:{ical_escape(description)}")
    if location:
        raw_lines.append(f"LOCATION:{ical_escape(location)}")
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
    if item.get("end"):
        return parse_upcoming_date(str(item["end"]))
    return start + timedelta(hours=3 if item_type == "broadcast" else 2)

def detail_identifier(kind: str, item: dict, site: dict) -> str:
    title = str(item.get("title_de") or item.get("title") or site["name"])
    if kind == "upcoming":
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
    slug = slugify(title_for_slug)
    if kind == "upcoming":
        date_part = parse_upcoming_date(str(item["date"])).strftime("%Y-%m-%d")
        folder = "termine"
    else:
        date_part = parse_date(str(item["date"])).strftime("%Y-%m-%d")
        folder = "sendungen"
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


def item_audio_duration(item: dict) -> str:
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

def episode_number_value(item: dict) -> int | None:
    value = item.get("episode_number")
    if value in (None, ""):
        return None
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None

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

    episode: dict = {
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
    if number:
        episode["episodeNumber"] = number
    data = {
        "@context": "https://schema.org",
        "@graph": [episode, series_schema(site, canonical_url, compact=True)],
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
    if number:
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
    number = episode_number_value(item) if item_type == "broadcast" else None
    label = "VERANSTALTUNG" if item_type == "event" else "SENDUNG"
    if number:
        label += f" {number}"
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
    default_location = "Radio Blau, Leipzig" if item_type == "broadcast" else ""
    location = str(item.get("location") or default_location).strip()
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
        path = urlparse(raw).path.lower()
        if not path.endswith(".png"):
            raise ValueError(f"social_image must be a PNG file: {raw}")
        if raw.startswith(("https://", "http://")):
            return raw
        return absolute_site_url(canonical_url, raw)
    return absolute_site_url(canonical_url, social_card_relative_path(kind, item, site))

def detail_description(item: dict, site: dict) -> str:
    value = (
        item.get("details_de")
        or item.get("summary_de")
        or item.get("summary")
        or site.get("description_de")
        or site["name"]
    )
    return meta_excerpt(value, 160)


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


def text_paragraphs(value: object) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    paragraphs = []
    for paragraph in raw.replace("\r\n", "\n").split("\n\n"):
        paragraph = paragraph.strip()
        if paragraph:
            paragraphs.append(f"<p>{esc(paragraph).replace(chr(10), '<br>')}</p>")
    return "".join(paragraphs)


def detail_text_blocks(item: dict) -> str:
    de_value = content_text(item, "de")
    en_value = content_text(item, "en")
    if not de_value and not en_value:
        return ""
    return (
        f'<div class="detail-prose" data-language-panel="de">{text_paragraphs(de_value)}</div>'
        f'<div class="detail-prose" data-language-panel="en" hidden>{text_paragraphs(en_value)}</div>'
    )

def shared_list(item: dict, field: str) -> list:
    value = item.get(field)
    return list(value) if isinstance(value, list) else []

def tracklist_items(values: list) -> str:
    rows = []
    for value in values:
        if isinstance(value, dict):
            artist = str(value.get("artist") or "").strip()
            title = str(value.get("title") or "").strip()
            timecode = str(value.get("time") or "").strip()
            label = str(value.get("label") or "").strip()
            url = str(value.get("url") or "").strip()
            main = " – ".join(part for part in [artist, title] if part)
            if label and main:
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
            artist = str(value.get("artist") or "").strip()
            title = str(value.get("title") or "").strip()
            label = str(value.get("label") or "").strip()
            year = str(value.get("year") or "").strip()
            url = str(value.get("url") or "").strip()
            note = str(value.get(f"note_{language}") or "").strip()
            main = " – ".join(part for part in [artist, title] if part)
            meta = " · ".join(part for part in [label, year] if part)
        else:
            main = str(value).strip().replace(" — ", " – ").replace(" - ", " – ")
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
    values = shared_list(item, "music_presentations")
    de_rows = music_presentation_items(values, "de")
    en_rows = music_presentation_items(values, "en")
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
    rows = tracklist_items(shared_list(item, "tracklist"))
    if not rows:
        return ""
    return (
        '<section class="detail-section">'
        '<h3>Tracklist</h3>'
        f'<ol class="detail-tracklist">{rows}</ol>'
        '</section>'
    )

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

def local_asset_path(value: str) -> Path | None:
    raw = str(value or "").strip()
    if not raw or raw.startswith(("https://", "http://", "data:")):
        return None
    candidate = (ROOT / raw.lstrip("/")).resolve()
    try:
        candidate.relative_to(ROOT.resolve())
    except ValueError:
        return None
    return candidate if candidate.is_file() else None


def responsive_artwork_widths(source: Path) -> list[int]:
    try:
        with Image.open(source) as opened:
            width = int(opened.width)
    except (OSError, ValueError):
        return []
    if width <= 0:
        return []
    return sorted({candidate for candidate in RESPONSIVE_ARTWORK_WIDTHS if candidate < width} | {width})


def responsive_artwork_entries(item: dict, base_path: str) -> list[tuple[str, int]]:
    source = local_asset_path(detail_image_source(item))
    if not source:
        return []
    stem = episode_artwork_stem(item)
    return [
        (site_href(base_path, f"assets/images/episodes/responsive/{stem}-{width}.webp"), width)
        for width in responsive_artwork_widths(source)
    ]


def write_responsive_artwork(items: list[dict]) -> None:
    target_dir = PUBLIC / "assets" / "images" / "episodes" / "responsive"
    target_dir.mkdir(parents=True, exist_ok=True)
    seen: set[str] = set()
    for item in items:
        local = local_asset_path(detail_image_source(item))
        if not local:
            continue
        stem = episode_artwork_stem(item)
        if stem in seen:
            continue
        seen.add(stem)
        try:
            with Image.open(local) as opened:
                image = ImageOps.exif_transpose(opened).convert("RGB")
                for width in responsive_artwork_widths(local):
                    if image.width == width:
                        resized = image.copy()
                    else:
                        height = max(1, round(image.height * width / image.width))
                        resized = image.resize((width, height), Image.Resampling.LANCZOS)
                    resized.save(target_dir / f"{stem}-{width}.webp", "WEBP", quality=84, method=6)
        except (OSError, ValueError):
            continue


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
    variants = responsive_artwork_entries(item, base_path)
    srcset = ""
    sizes = ""
    if variants:
        srcset = ' srcset="' + esc(", ".join(f"{url} {width}w" for url, width in variants)) + '"'
        sizes = ' sizes="(max-width: 720px) 62vw, (max-width: 1100px) 42vw, 520px"'
    return (
        '<figure class="detail-image detail-artwork">'
        f'<img src="{esc(src)}"{srcset}{sizes} alt="{esc(title_de)}" loading="lazy" decoding="async" '
        f'data-alt-de="{esc(title_de)}" data-alt-en="{esc(title_en)}">'
        '</figure>'
    )

def share_button(url: str, title_de: str, title_en: str) -> str:
    return (
        '<button class="button share-button" type="button" data-share-button '
        f'data-share-url="{esc(url)}" data-share-title-de="{esc(title_de)}" '
        f'data-share-title-en="{esc(title_en)}">'
        '<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">'
        '<circle cx="18" cy="5" r="2.5"/><circle cx="6" cy="12" r="2.5"/>'
        '<circle cx="18" cy="19" r="2.5"/><path d="m8.2 10.8 7.6-4.5M8.2 13.2l7.6 4.5"/>'
        '</svg>'
        '<span data-share-label data-bilingual data-de="Teilen" data-en="Share">Teilen</span>'
        '<span class="share-status" data-share-status aria-live="polite"></span>'
        '</button>'
    )


def external_action_links(item: dict) -> list[str]:
    links = item.get("links") if isinstance(item.get("links"), list) else []
    actions = []
    for link in links:
        if not isinstance(link, dict) or not link.get("url"):
            continue
        label_de = str(link.get("label_de") or "Details")
        label_en = str(link.get("label_en") or label_de)
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
    calendar_href: str,
    detail_url: str,
    heading_tag: str,
    heading_id: str,
) -> str:
    start = parse_upcoming_date(str(item["date"]))
    end = upcoming_end(item)
    item_type = str(item.get("type") or "broadcast").lower()
    title_de = str(item.get("title_de") or site["name"])
    title_en = str(item.get("title_en") or title_de)
    number = episode_number_value(item) if item_type == "broadcast" else None
    label_de = f"Sendung {number}" if number else ("Sendung" if item_type == "broadcast" else "Veranstaltung")
    label_en = f"Broadcast {number}" if number else ("Broadcast" if item_type == "broadcast" else "Event")
    default_location = "Radio Blau, Leipzig" if item_type == "broadcast" else ""
    location = str(item.get("location") or default_location)
    date_de = date_long(start, "de")
    date_en = date_long(start, "en")
    time_de = hour_range_clock(start, end, "de")
    time_en = hour_range_clock(start, end, "en")

    meta = [
        f'<time datetime="{esc(start.isoformat())}" data-bilingual data-de="{esc(date_de)}" data-en="{esc(date_en)}">{esc(date_de)}</time>',
        f'<span data-bilingual data-de="{esc(time_de)}" data-en="{esc(time_en)}">{esc(time_de)}</span>',
    ]
    if location:
        meta.append(f'<span>{esc(location)}</span>')

    actions = external_action_links(item)
    actions.append(share_button(detail_url, title_de, title_en))
    actions.append(
        f'<a class="button calendar-button" href="{esc(calendar_href)}" type="text/calendar">'
        '<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">'
        '<path d="M7 3v3M17 3v3M4.5 9h15M5 5.5h14a1 1 0 0 1 1 1V20H4V6.5a1 1 0 0 1 1-1Z"/>'
        '<path d="m9 14 2 2 4-4"/></svg>'
        '<span data-bilingual data-de="Termin speichern" data-en="Save event">Termin speichern</span></a>'
    )

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
        f'{detail_text_blocks(item)}'
        f'<div class="detail-actions">{"".join(actions)}</div>'
    )

def upcoming_detail_dialog(
    item: dict,
    site: dict,
    base_path: str,
    calendar_href: str,
    detail_url: str,
) -> str:
    dialog_id = detail_identifier("upcoming", item, site)
    heading_id = f"{dialog_id}-heading"
    title_de = str(item.get("title_de") or site["name"])
    page_title = f"{title_de} | {site['name']}"
    inner = upcoming_detail_inner(item, site, base_path, calendar_href, detail_url, "h2", heading_id)
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
    calendar_href: str,
    detail_url: str,
) -> str:
    heading_id = "detail-page-heading"
    inner = upcoming_detail_inner(item, site, base_path, calendar_href, detail_url, "h1", heading_id)
    return f'<article class="detail-page-card" aria-labelledby="{heading_id}">{inner}</article>'

def archive_detail_inner(
    item: dict,
    site: dict,
    base_path: str,
    detail_url: str,
    heading_tag: str,
    heading_id: str,
) -> str:
    value = parse_date(str(item["date"]))
    title_de = clean_archive_title(item["title_de"])
    title_en = clean_archive_title(item.get("title_en") or title_de)
    number = episode_number_value(item)
    label_de = f"Sendung {number}" if number else "Sendung"
    label_en = f"Broadcast {number}" if number else "Broadcast"
    date_de = f"{value.day:02d}. {MONTHS_DE[value.month - 1]} {value.year}"
    date_en = f"{value.day:02d} {MONTHS_EN[value.month - 1]} {value.year}"
    actions = [
        f'<a class="button button-primary" href="{esc(item["audio_url"])}" target="_blank" '
        'rel="noopener noreferrer" data-bilingual data-de="Auf SoundCloud anhören ↗" '
        'data-en="Listen on SoundCloud ↗">Auf SoundCloud anhören ↗</a>',
        share_button(detail_url, title_de, title_en),
    ]
    header_html = (
        '<header class="detail-header">'
        f'<p class="eyebrow" data-bilingual data-de="{esc(label_de)}" data-en="{esc(label_en)}">{esc(label_de)}</p>'
        f'<{heading_tag} id="{esc(heading_id)}" data-bilingual data-de="{esc(title_de)}" '
        f'data-en="{esc(title_en)}">{esc(title_de)}</{heading_tag}>'
        '<div class="detail-meta">'
        f'<time datetime="{esc(item["date"])}" data-bilingual data-de="{esc(date_de)}" '
        f'data-en="{esc(date_en)}">{esc(date_de)}</time>'
        '</div></header>'
    )
    image_html = detail_image(item, base_path, title_de, title_en)
    return (
        f'{detail_intro(header_html, image_html, "")}'
        f'{detail_text_blocks(item)}'
        f'{music_presentations_section(item)}'
        f'{tracklist_section(item)}'
        f'<div class="detail-actions">{"".join(actions)}</div>'
    )

def archive_detail_dialog(item: dict, site: dict, base_path: str, detail_url: str) -> str:
    dialog_id = detail_identifier("episode", item, site)
    heading_id = f"{dialog_id}-heading"
    title_de = str(item["title_de"])
    page_title = f"{title_de} | {site['name']}"
    inner = archive_detail_inner(item, site, base_path, detail_url, "h2", heading_id)
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

def archive_detail_page(item: dict, site: dict, base_path: str, detail_url: str) -> str:
    heading_id = "detail-page-heading"
    inner = archive_detail_inner(item, site, base_path, detail_url, "h1", heading_id)
    return f'<article class="detail-page-card" aria-labelledby="{heading_id}">{inner}</article>'

def upcoming_rows(items: list[dict], site: dict, base_path: str) -> tuple[str, str]:
    if not items:
        return (
            '<p class="upcoming-empty" data-bilingual '
            'data-de="Aktuell sind keine Termine eingetragen." '
            'data-en="No upcoming dates are currently listed.">Aktuell sind keine Termine eingetragen.</p>',
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
        number = episode_number_value(item) if item_type == "broadcast" else None
        label_de = f"Sendung {number}" if number else ("Sendung" if item_type == "broadcast" else "Veranstaltung")
        label_en = f"Broadcast {number}" if number else ("Broadcast" if item_type == "broadcast" else "Event")
        summary_de = content_text(item, "de")
        summary_en = content_text(item, "en")
        card_summary_de = card_excerpt(summary_de)
        card_summary_en = card_excerpt(summary_en)
        default_location = "Radio Blau, Leipzig" if item_type == "broadcast" else ""
        location = str(item.get("location") or default_location)
        dialog_id = detail_identifier("upcoming", item, site)
        relative_path = detail_relative_path("upcoming", item, site)
        detail_url = site_href(base_path, relative_path)
        calendar_href = site_href(base_path, f"calendar/{calendar_filename(item, site)}")

        summary_html = ""
        if card_summary_de or card_summary_en:
            summary_html = (
                f'<p class="upcoming-summary" data-bilingual data-de="{esc(card_summary_de)}" '
                f'data-en="{esc(card_summary_en)}">{esc(card_summary_de)}</p>'
            )
        footer_parts = [
            (date_long(start, "de"), date_long(start, "en")),
            (hour_range_clock(start, end, "de"), hour_range_clock(start, end, "en")),
        ]
        if location:
            footer_parts.append((location, location))
        footer_html = '<span class="upcoming-footer-separator" aria-hidden="true">·</span>'.join(
            f'<span data-bilingual data-de="{esc(de)}" data-en="{esc(en)}">{esc(de)}</span>'
            for de, en in footer_parts
        )
        calendar_button = (
            f'<a class="button calendar-button upcoming-calendar-button" href="{esc(calendar_href)}" type="text/calendar">'
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
            f'<span class="upcoming-year">{start.year}</span></div>'
            '<div class="upcoming-copy"><div class="upcoming-card-header">'
            f'<p class="eyebrow" data-bilingual data-de="{esc(label_de)}" data-en="{esc(label_en)}">{esc(label_de)}</p>'
            f'{calendar_button}</div><div class="upcoming-card-body">'
            f'<h3><a class="upcoming-title-link detail-title-link" href="{esc(detail_url)}" '
            f'data-detail-link data-detail-id="{esc(dialog_id)}" data-bilingual data-de="{esc(title_de)}" '
            f'data-en="{esc(title_en)}">{esc(title_de)}</a></h3>{summary_html}</div>'
            f'<footer class="upcoming-card-footer">{footer_html}</footer></div></article>'
        )
        dialogs.append(upcoming_detail_dialog(item, site, base_path, calendar_href, detail_url))
    return "".join(rows), "".join(dialogs)

def archive_match_key(item: dict) -> tuple[str, str]:
    date_value = str(item.get("date") or "")[:10]
    title = str(item.get("title_de") or item.get("title") or "")
    return date_value, slugify(title)


def load_archive(episodes: list[dict]) -> list[dict]:
    local_past = [item for item in episodes if item.get("audio_url")]
    local_by_url = {str(item["audio_url"]).rstrip("/"): item for item in local_past}
    local_by_key = {archive_match_key(item): item for item in local_past}
    result: list[dict] = []
    seen_urls: set[str] = set()

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
                    "title_de": clean_archive_title(item["title"]),
                    "title_en": clean_archive_title(item["title"]),
                    "summary_de": str(item.get("summary") or ""),
                    "summary_en": str(item.get("summary") or ""),
                    "audio_url": str(item["audio_url"]),
                    "duration_ms": item.get("duration_ms"),
                    "image": str(item.get("image") or ""),
                    "artwork_url": str(item.get("artwork_url") or ""),
                }
                normalised_url = base["audio_url"].rstrip("/")
                override = local_by_url.get(normalised_url) or local_by_key.get(archive_match_key(base))
                if override:
                    for key, value in override.items():
                        if key in {"date", "audio_url"}:
                            continue
                        base[key] = value
                base["title_de"] = clean_archive_title(base.get("title_de"))
                base["title_en"] = clean_archive_title(base.get("title_en") or base["title_de"])
                if not base.get("image"):
                    base["image"] = local_episode_artwork(base)
                result.append(base)
                seen_urls.add(normalised_url)
    except (OSError, json.JSONDecodeError, AttributeError, TypeError, ValueError):
        result = []

    for item in local_past:
        normalised_url = str(item["audio_url"]).rstrip("/")
        if normalised_url in seen_urls:
            continue
        local_item = dict(item)
        local_item["title_de"] = clean_archive_title(local_item.get("title_de"))
        local_item["title_en"] = clean_archive_title(local_item.get("title_en") or local_item["title_de"])
        if not local_item.get("image"):
            local_item["image"] = local_episode_artwork(local_item)
        result.append(local_item)
        seen_urls.add(normalised_url)
    return sorted(result, key=lambda item: parse_date(str(item["date"])), reverse=True)

def normalise_audio_url(value: object) -> str:
    return str(value or "").strip().rstrip("/")


def duration_clock(item: dict) -> str:
    try:
        milliseconds = int(item.get("duration_ms") or 0)
    except (TypeError, ValueError):
        milliseconds = 0
    if milliseconds <= 0:
        return ""
    total = round(milliseconds / 1000)
    hours, remainder = divmod(total, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours}:{minutes:02d}:{seconds:02d}" if hours else f"{minutes}:{seconds:02d}"


def featured_audio_items(site: dict, archive: list[dict]) -> list[dict]:
    requested = site.get("featured_audio_urls")
    if not isinstance(requested, list) or not requested:
        raise ValueError("content/site.json must contain featured_audio_urls")
    by_url = {normalise_audio_url(item.get("audio_url")): item for item in archive}
    result: list[dict] = []
    missing: list[str] = []
    for raw in requested[:5]:
        url = normalise_audio_url(raw)
        item = by_url.get(url)
        if not item:
            missing.append(url)
            continue
        result.append({
            "title": clean_archive_title(item.get("title_de") or item.get("title") or "Sendung"),
            "subtitle_de": content_text(item, "de"),
            "subtitle_en": content_text(item, "en"),
            "duration": duration_clock(item),
            "url": str(item["audio_url"]),
        })
    if missing:
        raise ValueError("Featured audio URL(s) not found in archive: " + ", ".join(missing))
    if not result:
        raise ValueError("No featured audio entries could be resolved")
    return result


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
        )
        summary_html = ""
        if card_summary_de or card_summary_en:
            summary_html = (
                f'<p data-bilingual data-de="{esc(card_summary_de)}" data-en="{esc(card_summary_en)}">{esc(card_summary_de)}</p>'
            )
        url_hash = hashlib.sha1(str(item["audio_url"]).encode("utf-8")).hexdigest()[:7]
        episode_id = f"episode-{value.strftime('%Y-%m-%d')}-{slugify(title_de)}-{url_hash}"
        dialog_id = detail_identifier("episode", item, site)
        relative_path = detail_relative_path("episode", item, site)
        detail_url = site_href(base_path, relative_path)
        rows.append(
            f'<article class="episode" id="{esc(episode_id)}" data-episode data-detail-id="{esc(dialog_id)}" '
            f'data-search="{esc(search_text)}">'
            f'<time class="episode-date" datetime="{esc(item["date"])}" data-bilingual '
            f'data-de="{esc(date_de)}" data-en="{esc(date_en)}">{esc(date_de)}</time>'
            '<div class="episode-copy"><div class="episode-title-row">'
            f'<h3><a class="episode-title-link detail-title-link" href="{esc(detail_url)}" data-detail-link '
            f'data-detail-id="{esc(dialog_id)}" data-bilingual data-de="{esc(title_de)}" '
            f'data-en="{esc(title_en)}">{esc(title_de)}</a></h3></div>{summary_html}</div>'
            f'<a class="episode-link" href="{esc(item["audio_url"])}" target="_blank" rel="noopener noreferrer" '
            'data-i18n="play_recording">Aufnahme abspielen ↗</a></article>'
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

def main() -> None:
    site = read_json(ROOT / "content" / "site.json")
    legal = read_json(ROOT / "content" / "legal.json")
    archive_entries = read_json_list(ROOT / "content" / "episodes.json")
    broadcast_entries = [
        dict(item, type="broadcast")
        for item in read_json_list(ROOT / "content" / "upcoming-broadcasts.json")
    ]
    event_entries = [
        dict(item, type="event")
        for item in read_json_list(ROOT / "content" / "upcoming-events.json")
    ]
    archive = load_archive(archive_entries)

    pages_url = str(os.environ.get("SITE_URL") or site.get("url") or "http://localhost:8000").rstrip("/")
    parsed = urlparse(pages_url)
    base_path = parsed.path.rstrip("/")
    canonical_url = pages_url + "/"
    home_href = site_href(base_path)

    now_utc = datetime.now(timezone.utc)
    upcoming = sorted(
        [
            item
            for item in broadcast_entries + event_entries
            if upcoming_end(item).astimezone(timezone.utc) > now_utc
        ],
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

    featured_mixes = featured_audio_items(site, archive)
    mix_rows = []
    for index, mix in enumerate(featured_mixes):
        duration = f'<span class="mix-duration">{esc(mix["duration"])}</span>' if mix.get("duration") else ""
        mix_rows.append(
            f'<button class="mix-item" type="button" role="listitem" data-mix-index="{index}" '
            f'data-title="{esc(mix["title"])}" data-subtitle-de="{esc(mix["subtitle_de"])}" '
            f'data-subtitle-en="{esc(mix["subtitle_en"])}" data-url="{esc(mix["url"])}" '
            f'data-embed="{esc(soundcloud_embed(mix["url"]))}" aria-pressed="{"true" if index == 0 else "false"}" '
            'aria-expanded="false" aria-controls="recording-player-panel">'
            f'<span class="mix-copy"><strong>{esc(mix["title"])}</strong>'
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

    upcoming_html, upcoming_dialogs = upcoming_rows(upcoming, site, base_path)
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
    }
    values = common_values | {
        "page_title": esc("sounds of electronic art – elektronische musik & klubkultur"),
        "description": esc(site["description_de"]),
        "canonical_url": esc(canonical_url),
        "structured_data_html": homepage_structured_data(site, canonical_url),
        "upcoming_html": upcoming_html,
        "mixes_html": "".join(mix_rows),
        "first_mix_title": esc(first_mix["title"]),
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
    shutil.copytree(ROOT / "assets", PUBLIC / "assets")
    write_responsive_artwork(upcoming + archive)
    write_social_cards(upcoming, archive, site)
    (PUBLIC / "calendar.ics").write_text(
        calendar_feed_content(upcoming, site, canonical_url), encoding="utf-8", newline=""
    )

    calendar_dir = PUBLIC / "calendar"
    calendar_dir.mkdir(parents=True, exist_ok=True)
    for item in upcoming:
        filename = calendar_filename(item, site)
        detail_url = absolute_site_url(canonical_url, detail_relative_path("upcoming", item, site))
        (calendar_dir / filename).write_text(
            calendar_event_content(item, site, detail_url), encoding="utf-8", newline=""
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
        calendar_href = site_href(base_path, f"calendar/{calendar_filename(item, site)}")
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
            "detail_content": upcoming_detail_page(
                item, site, base_path, calendar_href, canonical_detail_url
            ),
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
            "detail_content": archive_detail_page(item, site, base_path, canonical_detail_url),
            "detail_navigation": detail_navigation(archive, index, "episode", site, base_path),
        }
        (output_dir / "index.html").write_text(render(detail_template, detail_values), encoding="utf-8")

    archive_export = {
        "source": archive_playlist_url,
        "count": len(archive),
        "episodes": [
            {
                "date": item["date"],
                "episode_number": episode_number_value(item),
                "title": item["title_de"],
                "summary": content_text(item, "de"),
                "url": absolute_site_url(canonical_url, detail_relative_path("episode", item, site)),
                "audio_url": item["audio_url"],
                "image": item.get("image") or "",
                "music_presentations": item.get("music_presentations") or [],
                "tracklist": item.get("tracklist") or [],
            }
            for item in archive
        ],
    }
    (PUBLIC / "archive.json").write_text(
        json.dumps(archive_export, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
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
        f"User-agent: *\nAllow: /\nSitemap: {canonical_url}sitemap.xml\n", encoding="utf-8"
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
