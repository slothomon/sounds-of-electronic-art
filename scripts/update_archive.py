#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from io import BytesIO
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "content" / "archive-cache.json"
DEFAULT_PLAYLIST = "https://soundcloud.com/sounds-of-electronic-art/sets/sendungen"
DEFAULT_ARTWORK_DIR = ROOT / "assets" / "images" / "episodes"
ARTWORK_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp")
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
    """Normalize title dates, then remove a redundant trailing date.

    Notes such as ``(Komplette Sendung)`` remain untouched.
    """
    title = clean_text(value)
    title = re.sub(
        r"\b(20\d{2})\s*[-_.]\s*(\d{1,2})\s*[-_.]\s*(\d{1,2})\b",
        lambda match: f"{match.group(1)}-{int(match.group(2)):02d}-{int(match.group(3)):02d}",
        title,
    )
    title = re.sub(r"\s*\(\s*20\d{2}-\d{2}-\d{2}\s*\)\s*$", "", title)
    title = re.sub(r"\s+20\d{2}-\d{2}-\d{2}\s*$", "", title)
    return title.strip()


def valid_date(year: Any, month: Any, day: Any) -> date | None:
    try:
        candidate = date(int(year), int(month), int(day))
    except (TypeError, ValueError):
        return None
    if not 2011 <= candidate.year <= datetime.now().year + 1:
        return None
    return candidate


def date_from_metadata(sound: dict[str, Any]) -> date | None:
    # yt-dlp commonly exposes compact YYYYMMDD values for upload/release dates.
    for field in ("release_date", "upload_date"):
        value = clean_text(sound.get(field))
        if re.fullmatch(r"\d{8}", value):
            parsed = valid_date(value[:4], value[4:6], value[6:8])
            if parsed:
                return parsed

    # Some extractors expose Unix timestamps instead of formatted strings.
    for field in ("release_timestamp", "timestamp", "modified_timestamp"):
        value = sound.get(field)
        try:
            if value is not None:
                parsed = datetime.fromtimestamp(float(value), tz=timezone.utc)
                if parsed.year >= 2011:
                    return parsed.date()
        except (TypeError, ValueError, OSError, OverflowError):
            pass

    for field in ("display_date", "published_at", "created_at"):
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
    """Return the complete SoundCloud description with stable paragraph breaks."""
    description = unicodedata.normalize("NFKC", str(sound.get("description") or ""))
    description = re.sub(r"[\u200b-\u200d\u2060\ufeff]", "", description)
    description = description.replace("\u00a0", " ").replace("\r\n", "\n").replace("\r", "\n")

    lines: list[str] = []
    previous_blank = False
    for raw_line in description.split("\n"):
        line = re.sub(r"[ \t]+", " ", raw_line).strip()
        if line:
            lines.append(line)
            previous_blank = False
        elif lines and not previous_blank:
            lines.append("")
            previous_blank = True
    while lines and not lines[-1]:
        lines.pop()
    return "\n".join(lines)


def sound_summary(description: str, limit: int = 280) -> str:
    """Keep the former short cache summary while retaining the full description separately."""
    for line in str(description or "").splitlines():
        candidate = clean_text(line)
        if candidate and not re.match(r"^(?:https?://|\[[^\]]+\]\(https?://)", candidate, re.IGNORECASE):
            return candidate if len(candidate) <= limit else candidate[: limit - 3].rstrip() + "…"
    return ""

def slugify(value: str) -> str:
    text = str(value or "").lower()
    for source, target in {"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"}.items():
        text = text.replace(source, target)
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")[:80] or "sendung"


EPISODE_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{2,95}$")


def episode_identifier(episode_date: date, title: str) -> str:
    """Create a stable local identity that does not contain a source URL."""
    return f"{episode_date.isoformat()}-{slugify(clean_title(title))}"


def sound_artwork_url(sound: dict[str, Any]) -> str:
    thumbnails = sound.get("thumbnails") if isinstance(sound.get("thumbnails"), list) else []
    candidates: list[tuple[int, str]] = []
    for thumbnail in thumbnails:
        if not isinstance(thumbnail, dict):
            continue
        url = clean_text(thumbnail.get("url"))
        if not url.startswith(("https://", "http://")):
            continue
        width = thumbnail.get("width") or 0
        height = thumbnail.get("height") or 0
        try:
            area = int(width) * int(height)
        except (TypeError, ValueError):
            area = 0
        candidates.append((area, url))
    if candidates:
        return max(candidates, key=lambda candidate: candidate[0])[1]
    direct = clean_text(sound.get("thumbnail") or sound.get("artwork_url"))
    return direct if direct.startswith(("https://", "http://")) else ""


def artwork_stem(episode_date: date, title: str) -> str:
    return f"{episode_date.isoformat()}-{slugify(title)}"


def existing_artwork(artwork_dir: Path, stem: str) -> Path | None:
    for extension in ARTWORK_EXTENSIONS:
        candidate = artwork_dir / f"{stem}{extension}"
        if candidate.is_file():
            return candidate
    return None


def save_artwork(
    artwork_url: str,
    artwork_dir: Path,
    stem: str,
    timeout_ms: int,
    refresh: bool = False,
) -> Path | None:
    existing = existing_artwork(artwork_dir, stem)
    if existing and not refresh:
        return existing
    if not artwork_url:
        return existing

    try:
        from PIL import Image, UnidentifiedImageError
    except ImportError as error:
        raise RuntimeError("Pillow is required for artwork caching") from error

    request = Request(
        artwork_url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; sofea.radio archive updater/1.0)",
            "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
        },
    )
    try:
        with urlopen(request, timeout=max(15, timeout_ms // 1000)) as response:
            payload = response.read(20 * 1024 * 1024 + 1)
        if len(payload) > 20 * 1024 * 1024:
            raise RuntimeError("artwork exceeds 20 MB")
        image = Image.open(BytesIO(payload))
        image.load()
        if image.mode not in ("RGB", "L"):
            background = Image.new("RGB", image.size, "#171412")
            if "A" in image.getbands():
                background.paste(image, mask=image.getchannel("A"))
            else:
                background.paste(image.convert("RGB"))
            image = background
        else:
            image = image.convert("RGB")
        image.thumbnail((1600, 1600), Image.Resampling.LANCZOS)
        artwork_dir.mkdir(parents=True, exist_ok=True)
        target = artwork_dir / f"{stem}.jpg"
        temporary = target.with_suffix(".tmp.jpg")
        image.save(temporary, format="JPEG", quality=91, optimize=True, progressive=True)
        temporary.replace(target)
        if refresh and existing and existing != target:
            existing.unlink(missing_ok=True)
        try:
            display_target = target.relative_to(ROOT)
        except ValueError:
            display_target = target
        print(f"Artwork cached: {display_target}")
        return target
    except (HTTPError, URLError, TimeoutError, OSError, UnidentifiedImageError, RuntimeError) as error:
        print(f"WARNING: Could not cache artwork for {stem}: {error}", file=sys.stderr)
        return existing


def normalise_sounds(
    sounds: list[dict[str, Any]],
    playlist_url: str,
    artwork_dir: Path = DEFAULT_ARTWORK_DIR,
    timeout_ms: int = 45000,
    cache_artwork: bool = True,
    refresh_artwork: bool = False,
    artwork_title_overrides: dict[str, str] | None = None,
    artwork_path_overrides: dict[str, str] | None = None,
    existing_episode_ids: dict[str, str] | None = None,
) -> dict[str, Any]:
    episodes: list[dict[str, Any]] = []
    seen: set[str] = set()
    artwork_title_overrides = artwork_title_overrides or {}
    artwork_path_overrides = artwork_path_overrides or {}
    existing_episode_ids = existing_episode_ids or {}

    for sound in sounds:
        if not isinstance(sound, dict):
            continue
        title = clean_title(sound.get("title"))
        url = sound_url(sound)
        episode_date = extract_episode_date(sound)
        if not title or not url or not episode_date:
            continue

        source_id = clean_text(sound.get("id") or sound.get("urn"))
        key = source_id or url
        if key in seen:
            continue
        seen.add(key)

        duration_ms = sound.get("duration")
        try:
            duration_ms = int(duration_ms) if duration_ms is not None else None
        except (TypeError, ValueError):
            duration_ms = None

        normalised_url = url.rstrip("/")
        preserved_id = (
            existing_episode_ids.get(f"source:{source_id}")
            or existing_episode_ids.get(f"url:{normalised_url}")
            or ""
        )
        local_title = (
            artwork_title_overrides.get(f"id:{preserved_id}", "")
            or artwork_title_overrides.get(f"url:{normalised_url}", "")
        )
        identity_title = local_title or title
        generated_id = episode_identifier(episode_date, identity_title)
        episode_id = preserved_id or generated_id
        if not EPISODE_ID_RE.fullmatch(episode_id):
            episode_id = generated_id

        artwork_url = sound_artwork_url(sound)
        image_path = (
            artwork_path_overrides.get(f"id:{episode_id}", "")
            or artwork_path_overrides.get(f"url:{normalised_url}", "")
        )
        if cache_artwork and not image_path:
            target = save_artwork(
                artwork_url,
                artwork_dir,
                artwork_stem(episode_date, identity_title),
                timeout_ms,
                refresh=refresh_artwork,
            )
            if target:
                try:
                    image_path = target.relative_to(ROOT).as_posix()
                except ValueError:
                    print(
                        f"WARNING: Artwork directory is outside the repository; "
                        f"not writing image path for {title}.",
                        file=sys.stderr,
                    )

        episode = {
            "episode_id": episode_id,
            "date": episode_date.isoformat(),
            "title": title,
            "summary": sound_summary(sound_description(sound)),
                "description": sound_description(sound),
            "audio_url": url,
            "soundcloud_id": source_id,
            "duration_ms": duration_ms,
        }
        if artwork_url:
            episode["artwork_url"] = artwork_url
        if image_path:
            episode["image"] = image_path
        episodes.append(episode)

    episodes.sort(key=lambda item: (item["date"], item["title"].casefold()), reverse=True)
    return {
        "version": 2,
        "source": playlist_url,
        "updated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "count": len(episodes),
        "episodes": episodes,
    }

def _public_track_url(entry: dict[str, Any]) -> str:
    for field in ("webpage_url", "original_url", "url"):
        value = clean_text(entry.get(field))
        if value.startswith("https://soundcloud.com/"):
            return value
    return ""


def _entry_to_sound(entry: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": entry.get("id"),
        "urn": entry.get("urn"),
        "title": entry.get("title"),
        "description": entry.get("description"),
        "permalink_url": _public_track_url(entry),
        "permalink": entry.get("display_id"),
        "duration": int(float(entry["duration"]) * 1000) if entry.get("duration") else None,
        "release_date": entry.get("release_date"),
        "upload_date": entry.get("upload_date"),
        "release_timestamp": entry.get("release_timestamp"),
        "timestamp": entry.get("timestamp"),
        "modified_timestamp": entry.get("modified_timestamp"),
        "display_date": entry.get("display_date"),
        "published_at": entry.get("published_at"),
        "created_at": entry.get("created_at"),
        "thumbnail": entry.get("thumbnail"),
        "thumbnails": entry.get("thumbnails") if isinstance(entry.get("thumbnails"), list) else [],
        "user": entry.get("user") if isinstance(entry.get("user"), dict) else {},
    }


def fetch_sounds(playlist_url: str, timeout_ms: int) -> list[dict[str, Any]]:
    try:
        import yt_dlp
    except ImportError as error:
        raise RuntimeError("yt-dlp is not installed") from error

    # Do not use extract_flat here. Flat playlist entries generally contain only
    # an ID/title and omit descriptions, public URLs and publication dates.
    opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "extract_flat": False,
        "lazy_playlist": False,
        "socket_timeout": max(15, timeout_ms // 1000),
        "retries": 3,
        "fragment_retries": 3,
        "ignoreerrors": True,
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(playlist_url, download=False)

    entries = info.get("entries") if isinstance(info, dict) else None
    if not isinstance(entries, list) or not entries:
        raise RuntimeError("SoundCloud playlist returned no tracks")

    sounds = [_entry_to_sound(entry) for entry in entries if isinstance(entry, dict)]
    usable_urls = sum(bool(sound.get("permalink_url")) for sound in sounds)
    usable_dates = sum(bool(extract_episode_date(sound)) for sound in sounds)
    print(
        f"SoundCloud extractor returned {len(entries)} playlist entries; "
        f"{usable_urls} have public URLs and {usable_dates} have readable dates."
    )
    return sounds


def read_existing_cache(path: Path) -> dict[str, Any]:
    try:
        cache = json.loads(path.read_text(encoding="utf-8"))
        return cache if isinstance(cache, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def local_episode_id(entry: dict[str, Any]) -> str:
    explicit = clean_text(entry.get("episode_id")).lower()
    if EPISODE_ID_RE.fullmatch(explicit):
        return explicit
    date_value = clean_text(entry.get("date"))[:10]
    title = clean_text(entry.get("title_de") or entry.get("title"))
    try:
        parsed = date.fromisoformat(date_value)
    except ValueError:
        return ""
    return episode_identifier(parsed, title) if title else ""


def read_local_title_overrides(path: Path = ROOT / "content" / "episodes.json") -> dict[str, str]:
    try:
        entries = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(entries, list):
        return {}
    overrides: dict[str, str] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        url = clean_text(entry.get("audio_url")).rstrip("/")
        title = clean_text(entry.get("title_de") or entry.get("title"))
        identity = local_episode_id(entry)
        if url and title:
            overrides[f"url:{url}"] = title
        if identity and title:
            overrides[f"id:{identity}"] = title
    return overrides


def read_local_artwork_overrides(path: Path = ROOT / "content" / "episodes.json") -> dict[str, str]:
    try:
        entries = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(entries, list):
        return {}
    overrides: dict[str, str] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        url = clean_text(entry.get("audio_url")).rstrip("/")
        identity = local_episode_id(entry)
        image = clean_text(entry.get("image"))
        if not image or image.startswith(("https://", "http://")):
            continue
        relative = image.lstrip("/")
        if not (ROOT / relative).is_file():
            continue
        if url:
            overrides[f"url:{url}"] = relative
        if identity:
            overrides[f"id:{identity}"] = relative
    return overrides


def read_existing_episode_ids(cache: dict[str, Any]) -> dict[str, str]:
    """Preserve local IDs across title and permalink changes."""
    mappings: dict[str, str] = {}
    episodes = cache.get("episodes", []) if isinstance(cache, dict) else []
    if not isinstance(episodes, list):
        return mappings
    for entry in episodes:
        if not isinstance(entry, dict):
            continue
        identity = clean_text(entry.get("episode_id")).lower()
        if not EPISODE_ID_RE.fullmatch(identity):
            continue
        source_id = clean_text(entry.get("soundcloud_id"))
        url = clean_text(entry.get("audio_url")).rstrip("/")
        if source_id:
            mappings[f"source:{source_id}"] = identity
        if url:
            mappings[f"url:{url}"] = identity
    return mappings

def main() -> int:
    parser = argparse.ArgumentParser(description="Build a static archive cache from a SoundCloud playlist.")
    parser.add_argument("--playlist-url", default=DEFAULT_PLAYLIST)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--input-json", type=Path, help="Use saved raw Widget API data instead of opening SoundCloud.")
    parser.add_argument("--timeout", type=int, default=45000, help="Network timeout in milliseconds.")
    parser.add_argument("--artwork-dir", type=Path, default=DEFAULT_ARTWORK_DIR)
    parser.add_argument("--no-artwork", action="store_true", help="Do not download or update local artwork files.")
    parser.add_argument("--refresh-artwork", action="store_true", help="Replace existing automatic artwork files.")
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

        cache = normalise_sounds(
            sounds,
            args.playlist_url,
            artwork_dir=args.artwork_dir,
            timeout_ms=args.timeout,
            cache_artwork=not args.no_artwork,
            refresh_artwork=args.refresh_artwork,
            artwork_title_overrides=read_local_title_overrides(),
            artwork_path_overrides=read_local_artwork_overrides(),
            existing_episode_ids=read_existing_episode_ids(old_cache),
        )
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
