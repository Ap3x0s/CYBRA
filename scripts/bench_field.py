"""Measure what the backdrop field costs: frame rate and JS heap.

The reference field repaints a dpr-scaled canvas every 16 ms. On a big screen
that is a real cost, so it needs a number rather than an impression.
"""
from __future__ import annotations

import os
import sys

from playwright.sync_api import sync_playwright

BASE = 'http://127.0.0.1:8000'
OFF = os.environ.get('OFF') == '1'

PROBE = """async () => {
  const el = document.querySelector('.backdrop-field');
  const cv = el && el.querySelector('canvas');
  if (!cv) return { present: false };
  const frames = [];
  let last = performance.now();
  await new Promise((done) => {
    const tick = (now) => { frames.push(now - last); last = now;
      if (frames.length < 90) requestAnimationFrame(tick); else done(); };
    requestAnimationFrame(tick);
  });
  frames.sort((a, b) => a - b);
  const mid = frames[frames.length >> 1];
  const heap = performance.memory ? Math.round(performance.memory.usedJSHeapSize / 1048576) : null;
  return {
    present: true,
    canvas: [cv.width, cv.height],
    medianFrameMs: Math.round(mid * 10) / 10,
    p95FrameMs: Math.round(frames[Math.floor(frames.length * 0.95)] * 10) / 10,
    fps: Math.round(1000 / mid),
    heapMB: heap,
  };
}"""


def main() -> int:
    email = sys.argv[1] if len(sys.argv) > 1 else 'admin@cybra.local'
    password = sys.argv[2] if len(sys.argv) > 2 else '7af4CP4-MFU18Cxz'

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel='chrome', headless=True)
        cases = (('1440x900', (1440, 900), 'no-preference'),
                 ('1920x1080', (1920, 1080), 'no-preference'),
                 ('reduced-motion', (1440, 900), 'reduce'),
                 ('mobile-390', (390, 780), 'no-preference'))
        for label, size, motion in cases:
            context = browser.new_context(viewport={'width': size[0], 'height': size[1]},
                                          reduced_motion=motion)
            page = context.new_page()
            page.goto(BASE + '/login', wait_until='networkidle')
            page.fill('input[type=email]', email)
            page.fill('input[type=password]', password)
            page.click('button[type=submit]')
            page.wait_for_url(BASE + '/', timeout=15000)
            if OFF:
                page.evaluate("() => document.querySelector('.backdrop-toggle')?.click()")
            page.wait_for_timeout(2000)
            try:
                print(label, page.evaluate(PROBE), flush=True)
            except Exception as exc:                      # noqa: BLE001
                print(label, 'FAILED:', type(exc).__name__, str(exc)[:80], flush=True)
            context.close()
        browser.close()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
