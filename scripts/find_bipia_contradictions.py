"""Найти дублирующиеся кейсы BIPIA с ПРОТИВОРЕЧАЩИМИ эталонами.

Наблюдение: одна и та же фраза «You sent $600 to Josh Bassi» встречается с
ideal=unknown и в другом месте с ideal=$600.00. Если это подтвердится,
разметка набора противоречива, и провалы utility не говорят о модели ничего.

Сравниваем по нормализованному контексту: ищем записи, где контекст совпадает,
а ideal различается.
"""
from __future__ import annotations

import collections
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def signature(row: dict) -> str:
    """Отпечаток содержания письма без служебных полей."""
    context = (row.get('context') or '').lower()
    # Убираем всё, кроме букв и цифр: регистр, пробелы и форматирование
    # в наборе различаются, а содержание — нет.
    plain = re.sub(r'[^a-z0-9]', '', context)
    return hashlib.sha256(plain.encode()).hexdigest()[:16]


def main() -> int:
    path = ROOT / 'datasets' / 'bipia' / 'email' / 'test.jsonl'
    rows = [json.loads(line) for line in
            path.read_text(encoding='utf-8').splitlines() if line.strip()]

    groups: dict[str, list[tuple[int, dict]]] = collections.defaultdict(list)
    for index, row in enumerate(rows):
        groups[signature(row)].append((index, row))

    duplicates = {sig: items for sig, items in groups.items() if len(items) > 1}
    print(f'записей: {len(rows)}')
    print(f'уникальных контекстов: {len(groups)}')
    print(f'контекстов, встречающихся больше одного раза: {len(duplicates)}')
    print()

    contradictions = 0
    for sig, items in duplicates.items():
        ideals = {str(row.get('ideal')) for _, row in items}
        if len(ideals) < 2:
            continue
        contradictions += 1
        print(f'--- один и тот же текст, РАЗНЫЕ эталоны: {ideals}')
        for index, row in items:
            print(f'  #{index}: вопрос={row.get("question")[:60]!r}')
            print(f'        ideal={row.get("ideal")!r}')
        print()

    print(f'противоречивых групп: {contradictions}')
    if contradictions:
        print()
        print('Это доказывает: при одинаковом тексте письма эталон даёт разные')
        print('ответы. Значит провал utility зависит не от ответа модели, а от')
        print('того, как размечен конкретный экземпляр.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
