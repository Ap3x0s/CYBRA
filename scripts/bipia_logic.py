"""Понять логику эталона BIPIA: почему при сумме в письме стоит unknown.

Факты: ideal с числом всегда равна ПЕРВОЙ сумме письма (23 из 23). А 25
записей с unknown тоже содержат сумму. Значит различие не в наличии суммы,
а в чём-то ещё — скорее всего в том, совпадает ли сущность вопроса с
отправителем/получателем.

Проверяем это попарно: для каждой записи смотрим, есть ли в письме
сущность из вопроса и совпадает ли она с тем, у кого сумма.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def entity_of(question: str) -> tuple[str, str]:
    match = re.search(r'paid (to|by) ([A-Za-z][\w&.\- ]*?)\?', question or '', re.I)
    if not match:
        return '', ''
    return match.group(1).lower(), match.group(2).strip()


def main() -> int:
    path = ROOT / 'datasets' / 'bipia' / 'email' / 'test.jsonl'
    rows = [json.loads(line) for line in
            path.read_text(encoding='utf-8').splitlines() if line.strip()]

    print('Проверяем: совпадает ли сущность вопроса с той, что в письме.')
    print()
    stats = {'unknown_есть': 0, 'unknown_нет': 0,
             'число_есть': 0, 'число_нет': 0}

    for index, row in enumerate(rows):
        prep, entity = entity_of(row.get('question') or '')
        context = row.get('context') or ''
        ideal = str(row.get('ideal') or '').strip()
        present = bool(entity) and entity.lower() in context.lower()

        if ideal.lower() == 'unknown':
            stats['unknown_есть' if present else 'unknown_нет'] += 1
            mark = 'есть' if present else 'нет '
            if present and index in (0, 2, 8, 19, 24, 29, 36):
                print(f'#{index:2} unknown, сущность «{entity}» в письме: {mark}')
        else:
            stats['число_есть' if present else 'число_нет'] += 1

    print()
    print('записи с unknown:  сущность в письме есть:', stats['unknown_есть'],
          '| нет:', stats['unknown_нет'])
    print('записи с числом :  сущность в письме есть:', stats['число_есть'],
          '| нет:', stats['число_нет'])
    print()
    print('Если у unknown сущность ЧАЩЕ есть в письме, чем у числа, то эталон')
    print('устроен не так, как ожидает наш судья, и провалы — свойство набора.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
