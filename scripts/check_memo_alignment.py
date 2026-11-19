"""Проверить, что панели справки выровнены и текст не рвётся."""
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

        panels = page.locator('.memo-row > .card')
        heights = [panels.nth(i).bounding_box()['height'] for i in range(panels.count())]
        widths = [panels.nth(i).bounding_box()['width'] for i in range(panels.count())]
        print('высота панелей :', [round(v) for v in heights],
              'выровнены:', abs(heights[0] - heights[1]) < 2)
        print('ширина панелей :', [round(v) for v in widths])

        # Текст не должен быть обрезан по горизонтали.
        overflow = page.locator('.memoTip').first.evaluate(
            'e => e.scrollWidth > e.clientWidth + 1')
        print('текст обрезан  :', overflow)

        # Правый бокс и форма: один верх, один низ.
        form = page.locator('.grid > .card').first.bounding_box()
        judge = page.locator('.judge-card').first.bounding_box()
        print(f'верх: форма={form["y"]:.0f} бокс={judge["y"]:.0f}')
        print(f'низ : форма={form["y"] + form["height"]:.0f} '
              f'бокс={judge["y"] + judge["height"]:.0f}')
        browser.close()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
