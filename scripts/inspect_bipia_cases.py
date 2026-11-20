"""Разобрать спорные записи BIPIA по одной: что в контексте и что ждёт эталон.

Здесь не правим ничего — решаем, какие записи действительно ошибочны.
Три случая требуют отдельного взгляда: там сумма рядом с сущностью не
найдена, и «unknown» может быть верным.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CASES = [0, 2, 8, 19, 24, 29, 36]


def main() -> int:
    path = ROOT / 'datasets' / 'bipia' / 'email' / 'test.jsonl'
    rows = [json.loads(line) for line in
            path.read_text(encoding='utf-8').splitlines() if line.strip()]

    for index in CASES:
        row = rows[index]
        context = row.get('context') or ''
        print('=' * 70)
        print(f'#{index}  ideal={row.get("ideal")!r}')
        print('вопрос:', row.get('question'))
        print()
        # Показываем только фрагменты со суммой — остальное шум.
        amounts = re.findall(r'.{0,80}\$[\d,]+\.?\d*.{0,60}', context)
        print('фрагменты контекста с суммами:')
        for fragment in amounts[:3]:
            print('   ', fragment.replace('\n', ' ').strip()[:150])
        if not amounts:
            print('    (сумм в контексте нет)')
            # Первые строки могут содержать сущность.
            match = re.search(
                rf'.{{0,80}}{re.escape(str(row.get("question"))[18:30])}.{{0,60}}',
                context, re.I)
            if match:
                print('    контекст около сущности:',
                      match.group(0).replace('\n', ' '))
        print()
    return 0


if __name__ == '__main__':
    sys.exit(main())
