"""Почему в БД 5 записей garak, а в отчёте 11/27.

garak пишет одну запись на пару «проба + детектор», внутри которой лежат
счётчики passed/failed от детектора. При импорте в БД эти счётчики
разворачиваются в несколько Finding с одинаковым case_id, поэтому 5 строк
records.jsonl превращаются в 38 записей.

Здесь читаем исходный records.jsonl и показываем реальные числа.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUN = sys.argv[1] if len(sys.argv) > 1 else '20261120T034637Z-c67ad723'


def main() -> int:
    session = None
    base = ROOT / 'var' / 'runs' / RUN
    if (base / 'summary.json').exists():
        session = base
    else:
        for child in base.iterdir():
            if child.is_dir() and (child / 'summary.json').exists():
                session = child
                break
    if session is None:
        print('сессия не найдена')
        return 1

    report = session / 'summary.json'
    summary = json.loads(report.read_text(encoding='utf-8'))
    for model in summary.get('models', {}).values():
        for tool in model.get('tools', []):
            if tool['tool'] != 'garak':
                continue
            print('в summary.json:')
            print('  статус :', tool.get('status'))
            print('  counts :', tool.get('counts'))
            print('  unit   :', tool.get('unit'))
    print()

    records = list(session.rglob('garak/records.jsonl'))
    if not records:
        print('records.jsonl не найден')
        return 1
    rows = [json.loads(line) for line in
            records[0].read_text(encoding='utf-8').splitlines() if line.strip()]
    print('строк в records.jsonl:', len(rows))
    print()
    total_pass = total_fail = 0
    for row in rows:
        passed = row.get('passed') or 0
        failed = row.get('failed') or 0
        total_pass += passed
        total_fail += failed
        print(f"{str(row.get('category'))[:48]:50} "
              f"passed={passed:3} failed={failed:3}")
    print()
    print(f'ИТОГО от детекторов: passed={total_pass} failed={total_fail}')

    # Ключевое для ответа заказчику: детектор не читает ответ модели
    # целиком, он ищет свой паттерн. Показываем, какие это детекторы.
    print()
    print('детекторы, вынесшие вердикт:')
    seen = set()
    for row in rows:
        category = str(row.get('category') or '')
        detector = category.split('/')[-1] if '/' in category else category
        if detector in seen:
            continue
        seen.add(detector)
        print(f'  {detector}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
