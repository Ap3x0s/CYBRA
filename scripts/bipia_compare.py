"""Сравнить попарно: почему при наличии сущности эталон иногда число, иногда unknown.

Берём две выборки с сущностью в письме (13 unknown и 23 с числом) и смотрим,
чем они отличаются. Если ничем — разметка непоследовательна, и наши провалы
utility не значат ничего о модели.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def entity_of(question: str) -> str:
    match = re.search(r'paid (?:to|by) ([A-Za-z][\w&.\- ]*?)\?', question or '', re.I)
    return match.group(1).strip() if match else ''


def main() -> int:
    path = ROOT / 'datasets' / 'bipia' / 'email' / 'test.jsonl'
    rows = [json.loads(line) for line in
            path.read_text(encoding='utf-8').splitlines() if line.strip()]

    print('=== записи, где сущность есть в письме, а эталон = ЧИСЛО ===')
    for row in rows:
        ideal = str(row.get('ideal') or '')
        if ideal.lower() == 'unknown':
            continue
        entity = entity_of(row.get('question') or '')
        context = row.get('context') or ''
        if not entity or entity.lower() not in context.lower():
            continue
        line = next((p for p in context.split('\n')
                     if entity.lower() in p.lower()), '')
        print(f'  «{entity:16}» ideal={ideal:12} | {line.strip()[:95]}')

    print()
    print('=== записи, где сущность есть в письме, а эталон = unknown ===')
    for row in rows:
        ideal = str(row.get('ideal') or '')
        if ideal.lower() != 'unknown':
            continue
        entity = entity_of(row.get('question') or '')
        context = row.get('context') or ''
        if not entity or entity.lower() not in context.lower():
            continue
        line = next((p for p in context.split('\n')
                     if entity.lower() in p.lower()), '')
        print(f'  «{entity:16}» ideal=unknown     | {line.strip()[:95]}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
