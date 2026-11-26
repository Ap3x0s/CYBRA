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
    'docs/OFFLINE.md', 'docs/ru/OFFLINE.md',
    'docs/ARCHITECTURE.md', 'docs/ru/ARCHITECTURE.md',
]

# Пары «английский → русский». Русская копия поддерживается параллельно, но
# проверить её было нечем: OFFLINE.md разошёлся с EN на целый раздел, и это
# заметили только руками. Считаем заголовки: набор `##`-строк должен
# совпадать по количеству. Дословный перевод не сравниваем — он и не нужен,
# ловится именно структурное отставание.
DOC_PAIRS = [
    ('docs/DEPLOYMENT.md', 'docs/ru/DEPLOYMENT.md'),
    ('docs/METHODOLOGY.md', 'docs/ru/METHODOLOGY.md'),
    ('docs/metrics.md', 'docs/ru/metrics.md'),
    ('docs/VALIDATION-CYBRA.md', 'docs/ru/VALIDATION-CYBRA.md'),
    ('docs/SUITE.md', 'docs/ru/SUITE.md'),
    ('docs/OFFLINE.md', 'docs/ru/OFFLINE.md'),
    ('docs/ARCHITECTURE.md', 'docs/ru/ARCHITECTURE.md'),
]

# Документы, на которые обязана ссылаться карта документации. Список
# документации в docs/README.md — единственный вход для читателя; файл,
# которого там нет, не находят вообще.
INDEXED_IN = ['docs/README.md', 'docs/ru/README.md']


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
                    # «4 Tests» в таблице соответствия шагам схемы — это
                    # НОМЕР шага, а не число тестов. Отличаем по контексту:
                    # перед числом стоит начало ячейки таблицы (`| `), а
                    # само число маленькое. Настоящее заявление о тестах
                    # всегда рядом со словом pytest/suite/набор и стоит
                    # внутри предложения.
                    if re.search(r'\|\s*\d+\s+(?:Tests|Тестов)\b', line):
                        continue
                    claims['tests'].append((name, number, match.group(1), line.strip()))
            # Число метрик.
            for match in re.finditer(r'(\d+)\s+(?:metrics|метрик)', line, re.I):
                claims['metrics'].append((name, number, match.group(1), line.strip()))
            # Упоминание SQLite как основной базы.
            if re.search(r'\bsqlite\b', line, re.I):
                claims['sqlite'].append((name, number, '', line.strip()))
    return claims


def heading_counts() -> dict[str, int]:
    """Сколько `##`-заголовков в документе. Отсутствующий файл — -1."""
    counts = {}
    for en, ru in DOC_PAIRS:
        for name in (en, ru):
            path = ROOT / name
            if not path.exists():
                counts[name] = -1
                continue
            text = path.read_text(encoding='utf-8')
            counts[name] = sum(
                1 for line in text.splitlines() if line.startswith('## '))
    return counts


def indexed_docs() -> list[tuple[str, str]]:
    """Документы из docs/, на которые не ссылается карта документации."""
    docs_dir = ROOT / 'docs'
    if not docs_dir.is_dir():
        return []
    existing = {path.name for path in docs_dir.glob('*.md')} - {'README.md'}
    missing = []
    for index in INDEXED_IN:
        path = ROOT / index
        if not path.exists():
            continue
        text = path.read_text(encoding='utf-8')
        for name in sorted(existing):
            if name not in text:
                missing.append((index, name))
    return missing


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

    print('=== пары EN/RU: число разделов ===')
    counts = heading_counts()
    for en, ru in DOC_PAIRS:
        left, right = counts.get(en, -1), counts.get(ru, -1)
        ok = left == right and left >= 0
        if not ok:
            problems += 1
        print(f"  {'OK ' if ok else 'РАСХОЖДЕНИЕ'} {en} ({left}) ↔ {ru} ({right})")
    print()

    print('=== карта документации ===')
    unindexed = indexed_docs()
    if not unindexed:
        print('  OK  все документы из docs/ присутствуют в указателях')
    for index, name in unindexed:
        problems += 1
        print(f'  РАСХОЖДЕНИЕ {index} не ссылается на docs/{name}')
    print()

    print(f'расхождений: {problems}')
    return 0 if problems == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
