"""Проверить направление платежа в BIPIA: «paid to» против «received from».

Моя первая версия была «эталон противоречит контексту». Но в переписке есть
направление: «You received $136.97 BY ZAPIER» — это деньги ПОЛУЧЕНЫ от
Zapier, а вопрос спрашивает «paid TO Zapier». Тогда unknown верен, и ошибки
эталона нет — проверяется как раз способность различить направление.

Здесь сверяем: для записей с конкретным ideal — совпадает ли направление.
Для записей с unknown — есть ли в письме платёж именно В эту сторону.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Направления в тексте письма.
TO_MARKERS = ('sent an ach payment', 'paid', 'charged', 'preauthorized for',
              'you sent', 'payment to')
FROM_MARKERS = ('received', 'credit from', 'you received', 'refund')


def direction(text: str) -> str:
    low = (text or '').lower()
    to_hit = any(marker in low for marker in TO_MARKERS)
    from_hit = any(marker in low for marker in FROM_MARKERS)
    if to_hit and not from_hit:
        return 'to'
    if from_hit and not to_hit:
        return 'from'
    if to_hit and from_hit:
        return 'оба'
    return '?'


def main() -> int:
    path = ROOT / 'datasets' / 'bipia' / 'email' / 'test.jsonl'
    rows = [json.loads(line) for line in
            path.read_text(encoding='utf-8').splitlines() if line.strip()]

    print('=== записи с конкретным эталоном (модель должна была ответить) ===')
    for index, row in enumerate(rows):
        ideal = str(row.get('ideal') or '')
        if ideal.lower() == 'unknown':
            continue
        question = row.get('question') or ''
        context = row.get('context') or ''
        entity = ''
        match = re.search(r'paid (to|by) ([A-Za-z][\w&.\- ]*?)\?', question, re.I)
        prep = match.group(1).lower() if match else '?'
        if match:
            entity = match.group(2).strip()
        # Находим строку с этой суммой.
        line = ''
        for candidate in context.split('\n'):
            if ideal.replace(',', '') in candidate.replace(',', ''):
                line = candidate.strip()
                break
        print(f'#{index:2} «paid {prep} {entity}»  ideal={ideal}')
        print(f'     письмо: {line[:120]}')
        print(f'     направление в письме: {direction(line)}')
        print()

    print('=== записи с unknown ===')
    for index in (0, 2, 8, 11, 12, 15, 19, 21, 24, 26, 29, 33, 36):
        row = rows[index]
        question = row.get('question') or ''
        context = row.get('context') or ''
        match = re.search(r'paid (to|by) ([A-Za-z][\w&.\- ]*?)\?', question, re.I)
        prep = match.group(1).lower() if match else '?'
        entity = match.group(2).strip() if match else ''
        line = ''
        for candidate in context.split('\n'):
            if entity.lower() in candidate.lower() and re.search(r'\$[\d,]+', candidate):
                line = candidate.strip()
                break
        guess = direction(line)
        verdict = 'unknown ВЕРЕН' if guess != prep else 'спорно'
        print(f'#{index:2} «paid {prep:3} {entity:18}» в письме: {guess:5} -> {verdict}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
