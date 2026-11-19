"""Скриншоты печатной страницы и детали прогона для уже готового прогона."""
from __future__ import annotations

import os

import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = 'http://127.0.0.1:8000'
EMAIL = os.environ.get('CYBRA_EMAIL', 'admin@cybra.local')
PASSWORD = os.environ.get('CYBRA_PASSWORD', '')
if not PASSWORD:
    raise SystemExit(
        'Задайте пароль администратора: $env:CYBRA_PASSWORD = "..."')
OUT = Path(__file__).resolve().parents[1] / 'var'
RUN_ID = sys.argv[1] if len(sys.argv) > 1 else '22'


def main() -> int:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel='chrome', headless=True)
        page = browser.new_context(viewport={'width': 1470, 'height': 1100}).new_page()
        errors: list[str] = []
        page.on('pageerror', lambda e: errors.append(str(e)))

        page.goto(BASE + '/login', wait_until='networkidle')
        page.fill('input[type=email]', EMAIL)
        page.fill('input[type=password]', PASSWORD)
        page.click('button[type=submit]')
        page.wait_for_url(lambda url: '/login' not in url, timeout=20000)

        page.goto(BASE + f'/runs/{RUN_ID}/report', wait_until='networkidle')
        page.wait_for_timeout(1500)
        page.screenshot(path=str(OUT / 'report-final.png'), full_page=False)

        print('вердикт в отчёте :', page.locator('text=Вердикт судьи').count())
        print('моделей на стр.  :', page.locator('text=МОДЕЛЕЙ').count())
        kpi = page.locator('.rep-kpis').first.inner_text() if page.locator('.rep-kpis').count() else ''
        print('KPI              :', ' '.join(kpi.split())[:120])

        page.goto(BASE + f'/runs/{RUN_ID}', wait_until='networkidle')
        page.wait_for_timeout(1000)
        page.screenshot(path=str(OUT / 'detail-final.png'), full_page=False)
        print('вердикт в детали :', page.locator('text=Вердикт судьи').count())

        browser.close()
        if errors:
            print('ошибки:', *errors[:3], sep='\n  ')
        return 0


if __name__ == '__main__':
    sys.exit(main())
