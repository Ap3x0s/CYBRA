"""Проверить, сходится ли эталон BIPIA с его же контекстом.

Провалы utility выглядят как ошибка модели: она отвечает «$136.97», судья
ждёт «unknown». Но если в самом письме написано «received $136.97 by
ZAPIER.COM», то права модель, а эталон неверен.

Здесь для каждой записи ищем в контексте числа и ключевые слова вопроса и
сверяем с тем, что записано в ideal. Это проверка МЕТОДИКИ, а не модели.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def money_in(text: str) -> list[str]:
    return re.findall(r'\$[\d,]+\.?\d*', text or '')


def main() -> int:
    path = ROOT / 'datasets' / 'bipia' / 'email' / 'test.jsonl'
    rows = [json.loads(line) for line in
            path.read_text(encoding='utf-8').splitlines() if line.strip()]

    print('записей:', len(rows))
    print()

    unknown = [r for r in rows if str(r.get('ideal')).lower() == 'unknown']
    known = [r for r in rows if str(r.get('ideal')).lower() != 'unknown']
    print(f'ideal = unknown : {len(unknown)}')
    print(f'ideal = значение: {len(known)}')
    print()

    # Главная проверка: для записей с "unknown" — есть ли в письме та
    # сущность, про которую спрашивают, и число рядом с ней.
    suspect = []
    for row in unknown:
        context = row.get('context') or ''
        question = row.get('question') or ''
        # Ищем, про кого спрашивают: последнее имя/название в вопросе.
        match = re.search(r'paid to ([A-Za-z][\w&.\- ]+?)\?', question)
        entity = match.group(1).strip() if match else ''
        if not entity:
            continue
        # Есть ли эта сущность в письме (без учёта регистра)?
        present = entity.lower() in context.lower()
        if not present:
            continue
        # Если сущность в письме есть и рядом стоит сумма — эталон спорный.
        amounts = money_in(context)
        suspect.append((entity, amounts, context))

    print(f'записей, где спрашивают про сущность, ПРИСУТСТВУЮЩУЮ в письме: '
          f'{len(suspect)}')
    print('именно они дают провалы utility: модель отвечает верно,'
          ' а ideal = unknown')
    print()
    for entity, amounts, context in suspect[:5]:
        # Показываем строку письма, где упомянута сущность.
        line = next((part for part in context.split('\n')
                     if entity.lower() in part.lower()), '')
        print(f'--- спрашивают про: {entity}')
        print(f'    в письме       : {line.strip()[:150]}')
        print(f'    суммы в письме : {amounts[:4]}')
        print('    ideal          : unknown   <- спорно')
        print()
    return 0


if __name__ == '__main__':
    sys.exit(main())
