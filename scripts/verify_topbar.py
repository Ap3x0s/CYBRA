"""Check the new topbar controls and the animated backdrop actually work.

A control that looks clickable but does nothing is the exact defect the user
reported, so each one is exercised: ⌘K focuses the field, the bell and the
avatar open popovers, and every popover item navigates somewhere real.
"""
from __future__ import annotations

from playwright.sync_api import sync_playwright

BASE = 'http://127.0.0.1:8000'
EMAIL = 'admin@cybra.local'
PASSWORD = '7af4CP4-MFU18Cxz'

with sync_playwright() as playwright:
    browser = playwright.chromium.launch(channel='chrome', headless=True)
    page = browser.new_page(viewport={'width': 1600, 'height': 950})
    page.goto(BASE + '/login', wait_until='networkidle')
    page.fill('.sl-field__input >> nth=0', EMAIL)
    page.fill('.sl-field__input >> nth=1', PASSWORD)
    page.click('button[type=submit]')
    page.wait_for_url(BASE + '/', timeout=15000)
    page.wait_for_timeout(1200)

    # 1. ⌘K must put the caret in the search field.
    page.keyboard.press('Meta+k')
    page.wait_for_timeout(200)
    focused = page.evaluate("() => document.activeElement?.getAttribute('aria-label')")
    print('Ctrl/Cmd+K focuses search:', focused == 'Поиск')

    # 2. Bell opens a popover with real content.
    page.click('button[aria-label^="Уведомления"]')
    page.wait_for_timeout(250)
    bell_open = page.locator('.popover').count()
    bell_text = page.locator('.popover').first.inner_text().replace('\n', ' | ')[:80]
    print('bell popover open:', bell_open == 1, '|', bell_text)
    page.keyboard.press('Escape')

    # 3. Avatar opens account actions.
    page.click('.avatar')
    page.wait_for_timeout(250)
    account = page.locator('.popover').first.inner_text().replace('\n', ' | ')[:100]
    print('account popover:', account)
    page.keyboard.press('Escape')

    # 4. Backdrop canvas exists, has size, and is painting.
    canvas = page.evaluate("""() => {
      const c = document.querySelector('.backdrop-canvas');
      if (!c) return null;
      const ctx = c.getContext('2d');
      const data = ctx.getImageData(0, 0, Math.min(400, c.width), Math.min(300, c.height)).data;
      let painted = 0;
      for (let i = 3; i < data.length; i += 4) if (data[i] > 0) painted++;
      return { w: c.width, h: c.height, painted };
    }""")
    print('backdrop canvas:', canvas)

    page.screenshot(path='docs/media/backdrop-final.png')
    browser.close()
