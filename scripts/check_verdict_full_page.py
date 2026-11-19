"""Полный скриншот правой колонки шага «Параметры» (включая справку внизу)."""
from __future__ import annotations

import os

import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = os.environ.get('CYBRA_BASE', 'http://127.0.0.1:8000')

EMAIL = os.environ.get('CYBRA_EMAIL', 'admin@cybra.local')
PASSWORD = os.environ.get('CYBRA_PASSWORD', '')
if not PASSWORD:
    raise SystemExit(
        'Задайте пароль администратора: $env:CYBRA_PASSWORD = "..."')
OUT = Path(__file__).resolve().parents[1] / 'var'


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
        page.wait_for_timeout(1000)
        page.screenshot(path=str(OUT / 'layout-full.png'), full_page=True)
        print('снято:', OUT / 'layout-full.png')
        browser.close()
    return 0


if __name__ == '__main__':
    sys.exit(main())
