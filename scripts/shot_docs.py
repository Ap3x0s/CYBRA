"""Снять экран входа в чистой сессии и свежую главную.

Проблема в screenshots.py: он сначала логинится, а только потом обходит
список страниц. Из-за этого '/login' уже переадресуется на '/' — на
скриншоте оказывается дашборд, а не форма входа.

Здесь вход снимается ДО аутентификации, в отдельном контексте без cookie.
Остальные экраны — после логина, как обычно.
"""
from __future__ import annotations

import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = 'http://127.0.0.1:8000'
OUT = Path(__file__).resolve().parents[1] / 'docs' / 'media'


def main() -> int:
    email = sys.argv[1]
    password = sys.argv[2]
    OUT.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(channel='chrome', headless=True)

        # --- 1. Экран входа: чистый контекст, без cookie ---
        ctx = browser.new_context(viewport={'width': 1440, 'height': 900},
                                  device_scale_factor=2)
        page = ctx.new_page()
        page.goto(BASE + '/login', wait_until='networkidle')
        page.wait_for_timeout(900)
        url = page.url
        page.screenshot(path=str(OUT / 'login.png'), full_page=True)
        print(f'login: {url}')
        if '/login' not in url:
            print('  ВНИМАНИЕ: переадресовало, снимок неверный')
        ctx.close()

        # --- 2. Остальное: с сессией ---
        ctx = browser.new_context(viewport={'width': 1440, 'height': 900},
                                  device_scale_factor=2)
        page = ctx.new_page()
        errors = []
        page.on('console', lambda m: errors.append(m.text)
                if m.type == 'error' else None)

        page.goto(BASE + '/login', wait_until='networkidle')
        page.fill('input[type=email]', email)
        page.fill('input[type=password]', password)
        page.click('button[type=submit]')
        page.wait_for_url(BASE + '/', timeout=15000)
        page.wait_for_load_state('networkidle')
        page.wait_for_timeout(1200)

        # Главная — с реальными данными, курсор убран, чтобы не было hover
        page.mouse.move(5, 800)
        page.wait_for_timeout(400)
        page.screenshot(path=str(OUT / 'console.png'), full_page=True)
        print(f'console: {page.url}')

        for route, name in (('/runs', 'runs'),
                            ('/runs/17', 'run-detail'),
                            ('/runs/17/report', 'report'),
                            ('/datasets', 'datasets'),
                            ('/metrics', 'metrics'),
                            ('/models', 'models'),
                            ('/runs/new', 'new-run')):
            page.goto(BASE + route, wait_until='networkidle')
            page.wait_for_timeout(800)
            page.mouse.move(5, 800)
            page.wait_for_timeout(200)
            page.screenshot(path=str(OUT / f'{name}.png'), full_page=True)
            print(f'{name}: {page.url}')

        real_errors = [e for e in errors if '401' not in e]
        if real_errors:
            print('ОШИБКИ КОНСОЛИ:')
            for e in real_errors[:5]:
                print('  ', e)

        ctx.close()
        browser.close()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
