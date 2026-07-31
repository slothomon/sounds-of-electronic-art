#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import html
import json
import os
import shutil
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from pathlib import Path
from urllib.parse import quote, urlparse

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "public"
MONTHS_DE = ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September", "Oktober", "November", "Dezember"]
MONTHS_EN = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
WEEKDAYS_DE = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]
WEEKDAYS_EN = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def parse_date(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def render(template: str, values: dict[str, str]) -> str:
    for key, value in values.items():
        template = template.replace("{{ " + key + " }}", value)
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


def calendar_url(title: str, start: datetime, end: datetime, summary: str, location: str) -> str:
    start_value = start.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    end_value = end.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return (
        "https://calendar.google.com/calendar/render?action=TEMPLATE"
        f"&text={quote(title)}&dates={start_value}/{end_value}"
        f"&details={quote(summary)}&location={quote(location)}"
    )


def upcoming_rows(items: list[dict], site: dict) -> str:
    if not items:
        return (
            '<p class="upcoming-empty" data-bilingual '
            'data-de="Aktuell sind keine Termine eingetragen." '
            'data-en="No upcoming dates are currently listed.">'
            'Aktuell sind keine Termine eingetragen.</p>'
        )

    rows = []
    for item in sorted(items, key=lambda entry: parse_date(entry["date"])):
        start = parse_date(item["date"])
        item_type = str(item.get("type") or "broadcast").lower()
        default_hours = 3 if item_type == "broadcast" else 2
        end = parse_date(item["end"]) if item.get("end") else start + timedelta(
            hours=float(item.get("duration_hours") or default_hours)
        )

        title_de = str(item.get("title_de") or site["name"])
        title_en = str(item.get("title_en") or title_de)
        summary_de = str(item.get("summary_de") or "")
        summary_en = str(item.get("summary_en") or summary_de)
        default_label_de = "Sendung" if item_type == "broadcast" else "Veranstaltung"
        default_label_en = "Broadcast" if item_type == "broadcast" else "Event"
        label_de = str(item.get("label_de") or default_label_de)
        label_en = str(item.get("label_en") or default_label_en)

        default_location = "Radio Blau, Leipzig" if item_type == "broadcast" else ""
        location_de = str(item.get("location_de") or item.get("location") or default_location)
        location_en = str(item.get("location_en") or item.get("location") or location_de)

        date_de = date_long(start, "de")
        date_en = date_long(start, "en")
        utc_offset = start.utcoffset()
        if utc_offset == timedelta(hours=2):
            timezone_label = "CEST"
        elif utc_offset == timedelta(hours=1):
            timezone_label = "CET"
        else:
            timezone_label = start.tzname() or "Europe/Berlin"
        time_text = f"{start.strftime('%H:%M')}–{end.strftime('%H:%M')} · {timezone_label}"

        summary_html = ""
        if summary_de or summary_en:
            summary_html = (
                f'<p data-bilingual data-de="{esc(summary_de)}" data-en="{esc(summary_en)}">'
                f'{esc(summary_de)}</p>'
            )

        meta_parts = [
            f'<span data-bilingual data-de="{esc(date_de)}" data-en="{esc(date_en)}">{esc(date_de)}</span>',
            f'<span>{esc(time_text)}</span>',
        ]
        if location_de or location_en:
            meta_parts.append(
                f'<span data-bilingual data-de="{esc(location_de)}" data-en="{esc(location_en)}">'
                f'{esc(location_de)}</span>'
            )

        links = item.get("links")
        if not isinstance(links, list):
            links = []
        if not links and item_type == "broadcast":
            links = [
                {
                    "label_de": "Live hören",
                    "label_en": "Listen live",
                    "url": site["radio"]["stream_url"],
                    "primary": True,
                },
                {
                    "label_de": "Sendeplan",
                    "label_en": "Radio Blau schedule",
                    "url": site["radio"]["url"],
                },
            ]

        action_parts = []
        for link in links:
            if not isinstance(link, dict) or not link.get("url"):
                continue
            link_de = str(link.get("label_de") or link.get("label") or "Details")
            link_en = str(link.get("label_en") or link.get("label") or link_de)
            button_class = "button button-primary" if link.get("primary") else "button"
            action_parts.append(
                f'<a class="{button_class}" href="{esc(link["url"])}" target="_blank" '
                f'rel="noopener noreferrer" data-bilingual data-de="{esc(link_de)}" '
                f'data-en="{esc(link_en)}">{esc(link_de)}</a>'
            )

        action_parts.append(
            f'<a class="button" href="{esc(calendar_url(title_de, start, end, summary_de, location_de))}" '
            'target="_blank" rel="noopener noreferrer" data-bilingual '
            'data-de="Zum Kalender hinzufügen" data-en="Add to calendar">'
            'Zum Kalender hinzufügen</a>'
        )

        rows.append(
            '<article class="upcoming-card">'
            '<div class="date-panel">'
            f'<div><div class="day">{start.strftime("%d")}</div>'
            f'<div class="month" data-bilingual data-de="{esc(MONTHS_DE[start.month - 1])}" '
            f'data-en="{esc(MONTHS_EN[start.month - 1])}">{esc(MONTHS_DE[start.month - 1])}</div></div>'
            f'<div class="year">{start.strftime("%Y")}</div>'
            '</div>'
            '<div class="upcoming-copy"><div>'
            f'<p class="eyebrow" data-bilingual data-de="{esc(label_de)}" data-en="{esc(label_en)}">'
            f'{esc(label_de)}</p>'
            f'<h3 data-bilingual data-de="{esc(title_de)}" data-en="{esc(title_en)}">{esc(title_de)}</h3>'
            f'{summary_html}<div class="upcoming-meta">{"".join(meta_parts)}</div>'
            f'</div><div class="actions">{"".join(action_parts)}</div></div>'
            '</article>'
        )
    return "".join(rows)


def load_archive(episodes: list[dict]) -> list[dict]:
    cache_path = ROOT / "content" / "archive-cache.json"
    try:
        cache = read_json(cache_path)
        cached_episodes = cache.get("episodes", [])
        if isinstance(cached_episodes, list) and cached_episodes:
            result = []
            for item in cached_episodes:
                if not isinstance(item, dict):
                    continue
                if not item.get("date") or not item.get("title") or not item.get("audio_url"):
                    continue
                result.append(
                    {
                        "date": str(item["date"]),
                        "title_de": str(item["title"]),
                        "title_en": str(item["title"]),
                        "summary_de": str(item.get("summary") or ""),
                        "summary_en": str(item.get("summary") or ""),
                        "audio_url": str(item["audio_url"]),
                    }
                )
            if result:
                return sorted(result, key=lambda item: parse_date(item["date"]), reverse=True)
    except (OSError, json.JSONDecodeError, AttributeError, TypeError, ValueError):
        pass

    result = []
    for item in episodes:
        if item.get("status") == "upcoming" or not item.get("audio_url"):
            continue
        result.append(
            {
                "date": item["date"],
                "title_de": item["title_de"],
                "title_en": item.get("title_en") or item["title_de"],
                "summary_de": item.get("summary_de") or "",
                "summary_en": item.get("summary_en") or item.get("summary_de") or "",
                "audio_url": item["audio_url"],
            }
        )
    return sorted(result, key=lambda item: parse_date(item["date"]), reverse=True)


def episode_rows(archive: list[dict]) -> str:
    rows = []
    for item in archive:
        value = parse_date(item["date"])
        date_de = f"{value.day:02d}. {MONTHS_DE[value.month - 1]} {value.year}"
        date_en = f"{value.day:02d} {MONTHS_EN[value.month - 1][:3]} {value.year}"
        title_de = item["title_de"]
        title_en = item.get("title_en") or title_de
        summary_de = item.get("summary_de") or ""
        summary_en = item.get("summary_en") or summary_de
        search_text = " ".join(
            [item["date"], date_de, date_en, title_de, title_en, summary_de, summary_en]
        )
        summary_html = ""
        if summary_de or summary_en:
            summary_html = (
                f'<p data-bilingual data-de="{esc(summary_de)}" data-en="{esc(summary_en)}">'
                f"{esc(summary_de)}</p>"
            )
        rows.append(
            f'<article class="episode" data-episode data-search="{esc(search_text)}">'
            f'<time class="episode-date" datetime="{esc(item["date"])}" data-bilingual '
            f'data-de="{esc(date_de)}" data-en="{esc(date_en)}">{esc(date_de)}</time>'
            "<div>"
            f'<h3 data-bilingual data-de="{esc(title_de)}" data-en="{esc(title_en)}">{esc(title_de)}</h3>'
            f"{summary_html}</div>"
            f'<a class="episode-link" href="{esc(item["audio_url"])}" target="_blank" '
            'rel="noopener noreferrer" data-i18n="play_recording">Aufnahme abspielen ↗</a>'
            "</article>"
        )
    return "".join(rows)


def main() -> None:
    site = read_json(ROOT / "content" / "site.json")
    episodes = read_json(ROOT / "content" / "episodes.json")
    episodes.sort(key=lambda item: parse_date(item["date"]), reverse=True)
    archive = load_archive(episodes)

    pages_url = os.environ.get("SITE_URL") or "http://localhost:8000"
    parsed = urlparse(pages_url)
    base_path = parsed.path.rstrip("/")
    canonical_url = pages_url.rstrip("/") + "/"

    upcoming = [item for item in episodes if item.get("status") == "upcoming"]

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

    mix_rows = []
    for index, mix in enumerate(site["mixes"]):
        duration = f'<span class="mix-duration">{esc(mix["duration"])}</span>' if mix.get("duration") else ""
        mix_rows.append(
            f'<button class="mix-item" type="button" role="listitem" data-mix-index="{index}" '
            f'data-title="{esc(mix["title"])}" data-subtitle-de="{esc(mix["subtitle_de"])}" '
            f'data-subtitle-en="{esc(mix["subtitle_en"])}" data-url="{esc(mix["url"])}" '
            f'data-embed="{esc(soundcloud_embed(mix["url"]))}" aria-pressed="{"true" if index == 0 else "false"}">'
            f'<span class="mix-copy"><strong>{esc(mix["title"])}</strong>'
            f'<span data-mix-subtitle>{esc(mix["subtitle_de"])}</span></span>{duration}</button>'
        )

    first_mix = site["mixes"][0]
    archive_playlist_url = site.get("archive_playlist_url", "https://soundcloud.com/sounds-of-electronic-art/sets/sendungen")
    logo_svg = (ROOT / "assets" / "icons" / "logo.svg").read_text(encoding="utf-8")
    template = (ROOT / "templates" / "index.html").read_text(encoding="utf-8")

    values = {
        "page_title": esc(site["name"] + " — Radio Blau Leipzig"),
        "description": esc(site["description_de"]),
        "canonical_url": esc(canonical_url),
        "base_path": esc(base_path),
        "logo_svg": logo_svg,
        "radio_stream_url": esc(site["radio"]["stream_url"]),
        "radio_page_url": esc(site["radio"]["url"]),
        "upcoming_html": upcoming_rows(upcoming, site),
        "mixes_html": "".join(mix_rows),
        "first_mix_title": esc(first_mix["title"]),
        "first_mix_subtitle_de": esc(first_mix["subtitle_de"]),
        "first_mix_url": esc(first_mix["url"]),
        "first_mix_embed": esc(soundcloud_embed(first_mix["url"])),
        "team_html": team_html,
        "episodes_html": episode_rows(archive),
        "archive_status_de": esc(f"{len(archive)} Sendungen geladen."),
        "archive_status_en": esc(f"{len(archive)} broadcasts loaded."),
        "social_html": social_html,
        "archive_playlist_url": esc(archive_playlist_url),
        "build_year": str(datetime.now().year),
    }

    if PUBLIC.exists():
        shutil.rmtree(PUBLIC)
    PUBLIC.mkdir(parents=True)
    shutil.copytree(ROOT / "assets", PUBLIC / "assets")
    (PUBLIC / "index.html").write_text(render(template, values), encoding="utf-8")
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
        f'<url><loc>{esc(canonical_url)}</loc></url></urlset>'
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
