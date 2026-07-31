#!/usr/bin/env python3
from __future__ import annotations

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
    return datetime.fromisoformat(value)


def render(template: str, values: dict[str, str]) -> str:
    for key, value in values.items():
        template = template.replace("{{ " + key + " }}", value)
    return template


def soundcloud_embed(url: str, *, playlist: bool = False) -> str:
    height_options = "&visual=false" if playlist else ""
    return (
        "https://w.soundcloud.com/player/?url=" + quote(url, safe="")
        + "&color=%23ef9a55&auto_play=false&hide_related=true"
        + "&show_comments=true&show_user=true&show_reposts=true&show_playcount=true&show_teaser=false"
        + height_options
    )


def date_long(date: datetime, language: str) -> str:
    if language == "de":
        return f"{WEEKDAYS_DE[date.weekday()]}, {date.day}. {MONTHS_DE[date.month - 1]} {date.year}"
    return f"{WEEKDAYS_EN[date.weekday()]}, {date.day} {MONTHS_EN[date.month - 1]} {date.year}"


def main() -> None:
    site = read_json(ROOT / "content" / "site.json")
    episodes = read_json(ROOT / "content" / "episodes.json")
    episodes.sort(key=lambda item: parse_date(item["date"]), reverse=True)

    pages_url = os.environ.get("SITE_URL") or "http://localhost:8000"
    parsed = urlparse(pages_url)
    base_path = parsed.path.rstrip("/")
    canonical_url = pages_url.rstrip("/") + "/"

    upcoming = [item for item in episodes if item.get("status") == "upcoming"]
    next_episode = min(upcoming, key=lambda item: parse_date(item["date"])) if upcoming else episodes[0]
    next_date = parse_date(next_episode["date"])

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
        team_rows.append(
            f'<div class="team-member"><span>{esc(member["name"])}</span>{alias}</div>'
        )
    team_html = "".join(team_rows)
    social_html = "".join(
        f'<a href="{esc(link["url"])}" target="_blank" rel="noopener noreferrer">{esc(link["label"])}</a>'
        for link in site["social"]
    )

    # Static records remain as a no-JavaScript/privacy-blocker fallback. When the
    # SoundCloud widget is available, site.js replaces these rows with the full
    # playlist contents at runtime.
    past_episodes = [item for item in episodes if item.get("status") != "upcoming"]
    episode_rows = []
    for item in past_episodes:
        date = parse_date(item["date"])
        audio_url = item.get("audio_url")
        if audio_url:
            audio = (
                f'<a class="episode-link" href="{esc(audio_url)}" target="_blank" '
                'rel="noopener noreferrer" data-i18n="play_recording">Aufnahme abspielen ↗</a>'
            )
        else:
            audio = '<span class="episode-link" aria-disabled="true" data-i18n="recording_pending">Aufnahme folgt</span>'
        date_de = f"{date.day:02d}. {MONTHS_DE[date.month - 1]} {date.year}"
        date_en = f"{date.day:02d} {MONTHS_EN[date.month - 1][:3]} {date.year}"
        search_text = " ".join(
            [
                item["date"], date_de, date_en, item["title_de"], item["title_en"],
                item["summary_de"], item["summary_en"],
            ]
        )
        episode_rows.append(
            f'<article class="episode" data-episode data-search="{esc(search_text)}">'
            f'<time class="episode-date" datetime="{esc(item["date"])}" data-bilingual data-de="{esc(date_de)}" data-en="{esc(date_en)}">{esc(date_de)}</time>'
            '<div>'
            f'<h3 data-bilingual data-de="{esc(item["title_de"])}" data-en="{esc(item["title_en"])}">{esc(item["title_de"])}</h3>'
            f'<p data-bilingual data-de="{esc(item["summary_de"])}" data-en="{esc(item["summary_en"])}">{esc(item["summary_de"])}</p>'
            '</div>' + audio + '</article>'
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

    calendar_start = next_date.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    calendar_end = (next_date + timedelta(hours=3)).astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    calendar_url = (
        "https://calendar.google.com/calendar/render?action=TEMPLATE"
        f"&text={quote(site['name'])}&dates={calendar_start}/{calendar_end}"
        f"&details={quote(next_episode['summary_de'])}&location={quote('Radio Blau, Leipzig')}"
    )

    values = {
        "page_title": esc(site["name"] + " — Radio Blau Leipzig"),
        "description": esc(site["description_de"]),
        "canonical_url": esc(canonical_url),
        "base_path": esc(base_path),
        "logo_svg": logo_svg,
        "radio_stream_url": esc(site["radio"]["stream_url"]),
        "radio_page_url": esc(site["radio"]["url"]),
        "next_day": next_date.strftime("%d"),
        "next_month_de": esc(MONTHS_DE[next_date.month - 1]),
        "next_month_en": esc(MONTHS_EN[next_date.month - 1]),
        "next_year": next_date.strftime("%Y"),
        "next_title_de": esc(next_episode["title_de"]),
        "next_title_en": esc(next_episode["title_en"]),
        "next_summary_de": esc(next_episode["summary_de"]),
        "next_summary_en": esc(next_episode["summary_en"]),
        "next_date_de": esc(date_long(next_date, "de")),
        "next_date_en": esc(date_long(next_date, "en")),
        "next_time": next_date.strftime("%H:%M"),
        "next_timezone": next_date.tzname() or "Europe/Berlin",
        "calendar_url": esc(calendar_url),
        "mixes_html": "".join(mix_rows),
        "first_mix_title": esc(first_mix["title"]),
        "first_mix_subtitle_de": esc(first_mix["subtitle_de"]),
        "first_mix_url": esc(first_mix["url"]),
        "first_mix_embed": esc(soundcloud_embed(first_mix["url"])),
        "team_html": team_html,
        "episodes_html": "".join(episode_rows),
        "social_html": social_html,
        "archive_playlist_url": esc(archive_playlist_url),
        "archive_playlist_embed": esc(soundcloud_embed(archive_playlist_url, playlist=True)),
        "build_year": str(datetime.now().year),
    }

    if PUBLIC.exists():
        shutil.rmtree(PUBLIC)
    PUBLIC.mkdir(parents=True)
    shutil.copytree(ROOT / "assets", PUBLIC / "assets")
    (PUBLIC / "index.html").write_text(render(template, values), encoding="utf-8")

    feed_items = []
    for item in episodes:
        date = parse_date(item["date"])
        feed_items.append(
            "<item>"
            f"<title>{esc(item['title_de'])}</title>"
            f"<description>{esc(item['summary_de'])}</description>"
            f"<pubDate>{format_datetime(date)}</pubDate>"
            f"<guid isPermaLink=\"false\">sofea-{date.strftime('%Y%m%d')}</guid>"
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
    print(f"Built {PUBLIC} for {pages_url}")


if __name__ == "__main__":
    main()
