"""Screenshot the console with the system Chrome.

Purpose: visual verification of the UI before showing it. Uses Playwright's
channel=chrome so no Chromium download is needed.
"""
from __future__ import annotations

import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = 'http://127.0.0.1:8000'
OUT = Path(__file__).resolve().parents[1] / 'docs' / 'media'
OUT.mkdir(parents=True, exist_ok=True)

SHOTS = [
    ('/login', 'login', None),
    ('/', 'console', None),
    ('/runs', 'runs', None),
    ('/runs/1', 'run-detail', None),
    ('/runs/1/report', 'report', None),
    ('/datasets', 'datasets', None),
    ('/metrics', 'metrics', None),
    ('/models', 'models', None),
    ('/runs/new', 'new-run', None),
]


def main() -> int:
    email = sys.argv[1] if len(sys.argv) > 1 else 'admin@cybra.local'
    password = sys.argv[2] if len(sys.argv) > 2 else ''

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel='chrome', headless=True)
        context = browser.new_context(viewport={'width': 1440, 'height': 900},
                                      device_scale_factor=2)
        page = context.new_page()
        errors = []
        page.on('console', lambda message: errors.append(message.text)
                if message.type == 'error' else None)
        page.on('pageerror', lambda error: errors.append(str(error)))

        # Login flow first, so later navigations run with a session cookie.
        page.goto(BASE + '/login', wait_until='networkidle')
        page.screenshot(path=str(OUT / 'login.png'), full_page=True)
        page.fill('input[type=email]', email)
        page.fill('input[type=password]', password)
        page.click('button[type=submit]')
        page.wait_for_url(BASE + '/', timeout=15000)
        page.wait_for_load_state('networkidle')

        for path, name, _ in SHOTS:
            page.goto(BASE + path, wait_until='networkidle')
            page.wait_for_timeout(700)
            page.screenshot(path=str(OUT / f'{name}.png'), full_page=True)
            print(f'shot {name}: {page.url}', flush=True)

        if errors:
            print('CONSOLE ERRORS:', flush=True)
            for line in dict.fromkeys(errors):
                print('  ', line, flush=True)
        else:
            print('no console errors', flush=True)

        context.close()
        browser.close()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
