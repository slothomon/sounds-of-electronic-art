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


def hour_range(start: datetime, end: datetime, language: str) -> str:
    """Return a compact whole-hour range such as ``21–0 Uhr``."""
    start_hour = str(start.hour)
    end_hour = str(end.hour)
    suffix = " Uhr" if language == "de" else ""
    return f"{start_hour}–{end_hour}{suffix}"


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


def calendar_event_content(item: dict, site: dict, canonical_url: str) -> str:
    start = parse_upcoming_date(item["date"])
    end = upcoming_end(item)
    item_type = str(item.get("type") or "broadcast").lower()
    title = str(item.get("title_de") or site["name"])
    summary = str(item.get("summary_de") or "")
    default_location = "Radio Blau, Leipzig" if item_type == "broadcast" else ""
    location = str(item.get("location_de") or item.get("location") or default_location)

    links = item.get("links") if isinstance(item.get("links"), list) else []
    event_url = next(
        (str(link.get("url")) for link in links if isinstance(link, dict) and link.get("url")),
        canonical_url + "#upcoming",
    )
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

def upcoming_icon(item_type: str) -> str:
    if item_type == "event":
        return (
            '<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">'
            '<path d="M7 3v3M17 3v3M4.5 9h15M5 5.5h14a1 1 0 0 1 1 1V20H4V6.5a1 1 0 0 1 1-1Z"/>'
            '<path d="M8 13h2M14 13h2M8 17h2M14 17h2"/>'
            '</svg>'
        )
    return (
        '<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">'
        '<circle cx="12" cy="4.3" r="1.1"/>'
        '<path d="M12 5.5 7.6 21h8.8L12 5.5Z"/>'
        '<path d="M9.2 15.4h5.6M8.4 18.2h7.2M9.1 20.7l5-8.5M14.9 20.7l-5-8.5"/>'
        '<path d="M6.8 7.1a7.3 7.3 0 0 0 0 6.2M17.2 7.1a7.3 7.3 0 0 1 0 6.2"/>'
        '<path d="M4.2 4.8a11 11 0 0 0 0 10.6M19.8 4.8a11 11 0 0 1 0 10.6"/>'
        '</svg>'
    )


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


def upcoming_detail_dialog(item: dict, site: dict, base_path: str, calendar_href: str) -> str:
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
    dialog_id = detail_identifier("upcoming", item, site)
    heading_id = f"{dialog_id}-heading"
    date_de = date_long(start, "de")
    date_en = date_long(start, "en")
    time_de = hour_range(start, end, "de")
    time_en = hour_range(start, end, "en")

    meta = [
        f'<time datetime="{esc(start.isoformat())}" data-bilingual data-de="{esc(date_de)}" data-en="{esc(date_en)}">{esc(date_de)}</time>',
        f'<span data-bilingual data-de="{esc(time_de)}" data-en="{esc(time_en)}">{esc(time_de)}</span>',
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
        f'<dialog class="detail-dialog" id="{esc(dialog_id)}" data-detail-dialog aria-labelledby="{esc(heading_id)}">'
        '<article class="detail-dialog-shell">'
        '<button class="detail-close" type="button" data-detail-close '
        'data-label-de="Details schließen" data-label-en="Close details" aria-label="Details schließen">×</button>'
        '<header class="detail-header">'
        f'<p class="eyebrow" data-bilingual data-de="{esc(label_de)}" data-en="{esc(label_en)}">{esc(label_de)}</p>'
        f'<h2 id="{esc(heading_id)}" data-bilingual data-de="{esc(title_de)}" data-en="{esc(title_en)}">{esc(title_de)}</h2>'
        f'<div class="detail-meta">{"".join(meta)}</div>'
        '</header>'
        f'{detail_image(item, base_path, title_de, title_en)}'
        f'{summary_html}'
        f'{localized_prose(item, "details")}'
        f'{detail_collection_section(item, "lineup", "Line-up", "Line-up")}'
        f'{detail_collection_section(item, "tracklist", "Tracklist", "Track list", ordered=True)}'
        f'<div class="detail-actions">{"".join(actions)}</div>'
        '</article></dialog>'
    )


def archive_detail_dialog(item: dict, site: dict, base_path: str) -> str:
    value = parse_date(item["date"])
    title_de = str(item["title_de"])
    title_en = str(item.get("title_en") or title_de)
    summary_de = str(item.get("summary_de") or "")
    summary_en = str(item.get("summary_en") or summary_de)
    dialog_id = detail_identifier("episode", item, site)
    heading_id = f"{dialog_id}-heading"
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
        f'<dialog class="detail-dialog" id="{esc(dialog_id)}" data-detail-dialog aria-labelledby="{esc(heading_id)}">'
        '<article class="detail-dialog-shell">'
        '<button class="detail-close" type="button" data-detail-close '
        'data-label-de="Details schließen" data-label-en="Close details" aria-label="Details schließen">×</button>'
        '<header class="detail-header">'
        '<p class="eyebrow" data-bilingual data-de="Sendung" data-en="Broadcast">Sendung</p>'
        f'<h2 id="{esc(heading_id)}" data-bilingual data-de="{esc(title_de)}" data-en="{esc(title_en)}">{esc(title_de)}</h2>'
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
        '</article></dialog>'
    )


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
        calendar_href = f"calendar/{calendar_filename(item, site)}"

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
            f'<h3><a class="upcoming-title-link detail-title-link" href="#{esc(dialog_id)}" '
            f'data-detail-link data-bilingual data-de="{esc(title_de)}" data-en="{esc(title_en)}">'
            f'{esc(title_de)}</a></h3>'
            f'{summary_html}'
            '</div>'
            f'<footer class="upcoming-card-footer">{footer_html}</footer>'
            '</div>'
            '</article>'
        )
        dialogs.append(upcoming_detail_dialog(item, site, base_path, calendar_href))
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
        rows.append(
            f'<article class="episode" id="{esc(episode_id)}" data-episode '
            f'data-detail-id="{esc(dialog_id)}" data-search="{esc(search_text)}">'
            f'<time class="episode-date" datetime="{esc(item["date"])}" data-bilingual '
            f'data-de="{esc(date_de)}" data-en="{esc(date_en)}">{esc(date_de)}</time>'
            '<div class="episode-copy">'
            '<div class="episode-title-row">'
            f'<h3><a class="episode-title-link detail-title-link" href="#{esc(dialog_id)}" data-detail-link '
            f'data-bilingual data-de="{esc(title_de)}" data-en="{esc(title_en)}">{esc(title_de)}</a></h3>'
            '</div>'
            f'{summary_html}</div>'
            f'<a class="episode-link" href="{esc(item["audio_url"])}" target="_blank" '
            'rel="noopener noreferrer" data-i18n="play_recording">Aufnahme abspielen ↗</a>'
            '</article>'
        )
        dialogs.append(archive_detail_dialog(item, site, base_path))
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

        <h2>4. Eingebettete Inhalte von SoundCloud</h2>
        <p>Im Bereich „Hören“ werden Audioplayer von SoundCloud eingebettet. Beim Laden eines Players stellt der Browser eine direkte Verbindung zu SoundCloud her. Dabei können insbesondere die IP-Adresse, Browser- und Geräteinformationen, die aufgerufene Seite sowie Nutzungsinformationen an SoundCloud übermittelt werden. SoundCloud weist darauf hin, dass bei eingebetteten Playern Nutzungsdaten zu Analysezwecken erhoben und Cookies oder vergleichbare Technologien eingesetzt werden können.</p>
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

        <h2>4. Embedded SoundCloud content</h2>
        <p>The “Listen” section embeds audio players provided by SoundCloud. Loading a player establishes a direct connection between the browser and SoundCloud. This may transmit the IP address, browser and device information, the referring page and usage information. SoundCloud states that embedded players may collect usage information for analytics and may use cookies or similar technologies.</p>
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
    episodes.sort(key=lambda item: parse_date(item["date"]), reverse=True)
    archive = load_archive(episodes)

    pages_url = os.environ.get("SITE_URL") or "http://localhost:8000"
    parsed = urlparse(pages_url)
    base_path = parsed.path.rstrip("/")
    canonical_url = pages_url.rstrip("/") + "/"

    now_utc = datetime.now(timezone.utc)
    upcoming = [
        item for item in episodes
        if item.get("status") == "upcoming"
        and upcoming_end(item).astimezone(timezone.utc) > now_utc
    ]

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
        if "radioblau" not in str(link.get("url", "")).lower()
        and str(link.get("label", "")).strip().lower() != "radio blau"
    )

    featured_mixes = site["mixes"][:5]
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
    archive_playlist_url = site.get("archive_playlist_url", "https://soundcloud.com/sounds-of-electronic-art/sets/sendungen")
    logo_svg = (ROOT / "assets" / "icons" / "logo.svg").read_text(encoding="utf-8")
    template = (ROOT / "templates" / "index.html").read_text(encoding="utf-8")

    upcoming_html, upcoming_dialogs = upcoming_rows(upcoming, site, base_path)
    episodes_html, episode_dialogs = episode_rows(archive, site, base_path)

    values = {
        "page_title": esc(site["name"] + " — Radio Blau Leipzig"),
        "description": esc(site["description_de"]),
        "canonical_url": esc(canonical_url),
        "social_image_url": esc(canonical_url + "assets/images/sofea-social-card-v3.png"),
        "base_path": esc(base_path),
        "logo_svg": logo_svg,
        "radio_stream_url": esc(site["radio"]["stream_url"]),
        "radio_page_url": esc(site["radio"]["url"]),
        "radio_home_url": "https://www.radioblau.de/",
        "upcoming_html": upcoming_html,
        "mixes_html": "".join(mix_rows),
        "first_mix_title": esc(first_mix["title"]),
        "first_mix_subtitle_de": esc(first_mix["subtitle_de"]),
        "first_mix_url": esc(first_mix["url"]),
        "first_mix_embed": esc(soundcloud_embed(first_mix["url"])),
        "team_html": team_html,
        "episodes_html": episodes_html,
        "detail_dialogs_html": upcoming_dialogs + episode_dialogs,
        "social_html": social_html,
        "archive_playlist_url": esc(archive_playlist_url),
        "build_year": str(datetime.now().year),
    }

    if PUBLIC.exists():
        shutil.rmtree(PUBLIC)
    PUBLIC.mkdir(parents=True)
    shutil.copytree(ROOT / "assets", PUBLIC / "assets")
    calendar_dir = PUBLIC / "calendar"
    calendar_dir.mkdir(parents=True, exist_ok=True)
    for item in upcoming:
        filename = calendar_filename(item, site)
        (calendar_dir / filename).write_text(
            calendar_event_content(item, site, canonical_url), encoding="utf-8", newline=""
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
        current_values = values | {key: esc(value) if key != "legal_content" else value for key, value in page_values.items()}
        (PUBLIC / filename).write_text(render(legal_template, current_values), encoding="utf-8")
    archive_export = {
        "source": archive_playlist_url,
        "count": len(archive),
        "episodes": [
            {
                "date": item["date"],
                "title": item["title_de"],
                "summary": item.get("summary_de") or "",
                "audio_url": item["audio_url"],
            }
            for item in archive
        ],
    }
    (PUBLIC / "archive.json").write_text(
        json.dumps(archive_export, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    feed_items = []
    feed_records = [
        {
            "date": item["date"],
            "title": item["title_de"],
            "summary": item.get("summary_de") or "",
            "url": item.get("audio_url") or canonical_url,
        }
        for item in archive
    ]
    for item in feed_records:
        value = parse_date(item["date"])
        feed_items.append(
            "<item>"
            f"<title>{esc(item['title'])}</title>"
            f"<description>{esc(item['summary'])}</description>"
            f"<link>{esc(item['url'])}</link>"
            f"<pubDate>{format_datetime(value)}</pubDate>"
            f"<guid isPermaLink=\"false\">sofea-{value.strftime('%Y%m%d')}-{hashlib.sha1(item['title'].encode('utf-8')).hexdigest()[:12]}</guid>"
            "</item>"
        )
    feed = (
        '<?xml version="1.0" encoding="UTF-8"?>\n<rss version="2.0"><channel>'
        f'<title>{esc(site["name"])}</title><link>{esc(canonical_url)}</link>'
        f'<description>{esc(site["description_de"])}</description>'
        + "".join(feed_items)
        + "</channel></rss>"
    )
    (PUBLIC / "feed.xml").write_text(feed, encoding="utf-8")
    sitemap = (
        '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        f'<url><loc>{esc(canonical_url)}</loc></url>'
        f'<url><loc>{esc(canonical_url + "impressum.html")}</loc></url>'
        f'<url><loc>{esc(canonical_url + "datenschutz.html")}</loc></url>'
        '</urlset>'
    )
    (PUBLIC / "sitemap.xml").write_text(sitemap, encoding="utf-8")
    (PUBLIC / "robots.txt").write_text(
        f"User-agent: *\nAllow: /\nSitemap: {canonical_url}sitemap.xml\n", encoding="utf-8"
    )
    (PUBLIC / ".nojekyll").write_text("", encoding="utf-8")
    not_found_template = (ROOT / "templates" / "404.html").read_text(encoding="utf-8")
    (PUBLIC / "404.html").write_text(render(not_found_template, values), encoding="utf-8")
    print(f"Built {PUBLIC} for {pages_url} with {len(archive)} cached broadcasts")


if __name__ == "__main__":
    main()
