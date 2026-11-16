"""Восстановить логотип в Topbar.jsx после отката к чистой версии.

Файл откачен к a4ff76da, потому что предыдущая правка через PowerShell
испортила кодировку. Теперь все изменения вносятся Python-скриптом с явным
UTF-8 — PowerShell для правки этого файла больше не используется.

Что делаем:
  1. импорт картинок из assets;
  2. замена заглушки .brand-mark на фирменный знак + надпись;
  3. Bell size 15 → 18;
  4. draggable=false на картинках (user-select в CSS на drag не влияет).
"""
from __future__ import annotations

from pathlib import Path

PATH = Path('frontend/src/pages/Topbar.jsx')
MARKERS = ('РЎ', 'Р¤', 'вЂ')


def guard(text: str, where: str) -> None:
    bad = [line for line in text.split('\n') if any(m in line for m in MARKERS)]
    if bad:
        raise SystemExit(f'{where}: обнаружена порча кодировки — прервано')


def main() -> int:
    src = PATH.read_text(encoding='utf-8')
    guard(src, 'исходный файл')

    # --- 1. импорты картинок ---
    anchor = "import TopNav from '../components/TopNav'"
    if 'cybra-mark.png' not in src:
        if anchor not in src:
            raise SystemExit('не найден якорь для импорта TopNav')
        src = src.replace(
            anchor,
            anchor
            + "\nimport markUrl from '../assets/cybra-mark.png'"
            + "\nimport wordmarkUrl from '../assets/cybra-wordmark.png'",
            1,
        )
        print('+ импорты картинок')

    # --- 2. логотип вместо заглушки ---
    # Точный блок берём по разметке, а не по комментарию: в коммите a4ff76da
    # комментарий к заглушке другой, и поиск по тексту не сработал.
    old_brand = """        <div className="brand-mark">CY</div>
        <div>
          <div className="brand-name">CYBRA</div>
          <div className="brand-sub">security console</div>
        </div>"""

    new_brand = """        {/* Фирменный знак и надпись — растровые ассеты из docs/brand,
            обрезанные по альфе и сохранённые в 3x (см. scripts/prep_brand_assets.py).
            Картинка, а не инлайн-SVG: логотип объёмный, с градиентами
            металла, — трассировка в SVG потеряла бы эти переходы и дала бы
            ступенчатые края. Знак и надпись лежат отдельными файлами, чтобы
            их можно было позиционировать независимо.

            draggable=false обязателен: user-select в CSS запрещает выделение
            текста, но не перетаскивание картинки — в Chrome это отдельный
            механизм, и без атрибута лого утаскивается курсором. */}
        <img
          className="brand-logo"
          src={markUrl}
          alt=""
          aria-hidden="true"
          draggable="false"
        />
        <div className="brand-text">
          <img
            className="brand-wordmark-img"
            src={wordmarkUrl}
            alt="CYBRA"
            draggable="false"
          />
          <div className="brand-sub">security console</div>
        </div>"""

    if old_brand in src:
        src = src.replace(old_brand, new_brand, 1)
        print('+ фирменный знак вместо заглушки')
    elif 'brand-logo' in src:
        print('= логотип уже на месте')
    else:
        raise SystemExit('не найден блок заглушки — проверь разметку вручную')

    # --- 3. размер колокольчика ---
    if '<Bell size={15} weight="bold" />' in src:
        src = src.replace(
            '<Bell size={15} weight="bold" />',
            '<Bell size={18} weight="bold" />',
            1,
        )
        print('+ колокольчик 15 → 18')

    guard(src, 'результат')

    # грубая проверка целостности JSX
    if src.count('{') != src.count('}'):
        raise SystemExit('расхождение {} — файл не записан')

    PATH.write_text(src, encoding='utf-8', newline='\n')
    print(f'\nзаписано: {len(src.splitlines())} строк, UTF-8 + LF')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
