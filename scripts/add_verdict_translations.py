"""Добавить в i18n.js переводы строк нового блока «Общий вердикт судьи».

Почему скриптом, а не руками: словарь — 900+ строк, и правка по одной
гарантированно пропустит половину. Здесь список ключей рядом с их переводом,
и скрипт проверяет, что все они реально встречаются в исходниках.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
I18N = ROOT / 'frontend' / 'src' / 'i18n.js'

EN = {
    'Общий вердикт судьи': 'Overall judge verdict',
    'в отчёт': 'in the report',
    'Добавить общий вердикт в отчёт': 'Add an overall verdict to the report',
    'Один запрос к модели-судье на модель прогона, а не на кейс.':
        'One request to the judge model per run model, not per case.',
    'Критерий вердикта': 'Verdict criterion',
    'Вернуть по умолчанию': 'Restore default',
    'Правится свободно: судья получит именно этот текст. Системная рамка с '
    'защитой от инструкций внутри ответов модели не редактируется.':
        'Free to edit: the judge receives exactly this text. The system frame '
        'that protects against instructions inside model answers is not editable.',
    'блокирующих находок нет, объёма достаточно для вывода':
        'no blocking findings, the evidence is sufficient',
    'блокирующих нет, но есть существенные оговорки':
        'no blocking findings, but there are material caveats',
    'есть хотя бы одна блокирующая находка': 'at least one blocking finding',
    'данных не хватает, вердикт не выносится':
        'not enough data, no verdict is issued',
    'Балльного скора нет: у инструментов несравнимые единицы счёта, и среднее '
    'процентов было бы числом без смысла. Вердикт — суждение судьи рядом с '
    'машинными подсчётами, а не вместо них.':
        'There is no numeric score: the tools count incomparable units, and an '
        'average of percentages would be a meaningless number. The verdict is the '
        "judge's judgement alongside the machine counts, not instead of them.",
    'Вердикт судьи:': 'Judge verdict:',
    'допустима': 'acceptable',
    'допустима с оговорками': 'acceptable with caveats',
    'недопустима': 'not acceptable',
    'данных недостаточно': 'insufficient evidence',
    'включён': 'enabled',
    'выключен': 'disabled',
    'свой критерий': 'custom criterion',
    'Вердикт — суждение судьи по описанию выше, а не сертификат безопасности. '
    'Подсчёты в таблицах от него не зависят.':
        "The verdict is the judge's judgement based on the description above, "
        'not a security certificate. The counts in the tables do not depend on it.',
    'Вердикт — суждение судьи, а не сертификат безопасности. Подсчёты в '
    'таблицах от него не зависят.':
        "The verdict is the judge's judgement, not a security certificate. "
        'The counts in the tables do not depend on it.',
}


def render_ru(value: str) -> str:
    return "'" + value.replace('\\', '\\\\').replace("'", "\\'") + "'"


def render_en(value: str) -> str:
    return "'" + value.replace('\\', '\\\\').replace("'", "\\'") + "'"


def main() -> int:
    text = I18N.read_text(encoding='utf-8')

    # Проверяем, что ключи действительно есть в исходниках: перевод
    # неиспользуемой строки — мусор в словаре, который никто не заметит.
    sources = []
    for path in (ROOT / 'frontend' / 'src').rglob('*.jsx'):
        sources.append(path.read_text(encoding='utf-8'))
    haystack = '\n'.join(sources)

    missing_source = []
    for key in EN:
        if key not in haystack:
            missing_source.append(key)
    if missing_source:
        print('НЕТ В ИСХОДНИКАХ:', *missing_source, sep='\n  ')
        return 2

    # --- русский блок: добавляем ключ со значением, равным самому себе ---
    ru_marker = 'const RU = {'
    if ru_marker not in text:
        print('не найден блок RU')
        return 2

    added_ru, added_en = [], []
    for key, value in EN.items():
        ru_line = f'  {render_ru(key)}: {render_ru(key)},'
        if ru_line not in text:
            added_ru.append(ru_line)
        en_line = f'  {render_ru(key)}: {render_en(value)},'
        if en_line not in text:
            added_en.append(en_line)

    if not added_ru and not added_en:
        print('все переводы уже на месте')
        return 0

    # Вставляем в конец соответствующего словаря, перед закрывающей скобкой.
    def append_to(source: str, marker: str, lines: list[str]) -> str:
        start = source.index(marker)
        # Ищем закрывающую скобку словаря: ближайшую строку, начинающуюся с '}'.
        match = re.search(r'^\}$', source[start:], flags=re.M)
        if match is None:
            raise SystemExit(f'не найдена закрывающая скобка для {marker}')
        position = start + match.start()
        return source[:position] + '\n'.join(lines) + '\n' + source[position:]

    if added_ru:
        text = append_to(text, ru_marker, added_ru)
    if added_en:
        text = append_to(text, 'const EN = {', added_en)

    I18N.write_text(text, encoding='utf-8', newline='\n')
    print(f'добавлено RU: {len(added_ru)}, EN: {len(added_en)}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
