"""Drive the dataset edit flow in a real browser.

This is the requirement that matters most from the brief (editable datasets with
versioning), so it gets a scripted end-to-end check rather than a screenshot.
"""
from __future__ import annotations

import sys

from playwright.sync_api import sync_playwright

BASE = 'http://127.0.0.1:8000'
email = sys.argv[1]
password = sys.argv[2]

with sync_playwright() as playwright:
    browser = playwright.chromium.launch(channel='chrome', headless=True)
    page = browser.new_page(viewport={'width': 1440, 'height': 900})
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.on('console', lambda message: errors.append(message.text)
            if message.type == 'error' else None)

    page.goto(BASE + '/login', wait_until='networkidle')
    page.fill('input[type=email]', email)
    page.fill('input[type=password]', password)
    page.click('button[type=submit]')
    page.wait_for_url(BASE + '/', timeout=15000)

    # Datasets: pick the corporate version, then edit its first case.
    page.goto(BASE + '/datasets', wait_until='networkidle')
    page.get_by_text('CORPORATE', exact=False).first.wait_for(timeout=10000)
    page.get_by_role('button', name='v0.0.1').nth(2).click()
    page.wait_for_timeout(900)
    print('cases visible:', page.locator('table.data tbody tr').count())

    page.get_by_role('button', name='Править').first.click()
    page.wait_for_timeout(400)
    prompt_box = page.locator('textarea').first
    prompt_box.fill('[правка из UI] изменённый промпт для проверки версионирования')
    page.screenshot(path='docs/media/dataset-edit.png', full_page=True)

    page.get_by_role('button', name='Сохранить как новую версию').click()
    page.wait_for_timeout(2000)
    notice = page.locator('.banner').first.inner_text()
    print('NOTICE:', notice)

    # Verify a new version appeared in the sidebar list.
    page.wait_for_timeout(800)
    versions = page.locator('button:has-text("v0.0.2")').count()
    print('v0.0.2 visible:', versions)
    page.screenshot(path='docs/media/dataset-after-edit.png', full_page=True)

    # Metrics chart should render with real points.
    page.goto(BASE + '/metrics', wait_until='networkidle')
    page.wait_for_timeout(1200)
    polylines = page.locator('svg polyline, svg path[stroke]').count()
    print('chart paths:', polylines)
    page.screenshot(path='docs/media/metrics-final.png', full_page=True)

    print('ERRORS:', errors if errors else 'none')
    browser.close()
