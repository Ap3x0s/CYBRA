"""Переводы текстов ошибок, которые бэкенд отдаёт по-русски.

Найдено аудитом: api.py бросает HTTPException с русским detail, UI показывает
его как есть через ApiError, поэтому в английском интерфейсе ошибки входа и
работы с эндпоинтами оставались русскими. Это третья категория того же бага
(первые две — подписи метрик и литералы разметки).

Формат с подстановкой: params — то, что API подставляет в f-строку. В словаре
храним шаблон с теми же {}, иначе перевод не совпадёт с приходящей строкой.
"""
from __future__ import annotations

import re
from pathlib import Path

I18N = Path('frontend/src/i18n.js')

TRANSLATIONS = {
    'Неверный email или пароль': 'Wrong email or password',
    'Текущий пароль неверен': 'The current password is incorrect',
    'Модель не найдена': 'Model not found',
    'Прогон не найден': 'Run not found',
    'Кейс не найден': 'Case not found',
    'Версия не найдена': 'Version not found',
    'Неизвестная роль': 'Unknown role',
    'Этот прогон не выполняется': 'This run is not in progress',
    'Пользователь с таким email уже существует': 'A user with this email already exists',
    'Выберите хотя бы один инструмент': 'Select at least one tool',
    'Эндпоинт не найден': 'Endpoint not found',
    'Пользователь не найден': 'User not found',
    'Сначала добавьте модель для этого эндпоинта': 'Add a model to this endpoint first',
    'Неподдерживаемый тип файла: {suffix}': 'Unsupported file type: {suffix}',
    'Неизвестные инструменты: {", ".join(unknown)}':
        'Unknown tools: {", ".join(unknown)}',
    # main.py: сообщения при старте и 500-й. Второе видит пользователь.
    'Внутренняя ошибка сервера': 'Internal server error',
    'Отчёт ещё не готов': 'The report is not ready yet',
    'Импорт из {path.name}': 'Import from {path.name}',
    'Импорт файла {file.filename}': 'Import of file {file.filename}',
    'Импортировано из {relative}': 'Imported from {relative}',
    'Первичный импорт из комплекта': 'Initial import from the bundled set',
    'Ветка от {parent.version}': 'Forked from {parent.version}',
    'Правка кейса в {parent.version}': 'Case edit in {parent.version}',
    'Ответ без choices — это не Chat Completions':
        'A response without choices is not Chat Completions',
}


def js_str(value: str) -> str:
    escaped = value.replace('\\', '\\\\').replace("'", "\\'").replace('\n', '\\n')
    return f"'{escaped}'"


def main() -> int:
    text = I18N.read_text(encoding='utf-8')
    en_start = text.index('export const EN = {')
    en_end = text.index('export const DICT')
    block = text[en_start:en_end]

    existing = set(re.findall(r"^\s*'((?:\\.|[^'\\])*)'\s*:", block, re.MULTILINE))
    added = [(ru, en) for ru, en in TRANSLATIONS.items() if ru not in existing]

    if not added:
        print('добавлять нечего')
        return 0

    lines = ''.join(f'  {js_str(ru)}: {js_str(en)},\n' for ru, en in added)
    insert_at = block.rstrip().rfind('}')
    new_block = block[:insert_at] + lines + block[insert_at:]
    I18N.write_text(text[:en_start] + new_block + text[en_end:], encoding='utf-8', newline='\n')

    print(f'добавлено переводов ошибок: {len(added)}')
    for ru, _ in added:
        print(f'  + {ru[:60]!r}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
