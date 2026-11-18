"""Аудит переводов: найти всё, что в английском интерфейсе остаётся русским.

Три класса расхождений. Первый нашли раньше, второй — когда баг уехал в
релиз, третий — по ходу разбора.

1. Литерал в разметке. В i18n.js ключ записан со стрелкой — 'метрики →', а
   в коде вызывается t('метрики'). Ключ не находится, t() возвращает входную
   строку, и в EN остаётся русский текст.

2. Подпись приходит с бэкенда и передаётся в t() переменной —
   t(definition.label), где label = 'Просадка под атакой'. Литеральный поиск
   такие случаи не видит вообще: именно поэтому три метрики (просадка под
   атакой, полезность под инъекцией, блокировка законных действий) остались
   непереведёнными, хотя их подписи лежат в metrics.py.

3. Строка бэкенда рендерится вообще без t() — {entry.label} в RunReport.
   Такие места ловятся только глазами, но проверку на них можно поставить:
   любой русский литерал в .jsx вне t() считается нарушением.

Первая версия проверяла «все русские строки в backend/», и это давало 47
ложных срабатываний: в metrics.py многострочные тексты собираются из кусков
('...рассыпается от ' + 'переформулировки.'), и каждый кусок выглядел как
непереведённая подпись. Здесь вместо эвристики — импорт CATALOG: проверяем
ровно те поля, которые UI передаёт в t().

Запуск: python scripts/audit_i18n_keys.py
Код возврата 1, если есть непереведённое.
"""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'frontend' / 'src'
I18N = SRC / 'i18n.js'
BACKEND = ROOT / 'backend'

# Вызов t('строка') или t("строка") — только литералы, не переменные
CALL = re.compile(r"""\bt\(\s*(['"])((?:\\.|(?!\1).)*)\1""")

# Ключи словаря: строки вида 'ключ': 'значение',
KEY = re.compile(r"""^\s*'((?:\\.|[^'\\])*)'\s*:""", re.MULTILINE)

CYRILLIC = re.compile(r'[А-Яа-яЁё]')

# HTML-теги, которые sl-ui передаёт в t() как есть. Это не подписи.
HTML_TAGS = {'div', 'i', 'p', 'span', 'strong', 'b', 'em', 'small'}

# Слова, одинаковые в обоих языках: перевода не требуют, а ключа может не быть.
SAME_IN_BOTH = {'Email', 'PASS', 'FAIL', 'ERROR', 'UNSCORED', 'SKIPPED', 'Seed', 'URL'}

# Временный файл-витрина иконок: не продукт, в репозиторий не входит.
SKIP_FILES = {'IconsPreview.jsx'}

# Поля каталога метрик, которые Metrics.jsx отдаёт в t().
METRIC_FIELDS = ('label', 'formula', 'description', 'caveat')


def keys(lang: str) -> set[str]:
    text = I18N.read_text(encoding='utf-8')
    start = text.index(f'export const {lang.upper()} = {{')
    end = text.index('export const DICT')
    return set(KEY.findall(text[start:end]))


def literals_in_frontend() -> dict[str, list[str]]:
    found: dict[str, list[str]] = {}
    for path in sorted(list(SRC.rglob('*.jsx')) + list(SRC.rglob('*.js'))):
        if path.name == 'i18n.js':
            continue
        text = path.read_text(encoding='utf-8')
        for _, raw in CALL.findall(text):
            if raw in HTML_TAGS or raw in SAME_IN_BOTH:
                continue
            found.setdefault(raw, []).append(str(path.relative_to(ROOT)))
    return found


def untranslated_jsx_strings(en: set[str]) -> dict[str, list[str]]:
    """Русские литералы в .jsx, которые рендерятся в обход t().

    Случай 3: {entry.label} в RunReport подставлял 'полно'/'частично'/'ошибка'
    напрямую, и в EN они оставались русскими; часть help= в NewRun шла без
    t(), хотя соседние — с ним.

    Осторожно с ложными срабатываниями. Литерал в определении данных
    (STATUS_LABEL, STEPS) — не нарушение, если рендер идёт через t(значение):
    наличие такого вызова в файле означает, что значения прогоняются через
    словарь. Дополнительно: если ключ вообще есть в EN, строка переводится —
    это ловит случай, когда t() вызывается в другой строке файла.
    """
    found: dict[str, list[str]] = {}
    literal = re.compile(r"""(['"])((?:\\.|(?!\1).)*[А-Яа-яЁё](?:\\.|(?!\1).)*)\1""")
    renders_via_t = re.compile(r'\{\s*t\(\s*\w')
    for path in sorted(SRC.rglob('*.jsx')):
        if path.name in SKIP_FILES:
            continue
        text = path.read_text(encoding='utf-8')
        coerced = bool(renders_via_t.search(text))
        for line_no, line in enumerate(text.splitlines(), 1):
            stripped = line.lstrip()
            # Комментарии и JSDoc — не рендерятся.
            if stripped.startswith(('//', '*', '/*')):
                continue
            is_definition = bool(re.match(r'\s*(const|let|var)\s', line)) or stripped.startswith('{')
            for match in literal.finditer(line):
                value = match.group(2)
                before = line[:match.start()].rstrip()
                # Внутри t(...) — это перевод, не нарушение.
                if before.endswith('t('):
                    continue
                # Ключ есть в словаре — переводится, даже если t() в другой строке.
                if value in en:
                    continue
                if is_definition and coerced:
                    continue
                found.setdefault(value, []).append(
                    f'{path.relative_to(ROOT)}:{line_no}')
    return found


def metric_fields() -> dict[str, list[str]]:
    """Подписи метрик, которые UI реально передаёт в t().

    Импортировать cybra.metrics нельзя: модуль тянет sqlalchemy, которого нет
    в минимальном образе (python:3.12-slim + pyyaml). В CI это падало с
    ModuleNotFoundError. Разбираем литерал CATALOG стандартным ast — тот же
    результат без единой сторонней зависимости.
    """
    source = (BACKEND / 'cybra' / 'metrics.py').read_text(encoding='utf-8')
    tree = ast.parse(source)

    catalog: list[dict[str, object]] = []
    for node in ast.walk(tree):
        # Ищем `CATALOG = [...]` и соседние присваивания с тем же именем.
        target = None
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            candidate = node.targets[0]
            if isinstance(candidate, ast.Name) and candidate.id == 'CATALOG':
                target = node.value
        if target is None or not isinstance(target, ast.List):
            continue
        for element in target.elts:
            if isinstance(element, ast.Dict):
                catalog.append(ast.literal_eval(element))

    found: dict[str, list[str]] = {}
    for entry in catalog:
        for field in METRIC_FIELDS:
            value = entry.get(field)
            if isinstance(value, str) and CYRILLIC.search(value):
                found.setdefault(value, []).append(
                    f"metrics.py:{entry.get('id')}.{field}")
    return found


def report(title: str, missing: dict[str, list[str]]) -> int:
    if not missing:
        print(f'  {title}: всё переведено')
        return 0
    print(f'  {title}: без ключа в EN — {len(missing)}')
    for key in sorted(missing):
        files = sorted(set(missing[key]))
        print(f'    ✗ {key!r}  ← {", ".join(files[:2])}')
    return len(missing)


def main() -> int:
    en = keys('en')
    ru = keys('ru')
    print(f'ключей в RU: {len(ru)}, в EN: {len(en)}\n')

    # 1. Литералы разметки, переданные в t().
    calls = literals_in_frontend()
    total_calls = sum(len(v) for v in calls.values())
    print(f'вызовов t() литералом: {total_calls}')
    bad1 = report('разметка', {k: v for k, v in calls.items() if k not in en})

    # 2. Подписи метрик с бэкенда (через t(definition.*)).
    metrics = metric_fields()
    bad2 = report('метрики', {k: v for k, v in metrics.items() if k not in en})

    # 3. Русские литералы в .jsx в обход t().
    bare = untranslated_jsx_strings(en)
    bad3 = report('в обход t()', bare)

    only_en = en - ru
    if only_en:
        print(f'\n  ключи только в EN: {len(only_en)}')

    total = bad1 + bad2 + bad3
    print(f'\nитого непереведённого: {total}')
    return 0 if total == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
