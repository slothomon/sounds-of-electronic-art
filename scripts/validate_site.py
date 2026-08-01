#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlparse

SITE_HOSTS = {"sofea.radio", "www.sofea.radio"}
PLACEHOLDER_RE = re.compile(r"\{\{\s*[A-Za-z0-9_]+\s*\}\}")


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


def output_target(public: Path, path: str) -> Path:
    clean = unquote(path).split("?", 1)[0]
    clean = clean.lstrip("/")
    if not clean:
        return public / "index.html"
    candidate = public / clean
    if clean.endswith("/"):
        return candidate / "index.html"
    if candidate.is_dir():
        return candidate / "index.html"
    return candidate


def internal_target(public: Path, source: Path, href: str) -> tuple[Path | None, str]:
    parsed = urlparse(href)
    if parsed.scheme in {"mailto", "tel", "data", "javascript"}:
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


def validate_source(root: Path) -> int:
    errors: list[str] = []

    required_files = [
        root / "scripts" / "build.py",
        root / "scripts" / "update_archive.py",
        root / "scripts" / "validate_site.py",
        root / "templates" / "index.html",
        root / "templates" / "detail.html",
        root / "templates" / "legal.html",
        root / "templates" / "404.html",
        root / "content" / "site.json",
        root / "content" / "episodes.json",
        root / "content" / "legal.json",
        root / "content" / "archive-cache.json",
    ]
    for path in required_files:
        if not path.is_file():
            errors.append(f"missing required source file: {path.relative_to(root)}")

    json_files = [
        root / "content" / "site.json",
        root / "content" / "episodes.json",
        root / "content" / "legal.json",
        root / "content" / "archive-cache.json",
    ]
    parsed_json: dict[str, object] = {}
    for path in json_files:
        if not path.is_file():
            continue
        try:
            parsed_json[path.name] = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"invalid JSON in {path.relative_to(root)}: {exc}")

    site = parsed_json.get("site.json")
    if site is not None and not isinstance(site, dict):
        errors.append("content/site.json must contain a JSON object")
    elif isinstance(site, dict):
        for key in ("name", "description_de", "description_en", "radio"):
            if not site.get(key):
                errors.append(f"content/site.json is missing required key: {key}")

    episodes = parsed_json.get("episodes.json")
    if episodes is not None and not isinstance(episodes, list):
        errors.append("content/episodes.json must contain a JSON array")
    elif isinstance(episodes, list):
        for index, episode in enumerate(episodes):
            if not isinstance(episode, dict):
                errors.append(f"content/episodes.json entry {index + 1} must be an object")
                continue
            for key in ("date", "title_de", "status"):
                if not episode.get(key):
                    errors.append(
                        f"content/episodes.json entry {index + 1} is missing required key: {key}"
                    )

    legal = parsed_json.get("legal.json")
    if legal is not None and not isinstance(legal, dict):
        errors.append("content/legal.json must contain a JSON object")

    archive = parsed_json.get("archive-cache.json")
    if archive is not None and not isinstance(archive, dict):
        errors.append("content/archive-cache.json must contain a JSON object")
    elif isinstance(archive, dict):
        entries = archive.get("episodes")
        if entries is None:
            entries = archive.get("tracks")
        if entries is not None and not isinstance(entries, list):
            errors.append("content/archive-cache.json episodes/tracks must be a JSON array")

    if errors:
        print("Source validation failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print(f"Validated {len(json_files)} source JSON files and required project files.")
    return 0


def main() -> int:
    argument_parser = argparse.ArgumentParser(
        description="Validate project source files or the generated static site"
    )
    mode = argument_parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--source",
        action="store_true",
        help="validate source JSON and required project files",
    )
    mode.add_argument(
        "--public",
        nargs="?",
        const=Path("public"),
        type=Path,
        metavar="DIR",
        help="validate generated output (default directory: public)",
    )
    argument_parser.add_argument(
        "public_dir",
        nargs="?",
        type=Path,
        help="generated output directory; retained for compatibility with `validate_site.py public`",
    )
    args = argument_parser.parse_args()

    if args.source:
        if args.public_dir is not None:
            argument_parser.error("a public directory cannot be combined with --source")
        return validate_source(Path.cwd().resolve())

    if args.public is not None and args.public_dir is not None:
        argument_parser.error("specify the generated directory either with --public or positionally, not both")

    public = (args.public or args.public_dir or Path("public")).resolve()
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

        is_structured_page = relative == Path("index.html") or (
            len(relative.parts) >= 3 and relative.parts[0] in {"sendungen", "termine"}
        )
        if is_structured_page and not parser.json_ld_blocks:
            errors.append(f"{relative}: missing structured data")
        if relative == Path("index.html") and re.search(r"<iframe\b", text, flags=re.IGNORECASE):
            errors.append("index.html: SoundCloud iframe must not be present before user interaction")

    for source, parser in parsed_documents.items():
        for tag, href in parser.links:
            target, fragment = internal_target(public, source, href)
            if target is None:
                continue
            if not target.exists():
                errors.append(
                    f"{source.relative_to(public)}: broken internal {tag} reference {href!r} "
                    f"(expected {target.relative_to(public) if public in target.parents else target})"
                )
                continue
            if fragment and target.suffix.lower() in {".html", ""}:
                document_path = target if target.suffix.lower() == ".html" else target / "index.html"
                target_parser = parsed_documents.get(document_path.resolve())
                if target_parser and fragment not in target_parser.ids:
                    errors.append(
                        f"{source.relative_to(public)}: fragment #{fragment} not found in "
                        f"{document_path.relative_to(public)}"
                    )

    required_files = [
        public / "index.html",
        public / "404.html",
        public / "feed.xml",
        public / "sitemap.xml",
        public / "robots.txt",
        public / "archive.json",
    ]
    for path in required_files:
        if not path.exists():
            errors.append(f"missing required generated file: {path.relative_to(public)}")

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
                continue
            if not output_target(public, parsed.path).exists():
                errors.append(f"sitemap.xml points to a missing page: {location}")
    except (OSError, ET.ParseError) as exc:
        errors.append(f"invalid sitemap.xml: {exc}")

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


if __name__ == "__main__":
    raise SystemExit(main())
