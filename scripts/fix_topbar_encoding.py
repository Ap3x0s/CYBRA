"""Починить Topbar.jsx после двойного перекодирования.

Причина: предыдущая правка шла через PowerShell
    (Get-Content -Raw) -replace ... | Set-Content -Encoding UTF8
PowerShell прочитал UTF-8 файл как cp1251 (системная ANSI-кодировка) и
записал результат обратно в UTF-8. Русские комментарии превратились в
«мохнатый» текст: каждый исходный UTF-8 байт стал отдельным символом
cp1251.

Обратное преобразование: взять символы, закодировать в cp1251 (получим
исходные UTF-8 байты) и раскодировать как UTF-8.

Проверка до записи: результат обязан содержать осмысленный русский текст
и не содержать маркеров порчи. Скрипт отказывается писать, если проверка
не прошла, — иначе легко получить ещё худший файл.
"""
from __future__ import annotations

from pathlib import Path

PATH = Path('frontend/src/pages/Topbar.jsx')
MARKERS = ('РЎ', 'Р¤', 'вЂ', 'РЎС', 'РёС')


def is_corrupt(text: str) -> bool:
    return any(m in text for m in MARKERS)


def repair(text: str) -> str:
    """cp1251-байты обратно в UTF-8.

    BOM (\\ufeff) в cp1251 не кодируется, поэтому его снимаем отдельно:
    он появился из-за Set-Content -Encoding UTF8 в Windows PowerShell 5.1,
    который пишет BOM всегда. Возвращаем файл без BOM — исходный Vite-проект
    его не содержит.
    """
    text = text.lstrip('\ufeff')
    raw = text.encode('cp1251', errors='strict')
    return raw.decode('utf-8', errors='strict')


def main() -> int:
    original = PATH.read_text(encoding='utf-8')
    before = sum(1 for line in original.split('\n') if is_corrupt(line))
    print(f'строк с порчей до: {before}')

    if before == 0:
        print('файл чист, править нечего')
        return 0

    try:
        fixed = repair(original)
    except UnicodeError as exc:
        print(f'НЕ УДАЛОСЬ восстановить: {exc}')
        print('файл НЕ изменён — нужен ручной разбор')
        return 1

    after = sum(1 for line in fixed.split('\n') if is_corrupt(line))
    print(f'строк с порчей после: {after}')

    # Контрольные слова, которые обязаны появиться в осмысленном виде
    checks = ['Фирменный', 'заглушка', 'уведомлений', 'Единственная']
    found = [w for w in checks if w in fixed]
    print(f'контрольные слова найдены: {found}')

    # Баланс JSX-тегов и скобок как грубая проверка целостности
    ok_braces = fixed.count('{') == fixed.count('}')
    ok_parens = fixed.count('(') == fixed.count(')')
    print(f'скобки {{}}: {fixed.count("{")}/{fixed.count("}")} '
          f'{"OK" if ok_braces else "РАСХОЖДЕНИЕ"}')
    print(f'скобки (): {fixed.count("(")}/{fixed.count(")")} '
          f'{"OK" if ok_parens else "РАСХОЖДЕНИЕ"}')

    if after > 0 or not ok_braces or not ok_parens or len(found) < 3:
        print('\nПРОВЕРКА НЕ ПРОЙДЕНА — файл не записан')
        return 1

    PATH.write_text(fixed, encoding='utf-8', newline='\n')
    print('\nзаписано, LF сохранены')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
