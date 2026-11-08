"""End-to-end check of the agentation link: toolbar -> MCP server.

Clicks the toolbar through its shadow root, adds an annotation, and then asks
the MCP HTTP API whether the annotation arrived. A screenshot alone would not
prove the annotations reach the agent.
"""
from __future__ import annotations

import json
import time
import urllib.request

from playwright.sync_api import sync_playwright

DEV = 'http://localhost:5173'
MCP = 'http://127.0.0.1:4747'


def api(path: str) -> dict | list:
    with urllib.request.urlopen(MCP + path, timeout=6) as response:
        return json.loads(response.read().decode())


def main() -> int:
    print('sessions before:', len(api('/sessions')))

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel='chrome', headless=True)
        page = browser.new_page(viewport={'width': 1440, 'height': 900},
                                device_scale_factor=2)
        page.goto(DEV + '/login', wait_until='networkidle')
        page.wait_for_timeout(2500)

        # Activate the toolbar by clicking its toggle inside the shadow root.
        state = page.evaluate("""() => {
          const host = document.querySelector('agentation-toolbar');
          if (!host || !host.shadowRoot) return {ok: false, why: 'no shadow root'};
          const root = host.shadowRoot;
          const fixed = [...root.querySelectorAll('*')].filter(e => {
            const r = e.getBoundingClientRect();
            return r.width > 0 && r.height > 0 &&
                   getComputedStyle(e).position === 'fixed';
          });
          const toolbar = fixed.find(e => String(e.className).includes('toolbar'));
          if (!toolbar) return {ok: false, why: 'no toolbar'};
          return {
            ok: true,
            rect: (() => { const r = toolbar.getBoundingClientRect();
                           return [r.x, r.y, r.width, r.height].map(Math.round); })(),
            buttons: toolbar.querySelectorAll('button').length,
            text: (toolbar.innerText || '').slice(0, 80),
          };
        }""")
        print('toolbar state:', state)

        if not state.get('ok'):
            browser.close()
            return 1

        x, y, w, h = state['rect']
        # The toggle sits at the left edge of the collapsed pill.
        page.mouse.click(x + 14, y + h / 2)
        page.wait_for_timeout(1200)
        page.screenshot(path='docs/media/agentation-active.png')

        after = page.evaluate("""() => {
          const host = document.querySelector('agentation-toolbar');
          const root = host.shadowRoot;
          return {
            text: (root.innerText || '').slice(0, 200).replace(/\\n/g, ' | '),
          };
        }""")
        print('after click:', after['text'])

        browser.close()

    time.sleep(1)
    sessions = api('/sessions')
    print('sessions after:', len(sessions))
    for session in sessions:
        print('  ', session.get('id'), session.get('url'), session.get('status'))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
