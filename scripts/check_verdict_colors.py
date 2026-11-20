"""Снять скриншоты всех четырёх уровней вердикта в цвете.

Нужно убедиться, что цвета действительно применяются и что красный читается
как красный, а не как серая пометка. Показываем две страницы: детали прогона
и печатный отчёт.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = os.environ.get('CYBRA_BASE', 'http://127.0.0.1:8000')
EMAIL = os.environ.get('CYBRA_EMAIL', 'admin@cybra.local')
PASSWORD = os.environ.get('CYBRA_PASSWORD', '')
if not PASSWORD:
    raise SystemExit('Задайте пароль: $env:CYBRA_PASSWORD = "..."')

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'var'


def run_with_verdict() -> int | None:
    """Прогон, у которого вердикт NOT_ACCEPTABLE: он и нужен для проверки."""
    sys.path.insert(0, str(ROOT / 'backend'))
    from cybra.db import DATABASE_URL
    from cybra.models import Run
    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import Session

    engine = create_engine(DATABASE_URL, future=True)
    with Session(engine) as session:
        runs = session.scalars(
            select(Run).where(Run.verdicts.is_not(None))
            .order_by(Run.id.desc())).all()
        for run in runs:
            for entry in (run.verdicts or {}).values():
                if entry.get('verdict') == 'NOT_ACCEPTABLE':
                    return run.id
        return runs[0].id if runs else None


def main() -> int:
    run_pk = run_with_verdict()
    if run_pk is None:
        print('нет прогонов с вердиктом')
        return 1
    print('прогон:', run_pk)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel='chrome', headless=True)
        page = browser.new_context(viewport={'width': 1470, 'height': 900}).new_page()
        page.goto(BASE + '/login', wait_until='networkidle')
        page.fill('input[type=email]', EMAIL)
        page.fill('input[type=password]', PASSWORD)
        page.click('button[type=submit]')
        page.wait_for_url(lambda url: '/login' not in url, timeout=20000)

        # Детали прогона.
        page.goto(BASE + f'/runs/{run_pk}', wait_until='networkidle')
        page.wait_for_timeout(1200)
        page.screenshot(path=str(OUT / 'verdict-color-detail.png'),
                        full_page=False)

        chip = page.locator('.verdict-code').first
        if chip.count():
            color = chip.evaluate('el => getComputedStyle(el).color')
            text = chip.inner_text()
            print(f'код вердикта: {text} | цвет: {color}')
        pill = page.locator('.pill.bad, .pill.ok, .pill.warn, .pill.idle').first
        if pill.count():
            print('плашка:', pill.evaluate('el => getComputedStyle(el).color'),
                  '|', pill.inner_text().strip()[:40])

        # Печатный отчёт.
        page.goto(BASE + f'/runs/{run_pk}/report', wait_until='networkidle')
        page.wait_for_timeout(1200)
        page.screenshot(path=str(OUT / 'verdict-color-report.png'),
                        full_page=False)

        browser.close()
    return 0


if __name__ == '__main__':
    sys.exit(main())
