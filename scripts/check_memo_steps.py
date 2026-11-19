"""Памятка должна остаться на шагах «Цель» и «Инструменты»."""
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

        print('шаг 1 (Цель)       : памятка =', page.locator('.memo-card').count())
        checkbox = page.locator('label.checkbox input[type=checkbox]').first
        if checkbox.count():
            checkbox.check(force=True)
        page.wait_for_timeout(200)
        page.locator('button.btn.primary', has_text='Далее').first.click()
        page.wait_for_timeout(500)
        print('шаг 2 (Инструменты): памятка =', page.locator('.memo-card').count())
        page.locator('button.btn.primary', has_text='Далее').first.click()
        page.wait_for_timeout(500)
        print('шаг 3 (Параметры)  : памятка =', page.locator('.memo-card').count())
        browser.close()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
