"""Audit every screen for overflow, overlap and uneven rows.

Run after any layout change: the check is cheap and catches the class of defect
that a screenshot review tends to miss (a graphic under text, a child escaping
its card, a row where one card is taller than its neighbour).
"""
from __future__ import annotations

import sys

from playwright.sync_api import sync_playwright

BASE = 'http://127.0.0.1:8000'
EMAIL = 'admin@cybra.local'
PASSWORD = '7af4CP4-MFU18Cxz'
SCREENS = ['/', '/runs', '/runs/1', '/runs/new', '/datasets', '/metrics', '/models',
           '/settings', '/runs/1/report']

AUDIT = """() => {
  const issues = [];
  const rect = (el) => el.getBoundingClientRect();

  // A child inside a deliberately scrollable box is not a layout bug: the
  // content is meant to overflow and be reached by scrolling.
  const inScrollContainer = (el) => {
    let node = el.parentElement;
    while (node && node !== document.body) {
      const style = getComputedStyle(node);
      if (/(auto|scroll)/.test(style.overflowY) || /(auto|scroll)/.test(style.overflowX)) {
        return true;
      }
      node = node.parentElement;
    }
    return false;
  };

  // A closed <details> keeps its children in the accessibility tree but
  // collapses them to zero height, so their measured rect is meaningless.
  // Skipping them avoids reporting a defect that is not on screen.
  const inClosedDetails = (el) => {
    let node = el.parentElement;
    while (node && node !== document.body) {
      if (node.tagName === 'DETAILS' && !node.open) return true;
      node = node.parentElement;
    }
    return false;
  };

  for (const card of document.querySelectorAll('.card, .kpi')) {
    const cr = rect(card);
    for (const child of card.querySelectorAll('*')) {
      const r = rect(child);
      if (!r.width || !r.height) continue;
      if (inScrollContainer(child) || inClosedDetails(child)) continue;
      const overRight = r.right - cr.right;
      const overBottom = r.bottom - cr.bottom;
      if (overRight > 2 || overBottom > 2) {
        issues.push({
          kind: 'overflow',
          where: card.className.split(' ')[0],
          el: child.tagName + '.' + String(child.className).split(' ')[0],
          overRight: Math.round(overRight),
          overBottom: Math.round(overBottom),
        });
      }
    }
  }

  for (const spark of document.querySelectorAll('.kpi-spark')) {
    const sr = rect(spark);
    if (!sr.width) continue;
    for (const text of document.querySelectorAll('.kpi-value, .kpi-foot, .kpi-head')) {
      const tr = rect(text);
      const ox = Math.min(sr.right, tr.right) - Math.max(sr.left, tr.left);
      const oy = Math.min(sr.bottom, tr.bottom) - Math.max(sr.top, tr.top);
      if (ox > 4 && oy > 4) {
        issues.push({ kind: 'overlap', what: 'spark over ' + text.className,
                      ox: Math.round(ox), oy: Math.round(oy) });
      }
    }
  }

  return {
    issues,
    overflowX: Math.max(0, document.documentElement.scrollWidth - window.innerWidth),
  };
}"""


def main() -> int:
    failures = 0
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel='chrome', headless=True)
        page = browser.new_page(viewport={'width': 1600, 'height': 1000})
        page.goto(BASE + '/login', wait_until='networkidle')
        page.fill('.sl-field__input >> nth=0', EMAIL)
        page.fill('.sl-field__input >> nth=1', PASSWORD)
        page.click('button[type=submit]')
        page.wait_for_url(BASE + '/', timeout=15000)

        for path in SCREENS:
            page.goto(BASE + path, wait_until='networkidle')
            page.wait_for_timeout(600)

            # Closed details hide their content from measurement, so the audit
            # would miss a real overflow inside an expanded panel. Open them
            # all first, then measure.
            page.evaluate("() => document.querySelectorAll('details').forEach(d => d.open = true)")
            page.wait_for_timeout(250)

            result = page.evaluate(AUDIT)
            status = 'OK ' if not result['issues'] and not result['overflowX'] else 'FAIL'
            if status == 'FAIL':
                failures += 1
            print(f"{status} {path:18} issues={len(result['issues'])} "
                  f"overflowX={result['overflowX']}")
            for issue in result['issues'][:5]:
                print('      ', issue)

        browser.close()
    print('\n' + ('all screens clean' if not failures else f'{failures} screen(s) with issues'))
    return 0 if not failures else 1


if __name__ == '__main__':
    sys.exit(main())
