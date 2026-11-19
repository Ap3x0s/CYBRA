"""Замеры правой колонки после перестановки памятки и шкалы."""
from __future__ import annotations

import os

from playwright.sync_api import sync_playwright

BASE = os.environ.get('CYBRA_BASE', 'http://127.0.0.1:8000')

EMAIL = os.environ.get('CYBRA_EMAIL', 'admin@cybra.local')
PASSWORD = os.environ.get('CYBRA_PASSWORD', '')
if not PASSWORD:
    raise SystemExit(
        'Задайте пароль администратора: $env:CYBRA_PASSWORD = "..."')


def main() -> int:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel='chrome', headless=True)
        page = browser.new_context(viewport={'width': 1470, 'height': 1250}).new_page()
        page.goto(BASE + '/login', wait_until='networkidle')
        page.fill('input[type=email]', EMAIL)
        page.fill('input[type=password]', PASSWORD)
        page.click('button[type=submit]')
        page.wait_for_url(lambda url: '/login' not in url, timeout=20000)
        page.goto(BASE + '/runs/new', wait_until='networkidle')
        checkbox = page.locator('label.checkbox input[type=checkbox]').first
        if checkbox.count():
            checkbox.check(force=True)
        for _ in range(2):
            button = page.locator('button.btn.primary', has_text='Далее')
            if button.count() and button.first.is_enabled():
                button.first.click()
                page.wait_for_timeout(500)
        page.wait_for_timeout(900)

        grid = page.locator('.grid').first.bounding_box()
        left = page.locator('.grid > .card').first.bounding_box()
        print(f'{"grid":26} y={grid["y"]:6.0f} h={grid["height"]:6.0f}')
        print(f'{"левая форма":26} y={left["y"]:6.0f} h={left["height"]:6.0f}')

        right = page.locator('.grid > div').nth(1)
        kids = right.evaluate(
            'el => [...el.children].map(k => ({cls: k.className, '
            'h: Math.round(k.getBoundingClientRect().height)}))')
        for kid in kids:
            print(f'  правая: {kid["cls"][:30]:32} h={kid["h"]}')

        area = page.locator('textarea.judge-prompt').first
        print('поле критерия: scrollHeight=', area.evaluate('e => e.scrollHeight'),
              'clientHeight=', area.evaluate('e => e.clientHeight'))

        scale = page.locator('.scale-card').first.bounding_box()
        print(f'{"шкала":26} y={scale["y"]:6.0f} h={scale["height"]:6.0f}')

        items = page.locator('.scale-item')
        ys = [items.nth(i).bounding_box()['y'] for i in range(items.count())]
        print('строки шкалы (y):', [round(v) for v in ys],
              '-> в 2 столбца:', len(set(round(v) for v in ys)) == 2)
        browser.close()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
