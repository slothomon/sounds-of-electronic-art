#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys

TARGET = Path('scripts/build.py')


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise ValueError(f'{label}: expected exactly one matching block, found {count}')
    return text.replace(old, new, 1)


def transform(text: str) -> tuple[str, list[str]]:
    notes: list[str] = []

    text = replace_once(
        text,
        '''def upcoming_detail_inner(\n    item: dict,\n    site: dict,\n    base_path: str,\n    calendar_href: str,\n    heading_tag: str,\n    heading_id: str,\n) -> str:\n''',
        '''def upcoming_detail_inner(\n    item: dict,\n    site: dict,\n    base_path: str,\n    heading_tag: str,\n    heading_id: str,\n) -> str:\n''',
        'upcoming_detail_inner signature',
    )
    notes.append('can remove unused calendar_href from upcoming_detail_inner')

    text = replace_once(
        text,
        '''    actions = external_action_links(item)\n    actions.append(\n        f'<a class="button calendar-button" href="{esc(calendar_href)}" type="text/calendar">'\n        '<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">'\n        '<path d="M7 3v3M17 3v3M4.5 9h15M5 5.5h14a1 1 0 0 1 1 1V20H4V6.5a1 1 0 0 1 1-1Z"/>'\n        '<path d="m9 14 2 2 4-4"/></svg>'\n        '<span data-bilingual data-de="Termin speichern" data-en="Save event">Termin speichern</span></a>'\n    )\n''',
        '''    actions = external_action_links(item)\n    action_html = f'<div class="detail-actions">{"".join(actions)}</div>' if actions else ""\n''',
        'detail calendar action',
    )
    notes.append('can remove Termin speichern from upcoming detail views without leaving an empty action bar')

    text = replace_once(
        text,
        '''        f'{detail_prose(item)}'\n        f'<div class="detail-actions">{"".join(actions)}</div>'\n    )\n''',
        '''        f'{detail_prose(item)}'\n        f'{action_html}'\n    )\n''',
        'upcoming detail action rendering',
    )
    notes.append('can keep external detail links only when present')

    text = replace_once(
        text,
        '''def upcoming_detail_dialog(\n    item: dict,\n    site: dict,\n    base_path: str,\n    calendar_href: str,\n    detail_url: str,\n) -> str:\n''',
        '''def upcoming_detail_dialog(\n    item: dict,\n    site: dict,\n    base_path: str,\n    detail_url: str,\n) -> str:\n''',
        'upcoming_detail_dialog signature',
    )
    text = replace_once(
        text,
        '    inner = upcoming_detail_inner(item, site, base_path, calendar_href, "h2", heading_id)\n',
        '    inner = upcoming_detail_inner(item, site, base_path, "h2", heading_id)\n',
        'upcoming_detail_dialog inner call',
    )
    notes.append('can simplify upcoming_detail_dialog')

    text = replace_once(
        text,
        '''def upcoming_detail_page(\n    item: dict,\n    site: dict,\n    base_path: str,\n    calendar_href: str,\n) -> str:\n''',
        '''def upcoming_detail_page(\n    item: dict,\n    site: dict,\n    base_path: str,\n) -> str:\n''',
        'upcoming_detail_page signature',
    )
    text = replace_once(
        text,
        '    inner = upcoming_detail_inner(item, site, base_path, calendar_href, "h1", heading_id)\n',
        '    inner = upcoming_detail_inner(item, site, base_path, "h1", heading_id)\n',
        'upcoming_detail_page inner call',
    )
    notes.append('can simplify upcoming_detail_page')

    text = replace_once(
        text,
        '        dialogs.append(upcoming_detail_dialog(item, site, base_path, calendar_href, absolute_detail_url))\n',
        '        dialogs.append(upcoming_detail_dialog(item, site, base_path, absolute_detail_url))\n',
        'upcoming_rows dialog call',
    )
    notes.append('can keep the card-level Termin speichern button unchanged')

    text = replace_once(
        text,
        '        calendar_href = site_href(base_path, f"calendar/{calendar_filename(item, site)}")\n        canonical_detail_url = absolute_site_url(canonical_url, relative_path)\n',
        '        canonical_detail_url = absolute_site_url(canonical_url, relative_path)\n',
        'standalone detail calendar_href assignment',
    )
    text = replace_once(
        text,
        '            "detail_content": upcoming_detail_page(item, site, base_path, calendar_href),\n',
        '            "detail_content": upcoming_detail_page(item, site, base_path),\n',
        'standalone detail page call',
    )
    notes.append('can remove the now-unused detail-page calendar variable')

    return text, notes


def main() -> int:
    parser = argparse.ArgumentParser(
        description='Remove the redundant “Termin speichern” action from Demnächst detail views while keeping the card button and calendar subscription.'
    )
    parser.add_argument('--check', action='store_true', help='Only verify that the expected code is present.')
    args = parser.parse_args()

    if not TARGET.exists():
        print(f'ERROR: {TARGET} not found. Run this from the repository root.', file=sys.stderr)
        return 1

    original = TARGET.read_text(encoding='utf-8')
    try:
        updated, notes = transform(original)
    except ValueError as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        return 1

    if args.check:
        for note in notes:
            print(f'OK: {note}')
        print('\nCheck passed. Run without --check to modify scripts/build.py.')
        return 0

    TARGET.write_text(updated, encoding='utf-8', newline='\n')
    for note in notes:
        print(f'OK: {note}')
    print('\nDone. Review with:')
    print('  git diff --check')
    print('  git diff -- scripts/build.py')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
