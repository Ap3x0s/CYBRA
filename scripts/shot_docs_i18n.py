"""Снять скриншоты UI в двух языках: EN для docs/media, RU для docs/ru/media.

Язык хранится в localStorage под ключом 'cybra:lang'. Чтобы интерфейс
отрисовался на нужном языке с ПЕРВОГО кадра (без мигания русского), язык
выставляется через add_init_script до загрузки страницы.

Имена файлов одинаковые в обоих каталогах — ссылки в README и README.ru
отличаются только префиксом каталога.
"""
from __future__ import annotations

import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = 'http://127.0.0.1:8000'
ROOT = Path(__file__).resolve().parents[1]

PAGES = [
    ('/', 'console'),
    ('/runs', 'runs'),
    ('/runs/17', 'run-detail'),
    ('/runs/17/report', 'report'),
    ('/datasets', 'datasets'),
    ('/metrics', 'metrics'),
    ('/models', 'models'),
    ('/runs/new', 'new-run'),
]


def capture(browser, lang: str, out_dir: Path, email: str, password: str) -> int:
    out_dir.mkdir(parents=True, exist_ok=True)

    # --- Экран входа: отдельный контекст без cookie ---
    ctx = browser.new_context(viewport={'width': 1440, 'height': 900},
                              device_scale_factor=2)
    ctx.add_init_script(
        f"window.localStorage.setItem('cybra:lang', '{lang}')")
    page = ctx.new_page()
    page.goto(BASE + '/login', wait_until='networkidle')
    page.wait_for_timeout(900)
    page.screenshot(path=str(out_dir / 'login.png'), full_page=True)
    print(f'  [{lang}] login: {page.url}')
    ctx.close()

    # --- Остальные экраны: с сессией ---
    ctx = browser.new_context(viewport={'width': 1440, 'height': 900},
                              device_scale_factor=2)
    ctx.add_init_script(
        f"window.localStorage.setItem('cybra:lang', '{lang}')")
    page = ctx.new_page()
    errors: list[str] = []
    page.on('console', lambda m: errors.append(m.text)
            if m.type == 'error' and '401' not in m.text else None)

    page.goto(BASE + '/login', wait_until='networkidle')
    page.fill('input[type=email]', email)
    page.fill('input[type=password]', password)
    page.click('button[type=submit]')
    page.wait_for_url(BASE + '/', timeout=15000)
    page.wait_for_load_state('networkidle')

    for route, name in PAGES:
        page.goto(BASE + route, wait_until='networkidle')
        page.wait_for_timeout(900)
        page.mouse.move(5, 800)
        page.wait_for_timeout(250)
        page.screenshot(path=str(out_dir / f'{name}.png'), full_page=True)
        print(f'  [{lang}] {name}')

    if errors:
        print(f'  ОШИБКИ [{lang}]:', errors[:3])
    ctx.close()
    return 0


def main() -> int:
    email = sys.argv[1]
    password = sys.argv[2]

    with sync_playwright() as p:
        browser = p.chromium.launch(channel='chrome', headless=True)
        print('EN → docs/media')
        capture(browser, 'en', ROOT / 'docs' / 'media', email, password)
        print('RU → docs/ru/media')
        capture(browser, 'ru', ROOT / 'docs' / 'ru' / 'media', email, password)
        browser.close()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
