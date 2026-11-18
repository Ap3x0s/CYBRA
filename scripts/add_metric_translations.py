"""Добавить в EN-блок i18n.js переводы подписей метрик, которых там нет.

Баг: страница «Метрики» рендерит t(definition.label), t(definition.formula),
t(definition.description) и t(definition.caveat) — значения приходят с бэкенда
из metrics.py. Для трёх метрик (просадка под атакой, полезность под инъекцией,
блокировка законных действий) ключей в словаре не было вообще, поэтому в
английском интерфейсе оставался русский текст. Ещё у coverage не была
переведена description с «всего записей» внутри формулы.

Формулы вида FAIL(harmful) / (PASS + FAIL)(harmful) не переводим: это
математика, а не проза. Переводим те, где внутри есть русские слова.
"""
from __future__ import annotations

import re
from pathlib import Path

I18N = Path('frontend/src/i18n.js')

TRANSLATIONS = {
    # --- labels ---
    'Просадка под атакой': 'Degradation under attack',
    'Полезность под инъекцией': 'Utility under injection',
    'Блокировка законных действий': 'Blocking of legitimate actions',

    # --- formulas (только те, где есть русская проза) ---
    '(PASS + FAIL) / всего записей': '(PASS + FAIL) / total records',
    'Безопасность(прямые) − среднее Безопасность(обёртки)':
        'Security(direct) − mean Security(wrappers)',

    # --- descriptions ---
    'Доля записей с вердиктом. Единица — оценено всё.':
        'Share of records that received a verdict. One means everything was scored.',
    'Насколько модель хуже под атакующей обёрткой, чем на том же наборе без неё. '
    'Ноль означает устойчивую защиту; высокое значение — защита рассыпается от переформулировки.':
        'How much worse the model gets under an attacking wrapper than on the same '
        'set without one. Zero means the defence holds; a high value means it falls '
        'apart when the request is rephrased.',
    'Справляется ли модель с законной задачей, когда в контексте лежит инъекция. '
    'Показывает цену защиты: отражение атак не стоит ничего, если попутно ломается работа.':
        'Whether the model still completes a legitimate task when an injection sits in '
        'the context. Shows the price of the defence: repelling attacks is worth '
        'nothing if legitimate work breaks along the way.',
    'Доля законных задач агента, которые не были выполнены. '
    'Показывает, не ломает ли защита нормальную работу агента.':
        'Share of legitimate agent tasks that were not completed. Shows whether the '
        'defence breaks the agent\'s normal operation.',

    # --- caveats ---
    'Считается только там, где есть и прямые запросы, и обёртки (roleplay, authority). '
    'Методология MLCommons AILuminate: сравнение baseline и атаки на одном наборе.':
        'Only computed where both direct requests and wrappers (roleplay, authority) '
        'exist. MLCommons AILuminate methodology: baseline and attack compared on the '
        'same set.',
    'BIPIA делает обе записи (инъекцию и полезность) в одном прогоне, '
    'поэтому «чистой» полезности на том же наборе нет. Сравнивать '
    'стоит с benign_utility_rate других инструментов, а не внутри шага.':
        'BIPIA records both (injection and utility) in one run, so there is no "clean" '
        'utility on the same set. Compare against other tools\' benign_utility_rate '
        'rather than within the step.',
    'Использует baseline-записи AgentDojo — выполнение задачи без инъекции. '
    'Если инструмент не пишет baseline, метрика не вычисляется, а не подменяется нулём.':
        'Uses AgentDojo baseline records — task execution without an injection. If a '
        'tool writes no baseline, the metric is not computed instead of being replaced '
        'with zero.',
}


def js_str(value: str) -> str:
    """Однострочное JS-представление строки: экранируем кавычку и переводы."""
    escaped = value.replace('\\', '\\\\').replace("'", "\\'").replace('\n', '\\n')
    return f"'{escaped}'"


def main() -> int:
    text = I18N.read_text(encoding='utf-8')
    en_start = text.index('export const EN = {')
    en_end = text.index('export const DICT')
    block = text[en_start:en_end]

    existing = set(re.findall(r"^\s*'((?:\\.|[^'\\])*)'\s*:", block, re.MULTILINE))

    added = []
    for ru, en in TRANSLATIONS.items():
        if ru in existing:
            print(f'  уже есть: {ru[:50]!r}')
            continue
        added.append((ru, en))

    if not added:
        print('добавлять нечего')
        return 0

    lines = ''.join(f'  {js_str(ru)}: {js_str(en)},\n' for ru, en in added)

    # Вставляем перед закрывающей скобкой EN-блока, сохраняя перевод строки.
    insert_at = block.rstrip().rfind('}')
    new_block = block[:insert_at] + lines + block[insert_at:]
    text = text[:en_start] + new_block + text[en_end:]

    I18N.write_text(text, encoding='utf-8', newline='\n')
    print(f'добавлено ключей: {len(added)}')
    for ru, _ in added:
        print(f'  + {ru[:60]!r}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
