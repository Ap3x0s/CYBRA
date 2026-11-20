"""Разобрать файл вывода прогона: report.md и report.html.

Заказчик просил «проверить файл вывода». Проверяем не наличие файла, а его
содержимое: все ли 8 инструментов на месте, сходятся ли счётчики с БД,
корректна ли структура Markdown (таблицы, а не слипшиеся строки), есть ли
раздел вердикта.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUN = sys.argv[1] if len(sys.argv) > 1 else '20261120T003051Z-cecf1b4a'

TOOLS = ['harmbench', 'jailbreakbench', 'bipia', 'security-regression',
         'promptfoo', 'garak', 'pyrit', 'agentdojo']


def find_session(run_dir: Path) -> Path | None:
    if (run_dir / 'report.md').exists():
        return run_dir
    for child in run_dir.iterdir() if run_dir.exists() else []:
        if child.is_dir() and (child / 'report.md').exists():
            return child
    return None


def main() -> int:
    run_dir = ROOT / 'var' / 'runs' / RUN
    session = find_session(run_dir)
    if session is None:
        print('файлы вывода не найдены в', run_dir)
        return 1

    print('каталог сессии:', session.name)
    print('файлы:', ', '.join(sorted(p.name for p in session.iterdir()
                                     if p.is_file())))
    print()

    problems: list[str] = []

    md_path = session / 'report.md'
    html_path = session / 'report.html'
    summary_path = session / 'summary.json'

    for path in (md_path, html_path, summary_path):
        if not path.exists():
            problems.append(f'нет файла {path.name}')
    if problems:
        print(*problems, sep='\n')
        return 1

    md = md_path.read_text(encoding='utf-8')
    html = html_path.read_text(encoding='utf-8')
    summary = json.loads(summary_path.read_text(encoding='utf-8'))

    print(f'report.md   : {len(md)} символов, {len(md.splitlines())} строк')
    print(f'report.html : {len(html)} символов')
    print()

    # 1. Все ли инструменты попали в отчёт.
    missing = [t for t in TOOLS if t not in md]
    print('инструментов в .md:', len(TOOLS) - len(missing), 'из', len(TOOLS))
    if missing:
        problems.append(f'в отчёте нет инструментов: {missing}')

    # 2. Сходятся ли счётчики с summary.json.
    #    Разбираем таблицу по-настоящему: делим строки на ячейки, а не
    #    подгоняем регулярное выражение под пробелы. Первая версия проверки
    #    искала "\s*".join(числа) и падала на "| 35 | 0 | 1 |": между числом
    #    и чертой есть пробелы, которых шаблон не предусматривал.
    rows: dict[str, list[str]] = {}
    for line in md.splitlines():
        if not line.startswith('|') or '---' in line:
            continue
        cells = [cell.strip() for cell in line.strip('|').split('|')]
        if len(cells) >= 5 and cells[0] not in ('Инструмент',):
            rows[cells[0]] = cells

    for result in summary.get('models', {}).values():
        for tool in result.get('tools', []):
            name = tool['tool']
            counts = tool.get('counts') or {}
            expected = [str(counts.get('PASS', 0)), str(counts.get('FAIL', 0)),
                        str(counts.get('ERROR', 0))]
            actual = rows.get(name)
            if actual is None:
                problems.append(f'{name}: нет строки в таблице .md')
                continue
            got = actual[2:5]
            if got != expected:
                problems.append(
                    f'{name}: в .md {got}, в summary.json {expected}')

    # 3. Структура Markdown: таблицы должны иметь шапку с разделителем.
    tables = len(re.findall(r'^\|.*\|$', md, re.M))
    separators = len(re.findall(r'^\|[-: |]+\|$', md, re.M))
    print(f'строк таблиц     : {tables}')
    print(f'разделителей шапок: {separators}')
    if tables and not separators:
        problems.append('таблицы не распознаются: нет строк-разделителей')

    # 4. Вердикт судьи.
    has_verdict = 'Вердикт судьи' in md
    print('раздел вердикта  :', 'есть' if has_verdict else 'НЕТ')
    verdicts = summary.get('verdicts') or {}
    print('вердиктов в JSON :', len(verdicts))
    for model, entry in verdicts.items():
        print(f"  {model}: {entry.get('verdict')} "
              f"проблем={len(entry.get('problems') or [])}")
        problems_list = entry.get('problems') or []
        if problems_list:
            print(f"    причина: {problems_list[0][:120]}")

    # 5. Демо-режим помечен? Прогон настоящий, значит врезки быть не должно.
    is_mock = 'демонстрационном режиме' in md
    print('врезка mock      :', 'есть (ошибка!)' if is_mock else 'нет, верно')
    if is_mock:
        problems.append('в отчёте врезка mock, хотя прогон настоящий')

    print()
    if problems:
        print('ПРОБЛЕМЫ:')
        for problem in problems:
            print('  -', problem)
        return 1
    print('файлы вывода корректны')

    # Показываем начало отчёта, чтобы видеть результат, а не только счётчики.
    print()
    print('=== начало report.md ===')
    print('\n'.join(md.splitlines()[:24]))
    return 0


if __name__ == '__main__':
    sys.exit(main())
