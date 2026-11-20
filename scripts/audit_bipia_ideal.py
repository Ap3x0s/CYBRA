"""Найти все записи BIPIA, где эталон противоречит контексту.

Задача: перед правкой понять масштаб. Для каждой записи с ideal='unknown'
проверяем, есть ли в письме/таблице сущность из вопроса вместе с ответом.
Если есть — эталон спорный и должен быть либо исправлен, либо помечен.

Скрипт НИЧЕГО не меняет: только показывает, что будет правлено.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def entity_of(question: str) -> str:
    """О ком/чём спрашивают: последнее имя в «paid to X?» или «paid by X?»."""
    patterns = [
        r'paid to ([A-Za-z][\w&.\- ]*?)\?',
        r'paid by ([A-Za-z][\w&.\- ]*?)\?',
        r'from ([A-Za-z][\w&.\- ]*?)\?',
    ]
    for pattern in patterns:
        match = re.search(pattern, question or '', re.I)
        if match:
            return match.group(1).strip()
    return ''


def amount_near(context: str, entity: str) -> str:
    """Сумма в той же строке, где упомянута сущность."""
    for line in (context or '').split('\n'):
        if entity.lower() in line.lower():
            found = re.findall(r'\$[\d,]+\.?\d*', line)
            if found:
                return found[0]
    return ''


def main() -> int:
    total_checked = 0
    suspect = []
    for task in ('email', 'table'):
        path = ROOT / 'datasets' / 'bipia' / task / 'test.jsonl'
        if not path.exists():
            continue
        rows = [json.loads(line) for line in
                path.read_text(encoding='utf-8').splitlines() if line.strip()]
        print(f'{task}: записей {len(rows)}')
        for index, row in enumerate(rows):
            total_checked += 1
            ideal = str(row.get('ideal') or '').strip()
            if ideal.lower() != 'unknown':
                continue
            entity = entity_of(row.get('question') or '')
            if not entity:
                continue
            context = row.get('context') or ''
            if entity.lower() not in context.lower():
                continue
            amount = amount_near(context, entity)
            suspect.append({
                'task': task, 'index': index, 'entity': entity,
                'amount': amount, 'question': row.get('question'),
            })
        print()

    print(f'проверено записей: {total_checked}')
    print(f'эталон противоречит контексту: {len(suspect)}')
    print()
    for item in suspect:
        print(f"{item['task']:6} #{item['index']:2}  "
              f"{item['entity']:20} сумма в контексте: "
              f"{item['amount'] or 'не найдена'}")
        if not item['amount']:
            print(f"          вопрос: {item['question'][:80]}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
