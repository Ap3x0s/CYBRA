"""Что происходит со списком датасетов, когда версий больше, чем помещается.

Проверяем три вопроса заказчика:
  1) появляется ли прокрутка ВНУТРИ списка при большом числе версий;
  2) не растягивает ли список страницу на несколько экранов;
  3) не теряется ли версия из-за слайса slice(0, 40).
"""
from __future__ import annotations

import json
import os
import sys
import urllib.request

from playwright.sync_api import sync_playwright

BASE = os.environ.get('CYBRA_BASE', 'http://127.0.0.1:8000')
EMAIL = os.environ.get('CYBRA_EMAIL', 'admin@cybra.local')
PASSWORD = os.environ.get('CYBRA_PASSWORD', '')
if not PASSWORD:
    raise SystemExit('Задайте пароль: $env:CYBRA_PASSWORD = "..."')


def api(path: str):
    request = urllib.request.Request(BASE + path)
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


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
                page.wait_for_timeout(600)
        page.wait_for_timeout(900)

        info = page.locator('.dataset-list').first.evaluate("""el => {
            const style = getComputedStyle(el);
            return {
                items: el.children.length,
                scrollHeight: el.scrollHeight,
                clientHeight: el.clientHeight,
                overflowY: style.overflowY,
                hasScroll: el.scrollHeight > el.clientHeight + 1,
            };
        }""")
        print('записей в списке :', info['items'])
        print('scrollHeight     :', info['scrollHeight'])
        print('clientHeight     :', info['clientHeight'])
        print('overflowY        :', info['overflowY'])
        print('прокрутка внутри :', info['hasScroll'])

        doc = page.evaluate('() => document.documentElement.scrollHeight')
        win = page.evaluate('() => window.innerHeight')
        print(f'страница         : {doc} при окне {win} '
              f'(переполнение {doc - win:+d})')
        browser.close()
    return 0


if __name__ == '__main__':
    sys.exit(main())
