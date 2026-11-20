"""Проверить гипотезу: набор BIPIA не различает направление платежа.

Наблюдение: в записи #5 вопрос «paid to Ganesha», в письме «Ganesha's card
received a $420.00 credit from TYPEFORM», а эталон — $420.00. То есть
сумма взята правильно, но направление проигнорировано.

Если это так, то «unknown» в спорных записях означает не ошибку эталона, а
другое: сумму НЕ нашли вообще. Проверяем, есть ли в тех контекстах сумма,
связанная с сущностью, или же эталон просто неполон.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    path = ROOT / 'datasets' / 'bipia' / 'email' / 'test.jsonl'
    rows = [json.loads(line) for line in
            path.read_text(encoding='utf-8').splitlines() if line.strip()]

    print('всего записей:', len(rows))
    print()

    # Сколько записей имеют ideal, сколько unknown.
    unknown = sum(1 for r in rows
                  if str(r.get('ideal') or '').lower() == 'unknown')
    print(f'ideal = unknown : {unknown} ({100 * unknown / len(rows):.0f}%)')
    print(f'ideal = значение: {len(rows) - unknown}')
    print()

    print('=== есть ли в письме ЛЮБАЯ сумма (независимо от сущности) ===')
    no_amount_unknown = 0
    has_amount_unknown = 0
    for index, row in enumerate(rows):
        context = row.get('context') or ''
        ideal = str(row.get('ideal') or '').lower()
        amounts = re.findall(r'\$[\d,]+\.?\d*', context)
        if ideal == 'unknown':
            if amounts:
                has_amount_unknown += 1
            else:
                no_amount_unknown += 1
    print(f'unknown, но сумма в письме ЕСТЬ : {has_amount_unknown}')
    print(f'unknown, и суммы в письме НЕТ    : {no_amount_unknown}')
    print()

    # Ключевой тест гипотезы: у записей, где ideal — число, совпадает ли
    # оно с первым числом в письме. Если да — набор берёт первое число.
    print('=== совпадает ли ideal с первой суммой письма ===')
    match = miss = 0
    for row in rows:
        ideal = str(row.get('ideal') or '')
        if ideal.lower() == 'unknown':
            continue
        amounts = re.findall(r'\$[\d,]+\.?\d*', row.get('context') or '')
        if not amounts:
            continue
        first = amounts[0].replace(' ', '').replace(',', '')
        target = ideal.replace(' ', '').replace(',', '')
        if target in first or first in target:
            match += 1
        else:
            miss += 1
    print(f'совпало с первой суммой : {match}')
    print(f'не совпало              : {miss}')
    print()
    print('Если совпадений много, набор берёт первое число письма, а не')
    print('разбирает, кому и в какую сторону ушёл платёж. Тогда высокий')
    print('процент провалов BIPIA — свойство набора, а не модели.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
