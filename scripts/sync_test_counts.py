"""Обновить числа тестов в документации по фактическому состоянию.

Числа «40 тестов» и «15 тестов» разъехались с кодом (сейчас 89 и 23).
Такие цифры устаревают при каждом новом тесте, поэтому проставляем
фактическое значение из pytest, а не правим руками.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# (файл, шаблон, замена). В шаблоне одна группа — само число.
GENERAL = [
    ('README.md', r'(\d+)\s+tests\b'),
    ('README.ru.md', r'(\d+)\s+тестов\b'),
    ('docs/DEPLOYMENT.md', r'(\d+)\s+tests\b'),
    ('docs/ru/DEPLOYMENT.md', r'(\d+)\s+тестов\b'),
    ('docs/VALIDATION-CYBRA.md', r'(\d+)\s+tests\b'),
    ('docs/ru/VALIDATION-CYBRA.md', r'(\d+)\s+тестов\b'),
]


def count(args: list[str]) -> int:
    result = subprocess.run(
        [sys.executable, '-m', 'pytest', *args, '-q'],
        cwd=ROOT, capture_output=True, text=True, encoding='utf-8')
    match = re.search(r'(\d+) passed', result.stdout or '')
    return int(match.group(1)) if match else 0


def main() -> int:
    total = count(['tests/'])
    metrics = count(['tests/test_metrics_new.py'])
    if not total:
        print('не удалось узнать число тестов')
        return 1
    print(f'всего тестов: {total} | тестов метрик: {metrics}')
    print()

    changed = []

    # 1. Отдельно — строки про набор тестов метрик: там своё число.
    for name in ('docs/VALIDATION-CYBRA.md', 'docs/ru/VALIDATION-CYBRA.md'):
        path = ROOT / name
        if not path.exists():
            continue
        text = path.read_text(encoding='utf-8')
        before = text
        text = re.sub(r'(\d+)\s+tests for\b', f'{metrics} tests for', text)
        text = re.sub(r'(\d+)\s+тестов на\b', f'{metrics} тестов на', text)
        if text != before:
            path.write_text(text, encoding='utf-8', newline='\n')
            if name not in changed:
                changed.append(name)

    # 2. Общее число тестов во всех документах.
    for name, pattern in GENERAL:
        path = ROOT / name
        if not path.exists():
            continue
        text = path.read_text(encoding='utf-8')
        before = text
        text = re.sub(pattern, lambda match: f'{total} ' + match.group(0).split()[1],
                      text)
        if text != before:
            path.write_text(text, encoding='utf-8', newline='\n')
            if name not in changed:
                changed.append(name)

    for name in changed:
        print('обновлён:', name)
    return 0


if __name__ == '__main__':
    sys.exit(main())
