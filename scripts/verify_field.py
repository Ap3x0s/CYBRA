"""Measure the background ASCII field after a real page load.

The field exposes its own telemetry on the container (dataset.drawn / .grid /
.time), copied from the reference. This checks it is actually painting, how
dense it is, that the glyphs keep moving, and that no console errors appeared.
"""
from __future__ import annotations

import sys

from playwright.sync_api import sync_playwright

BASE = 'http://127.0.0.1:8000'


def main() -> int:
    email = sys.argv[1] if len(sys.argv) > 1 else 'admin@cybra.local'
    password = sys.argv[2] if len(sys.argv) > 2 else '7af4CP4-MFU18Cxz'
    out = sys.argv[3] if len(sys.argv) > 3 else 'field.png'

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel='chrome', headless=True)
        context = browser.new_context(viewport={'width': 1440, 'height': 900},
                                      device_scale_factor=2)
        page = context.new_page()
        errors: list[str] = []
        page.on('console', lambda m: errors.append(m.text) if m.type == 'error' else None)
        page.on('pageerror', lambda e: errors.append(str(e)))

        page.goto(BASE + '/login', wait_until='networkidle')
        page.fill('input[type=email]', email)
        page.fill('input[type=password]', password)
        page.click('button[type=submit]')
        page.wait_for_url(BASE + '/', timeout=15000)
        # the field reports its own telemetry only when ?debug is in the URL
        page.goto(BASE + '/?debug', wait_until='networkidle')
        page.wait_for_timeout(2500)

        stats = page.evaluate(
            """() => {
                const el = document.querySelector('.backdrop-field');
                if (!el) return { present: false };
                const cv = el.querySelector('canvas');
                return {
                    present: true,
                    ready: el.dataset.ready !== undefined,
                    drawn: Number(el.dataset.drawn || 0),
                    grid: el.dataset.grid || '',
                    taps: Number(el.dataset.taps || 0),
                    time: Number(el.dataset.time || 0),
                    w: el.clientWidth, h: el.clientHeight,
                    canvases: el.querySelectorAll('canvas').length,
                    canvasSize: cv ? [cv.width, cv.height] : null,
                    opacity: getComputedStyle(el).opacity,
                    color: getComputedStyle(el).color,
                };
            }"""
        )

        page.wait_for_timeout(1200)
        t2 = page.evaluate(
            """() => Number(document.querySelector('.backdrop-field')?.dataset.time || 0)"""
        )

        page.screenshot(path=out)
        # a crop with UI hidden, so the field itself is visible
        page.evaluate(
            """() => { const s = document.querySelector('.shell');
                       if (s) s.style.visibility = 'hidden'; }"""
        )
        page.wait_for_timeout(400)
        page.screenshot(path=out.replace('.png', '-bare.png'))

        print('stats:', stats)
        print('time after 1.2s:', t2, '| moved:', t2 > stats.get('time', 0))
        print('console errors:', errors[:5] if errors else 'none')
        print('saved:', out, out.replace('.png', '-bare.png'))
        browser.close()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
