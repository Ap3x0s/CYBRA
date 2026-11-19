"""Посмотреть бокс вердикта вживую: логин, шаг «Параметры», скриншоты.

Проверяем то, что не видно в тестах: бокс стоит ВЫШЕ памятки, переключатель
включает поле, а промт приезжает с сервера, а не из JS.
"""
from __future__ import annotations

import os

import json
import sys
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = 'http://127.0.0.1:8000'
EMAIL = os.environ.get('CYBRA_EMAIL', 'admin@cybra.local')
PASSWORD = os.environ.get('CYBRA_PASSWORD', '')
if not PASSWORD:
    raise SystemExit(
        'Задайте пароль администратора: $env:CYBRA_PASSWORD = "..."')
OUT = Path(__file__).resolve().parents[1] / 'var'


def api_post(path: str, payload: dict) -> dict:
    request = urllib.request.Request(
        BASE + path, data=json.dumps(payload).encode(),
        headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def main() -> int:
    # Критерий обязан приходить с сервера — иначе UI показывает пустое поле.
    try:
        api_post('/api/v1/auth/login', {'email': EMAIL, 'password': PASSWORD})
    except Exception as error:  # noqa: BLE001
        print('логин через API не удался:', error)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel='chrome', headless=True)
        page = browser.new_page(viewport={'width': 1470, 'height': 900})
        errors: list[str] = []
        page.on('console', lambda m: errors.append(m.text) if m.type == 'error' else None)
        page.on('pageerror', lambda e: errors.append(str(e)))

        page.goto(BASE + '/login', wait_until='networkidle')
        page.fill('input[type=email]', EMAIL)
        page.fill('input[type=password]', PASSWORD)
        page.click('button[type=submit]')
        page.wait_for_url(lambda url: '/login' not in url, timeout=20000)

        page.goto(BASE + '/runs/new', wait_until='networkidle')
        # Шаг 0 требует выбрать хотя бы одну модель: без этого «Далее»
        # заблокирована, и до шага «Параметры» не добраться.
        first_model = page.locator('label.checkbox input[type=checkbox]').first
        if first_model.count():
            first_model.check(force=True)
            page.wait_for_timeout(200)
        for _ in range(2):
            button = page.locator('button.btn.primary', has_text='Далее')
            if button.count() and button.first.is_enabled():
                button.first.click()
                page.wait_for_timeout(500)

        page.wait_for_timeout(600)
        page.screenshot(path=str(OUT / 'judge-step.png'), full_page=False)

        # Поле критерия обязано быть непустым: текст приходит с сервера.
        area = page.locator('textarea.judge-prompt')
        visible = area.count() > 0
        text = area.first.input_value() if visible else ''
        print('поле критерия найдено:', visible)
        print('длина критерия      :', len(text))
        print('начало              :', text[:60].replace('\n', ' '))

        # Переключатель включает поле.
        toggle = page.locator('input[type=checkbox]').last
        disabled_before = area.first.is_disabled() if visible else None
        toggle.check(force=True)
        page.wait_for_timeout(300)
        disabled_after = area.first.is_disabled() if visible else None
        print('поле выключено до   :', disabled_before)
        print('поле выключено после:', disabled_after)
        page.screenshot(path=str(OUT / 'judge-on.png'), full_page=False)

        # Памятка должна остаться НИЖЕ бокса вердикта.
        y_judge = page.locator('textarea.judge-prompt').first.bounding_box()['y']
        y_memo = page.locator('h3', has_text='Памятка').first.bounding_box()['y']
        print('памятка ниже бокса  :', y_memo > y_judge, f'({y_memo:.0f} > {y_judge:.0f})')

        browser.close()
        if errors:
            print('ошибки консоли:', *errors[:5], sep='\n  ')
        return 0


if __name__ == '__main__':
    sys.exit(main())
