"""Шаг «Параметры»: только бокс вердикта, без памятки и шкалы.

Проверяем то, о чём просил заказчик: страница не прокручивается, бокс
занимает всю правую колонку, поле критерия стало крупнее.
"""
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
        page = browser.new_context(viewport={'width': 1470, 'height': 900}).new_page()
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

        # 1. Памятки и шкалы на этом шаге нет.
        print('памятка на шаге   :', page.locator('.memo-card').count())
        print('шкала на шаге     :', page.locator('.scale-card').count())

        # 2. Колонки и поле.
        form = page.locator('.grid > .card').first.bounding_box()
        judge = page.locator('.judge-card').first.bounding_box()
        area = page.locator('textarea.judge-prompt').first.bounding_box()
        print(f'форма: y={form["y"]:.0f} h={form["height"]:.0f}')
        print(f'бокс : y={judge["y"]:.0f} h={judge["height"]:.0f} '
              f'(совпадает: {abs(form["height"] - judge["height"]) < 2})')
        print(f'поле критерия: h={area["height"]:.0f}px')

        # 3. Страница не должна прокручиваться: заказчик просил убрать
        #    полосу прокрутки именно у страницы параметров.
        heights = page.evaluate(
            '() => ({doc: document.documentElement.scrollHeight, '
            'win: window.innerHeight})')
        print(f'высота документа  : {heights["doc"]}, окна: {heights["win"]}')
        print('прокрутка страницы:', heights['doc'] > heights['win'] + 2)

        # 4. Правый бокс растянут на всю колонку.
        right = page.locator('.grid > div').nth(1).bounding_box()
        print(f'правая колонка: y={right["y"]:.0f} h={right["height"]:.0f}, '
              f'заполнена: {abs(right["height"] - judge["height"]) < 2}')
        browser.close()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
