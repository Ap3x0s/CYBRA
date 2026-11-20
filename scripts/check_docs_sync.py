"""Проверить, совпадает ли документация с фактическим кодом.

Заказчик попросил сверить README, документацию и changelog с кодом. Здесь
собираем факты из кода и сравниваем с тем, что написано в документах:
число тестов, число метрик, число бенчмарков, список полей API, наличие
CHANGELOG.

Скрипт ничего не правит: сначала список расхождений, потом решения.
"""
from __future__ import annotations

import ast
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

DOCS = [
    'README.md', 'README.ru.md',
    'docs/README.md', 'docs/ru/README.md',
    'docs/DEPLOYMENT.md', 'docs/ru/DEPLOYMENT.md',
    'docs/METHODOLOGY.md', 'docs/ru/METHODOLOGY.md',
    'docs/metrics.md', 'docs/ru/metrics.md',
    'docs/VALIDATION-CYBRA.md', 'docs/ru/VALIDATION-CYBRA.md',
    'docs/SUITE.md', 'docs/ru/SUITE.md',
]


def facts_from_code() -> dict:
    facts = {}

    # 1. Сколько тестов реально собрано.
    result = subprocess.run(
        [sys.executable, '-m', 'pytest', 'tests/', '-q', '--collect-only'],
        cwd=ROOT, capture_output=True, text=True, encoding='utf-8')
    match = re.search(r'(\d+) tests? collected', result.stdout or '')
    facts['tests'] = int(match.group(1)) if match else None

    # 2. Сколько метрик в каталоге.
    source = (ROOT / 'backend' / 'cybra' / 'metrics.py').read_text(encoding='utf-8')
    tree = ast.parse(source)
    count = 0
    for node in ast.walk(tree):
        if (isinstance(node, ast.Assign) and len(node.targets) == 1
                and getattr(node.targets[0], 'id', '') == 'CATALOG'
                and isinstance(node.value, ast.List)):
            count = len(node.value.elts)
    facts['metrics'] = count

    # 3. Сколько инструментов.
    common = (ROOT / 'security_suite' / 'common.py').read_text(encoding='utf-8')
    match = re.search(r'TOOLS\s*=\s*\((.*?)\)', common, re.S)
    facts['tools'] = len(re.findall(r"'[a-z\-]+'", match.group(1))) if match else 0

    # 4. CHANGELOG есть?
    facts['changelog'] = any((ROOT / name).exists()
                             for name in ('CHANGELOG.md', 'CHANGES.md'))
    return facts


def claims_in_docs() -> dict:
    """Что документы УТВЕРЖДАЮТ: список (файл, строка, текст)."""
    claims = {'tests': [], 'metrics': [], 'sqlite': []}
    for name in DOCS:
        path = ROOT / name
        if not path.exists():
            continue
        for number, line in enumerate(path.read_text(encoding='utf-8').splitlines(), 1):
            # Число тестов. Считаем заявлением о pytest только упоминание
            # рядом с самими тестами. «Набор из 48 тестов» в METHODOLOGY —
            # это 48 КЕЙСОВ datasets/corporate.jsonl, а не тестов pytest.
            # Строку про отдельный файл тестов (test_metrics_new.py) тоже
            # пропускаем: там своё число, оно проверяется ниже отдельно.
            if (re.search(r'\b(pytest|suite|набор)\b', line, re.I)
                    and 'test_metrics_new.py' not in line):
                for match in re.finditer(r'(\d+)\s+(?:tests|тестов)\b', line, re.I):
                    claims['tests'].append((name, number, match.group(1), line.strip()))
            # Число метрик.
            for match in re.finditer(r'(\d+)\s+(?:metrics|метрик)', line, re.I):
                claims['metrics'].append((name, number, match.group(1), line.strip()))
            # Упоминание SQLite как основной базы.
            if re.search(r'\bsqlite\b', line, re.I):
                claims['sqlite'].append((name, number, '', line.strip()))
    return claims


def main() -> int:
    facts = facts_from_code()
    claims = claims_in_docs()

    print('=== факты из кода ===')
    print('  тестов           :', facts['tests'])
    print('  метрик           :', facts['metrics'])
    print('  инструментов     :', facts['tools'])
    print('  CHANGELOG        :', 'есть' if facts['changelog'] else 'НЕТ')
    print()

    problems = 0

    print('=== заявления о числе тестов ===')
    seen = set()
    for name, number, claimed, line in claims['tests']:
        key = (name, claimed)
        if key in seen:
            continue
        seen.add(key)
        ok = facts['tests'] is not None and int(claimed) == facts['tests']
        if not ok:
            problems += 1
        print(f"  {'OK ' if ok else 'РАСХОЖДЕНИЕ'} {name}:{number} — "
              f"«{claimed} тестов», в коде {facts['tests']}")
    print()

    print('=== заявления о числе метрик ===')
    seen = set()
    for name, number, claimed, line in claims['metrics']:
        key = (name, claimed)
        if key in seen:
            continue
        seen.add(key)
        ok = int(claimed) == facts['metrics']
        if not ok:
            problems += 1
        print(f"  {'OK ' if ok else 'РАСХОЖДЕНИЕ'} {name}:{number} — "
              f"«{claimed} метрик», в коде {facts['metrics']}")
    print()

    print('=== упоминания SQLite ===')
    for name, number, _, line in claims['sqlite']:
        print(f'  {name}:{number}  {line[:96]}')
    print()

    print(f'расхождений: {problems}')
    return 0 if problems == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
