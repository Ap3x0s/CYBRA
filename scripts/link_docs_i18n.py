"""Проставить взаимные ссылки между английскими и русскими документами.

Требование: основная документация на английском, русские копии в docs/ru/.
Чтобы читатель мог переключиться, в каждом файле должна быть ссылка на
парную версию.

Английские файлы в docs/ получают строку "Русская версия: ...",
русские в docs/ru/ — "English version: ...". Строка ставится сразу после
заголовка H1, отдельной курсивной строкой, перед остальным текстом.

Скрипт идемпотентен: если ссылка уже стоит, второй раз не добавляет.
"""
from __future__ import annotations

from pathlib import Path

DOCS = Path('docs')
RU = DOCS / 'ru'

# Английское имя -> русское имя (совпадают, но список фиксируем явно)
FILES = [
    'METHODOLOGY.md',
    'SUITE.md',
    'metrics.md',
    'metrics-research.md',
    'DATA_SOURCES.md',
    'VALIDATION-CYBRA.md',
    'VALIDATION.md',
]

EN_LINK = '> Russian version: [docs/ru/{name}](ru/{name}).'
RU_LINK = '> English version: [docs/{name}](../{name}).'

# Проверять надо ЛЮБУЮ из уже стоящих меток, а не только ту, которую ставим:
# первую версию скрипта писали с меткой «Русская версия:» в английских файлах,
# потом её заменили на «Russian version:». Если проверять только новую метку,
# повторный запуск не найдёт старую форму и вставит вторую ссылку подряд.
EN_MARKERS = ('Russian version:', 'Русская версия:')
RU_MARKERS = ('English version:',)


def add_link(path: Path, markers: tuple[str, ...], link: str) -> bool:
    """Вставить ссылку после первого H1. Вернуть True, если файл изменён."""
    if not path.exists():
        print(f'  {path}: нет файла')
        return False

    text = path.read_text(encoding='utf-8')
    if any(m in text for m in markers):
        print(f'  {path}: ссылка уже есть')
        return False

    lines = text.split('\n')
    # Найти первый заголовок H1
    try:
        h1 = next(i for i, line in enumerate(lines) if line.startswith('# '))
    except StopIteration:
        print(f'  {path}: нет заголовка H1, пропуск')
        return False

    # Найти первую пустую строку после H1
    insert_at = h1 + 1
    while insert_at < len(lines) and lines[insert_at].strip() == '':
        insert_at += 1

    lines[insert_at:insert_at] = [link, '']
    path.write_text('\n'.join(lines), encoding='utf-8', newline='\n')
    print(f'  {path}: ссылка добавлена')
    return True


def main() -> int:
    print('английские файлы → ссылка на русскую версию:')
    changed = 0
    for name in FILES:
        if add_link(DOCS / name,
                    EN_MARKERS,
                    EN_LINK.format(name=name)):
            changed += 1

    print('\nрусские файлы → ссылка на английскую версию:')
    for name in FILES:
        if add_link(RU / name,
                    RU_MARKERS,
                    RU_LINK.format(name=name)):
            changed += 1

    print(f'\nизменено файлов: {changed}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
