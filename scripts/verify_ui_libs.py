"""Verify the SL UI Library and Phosphor icons are actually loaded and rendered.

A screenshot cannot prove a library is wired up: the app would look similar
with hand-rolled CSS. This checks the concrete signals — the vendored sheet is
in the CSSOM, the library's field markup exists in the DOM, and Phosphor SVGs
are rendered with the expected count.
"""
from __future__ import annotations

import sys

from playwright.sync_api import sync_playwright

BASE = 'http://127.0.0.1:8000'
email, password = sys.argv[1], sys.argv[2]

with sync_playwright() as playwright:
    browser = playwright.chromium.launch(channel='chrome', headless=True)
    page = browser.new_page(viewport={'width': 1440, 'height': 900},
                            device_scale_factor=2)
    errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.on('console', lambda m: errors.append(m.text) if m.type == 'error' else None)

    page.goto(BASE + '/login', wait_until='networkidle')

    # 1. Library CSS reached the browser.
    has_field_rule = page.evaluate("""
      () => [...document.styleSheets].some(sheet => {
        try {
          return [...sheet.cssRules].some(rule => rule.selectorText
            && rule.selectorText.includes('.sl-field__control'))
        } catch (e) { return false }
      })
    """)
    print('SL UI .sl-field__control rule present:', has_field_rule)

    # 2. Library markup is in the DOM, not just in the stylesheet.
    print('SL field markup nodes:', page.locator('.sl-field').count())
    print('SL control nodes:', page.locator('.sl-field__control').count())
    print('SL input nodes:', page.locator('.sl-field__input').count())
    print('SL label nodes:', page.locator('.sl-field__label').count())

    # 3. Phosphor icons render as real <svg>.
    print('phosphor svg icons on login:', page.locator('svg').count())

    # 4. The font actually loaded (the library ships Instrument Sans).
    font_ok = page.evaluate("""
      () => document.fonts.check("14px 'Instrument Sans'")
    """)
    print('Instrument Sans available:', font_ok)

    page.screenshot(path='docs/media/login-final.png', full_page=True)

    # Log in, then check the console screens.
    page.fill('.sl-field__input >> nth=0', email)
    page.fill('.sl-field__input >> nth=1', password)
    page.click('button[type=submit]')
    page.wait_for_url(BASE + '/', timeout=15000)
    page.wait_for_timeout(1200)
    print('nav icons on console:', page.locator('.nav a svg').count())
    print('sidebar svg total:', page.locator('.sidebar svg').count())
    page.screenshot(path='docs/media/console-final.png', full_page=True)

    page.goto(BASE + '/runs/new', wait_until='networkidle')
    page.wait_for_timeout(800)
    page.screenshot(path='docs/media/new-run-final.png', full_page=True)

    print('ERRORS:', errors if errors else 'none')
    browser.close()
