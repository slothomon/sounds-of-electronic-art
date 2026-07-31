#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "content" / "archive-cache.json"
DEFAULT_PLAYLIST = "https://soundcloud.com/sounds-of-electronic-art/sets/sendungen"
MONTHS = {
    "januar": 1, "january": 1,
    "februar": 2, "february": 2,
    "marz": 3, "maerz": 3, "march": 3,
    "april": 4,
    "mai": 5, "may": 5,
    "juni": 6, "june": 6,
    "juli": 7, "july": 7,
    "august": 8,
    "september": 9,
    "oktober": 10, "october": 10,
    "november": 11,
    "dezember": 12, "december": 12,
}


def clean_text(value: Any) -> str:
    text = unicodedata.normalize("NFKC", str(value or ""))
    text = re.sub(r"[\u200b-\u200d\u2060\ufeff]", "", text)
    text = text.replace("\u00a0", " ")
    return re.sub(r"\s+", " ", text).strip()


def normalise_text(value: Any) -> str:
    text = clean_text(value).lower()
    text = unicodedata.normalize("NFD", text)
    return "".join(char for char in text if unicodedata.category(char) != "Mn")


def clean_title(value: Any) -> str:
    title = clean_text(value)
    return re.sub(
        r"\b(20\d{2})\s*[-_.]\s*(\d{1,2})\s*[-_.]\s*(\d{1,2})\b",
        lambda match: f"{match.group(1)}-{int(match.group(2)):02d}-{int(match.group(3)):02d}",
        title,
    )


def valid_date(year: Any, month: Any, day: Any) -> date | None:
    try:
        candidate = date(int(year), int(month), int(day))
    except (TypeError, ValueError):
        return None
    if not 2011 <= candidate.year <= datetime.now().year + 1:
        return None
    return candidate


def date_from_metadata(sound: dict[str, Any]) -> date | None:
    for field in ("release_date", "display_date", "published_at", "created_at"):
        value = clean_text(sound.get(field))
        if not value:
            continue
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            continue
        if parsed.year >= 2011:
            return parsed.date()
    return None


def extract_episode_date(sound: dict[str, Any]) -> date | None:
    text = clean_text(
        " ".join(
            str(sound.get(field) or "")
            for field in ("title", "description", "permalink_url", "permalink")
        )
    )

    match = re.search(r"\b(20\d{2})\s*[-_.]\s*(\d{1,2})\s*[-_.]\s*(\d{1,2})\b", text)
    if match:
        parsed = valid_date(match.group(1), match.group(2), match.group(3))
        if parsed:
            return parsed

    match = re.search(r"\b(\d{1,2})\s*[./-]\s*(\d{1,2})\s*[./-]\s*(20\d{2})\b", text)
    if match:
        parsed = valid_date(match.group(3), match.group(2), match.group(1))
        if parsed:
            return parsed

    normalised = normalise_text(text)
    month_pattern = "|".join(sorted(MONTHS, key=len, reverse=True))
    match = re.search(rf"\b(\d{{1,2}})\.?\s+({month_pattern})\s+(20\d{{2}})\b", normalised)
    if match:
        parsed = valid_date(match.group(3), MONTHS[match.group(2)], match.group(1))
        if parsed:
            return parsed

    return date_from_metadata(sound)


def sound_url(sound: dict[str, Any]) -> str:
    direct = clean_text(sound.get("permalink_url"))
    if direct.startswith("https://"):
        return direct
    user = sound.get("user") if isinstance(sound.get("user"), dict) else {}
    user_permalink = clean_text(user.get("permalink"))
    track_permalink = clean_text(sound.get("permalink"))
    if user_permalink and track_permalink:
        return f"https://soundcloud.com/{user_permalink}/{track_permalink}"
    return ""


def sound_description(sound: dict[str, Any]) -> str:
    description = str(sound.get("description") or "")
    for line in description.splitlines():
        candidate = clean_text(line)
        if candidate and not re.match(r"^https?://", candidate, re.IGNORECASE):
            return candidate if len(candidate) <= 280 else candidate[:277].rstrip() + "…"
    return ""


def normalise_sounds(sounds: list[dict[str, Any]], playlist_url: str) -> dict[str, Any]:
    episodes: list[dict[str, Any]] = []
    seen: set[str] = set()

    for sound in sounds:
        if not isinstance(sound, dict):
            continue
        title = clean_title(sound.get("title"))
        url = sound_url(sound)
        episode_date = extract_episode_date(sound)
        if not title or not url or not episode_date:
            continue

        key = clean_text(sound.get("id") or sound.get("urn") or url)
        if key in seen:
            continue
        seen.add(key)

        duration_ms = sound.get("duration")
        try:
            duration_ms = int(duration_ms) if duration_ms is not None else None
        except (TypeError, ValueError):
            duration_ms = None

        episodes.append(
            {
                "date": episode_date.isoformat(),
                "title": title,
                "summary": sound_description(sound),
                "audio_url": url,
                "soundcloud_id": clean_text(sound.get("id") or sound.get("urn")),
                "duration_ms": duration_ms,
            }
        )

    episodes.sort(key=lambda item: (item["date"], item["title"].casefold()), reverse=True)
    return {
        "version": 1,
        "source": playlist_url,
        "updated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "count": len(episodes),
        "episodes": episodes,
    }


def fetch_sounds(playlist_url: str, timeout_ms: int) -> list[dict[str, Any]]:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as error:
        raise RuntimeError(
            "Playwright is not installed. Run: python -m pip install 'playwright<2'"
        ) from error

    embed = (
        "https://w.soundcloud.com/player/?url="
        + quote(playlist_url, safe="")
        + "&auto_play=false&hide_related=true&show_comments=false&show_user=false"
        + "&show_reposts=false&show_playcount=false&show_teaser=false&visual=false"
    )
    page_html = f"""<!doctype html>
<html><body>
<iframe id="playlist" width="600" height="450" allow="autoplay" src="{embed}"></iframe>
<script src="https://w.soundcloud.com/player/api.js"></script>
</body></html>"""

    extraction_script = """
    async ({ timeoutMs }) => {
      const frame = document.querySelector('#playlist');
      if (!frame || !window.SC || !window.SC.Widget) throw new Error('SoundCloud Widget API unavailable');
      const widget = window.SC.Widget(frame);
      const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
      const getter = (method, timeout = 2500) => new Promise((resolve) => {
        let done = false;
        const finish = (value) => { if (!done) { done = true; clearTimeout(timer); resolve(value); } };
        const timer = setTimeout(() => finish(null), timeout);
        try { widget[method]((value) => finish(value)); } catch (_) { finish(null); }
      });
      const readable = (sound) => Boolean(
        sound && sound.title && (sound.permalink_url || (sound.user && sound.user.permalink && sound.permalink))
      );

      let stubs = await getter('getSounds', 3500);
      if (!Array.isArray(stubs) || stubs.length === 0) {
        await new Promise((resolve, reject) => {
          const timer = setTimeout(() => reject(new Error('SoundCloud widget READY timeout')), timeoutMs);
          widget.bind(window.SC.Widget.Events.READY, () => { clearTimeout(timer); resolve(); });
          widget.bind(window.SC.Widget.Events.ERROR, () => { clearTimeout(timer); reject(new Error('SoundCloud widget error')); });
        });
        stubs = await getter('getSounds', timeoutMs);
      }
      if (!Array.isArray(stubs) || stubs.length === 0) throw new Error('Playlist returned no tracks');
      const originalIndex = await getter('getCurrentSoundIndex', 2000);
      try { widget.pause(); } catch (_) {}

      const result = [];
      for (let index = 0; index < stubs.length; index += 1) {
        let sound = stubs[index] || {};
        if (!readable(sound)) {
          try { widget.skip(index); } catch (_) {}
          for (let attempt = 0; attempt < 12; attempt += 1) {
            await wait(attempt === 0 ? 180 : 220);
            const [current, currentIndex] = await Promise.all([
              getter('getCurrentSound', 1800),
              getter('getCurrentSoundIndex', 1800),
            ]);
            if (Number(currentIndex) === index && readable(current)) {
              sound = { ...sound, ...current, user: current.user || sound.user };
              break;
            }
          }
        }
        result.push(sound);
      }

      if (Number.isInteger(Number(originalIndex))) {
        try { widget.skip(Number(originalIndex)); widget.pause(); } catch (_) {}
      }
      return result;
    }
    """

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 900, "height": 700})
        page.set_content(page_html, wait_until="domcontentloaded", timeout=timeout_ms)
        page.wait_for_function("window.SC && window.SC.Widget", timeout=timeout_ms)
        sounds = page.evaluate(extraction_script, {"timeoutMs": timeout_ms})
        browser.close()

    return sounds


def read_existing_cache(path: Path) -> dict[str, Any]:
    try:
        cache = json.loads(path.read_text(encoding="utf-8"))
        return cache if isinstance(cache, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a static archive cache from a SoundCloud playlist.")
    parser.add_argument("--playlist-url", default=DEFAULT_PLAYLIST)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--input-json", type=Path, help="Use saved raw Widget API data instead of opening SoundCloud.")
    parser.add_argument("--timeout", type=int, default=45000, help="Browser timeout in milliseconds.")
    parser.add_argument("--strict", action="store_true", help="Fail even when an existing cache can be retained.")
    args = parser.parse_args()

    old_cache = read_existing_cache(args.output)
    old_episodes = old_cache.get("episodes", []) if isinstance(old_cache.get("episodes", []), list) else []
    old_count = len(old_episodes)
    try:
        if args.input_json:
            raw = json.loads(args.input_json.read_text(encoding="utf-8"))
            sounds = raw.get("sounds", raw) if isinstance(raw, dict) else raw
        else:
            sounds = fetch_sounds(args.playlist_url, args.timeout)
        if not isinstance(sounds, list):
            raise RuntimeError("SoundCloud result is not a list")

        cache = normalise_sounds(sounds, args.playlist_url)
        new_count = cache["count"]
        minimum_acceptable = max(5, int(old_count * 0.8)) if old_count else 5
        if new_count < minimum_acceptable:
            raise RuntimeError(
                f"Only {new_count} readable entries were returned; refusing to replace a cache with {old_count} entries"
            )

        if old_episodes == cache["episodes"] and old_cache.get("source") == args.playlist_url:
            print(f"Archive cache unchanged: {new_count} broadcasts")
            return 0

        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(cache, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"Archive cache updated: {new_count} broadcasts written to {args.output}")
        return 0
    except Exception as error:  # The existing cache deliberately keeps deployment resilient.
        if old_count and not args.strict:
            print(f"WARNING: Archive refresh failed; retaining existing cache with {old_count} entries: {error}", file=sys.stderr)
            return 0
        print(f"ERROR: Archive refresh failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
