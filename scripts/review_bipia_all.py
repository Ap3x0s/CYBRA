"""Показать все 13 спорных записей с их контекстом — для решения по каждой.

Нужно отделить настоящие ошибки эталона от случаев, где «unknown»
корректен: например, в письме есть баланс $0.00, но спрашивают про платёж.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ALL = [0, 2, 8, 11, 12, 15, 19, 21, 24, 26, 29, 33, 36]


def main() -> int:
    path = ROOT / 'datasets' / 'bipia' / 'email' / 'test.jsonl'
    rows = [json.loads(line) for line in
            path.read_text(encoding='utf-8').splitlines() if line.strip()]

    for index in ALL:
        row = rows[index]
        context = row.get('context') or ''
        question = row.get('question') or ''
        entity = ''
        match = re.search(r'paid (?:to|by) ([A-Za-z][\w&.\- ]*?)\?', question, re.I)
        if match:
            entity = match.group(1).strip()

        # Ищем строку, где сущность и сумма стоят рядом.
        best = ''
        for line in context.split('\n'):
            if entity and entity.lower() in line.lower():
                if re.search(r'\$[\d,]+\.?\d*', line):
                    best = line.strip()
                    break

        verdict = 'ЭТАЛОН ОШИБОЧЕН' if best else 'проверить вручную'
        print(f'#{index:2} {entity:18} {verdict}')
        if best:
            print(f'     {best[:150]}')
        else:
            print(f'     вопрос: {question[:80]}')
        print()
    return 0


if __name__ == '__main__':
    sys.exit(main())
