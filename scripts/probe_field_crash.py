"""Isolate the crash: one page, backdrop on vs off, long observation.

bench_field crashed while cycling four browser contexts. This version keeps a
single context and just watches it, so the result says whether the field alone
brings the renderer down or whether it was the context churn.
"""
from __future__ import annotations

import os
import sys
import time

from playwright.sync_api import sync_playwright

BASE = 'http://127.0.0.1:8000'


def main() -> int:
    target = sys.argv[1] if len(sys.argv) > 1 else 'app'
    off = target == 'off'
    seconds = int(sys.argv[2]) if len(sys.argv) > 2 else 25

    with sync_playwright() as playwright:
        headless = os.environ.get('HEADFUL') != '1'
        browser = playwright.chromium.launch(channel='chrome', headless=headless)
        dsf = float(os.environ.get('DSF', '1'))
        context = browser.new_context(viewport={'width': 1440, 'height': 900},
                                      device_scale_factor=dsf)
        page = context.new_page()
        if target == 'ref':
            page.goto('file:///D:/projects/sdk-hub/demo/index.html', wait_until='domcontentloaded')
            page.wait_for_timeout(3000)
        else:
            page.goto(BASE + '/login', wait_until='networkidle')
            page.fill('input[type=email]', 'admin@cybra.local')
            page.fill('input[type=password]', '7af4CP4-MFU18Cxz')
            page.click('button[type=submit]')
            page.wait_for_url(BASE + '/', timeout=15000)

        if off:
            page.evaluate("() => document.querySelector('.backdrop-toggle')?.click()")
        page.wait_for_timeout(1500)

        started = time.time()
        while time.time() - started < seconds:
            try:
                info = page.evaluate(
                    """() => {
                        const el = document.querySelector('.backdrop-field') || document.querySelector('#texture');
                        const cv = el && el.querySelector('canvas');
                        const m = performance.memory;
                        return {
                            t: Math.round(performance.now() / 1000),
                            canvas: cv ? cv.width + 'x' + cv.height : null,
                            heapMB: m ? Math.round(m.usedJSHeapSize / 1048576) : null,
                            totalMB: m ? Math.round(m.totalJSHeapSize / 1048576) : null,
                            dom: document.querySelectorAll('*').length,
                        };
                    }"""
                )
                print(('off ' if off else 'on  ') + str(info), flush=True)
            except Exception as exc:                       # noqa: BLE001
                print('CRASHED after', round(time.time() - started, 1), 's:', type(exc).__name__)
                return 1
            time.sleep(3)

        print('survived', seconds, 's')
        browser.close()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
