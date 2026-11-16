"""Перестроить шапку обоих README: название по центру, переключатель под ним.

Требование: «CYBRA» по центру сверху, а переключатель языка — сразу под
названием, в самом начале файла, а не «чуть позже» в виде примечания
«also available in…» после вводных абзацев.

В Markdown нет выравнивания заголовков, поэтому центрирование делается
HTML-блоком <div align="center">. Внутри — заголовок H1, дескрипшн и
строка-переключатель. GitHub и большинство рендереров поддерживают
атрибут align.

Скрипт идемпотентен: если шапка уже в новом формате, второй раз не
трогает.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Метка, по которой узнаём, что шапка уже переделана
MARKER = '<div align="center">'

EN_HEAD = """<div align="center">

# CYBRA

**Cybersecurity benchmarks for testing the security of your LLM/AI models.**

[English](README.md) · [Русский](README.ru.md)

</div>
"""

RU_HEAD = """<div align="center">

# CYBRA

**Кибербезопасность: бенчмарки для проверки безопасности ваших LLM/AI-моделей.**

[English](README.md) · [Русский](README.ru.md)

</div>
"""


def rebuild(path: Path, head: str, drop_line_prefix: str) -> bool:
    text = path.read_text(encoding='utf-8')
    if MARKER in text:
        print(f'  {path.name}: шапка уже переделана')
        return False

    lines = text.split('\n')

    # Найти границы старой шапки: от H1 до первого раздела '## '.
    # Всё, что было до первого '## ', — это вводная часть (дескрипшн,
    # абзацы о проекте, примечание о языке). Вводные абзацы сохраняем,
    # выкидываем только строку «also available in …».
    try:
        h1 = next(i for i, l in enumerate(lines) if l.startswith('# '))
        first_h2 = next(i for i, l in enumerate(lines) if l.startswith('## '))
    except StopIteration:
        print(f'  {path.name}: не найдены заголовки, пропуск')
        return False

    body_intro = [
        l for l in lines[h1 + 1:first_h2]
        if not l.startswith(drop_line_prefix)
    ]
    # Убрать ведущие и хвостовые пустые строки вводной части
    while body_intro and body_intro[0].strip() == '':
        body_intro.pop(0)
    while body_intro and body_intro[-1].strip() == '':
        body_intro.pop()

    new_lines = (
        head.split('\n')
        + body_intro
        + ['']
        + lines[first_h2:]
    )
    path.write_text('\n'.join(new_lines), encoding='utf-8', newline='\n')
    print(f'  {path.name}: шапка перестроена')
    return True


def main() -> int:
    print('перестройка шапок README:')
    changed = 0
    if rebuild(ROOT / 'README.md', EN_HEAD, '> Also available in'):
        changed += 1
    if rebuild(ROOT / 'README.ru.md', RU_HEAD, '> English version'):
        changed += 1
    print(f'\nизменено файлов: {changed}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
