"""Скриншоты README: шаг «Параметры» с боксом вердикта и отчёт с вердиктом.

Скрипт scripts/screenshots.py снимает /runs/new на первом шаге, где бокса
вердикта нет вовсе — новая функция в README не была видна. Здесь снимаем
именно шаг «Параметры» и печатный отчёт прогона, в котором вердикт есть.
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
OUT_EN = ROOT / 'docs' / 'media'
OUT_RU = ROOT / 'docs' / 'ru' / 'media'
for folder in (OUT_EN, OUT_RU):
    folder.mkdir(parents=True, exist_ok=True)


def find_run_with_verdict() -> int | None:
    """Прогон, у которого в БД есть вердикт: иначе блок в отчёте не покажется."""
    import sqlite3

    database = ROOT / 'var' / 'cybra.sqlite3'
    if not database.exists():
        return None
    connection = sqlite3.connect(database)
    try:
        row = connection.execute(
            'SELECT id FROM runs WHERE verdicts IS NOT NULL '
            'AND status = "COMPLETE" ORDER BY id DESC LIMIT 1').fetchone()
        return row[0] if row else None
    finally:
        connection.close()


def main() -> int:
    run_pk = find_run_with_verdict()
    if run_pk is None:
        print('нет прогона с вердиктом — сначала выполните прогон с включённой функцией')
        return 1
    print('прогон с вердиктом:', run_pk)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel='chrome', headless=True)
        for lang, folder in (('ru', OUT_RU), ('en', OUT_EN)):
            context = browser.new_context(
                viewport={'width': 1440, 'height': 900}, device_scale_factor=2)
            # Язык задаём до первой навигации: иначе страница отрисуется на
            # языке по умолчанию и скрин придётся снимать заново.
            context.add_init_script(
                f"window.localStorage.setItem('cybra:lang', '{lang}')")
            page = context.new_page()

            page.goto(BASE + '/login', wait_until='networkidle')
            page.fill('input[type=email]', EMAIL)
            page.fill('input[type=password]', PASSWORD)
            page.click('button[type=submit]')
            page.wait_for_url(lambda url: '/login' not in url, timeout=20000)

            # 1. Шаг «Параметры» с боксом вердикта.
            page.goto(BASE + '/runs/new', wait_until='networkidle')
            checkbox = page.locator('label.checkbox input[type=checkbox]').first
            if checkbox.count():
                checkbox.check(force=True)
            # Ищем кнопку «Далее» по тексту: .nth(1) попадал не туда и
            # скриншот снимался на первом шаге, где бокса вердикта нет.
            for _ in range(2):
                button = page.locator('button.btn.primary', has_text='Далее')
                if not button.count():
                    button = page.locator('button.btn.primary', has_text='Next')
                if button.count() and button.first.is_enabled():
                    button.first.click()
                    page.wait_for_timeout(700)
            page.wait_for_timeout(900)
            # Убеждаемся, что попали на шаг 3, иначе скрин бесполезен.
            assert page.locator('.judge-card').count(), 'не дошли до шага «Параметры»'
            page.screenshot(path=str(folder / 'new-run-verdict.png'), full_page=True)
            print(f'shot {lang}/new-run-verdict')

            # 2. Печатный отчёт прогона с вердиктом.
            page.goto(BASE + f'/runs/{run_pk}/report', wait_until='networkidle')
            page.wait_for_timeout(1200)
            page.screenshot(path=str(folder / 'report-verdict.png'), full_page=True)
            print(f'shot {lang}/report-verdict')
            context.close()

        browser.close()
    return 0


if __name__ == '__main__':
    sys.exit(main())
