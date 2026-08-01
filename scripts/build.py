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
from urllib.parse import quote, urlparse

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "public"
MONTHS_DE = ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September", "Oktober", "November", "Dezember"]
MONTHS_EN = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
WEEKDAYS_DE = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]
WEEKDAYS_EN = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
BERLIN_TZ = ZoneInfo("Europe/Berlin")


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


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


def hour_range_clock(start: datetime, end: datetime) -> str:
    """Return a clock-style whole-hour range such as ``21:00–00:00``."""
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


def calendar_event_content(item: dict, site: dict, event_url: str) -> str:
    start = parse_upcoming_date(item["date"])
    end = upcoming_end(item)
    item_type = str(item.get("type") or "broadcast").lower()
    title = str(item.get("title_de") or site["name"])
    summary = str(item.get("summary_de") or "")
    default_location = "Radio Blau, Leipzig" if item_type == "broadcast" else ""
    location = str(item.get("location_de") or item.get("location") or default_location)

    uid_source = f"{start.isoformat()}|{title}"
    uid = hashlib.sha1(uid_source.encode("utf-8")).hexdigest()[:24] + "@sofea.radio"
    now = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    raw_lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//sounds of electronic art//sofea.radio//DE",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "BEGIN:VEVENT",
        f"UID:{uid}",
        f"DTSTAMP:{now}",
        f"DTSTART:{start.astimezone(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        f"DTEND:{end.astimezone(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        f"SUMMARY:{ical_escape(title)}",
    ]
    if summary:
        raw_lines.append(f"DESCRIPTION:{ical_escape(summary)}")
    if location:
        raw_lines.append(f"LOCATION:{ical_escape(location)}")
    stream_url = str(site.get("radio", {}).get("stream_url") or "")
    if item_type == "broadcast" and stream_url:
        raw_lines.append(f"COMMENT:{ical_escape('Livestream: ' + stream_url)}")
    raw_lines.extend([
        f"URL:{ical_escape(event_url)}",
        "STATUS:CONFIRMED",
        "TRANSP:OPAQUE",
        "END:VEVENT",
        "END:VCALENDAR",
    ])

    folded = [part for line in raw_lines for part in fold_ical_line(line)]
    return "\r\n".join(folded) + "\r\n"

def upcoming_end(item: dict) -> datetime:
    start = parse_upcoming_date(item["date"])
    item_type = str(item.get("type") or "broadcast").lower()
    default_hours = 3 if item_type == "broadcast" else 2
    return parse_upcoming_date(item["end"]) if item.get("end") else start + timedelta(
        hours=float(item.get("duration_hours") or default_hours)
    )



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
    custom_slug = str(item.get("slug") or "").strip()
    slug = slugify(custom_slug or title_for_slug)
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


def item_audio_duration(item: dict, site: dict) -> str:
    duration_ms = item.get("duration_ms")
    try:
        if duration_ms not in (None, ""):
            return iso_duration_from_seconds(round(float(duration_ms) / 1000))
    except (TypeError, ValueError):
        pass
    raw = str(item.get("duration") or "").strip()
    if not raw and item.get("audio_url"):
        target = str(item["audio_url"]).rstrip("/")
        for mix in site.get("mixes", []):
            if isinstance(mix, dict) and str(mix.get("url") or "").rstrip("/") == target:
                raw = str(mix.get("duration") or "").strip()
                break
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


def lineup_schema(values: object) -> list[dict]:
    if not isinstance(values, list):
        return []
    performers: list[dict] = []
    for value in values:
        if isinstance(value, dict):
            name = str(value.get("name") or value.get("artist") or value.get("label") or "").strip()
            url = str(value.get("url") or "").strip()
            schema_type = str(value.get("schema_type") or "PerformingGroup").strip()
        else:
            name = str(value).strip()
            url = ""
            schema_type = "PerformingGroup"
        if not name:
            continue
        performer = {"@type": schema_type, "name": name}
        if url:
            performer["sameAs"] = url
        performers.append(performer)
    return performers


def upcoming_structured_data(item: dict, site: dict, canonical_url: str, detail_url: str) -> str:
    start = parse_upcoming_date(str(item["date"]))
    end = upcoming_end(item)
    item_type = str(item.get("type") or "broadcast").lower()
    title = str(item.get("title_de") or site["name"] or "")
    description = detail_description(item, site)
    image = detail_social_image(item, canonical_url)
    if item_type == "event":
        location_name = str(item.get("venue_name") or item.get("location_de") or item.get("location") or "").strip()
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
        }
        if location_name:
            place: dict = {"@type": "Place", "name": location_name}
            address = {
                key: value
                for key, value in {
                    "@type": "PostalAddress",
                    "streetAddress": item.get("street_address"),
                    "postalCode": item.get("postal_code"),
                    "addressLocality": item.get("address_locality"),
                    "addressRegion": item.get("address_region"),
                    "addressCountry": item.get("address_country") or "DE",
                }.items()
                if value not in (None, "")
            }
            if len(address) > 2:
                place["address"] = address
            event["location"] = place
        performers = lineup_schema(item.get("lineup_de") or item.get("lineup"))
        if performers:
            event["performer"] = performers
        if item.get("image") or item.get("image_url"):
            event["image"] = [image]
        external_urls = [
            str(link["url"])
            for link in item.get("links", [])
            if isinstance(link, dict) and link.get("url")
        ]
        if external_urls:
            event["sameAs"] = external_urls
        return json_ld_script(event)

    episode = {
        "@context": "https://schema.org",
        "@graph": [
            {
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
            },
            series_schema(site, canonical_url, compact=True),
        ],
    }
    return json_ld_script(episode)


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
        "image": detail_social_image(item, canonical_url),
    }
    audio_url = str(item.get("audio_url") or "").strip()
    if audio_url:
        audio: dict = {
            "@type": "AudioObject",
            "@id": detail_url.rstrip("/") + "/#audio",
            "name": title,
            "url": audio_url,
            "embedUrl": soundcloud_embed(audio_url),
        }
        duration = item_audio_duration(item, site)
        if duration:
            audio["duration"] = duration
        episode["associatedMedia"] = audio
    data = {
        "@context": "https://schema.org",
        "@graph": [episode, series_schema(site, canonical_url, compact=True)],
    }
    return json_ld_script(data)


def detail_social_image(item: dict, canonical_url: str) -> str:
    raw = str(item.get("image") or item.get("image_url") or "").strip()
    if not raw:
        return absolute_site_url(canonical_url, "assets/images/sofea-social-card-v3.png")
    if raw.startswith(("https://", "http://")):
        return raw
    return absolute_site_url(canonical_url, raw)


def detail_description(item: dict, site: dict) -> str:
    value = (
        item.get("summary_de")
        or item.get("details_de")
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
            main = " — ".join(part for part in [artist, title] if part) or label
            if label and main != label:
                main += f" ({label})"
        else:
            main = str(value).strip()
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


def detail_collection_section(item: dict, field: str, heading_de: str, heading_en: str, ordered: bool = False) -> str:
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


def detail_image(item: dict, base_path: str, title_de: str, title_en: str) -> str:
    src = asset_href(item.get("image") or item.get("image_url"), base_path)
    if not src:
        return ""
    alt_de = str(item.get("image_alt_de") or item.get("image_alt") or title_de)
    alt_en = str(item.get("image_alt_en") or item.get("image_alt") or title_en)
    return (
        '<figure class="detail-image">'
        f'<img src="{esc(src)}" alt="{esc(alt_de)}" loading="lazy" '
        f'data-alt-de="{esc(alt_de)}" data-alt-en="{esc(alt_en)}">'
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
    calendar_href: str,
    heading_tag: str,
    heading_id: str,
) -> str:
    start = parse_upcoming_date(item["date"])
    end = upcoming_end(item)
    item_type = str(item.get("type") or "broadcast").lower()
    title_de = str(item.get("title_de") or site["name"])
    title_en = str(item.get("title_en") or title_de)
    summary_de = str(item.get("summary_de") or "")
    summary_en = str(item.get("summary_en") or summary_de)
    label_de = str(item.get("label_de") or ("Sendung" if item_type == "broadcast" else "Veranstaltung"))
    label_en = str(item.get("label_en") or ("Broadcast" if item_type == "broadcast" else "Event"))
    default_location = "Radio Blau, Leipzig" if item_type == "broadcast" else ""
    location_de = str(item.get("location_de") or item.get("location") or default_location)
    location_en = str(item.get("location_en") or item.get("location") or location_de)
    date_de = date_long(start, "de")
    date_en = date_long(start, "en")
    time_value = hour_range_clock(start, end)

    meta = [
        f'<time datetime="{esc(start.isoformat())}" data-bilingual data-de="{esc(date_de)}" data-en="{esc(date_en)}">{esc(date_de)}</time>',
        f'<span>{esc(time_value)}</span>',
    ]
    if location_de or location_en:
        meta.append(
            f'<span data-bilingual data-de="{esc(location_de)}" data-en="{esc(location_en)}">{esc(location_de)}</span>'
        )

    summary_html = ""
    if summary_de or summary_en:
        summary_html = (
            f'<p class="detail-lead" data-bilingual data-de="{esc(summary_de)}" '
            f'data-en="{esc(summary_en)}">{esc(summary_de)}</p>'
        )

    actions = external_action_links(item)
    actions.append(
        f'<a class="button calendar-button" href="{esc(calendar_href)}" type="text/calendar">'
        '<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">'
        '<path d="M7 3v3M17 3v3M4.5 9h15M5 5.5h14a1 1 0 0 1 1 1V20H4V6.5a1 1 0 0 1 1-1Z"/>'
        '<path d="m9 14 2 2 4-4"/></svg>'
        '<span data-bilingual data-de="Termin speichern" data-en="Save event">Termin speichern</span></a>'
    )

    return (
        '<header class="detail-header">'
        f'<p class="eyebrow" data-bilingual data-de="{esc(label_de)}" data-en="{esc(label_en)}">{esc(label_de)}</p>'
        f'<{heading_tag} id="{esc(heading_id)}" data-bilingual data-de="{esc(title_de)}" '
        f'data-en="{esc(title_en)}">{esc(title_de)}</{heading_tag}>'
        f'<div class="detail-meta">{"".join(meta)}</div>'
        '</header>'
        f'{detail_image(item, base_path, title_de, title_en)}'
        f'{summary_html}'
        f'{localized_prose(item, "details")}'
        f'{detail_collection_section(item, "lineup", "Line-up", "Line-up")}'
        f'{detail_collection_section(item, "tracklist", "Tracklist", "Track list", ordered=True)}'
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
    inner = upcoming_detail_inner(item, site, base_path, calendar_href, "h2", heading_id)
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


def upcoming_detail_page(item: dict, site: dict, base_path: str, calendar_href: str) -> str:
    heading_id = "detail-page-heading"
    inner = upcoming_detail_inner(item, site, base_path, calendar_href, "h1", heading_id)
    return f'<article class="detail-page-card" aria-labelledby="{heading_id}">{inner}</article>'


def archive_detail_inner(
    item: dict,
    site: dict,
    base_path: str,
    heading_tag: str,
    heading_id: str,
) -> str:
    value = parse_date(str(item["date"]))
    title_de = str(item["title_de"])
    title_en = str(item.get("title_en") or title_de)
    summary_de = str(item.get("summary_de") or "")
    summary_en = str(item.get("summary_en") or summary_de)
    date_de = f"{value.day:02d}. {MONTHS_DE[value.month - 1]} {value.year}"
    date_en = f"{value.day:02d} {MONTHS_EN[value.month - 1]} {value.year}"
    summary_html = ""
    if summary_de or summary_en:
        summary_html = (
            f'<p class="detail-lead" data-bilingual data-de="{esc(summary_de)}" '
            f'data-en="{esc(summary_en)}">{esc(summary_de)}</p>'
        )
    actions = external_action_links(item)
    actions.insert(
        0,
        f'<a class="button button-primary" href="{esc(item["audio_url"])}" target="_blank" '
        'rel="noopener noreferrer" data-bilingual data-de="Auf SoundCloud anhören ↗" '
        'data-en="Listen on SoundCloud ↗">Auf SoundCloud anhören ↗</a>',
    )
    return (
        '<header class="detail-header">'
        '<p class="eyebrow" data-bilingual data-de="Sendung" data-en="Broadcast">Sendung</p>'
        f'<{heading_tag} id="{esc(heading_id)}" data-bilingual data-de="{esc(title_de)}" '
        f'data-en="{esc(title_en)}">{esc(title_de)}</{heading_tag}>'
        '<div class="detail-meta">'
        f'<time datetime="{esc(item["date"])}" data-bilingual data-de="{esc(date_de)}" '
        f'data-en="{esc(date_en)}">{esc(date_de)}</time>'
        '</div></header>'
        f'{detail_image(item, base_path, title_de, title_en)}'
        f'{summary_html}'
        f'{localized_prose(item, "details")}'
        f'{detail_collection_section(item, "lineup", "Mitwirkende", "Contributors")}'
        f'{detail_collection_section(item, "tracklist", "Tracklist", "Track list", ordered=True)}'
        f'<div class="detail-actions">{"".join(actions)}</div>'
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
    for item in sorted(items, key=lambda entry: parse_upcoming_date(entry["date"])):
        start = parse_upcoming_date(item["date"])
        item_type = str(item.get("type") or "broadcast").lower()
        end = upcoming_end(item)
        title_de = str(item.get("title_de") or site["name"])
        title_en = str(item.get("title_en") or title_de)
        summary_de = str(item.get("summary_de") or "")
        summary_en = str(item.get("summary_en") or summary_de)
        card_summary_de = card_excerpt(summary_de)
        card_summary_en = card_excerpt(summary_en)
        default_label_de = "Sendung" if item_type == "broadcast" else "Veranstaltung"
        default_label_en = "Broadcast" if item_type == "broadcast" else "Event"
        label_de = str(item.get("label_de") or default_label_de)
        label_en = str(item.get("label_en") or default_label_en)
        default_location = "Radio Blau, Leipzig" if item_type == "broadcast" else ""
        location_de = str(item.get("location_de") or item.get("location") or default_location)
        location_en = str(item.get("location_en") or item.get("location") or location_de)
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

        footer_date_de = date_long(start, "de")
        footer_date_en = date_long(start, "en")
        footer_time = hour_range_clock(start, end)
        footer_parts = [
            (footer_date_de, footer_date_en),
            (footer_time, footer_time),
        ]
        if location_de or location_en:
            footer_parts.append((location_de, location_en))
        footer_html = '<span class="upcoming-footer-separator" aria-hidden="true">·</span>'.join(
            f'<span data-bilingual data-de="{esc(de)}" data-en="{esc(en)}">{esc(de)}</span>'
            for de, en in footer_parts
        )

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
            f'data-de="{esc(title_de)}" data-en="{esc(title_en)}">'
            f'{esc(title_de)}</a></h3>'
            f'{summary_html}'
            '</div>'
            f'<footer class="upcoming-card-footer">{footer_html}</footer>'
            '</div>'
            '</article>'
        )
        dialogs.append(upcoming_detail_dialog(item, site, base_path, calendar_href, detail_url))
    return "".join(rows), "".join(dialogs)

def archive_match_key(item: dict) -> tuple[str, str]:
    date_value = str(item.get("date") or "")[:10]
    title = str(item.get("title_de") or item.get("title") or "")
    return date_value, slugify(title)


def load_archive(episodes: list[dict]) -> list[dict]:
    local_past = [
        item for item in episodes
        if item.get("status") != "upcoming" and item.get("audio_url")
    ]
    local_by_url = {
        str(item["audio_url"]).rstrip("/"): item
        for item in local_past
        if item.get("audio_url")
    }
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
                    "title_de": str(item["title"]),
                    "title_en": str(item["title"]),
                    "summary_de": str(item.get("summary") or ""),
                    "summary_en": str(item.get("summary") or ""),
                    "audio_url": str(item["audio_url"]),
                    "duration_ms": item.get("duration_ms"),
                }
                normalised_url = base["audio_url"].rstrip("/")
                override = local_by_url.get(normalised_url) or local_by_key.get(archive_match_key(base))
                if override:
                    for key, value in override.items():
                        if key in {"status", "date", "audio_url"}:
                            continue
                        base[key] = value
                result.append(base)
                seen_urls.add(normalised_url)
    except (OSError, json.JSONDecodeError, AttributeError, TypeError, ValueError):
        result = []

    for item in local_past:
        normalised_url = str(item["audio_url"]).rstrip("/")
        if normalised_url in seen_urls:
            continue
        result.append(dict(item))
        seen_urls.add(normalised_url)

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
        title_de = str(item["title_de"])
        title_en = str(item.get("title_en") or title_de)
        summary_de = str(item.get("summary_de") or "")
        summary_en = str(item.get("summary_en") or summary_de)
        search_text = " ".join(
            [str(item["date"]), date_de, date_en, title_de, title_en, summary_de, summary_en]
            + flatten_search_values(item.get("details_de"))
            + flatten_search_values(item.get("details_en"))
            + flatten_search_values(item.get("lineup"))
            + flatten_search_values(item.get("tracklist"))
        )
        summary_html = ""
        if summary_de or summary_en:
            summary_html = (
                f'<p data-bilingual data-de="{esc(summary_de)}" data-en="{esc(summary_en)}">{esc(summary_de)}</p>'
            )
        url_hash = hashlib.sha1(str(item["audio_url"]).encode("utf-8")).hexdigest()[:7]
        episode_id = f"episode-{value.strftime('%Y-%m-%d')}-{slugify(title_de)}-{url_hash}"
        dialog_id = detail_identifier("episode", item, site)
        relative_path = detail_relative_path("episode", item, site)
        detail_url = site_href(base_path, relative_path)
        rows.append(
            f'<article class="episode" id="{esc(episode_id)}" data-episode '
            f'data-detail-id="{esc(dialog_id)}" data-search="{esc(search_text)}">'
            f'<time class="episode-date" datetime="{esc(item["date"])}" data-bilingual '
            f'data-de="{esc(date_de)}" data-en="{esc(date_en)}">{esc(date_de)}</time>'
            '<div class="episode-copy">'
            '<div class="episode-title-row">'
            f'<h3><a class="episode-title-link detail-title-link" href="{esc(detail_url)}" data-detail-link '
            f'data-detail-id="{esc(dialog_id)}" data-bilingual data-de="{esc(title_de)}" '
            f'data-en="{esc(title_en)}">{esc(title_de)}</a></h3>'
            '</div>'
            f'{summary_html}</div>'
            f'<a class="episode-link" href="{esc(item["audio_url"])}" target="_blank" '
            'rel="noopener noreferrer" data-i18n="play_recording">Aufnahme abspielen ↗</a>'
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
      <h1 class="legal-title">Datenschutzerklärung</h1>

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
    episodes = read_json(ROOT / "content" / "episodes.json")
    archive = load_archive(episodes)

    pages_url = str(os.environ.get("SITE_URL") or site.get("url") or "http://localhost:8000").rstrip("/")
    parsed = urlparse(pages_url)
    base_path = parsed.path.rstrip("/")
    canonical_url = pages_url + "/"
    home_href = site_href(base_path)

    now_utc = datetime.now(timezone.utc)
    upcoming = sorted(
        [
            item
            for item in episodes
            if item.get("status") == "upcoming"
            and upcoming_end(item).astimezone(timezone.utc) > now_utc
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

    featured_mixes = site["mixes"][:5]
    if not featured_mixes:
        raise ValueError("content/site.json must contain at least one mix")
    mix_rows = []
    for index, mix in enumerate(featured_mixes):
        duration = f'<span class="mix-duration">{esc(mix["duration"])}</span>' if mix.get("duration") else ""
        mix_rows.append(
            f'<button class="mix-item" type="button" role="listitem" data-mix-index="{index}" '
            f'data-title="{esc(mix["title"])}" data-subtitle-de="{esc(mix["subtitle_de"])}" '
            f'data-subtitle-en="{esc(mix["subtitle_en"])}" data-url="{esc(mix["url"])}" '
            f'data-embed="{esc(soundcloud_embed(mix["url"]))}" aria-pressed="{"true" if index == 0 else "false"}">'
            f'<span class="mix-copy"><strong>{esc(mix["title"])}</strong>'
            f'<span data-mix-subtitle>{esc(mix["subtitle_de"])}</span></span>{duration}</button>'
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
    }
    values = common_values | {
        "page_title": esc(site["name"] + " — Radio Blau Leipzig"),
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
        calendar_href = site_href(base_path, f"calendar/{calendar_filename(item, site)}")
        canonical_detail_url = absolute_site_url(canonical_url, relative_path)
        item_type = str(item.get("type") or "broadcast").lower()
        back_de = "← Zurück zu Upcoming"
        back_en = "← Back to upcoming"
        detail_values = common_values | {
            "page_title": esc(detail_page_title("upcoming", item, site)),
            "description": esc(detail_description(item, site)),
            "canonical_url": esc(canonical_detail_url),
            "social_image_url": esc(detail_social_image(item, canonical_url)),
            "social_image_alt": esc(str(item.get("image_alt_de") or item.get("title_de") or site["name"])),
            "og_type": "article" if item_type == "broadcast" else "website",
            "structured_data_html": upcoming_structured_data(
                item, site, canonical_url, canonical_detail_url
            ),
            "detail_back_href": esc(site_href(base_path, "#upcoming")),
            "detail_back_de": esc(back_de),
            "detail_back_en": esc(back_en),
            "detail_content": upcoming_detail_page(item, site, base_path, calendar_href),
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
            "social_image_url": esc(detail_social_image(item, canonical_url)),
            "social_image_alt": esc(str(item.get("image_alt_de") or item.get("title_de") or site["name"])),
            "og_type": "article",
            "structured_data_html": archive_structured_data(
                item, site, canonical_url, canonical_detail_url
            ),
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
                "date": item["date"],
                "title": item["title_de"],
                "summary": item.get("summary_de") or "",
                "url": absolute_site_url(canonical_url, detail_relative_path("episode", item, site)),
                "audio_url": item["audio_url"],
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
            f"<description>{esc(item.get('summary_de') or '')}</description>"
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
