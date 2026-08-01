#!/usr/bin/env python3
"""Validate source JSON and generated static-site output using the stdlib only."""
from __future__ import annotations

import argparse
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlparse
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "public"
SOURCE_JSON = [
    ROOT / "content" / "site.json",
    ROOT / "content" / "episodes.json",
    ROOT / "content" / "legal.json",
    ROOT / "content" / "archive-cache.json",
]
PLACEHOLDER_RE = re.compile(r"\{\{\s*[A-Za-z0-9_]+\s*\}\}")


class PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.ids: list[str] = []
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if values.get("id"):
            self.ids.append(str(values["id"]))
        if tag in {"a", "link"} and values.get("href"):
            self.links.append(str(values["href"]))
        if tag in {"img", "script", "iframe", "source"} and values.get("src"):
            self.links.append(str(values["src"]))


def fail(messages: list[str]) -> None:
    for message in messages:
        print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def validate_source() -> None:
    errors: list[str] = []
    for path in SOURCE_JSON:
        try:
            json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:  # report the exact file and parser error
            errors.append(f"{path.relative_to(ROOT)}: {exc}")

    site_path = ROOT / "content" / "site.json"
    try:
        site = json.loads(site_path.read_text(encoding="utf-8"))
        url = str(site.get("url") or "")
        if not url.startswith("https://"):
            errors.append("content/site.json: url must be an absolute HTTPS URL")
    except Exception:
        pass

    if errors:
        fail(errors)
    print(f"Validated {len(SOURCE_JSON)} source JSON files.")


def href_to_file(page: Path, href: str) -> Path | None:
    parsed = urlparse(href)
    if parsed.scheme or parsed.netloc or href.startswith(("mailto:", "tel:", "data:")):
        return None
    raw_path = unquote(parsed.path)
    if not raw_path:
        return page
    if raw_path.startswith("/"):
        candidate = PUBLIC / raw_path.lstrip("/")
    else:
        candidate = page.parent / raw_path
    if candidate.is_dir() or raw_path.endswith("/"):
        candidate = candidate / "index.html"
    return candidate.resolve()


def validate_public() -> None:
    errors: list[str] = []
    html_files = sorted(PUBLIC.rglob("*.html"))
    if not html_files:
        fail(["public/: no generated HTML files found"])

    public_root = PUBLIC.resolve()
    for page in html_files:
        text = page.read_text(encoding="utf-8")
        unresolved = PLACEHOLDER_RE.findall(text)
        if unresolved:
            errors.append(f"{page.relative_to(ROOT)}: unresolved placeholders {sorted(set(unresolved))}")

        parser = PageParser()
        parser.feed(text)
        duplicate_ids = sorted({value for value in parser.ids if parser.ids.count(value) > 1})
        if duplicate_ids:
            errors.append(f"{page.relative_to(ROOT)}: duplicate IDs {duplicate_ids}")

        for href in parser.links:
            target = href_to_file(page, href)
            if target is None:
                continue
            try:
                target.relative_to(public_root)
            except ValueError:
                errors.append(f"{page.relative_to(ROOT)}: internal link escapes public/: {href}")
                continue
            if not target.exists():
                errors.append(f"{page.relative_to(ROOT)}: missing internal target {href}")

    sitemap = PUBLIC / "sitemap.xml"
    feed = PUBLIC / "feed.xml"
    for xml_path in (sitemap, feed):
        if not xml_path.exists():
            errors.append(f"{xml_path.relative_to(ROOT)} is missing")
            continue
        try:
            ElementTree.parse(xml_path)
        except ElementTree.ParseError as exc:
            errors.append(f"{xml_path.relative_to(ROOT)}: invalid XML: {exc}")

    if sitemap.exists():
        sitemap_text = sitemap.read_text(encoding="utf-8")
        detail_page_count = sum(1 for path in html_files if "sendungen" in path.parts or "termine" in path.parts)
        sitemap_detail_count = sitemap_text.count("/sendungen/") + sitemap_text.count("/termine/")
        if sitemap_detail_count != detail_page_count:
            errors.append(
                f"public/sitemap.xml contains {sitemap_detail_count} detail URLs, "
                f"but {detail_page_count} detail pages were generated"
            )

    if errors:
        fail(errors)
    print(f"Validated {len(html_files)} generated HTML pages and their internal assets/links.")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", action="store_true", help="validate source JSON")
    parser.add_argument("--public", action="store_true", help="validate generated public files")
    args = parser.parse_args()
    if not args.source and not args.public:
        args.source = args.public = True
    if args.source:
        validate_source()
    if args.public:
        validate_public()


if __name__ == "__main__":
    main()
