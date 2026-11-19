"""Проверить бокс вердикта: раскладку и смену языка промта.

Три вещи, которые видно только в браузере:
  1) форма и бокс начинаются на одном уровне;
  2) промт меняется вместе с языком интерфейса;
  3) памятка стоит ПОД обоими боксами, в ряд.
"""
from __future__ import annotations

import os

import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = 'http://127.0.0.1:8000'
EMAIL = os.environ.get('CYBRA_EMAIL', 'admin@cybra.local')
PASSWORD = os.environ.get('CYBRA_PASSWORD', '')
if not PASSWORD:
    raise SystemExit(
        'Задайте пароль администратора: $env:CYBRA_PASSWORD = "..."')
OUT = Path(__file__).resolve().parents[1] / 'var'


def main() -> int:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel='chrome', headless=True)
        page = browser.new_context(viewport={'width': 1470, 'height': 900}).new_page()
        errors: list[str] = []
        page.on('pageerror', lambda e: errors.append(str(e)))

        page.goto(BASE + '/login', wait_until='networkidle')
        page.fill('input[type=email]', EMAIL)
        page.fill('input[type=password]', PASSWORD)
        page.click('button[type=submit]')
        page.wait_for_url(lambda url: '/login' not in url, timeout=20000)

        page.goto(BASE + '/runs/new', wait_until='networkidle')
        first_model = page.locator('label.checkbox input[type=checkbox]').first
        if first_model.count():
            first_model.check(force=True)
        for _ in range(2):
            button = page.locator('button.btn.primary', has_text='Далее')
            if button.count() and button.first.is_enabled():
                button.first.click()
                page.wait_for_timeout(500)
        page.wait_for_timeout(900)

        # 1. Верх и низ колонок.
        form = page.locator('.grid > .card').first.bounding_box()
        judge = page.locator('.judge-card').first.bounding_box()
        print(f'верх формы  : {form["y"]:.0f}')
        print(f'верх бокса  : {judge["y"]:.0f}  (совпадает: {abs(form["y"] - judge["y"]) < 2})')
        print(f'низ формы   : {form["y"] + form["height"]:.0f}')
        print(f'низ бокса   : {judge["y"] + judge["height"]:.0f}')

        # 2. Памятка под обоими боксами: две вертикальные панели рядом.
        # Памятка вернулась в правую колонку ПОД бокс вердикта (заказчик:
        # три короткие мысли там помещаются, а шкала рвалась). Шкала — внизу
        # отдельным боксом в два столбца.
        memo = page.locator('.memo-card').first.bounding_box()
        right = page.locator('.grid > div').nth(1).bounding_box()
        print(f'памятка в правой колонке: '
              f'{right["x"] <= memo["x"] <= right["x"] + right["width"]}')
        print(f'памятка под боксом      : {memo["y"] > judge["y"] + judge["height"] - 2}')

        scale = page.locator('.scale-card').first.bounding_box()
        print(f'шкала ниже колонок      : {scale["y"] >= form["y"] + form["height"] - 2}')
        scale_width = scale['width']
        items = page.locator('.scale-item')
        tops = [items.nth(i).bounding_box()['y'] for i in range(items.count())]
        print(f'уровней в шкале         : {items.count()}, '
              f'строк (y): {sorted({round(v) for v in tops})}')
        print(f'столбцов в шкале        : '
              f'{items.nth(0).bounding_box()["x"] != items.nth(1).bounding_box()["x"]}')
        print(f'шкала на всю ширину     : {scale_width > form["width"]}')

        # Поле критерия не должно сжаться до нечитаемого: памятка отнимает
        # у него высоту, поэтому за этим следим отдельно.
        area_first = page.locator('textarea.judge-prompt').first
        print(f'высота поля критерия    : {area_first.bounding_box()["height"]:.0f}px')

        # 3. Промт следует языку.
        area = page.locator('textarea.judge-prompt')
        ru_text = area.first.input_value()
        page.screenshot(path=str(OUT / 'judge-ru.png'), full_page=False)

        page.click('button.lang-btn')
        page.wait_for_timeout(300)
        page.locator('.popover-lang .popover-item', has_text='English').first.click()
        page.wait_for_timeout(1800)
        en_text = area.first.input_value()
        page.screenshot(path=str(OUT / 'judge-en.png'), full_page=False)

        print(f'промт RU началось : {ru_text[:55]!r}')
        print(f'промт EN началось : {en_text[:55]!r}')
        print(f'язык переключился : {ru_text != en_text}')
        print(f'RU по-русски      : {any("а" <= c.lower() <= "я" for c in ru_text[:80])}')
        print(f'EN по-английски   : {not any("а" <= c.lower() <= "я" for c in en_text[:80])}')

        browser.close()
        if errors:
            print('ошибки:', *errors[:3], sep='\n  ')
        return 0


if __name__ == '__main__':
    sys.exit(main())
