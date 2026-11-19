"""Замеры страницы «Параметры»: где именно образуется переполнение."""
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

        doc = page.evaluate('() => document.documentElement.scrollHeight')
        win = page.evaluate('() => window.innerHeight')
        print(f'документ={doc} окно={win} переполнение={doc - win:+d}')

        for name, selector in (
            ('форма', '.grid > .card'),
            ('бокс вердикта', '.judge-card'),
            ('поле', 'textarea.judge-prompt'),
            ('шкала', '.judge-scale'),
            ('список датасетов', '.dataset-list'),
            ('шаги', '.page-head'),
        ):
            locator = page.locator(selector)
            if not locator.count():
                continue
            box = locator.first.bounding_box()
            print(f'{name:18} y={box["y"]:6.0f} h={box["height"]:6.0f} '
                  f'низ={box["y"] + box["height"]:.0f}')

        # Есть ли прокрутка внутри списка датасетов.
        inner = page.locator('.dataset-list').first.evaluate(
            'e => ({scroll: e.scrollHeight, client: e.clientHeight, '
            'overflow: getComputedStyle(e).overflowY})')
        print('прокрутка в списке датасетов:', inner)
        browser.close()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
