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

    team_html = "".join(
        f'<div class="team-member"><span>{esc(member["name"])}</span><span>{esc(member["alias"])}</span></div>'
        for member in site["team"]
    )

    social_html = "".join(
        f'<a href="{esc(link["url"])}">{esc(link["label"])}</a>' for link in site["social"]
    )

    past_episodes = [item for item in episodes if item.get("status") != "upcoming"]
    episode_rows = []
    for item in past_episodes:
        date = parse_date(item["date"])
        audio_url = item.get("audio_url")
        if audio_url:
            audio = f'<a class="episode-link" href="{esc(audio_url)}">Play recording ↗</a>'
        else:
            audio = '<span class="episode-link" aria-disabled="true">Recording pending</span>'
        guests = item.get("guests") or []
        guest_suffix = f' · Guests: {", ".join(guests)}' if guests else ""
        episode_rows.append(
            '<article class="episode" data-episode>'
            f'<time class="episode-date" datetime="{esc(item["date"])}">{date.strftime("%d %b %Y")}</time>'
            '<div>'
            f'<h3>{esc(item["title"])}</h3>'
            f'<p>{esc(item["summary"] + guest_suffix)}</p>'
            '</div>'
            f'{audio}'
            '</article>'
        )

    logo_svg = (ROOT / "assets" / "icons" / "logo.svg").read_text(encoding="utf-8")
    template = (ROOT / "templates" / "index.html").read_text(encoding="utf-8")

    calendar_start = next_date.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    calendar_end = (next_date + timedelta(hours=3)).astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    calendar_url = (
        "https://calendar.google.com/calendar/render?action=TEMPLATE"
        f"&text={quote(site['name'])}"
        f"&dates={calendar_start}/{calendar_end}"
        f"&details={quote(next_episode['summary'])}"
        f"&location={quote('Radio Blau, Leipzig') }"
    )

    values = {
        "page_title": esc(site["name"] + " — Radio Blau Leipzig"),
        "description": esc(site["description"]),
        "canonical_url": esc(canonical_url),
        "base_path": esc(base_path),
        "logo_svg": logo_svg,
        "radio_stream_url": esc(site["radio"]["stream_url"]),
        "radio_page_url": esc(site["radio"]["url"]),
        "next_day": next_date.strftime("%d"),
        "next_month": next_date.strftime("%B"),
        "next_year": next_date.strftime("%Y"),
        "next_title": esc(next_episode["title"]),
        "next_summary": esc(next_episode["summary"]),
        "next_date_long": next_date.strftime("%A, %d %B %Y"),
        "next_time": next_date.strftime("%H:%M"),
        "next_timezone": next_date.tzname() or "Europe/Berlin",
        "calendar_url": esc(calendar_url),
        "featured_title": esc(site["featured_mix"]["title"]),
        "featured_embed": esc(site["featured_mix"]["embed"]),
        "team_html": team_html,
        "episodes_html": "".join(episode_rows),
        "social_html": social_html,
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
            f"<title>{esc(item['title'])}</title>"
            f"<description>{esc(item['summary'])}</description>"
            f"<pubDate>{format_datetime(date)}</pubDate>"
            f"<guid isPermaLink=\"false\">soea-{date.strftime('%Y%m%d')}</guid>"
            "</item>"
        )
    feed = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<rss version="2.0"><channel>'
        f'<title>{esc(site["name"])}</title>'
        f'<link>{esc(canonical_url)}</link>'
        f'<description>{esc(site["description"])}</description>'
        + "".join(feed_items)
        + '</channel></rss>'
    )
    (PUBLIC / "feed.xml").write_text(feed, encoding="utf-8")

    sitemap = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        f'<url><loc>{esc(canonical_url)}</loc></url>'
        '</urlset>'
    )
    (PUBLIC / "sitemap.xml").write_text(sitemap, encoding="utf-8")
    (PUBLIC / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {canonical_url}sitemap.xml\n", encoding="utf-8")
    (PUBLIC / ".nojekyll").write_text("", encoding="utf-8")
    not_found_template = (ROOT / "templates" / "404.html").read_text(encoding="utf-8")
    (PUBLIC / "404.html").write_text(
        render(not_found_template, values),
        encoding="utf-8",
    )

    print(f"Built {PUBLIC} for {pages_url}")


if __name__ == "__main__":
    main()
