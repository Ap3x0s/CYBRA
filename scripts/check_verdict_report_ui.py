"""Прогон с включённым вердиктом и проверка печатной страницы.

Модель-судья здесь недоступна (endpoint фиктивный), поэтому ожидаемый
результат — INSUFFICIENT_EVIDENCE с причиной. Это тоже штатное состояние:
отчёт обязан показать честное «данных недостаточно», а не пустоту и не
выдуманный вердикт.
"""
from __future__ import annotations

import os

import json
import sys
import time
import urllib.error
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


def call(path: str, payload: dict | None = None, token: str = '') -> dict:
    data = json.dumps(payload).encode() if payload is not None else None
    headers = {'Content-Type': 'application/json'}
    if token:
        headers['Cookie'] = token
    request = urllib.request.Request(BASE + path, data=data, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        return {'error': error.code, 'body': error.read(2000).decode(errors='replace')}


def main() -> int:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel='chrome', headless=True)
        context = browser.new_context(viewport={'width': 1470, 'height': 1000})
        page = context.new_page()
        errors: list[str] = []
        page.on('pageerror', lambda e: errors.append(str(e)))

        page.goto(BASE + '/login', wait_until='networkidle')
        page.fill('input[type=email]', EMAIL)
        page.fill('input[type=password]', PASSWORD)
        page.click('button[type=submit]')
        page.wait_for_url(lambda url: '/login' not in url, timeout=20000)

        # Прогон создаём прямо через API: UI-путь уже проверен отдельно.
        payload = {
            'label': 'Проверка вердикта (mock)',
            'target_ids': [1],
            'judge_target_id': 1,
            'tools': ['harmbench', 'security-regression'],
            'engine_mode': 'mock',
            'limit': 3,
            'seed': 42,
            'judge_verdict': True,
            'judge_verdict_prompt': '',
        }
        # CSRF приходит в cookie-сессии; берём её из контекста браузера.
        cookies = '; '.join(f'{c["name"]}={c["value"]}' for c in context.cookies())
        me = call('/api/v1/auth/me', token=cookies)
        csrf = me.get('csrf_token', '')
        request = urllib.request.Request(
            BASE + '/api/v1/runs', data=json.dumps(payload).encode(),
            headers={'Content-Type': 'application/json', 'Cookie': cookies,
                     'x-csrf-token': csrf})
        with urllib.request.urlopen(request, timeout=60) as response:
            run = json.load(response)
        run_id = run['id']
        print('прогон создан:', run_id, run['run_id'])

        for _ in range(60):
            state = call(f'/api/v1/runs/{run_id}', token=cookies)
            if state.get('status') not in ('PENDING', 'RUNNING'):
                break
            time.sleep(2)
        print('статус        :', state.get('status'))
        print('вердикты      :', json.dumps(state.get('verdicts'), ensure_ascii=False)[:300])

        page.goto(BASE + f'/runs/{run_id}/report', wait_until='networkidle')
        page.wait_for_timeout(1200)
        page.screenshot(path=str(OUT / 'report-verdict.png'), full_page=False)

        has_block = page.locator('text=Вердикт судьи').count() > 0
        print('блок в отчёте :', has_block)
        if has_block:
            text = page.locator('text=Вердикт судьи').first.inner_text()
            print('заголовок     :', text.strip())

        page.goto(BASE + f'/runs/{run_id}', wait_until='networkidle')
        page.wait_for_timeout(900)
        page.screenshot(path=str(OUT / 'run-detail-verdict.png'), full_page=False)
        print('блок в детали :', page.locator('text=Вердикт судьи:').count() > 0)

        browser.close()
        if errors:
            print('ошибки:', *errors[:3], sep='\n  ')
        print('RUN_ID=%s' % run_id)
        return 0


if __name__ == '__main__':
    sys.exit(main())
