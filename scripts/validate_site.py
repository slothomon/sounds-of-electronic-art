#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlparse

SITE_HOSTS = {"sofea.radio", "www.sofea.radio"}
PLACEHOLDER_RE = re.compile(r"\{\{\s*[A-Za-z0-9_]+\s*\}\}")
ARTWORK_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
FORBIDDEN_LEGACY_FIELDS = {
    "status", "type", "summary_de", "summary_en", "location_de", "location_en",
    "venue_name", "street_address", "postal_code", "address_locality", "address_region",
    "address_country", "lineup", "lineup_de", "lineup_en", "image_alt", "image_alt_de",
    "image_alt_en", "label_de", "label_en", "slug", "social_image_url",
    "music_presentations_de", "music_presentations_en", "tracklist_de", "tracklist_en",
    "duration_hours", "image_url",
}


class DocumentParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.ids: list[str] = []
        self.links: list[tuple[str, str]] = []
        self.canonical: list[str] = []
        self.title_parts: list[str] = []
        self.in_title = False
        self.description: list[str] = []
        self.html_lang = ""
        self.json_ld_blocks: list[str] = []
        self.in_json_ld = False
        self.json_ld_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {key: value or "" for key, value in attrs}
        if tag == "html":
            self.html_lang = values.get("lang", "")
        if values.get("id"):
            self.ids.append(values["id"])
        if tag in {"a", "link"} and values.get("href"):
            self.links.append((tag, values["href"]))
        if tag in {"img", "script", "iframe"} and values.get("src"):
            self.links.append((tag, values["src"]))
        if tag == "img" and values.get("srcset"):
            for candidate in values["srcset"].split(","):
                url = candidate.strip().split()[0] if candidate.strip() else ""
                if url:
                    self.links.append(("img-srcset", url))
        if tag == "link" and values.get("rel") == "canonical" and values.get("href"):
            self.canonical.append(values["href"])
        if tag == "meta" and values.get("name") == "description":
            self.description.append(values.get("content", ""))
        if tag == "title":
            self.in_title = True
        if tag == "script" and values.get("type", "").lower() == "application/ld+json":
            self.in_json_ld = True
            self.json_ld_parts = []

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self.in_title = False
        if tag == "script" and self.in_json_ld:
            self.in_json_ld = False
            self.json_ld_blocks.append("".join(self.json_ld_parts).strip())
            self.json_ld_parts = []

    def handle_data(self, data: str) -> None:
        if self.in_title:
            self.title_parts.append(data)
        if self.in_json_ld:
            self.json_ld_parts.append(data)

    @property
    def title(self) -> str:
        return "".join(self.title_parts).strip()


def slugify(value: object) -> str:
    text = str(value or "").lower()
    for source, target in {"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"}.items():
        text = text.replace(source, target)
    text = "".join(char if char.isalnum() else "-" for char in text)
    return "-".join(part for part in text.split("-") if part)[:80] or "sendung"


def clean_archive_title(value: object) -> str:
    title = " ".join(str(value or "").split())
    title = re.sub(r"\s*\(\s*(20\d{2})[-_.](\d{1,2})[-_.](\d{1,2})\s*\)\s*$", "", title)
    title = re.sub(r"\s+(20\d{2})[-_.](\d{1,2})[-_.](\d{1,2})\s*$", "", title)
    return title.strip()


def detail_path(kind: str, item: dict) -> str:
    title = clean_archive_title(item.get("title_de") or item.get("title") or "sendung")
    date_value = str(item.get("date") or "")[:10]
    folder = "termine" if kind == "upcoming" else "sendungen"
    return f"{folder}/{date_value}-{slugify(title)}/"


def calendar_filename(item: dict) -> str:
    return f"{str(item.get('date') or '')[:10]}-{slugify(item.get('title_de') or 'termin')}.ics"


def artwork_stem(item: dict) -> str:
    return f"{str(item.get('date') or '')[:10]}-{slugify(item.get('title_de') or item.get('title') or 'sendung')}"


def http_url(value: object) -> bool:
    parsed = urlparse(str(value or "").strip())
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def validate_url(errors: list[str], context: str, value: object) -> None:
    if value not in (None, "") and not http_url(value):
        errors.append(f"{context} must be an absolute http(s) URL")


def validate_local_asset(errors: list[str], root: Path, context: str, value: object) -> None:
    raw = str(value or "").strip()
    if not raw or raw.startswith(("http://", "https://")):
        return
    candidate = (root / raw.lstrip("/")).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError:
        errors.append(f"{context} points outside the repository: {raw}")
        return
    if not candidate.is_file():
        errors.append(f"{context} references a missing local file: {raw}")


def validate_episode_number(errors: list[str], context: str, item: dict) -> None:
    value = item.get("episode_number")
    if value in (None, ""):
        return
    if isinstance(value, bool):
        errors.append(f"{context}.episode_number must be a positive integer")
        return
    try:
        number = int(value)
    except (TypeError, ValueError):
        errors.append(f"{context}.episode_number must be a positive integer")
        return
    if number <= 0 or str(number) != str(value).strip():
        errors.append(f"{context}.episode_number must be a positive integer")


def validate_editorial_list(errors: list[str], context: str, value: object) -> None:
    if value in (None, ""):
        return
    if not isinstance(value, list):
        errors.append(f"{context} must be an array")
        return
    for index, row in enumerate(value, start=1):
        row_context = f"{context}[{index}]"
        if isinstance(row, str):
            if not row.strip():
                errors.append(f"{row_context} must not be empty")
            continue
        if not isinstance(row, dict):
            errors.append(f"{row_context} must be an object")
            continue
        if not str(row.get("title") or "").strip():
            errors.append(f"{row_context} is missing title")
        validate_url(errors, f"{row_context}.url", row.get("url"))


def validate_social_image(errors: list[str], root: Path, context: str, item: dict) -> None:
    raw = str(item.get("social_image") or "").strip()
    if not raw:
        return
    if not urlparse(raw).path.lower().endswith(".png"):
        errors.append(f"{context}.social_image must reference a PNG file")
    if raw.startswith(("http://", "https://")):
        validate_url(errors, f"{context}.social_image", raw)
    else:
        validate_local_asset(errors, root, f"{context}.social_image", raw)


def validate_common_entry(errors: list[str], root: Path, context: str, item: dict) -> None:
    validate_episode_number(errors, context, item)
    validate_local_asset(errors, root, f"{context}.image", item.get("image"))
    validate_social_image(errors, root, context, item)
    legacy = sorted(FORBIDDEN_LEGACY_FIELDS.intersection(item))
    if legacy:
        errors.append(f"{context} uses removed legacy fields: {', '.join(legacy)}")


def validate_source(root: Path) -> int:
    errors: list[str] = []
    warnings: list[str] = []
    required_files = [
        root / ".pages.yml",
        root / "CONTENT-LICENSE.md",
        root / "scripts" / "build.py",
        root / "scripts" / "check.py",
        root / "scripts" / "update_archive.py",
        root / "scripts" / "validate_site.py",
        root / "templates" / "index.html",
        root / "templates" / "detail.html",
        root / "templates" / "legal.html",
        root / "templates" / "404.html",
        root / "docs" / "structured-data.md",
        root / "content" / "site.json",
        root / "content" / "episodes.json",
        root / "content" / "upcoming-broadcasts.json",
        root / "content" / "upcoming-events.json",
        root / "content" / "legal.json",
        root / "content" / "archive-cache.json",
    ]
    for path in required_files:
        if not path.is_file():
            errors.append(f"missing required source file: {path.relative_to(root)}")

    json_paths = [
        root / "content" / "site.json",
        root / "content" / "episodes.json",
        root / "content" / "upcoming-broadcasts.json",
        root / "content" / "upcoming-events.json",
        root / "content" / "legal.json",
        root / "content" / "archive-cache.json",
    ]
    parsed_json: dict[str, object] = {}
    for path in json_paths:
        if not path.is_file():
            continue
        try:
            parsed_json[path.name] = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"invalid JSON in {path.relative_to(root)}: {exc}")

    site = parsed_json.get("site.json")
    if not isinstance(site, dict):
        errors.append("content/site.json must contain a JSON object")
        site = {}
    else:
        for key in ("name", "description_de", "description_en", "radio", "featured_audio_urls"):
            if not site.get(key):
                errors.append(f"content/site.json is missing required key: {key}")
        if "locale" in site or "mixes" in site:
            errors.append("content/site.json still contains removed locale/mixes configuration")
        featured = site.get("featured_audio_urls")
        if not isinstance(featured, list) or not 1 <= len(featured) <= 5:
            errors.append("content/site.json featured_audio_urls must contain 1 to 5 URLs")
        elif len(set(map(str, featured))) != len(featured):
            errors.append("content/site.json featured_audio_urls contains duplicates")
        else:
            for index, value in enumerate(featured, start=1):
                validate_url(errors, f"content/site.json featured_audio_urls[{index}]", value)
        radio = site.get("radio") if isinstance(site.get("radio"), dict) else {}
        validate_url(errors, "content/site.json radio.url", radio.get("url"))
        validate_url(errors, "content/site.json radio.stream_url", radio.get("stream_url"))
        for index, value in enumerate(site.get("social") or [], start=1):
            if isinstance(value, dict):
                validate_url(errors, f"content/site.json social[{index}].url", value.get("url"))
        for index, value in enumerate(site.get("team") or [], start=1):
            if isinstance(value, dict):
                validate_url(errors, f"content/site.json team[{index}].alias_url", value.get("alias_url"))

    archive_entries = parsed_json.get("episodes.json")
    if not isinstance(archive_entries, list):
        errors.append("content/episodes.json must contain a JSON array")
        archive_entries = []
    archive_urls: Counter[str] = Counter()
    detail_paths: Counter[str] = Counter()
    expected_artwork: set[str] = set()
    for index, episode in enumerate(archive_entries, start=1):
        context = f"content/episodes.json entry {index}"
        if not isinstance(episode, dict):
            errors.append(f"{context} must be an object")
            continue
        for key in ("date", "title_de", "title_en", "audio_url"):
            if not episode.get(key):
                errors.append(f"{context} is missing required key: {key}")
        validate_common_entry(errors, root, context, episode)
        validate_url(errors, f"{context}.audio_url", episode.get("audio_url"))
        validate_editorial_list(errors, f"{context}.music_presentations", episode.get("music_presentations"))
        validate_editorial_list(errors, f"{context}.tracklist", episode.get("tracklist"))
        url = str(episode.get("audio_url") or "").rstrip("/")
        if url:
            archive_urls[url] += 1
        expected_artwork.add(artwork_stem(episode))
    for url, count in archive_urls.items():
        if count > 1:
            errors.append(f"content/episodes.json contains duplicate audio_url: {url}")

    upcoming_identity: Counter[tuple[str, str]] = Counter()
    calendar_names: Counter[str] = Counter()
    for filename, required_keys, kind in (
        ("upcoming-broadcasts.json", ("date", "title_de", "title_en", "details_de", "details_en"), "broadcast"),
        ("upcoming-events.json", ("date", "title_de", "title_en", "details_de", "details_en", "location"), "event"),
    ):
        entries = parsed_json.get(filename)
        if not isinstance(entries, list):
            errors.append(f"content/{filename} must contain a JSON array")
            continue
        for index, entry in enumerate(entries, start=1):
            context = f"content/{filename} entry {index}"
            if not isinstance(entry, dict):
                errors.append(f"{context} must be an object")
                continue
            for key in required_keys:
                if not entry.get(key):
                    errors.append(f"{context} is missing required key: {key}")
            validate_common_entry(errors, root, context, entry)
            date_value = str(entry.get("date") or "")
            if re.search(r"(?:Z|[+-]\d{2}:?\d{2})$", date_value):
                errors.append(f"{context}.date must be local Leipzig time without a UTC offset")
            try:
                start = datetime.fromisoformat(date_value)
            except ValueError:
                errors.append(f"{context}.date is not a valid ISO local date/time")
                start = None
            if entry.get("end"):
                try:
                    end = datetime.fromisoformat(str(entry["end"]))
                    if start and end <= start:
                        errors.append(f"{context}.end must be later than date")
                except ValueError:
                    errors.append(f"{context}.end is not a valid ISO local date/time")
            if kind == "event" and entry.get("episode_number") not in (None, ""):
                errors.append(f"{context}.episode_number is only valid for broadcasts")
            for link_index, link in enumerate(entry.get("links") or [], start=1):
                if not isinstance(link, dict):
                    errors.append(f"{context}.links[{link_index}] must be an object")
                    continue
                if not link.get("label_de") or not link.get("url"):
                    errors.append(f"{context}.links[{link_index}] requires label_de and url")
                validate_url(errors, f"{context}.links[{link_index}].url", link.get("url"))
            upcoming_identity[(date_value, str(entry.get("title_de") or "").casefold())] += 1
            detail_paths[detail_path("upcoming", entry)] += 1
            calendar_names[calendar_filename(entry)] += 1
            expected_artwork.add(artwork_stem(entry))

    for identity, count in upcoming_identity.items():
        if count > 1:
            errors.append(f"duplicate upcoming date/title identity: {identity[0]} / {identity[1]}")
    for filename, count in calendar_names.items():
        if count > 1:
            errors.append(f"duplicate calendar filename: {filename}")

    archive_cache = parsed_json.get("archive-cache.json")
    cache_entries: list[dict] = []
    if not isinstance(archive_cache, dict):
        errors.append("content/archive-cache.json must contain a JSON object")
    else:
        raw_entries = archive_cache.get("episodes", archive_cache.get("tracks"))
        if not isinstance(raw_entries, list):
            errors.append("content/archive-cache.json episodes/tracks must be a JSON array")
        else:
            cache_entries = [item for item in raw_entries if isinstance(item, dict)]
            for item in cache_entries:
                expected_artwork.add(artwork_stem({
                    "date": item.get("date"),
                    "title": clean_archive_title(item.get("title")),
                }))
    # Recreate the final archive identities closely enough to catch detail-URL
    # collisions after cache metadata and local editorial overrides are merged.
    local_by_url = {
        str(item.get("audio_url") or "").rstrip("/"): item
        for item in archive_entries
        if isinstance(item, dict) and item.get("audio_url")
    }
    final_archive: list[dict] = []
    seen_final_urls: set[str] = set()
    for cached in cache_entries:
        url = str(cached.get("audio_url") or "").rstrip("/")
        if not url or not cached.get("date") or not cached.get("title"):
            continue
        merged = {
            "date": str(cached["date"]),
            "title_de": clean_archive_title(cached["title"]),
        }
        if url in local_by_url:
            merged.update(local_by_url[url])
        final_archive.append(merged)
        seen_final_urls.add(url)
    for local in archive_entries:
        if not isinstance(local, dict):
            continue
        url = str(local.get("audio_url") or "").rstrip("/")
        if url and url not in seen_final_urls:
            final_archive.append(local)
    for item in final_archive:
        detail_paths[detail_path("episode", item)] += 1
    for path, count in detail_paths.items():
        if count > 1:
            errors.append(f"duplicate generated detail URL: /{path}")

    if isinstance(site, dict) and isinstance(site.get("featured_audio_urls"), list):
        known_urls = archive_urls | Counter(
            str(item.get("audio_url") or "").rstrip("/") for item in cache_entries
        )
        for value in site["featured_audio_urls"]:
            if str(value).rstrip("/") not in known_urls:
                errors.append(f"featured_audio_url is not present in archive data: {value}")

    legal = parsed_json.get("legal.json")
    if not isinstance(legal, dict):
        errors.append("content/legal.json must contain a JSON object")

    artwork_dir = root / "assets" / "images" / "episodes"
    if artwork_dir.is_dir():
        for image in artwork_dir.iterdir():
            if image.is_file() and image.suffix.lower() in ARTWORK_EXTENSIONS:
                if image.stem not in expected_artwork:
                    warnings.append(f"orphaned episode artwork (review manually): {image.relative_to(root)}")

    if warnings:
        print("Source validation warnings:", file=sys.stderr)
        for warning in warnings:
            print(f"- {warning}", file=sys.stderr)
    if errors:
        print("Source validation failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print(f"Validated {len(json_paths)} source JSON files and required project files.")
    return 0


def output_target(public: Path, path: str) -> Path:
    clean = unquote(path).split("?", 1)[0].lstrip("/")
    if not clean:
        return public / "index.html"
    candidate = public / clean
    if clean.endswith("/") or candidate.is_dir():
        return candidate / "index.html"
    return candidate


def internal_target(public: Path, source: Path, href: str) -> tuple[Path | None, str]:
    parsed = urlparse(href)
    if parsed.scheme in {"mailto", "tel", "data", "javascript", "webcal"}:
        return None, ""
    if parsed.scheme in {"http", "https"}:
        if parsed.hostname not in SITE_HOSTS:
            return None, ""
        return output_target(public, parsed.path), parsed.fragment
    if parsed.scheme or parsed.netloc:
        return None, ""
    if not parsed.path:
        return source, parsed.fragment
    if parsed.path.startswith("/"):
        return output_target(public, parsed.path), parsed.fragment
    target = (source.parent / unquote(parsed.path)).resolve()
    try:
        target.relative_to(public.resolve())
    except ValueError:
        return target, parsed.fragment
    if parsed.path.endswith("/") or target.is_dir():
        target = target / "index.html"
    return target, parsed.fragment


def parse_document(path: Path) -> tuple[DocumentParser, str]:
    text = path.read_text(encoding="utf-8")
    parser = DocumentParser()
    parser.feed(text)
    return parser, text


def validate_public(public: Path) -> int:
    errors: list[str] = []
    if not public.is_dir():
        print(f"ERROR: generated directory does not exist: {public}", file=sys.stderr)
        return 1
    html_files = sorted(public.rglob("*.html"))
    parsed_documents: dict[Path, DocumentParser] = {}
    for path in html_files:
        parser, text = parse_document(path)
        parsed_documents[path.resolve()] = parser
        relative = path.relative_to(public)
        unresolved = PLACEHOLDER_RE.findall(text)
        if unresolved:
            errors.append(f"{relative}: unresolved template placeholders: {sorted(set(unresolved))}")
        duplicates = sorted(value for value, count in Counter(parser.ids).items() if count > 1)
        if duplicates:
            errors.append(f"{relative}: duplicate HTML ids: {duplicates}")
        if not parser.html_lang:
            errors.append(f"{relative}: missing html[lang]")
        if not parser.title:
            errors.append(f"{relative}: missing <title>")
        if relative.name != "404.html":
            if len(parser.canonical) != 1:
                errors.append(f"{relative}: expected one canonical URL, found {len(parser.canonical)}")
            if not parser.description or not parser.description[0].strip():
                errors.append(f"{relative}: missing meta description")
        for index, block in enumerate(parser.json_ld_blocks, start=1):
            try:
                value = json.loads(block)
                if not isinstance(value, dict) or value.get("@context") != "https://schema.org":
                    errors.append(f"{relative}: JSON-LD block {index} lacks the Schema.org context")
            except json.JSONDecodeError as exc:
                errors.append(f"{relative}: invalid JSON-LD block {index}: {exc}")
        is_structured = relative == Path("index.html") or (
            len(relative.parts) >= 3 and relative.parts[0] in {"sendungen", "termine"}
        )
        if is_structured and not parser.json_ld_blocks:
            errors.append(f"{relative}: missing structured data")
        if relative == Path("index.html") and re.search(r"<iframe\b", text, flags=re.IGNORECASE):
            errors.append("index.html: SoundCloud iframe must not be present before user interaction")

    for source, parser in parsed_documents.items():
        for tag, href in parser.links:
            target, fragment = internal_target(public, source, href)
            if target is None:
                continue
            if not target.exists():
                expected = target.relative_to(public) if public in target.parents else target
                errors.append(f"{source.relative_to(public)}: broken internal {tag} reference {href!r} (expected {expected})")
                continue
            if fragment and target.suffix.lower() in {".html", ""}:
                document_path = target if target.suffix.lower() == ".html" else target / "index.html"
                target_parser = parsed_documents.get(document_path.resolve())
                if target_parser and fragment not in target_parser.ids:
                    errors.append(f"{source.relative_to(public)}: fragment #{fragment} not found in {document_path.relative_to(public)}")

    for name in ("index.html", "404.html", "feed.xml", "sitemap.xml", "robots.txt", "archive.json", "calendar.ics"):
        if not (public / name).exists():
            errors.append(f"missing required generated file: {name}")

    sitemap_locations: list[str] = []
    try:
        sitemap_root = ET.parse(public / "sitemap.xml").getroot()
        namespace = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        sitemap_locations = [element.text or "" for element in sitemap_root.findall("sm:url/sm:loc", namespace)]
        if not sitemap_locations:
            errors.append("sitemap.xml contains no URLs")
        for location in sitemap_locations:
            parsed = urlparse(location)
            if parsed.hostname not in SITE_HOSTS:
                errors.append(f"sitemap.xml contains an unexpected host: {location}")
            elif not output_target(public, parsed.path).exists():
                errors.append(f"sitemap.xml points to a missing page: {location}")
    except (OSError, ET.ParseError) as exc:
        errors.append(f"invalid sitemap.xml: {exc}")

    detail_canonicals = {
        parser.canonical[0]
        for path, parser in parsed_documents.items()
        if parser.canonical and path.relative_to(public).parts[0] in {"sendungen", "termine"}
    }
    missing_from_sitemap = sorted(detail_canonicals.difference(sitemap_locations))
    if missing_from_sitemap:
        errors.append(f"detail pages missing from sitemap: {missing_from_sitemap}")

    try:
        ET.parse(public / "feed.xml")
    except (OSError, ET.ParseError) as exc:
        errors.append(f"invalid feed.xml: {exc}")
    try:
        archive = json.loads((public / "archive.json").read_text(encoding="utf-8"))
        if archive.get("count") != len(archive.get("episodes", [])):
            errors.append("archive.json count does not match its episode list")
    except (OSError, json.JSONDecodeError, AttributeError) as exc:
        errors.append(f"invalid archive.json: {exc}")

    if errors:
        print("Generated-site validation failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    detail_pages = len(list((public / "sendungen").glob("*/index.html"))) + len(
        list((public / "termine").glob("*/index.html"))
    )
    print(f"Validated {len(html_files)} HTML files and {detail_pages} detail pages successfully.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate project source files or generated output")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--source", action="store_true")
    mode.add_argument("--public", nargs="?", const=Path("public"), type=Path, metavar="DIR")
    parser.add_argument("public_dir", nargs="?", type=Path)
    args = parser.parse_args()
    if args.source:
        if args.public_dir is not None:
            parser.error("a public directory cannot be combined with --source")
        return validate_source(Path.cwd().resolve())
    if args.public is not None and args.public_dir is not None:
        parser.error("specify the generated directory either with --public or positionally, not both")
    return validate_public((args.public or args.public_dir or Path("public")).resolve())


if __name__ == "__main__":
    raise SystemExit(main())
