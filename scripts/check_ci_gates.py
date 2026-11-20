"""Соответствие схеме: какие проверки блокируют конвейер, а какие нет."""
from __future__ import annotations

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
data = yaml.safe_load((ROOT / '.gitlab-ci.yml').read_text(encoding='utf-8'))

print(f"{'job':24} {'stage':13} {'блокирует':10} {'ручной':7}")
blocking = nonblocking = 0
for name, body in data.items():
    if not isinstance(body, dict) or 'stage' not in body:
        continue
    rules = body.get('rules') or []
    manual = any(r.get('when') == 'manual' for r in rules if isinstance(r, dict))
    af = body.get('allow_failure', False)
    blocks = (not af) and (not manual)
    if blocks:
        blocking += 1
    else:
        nonblocking += 1
    print(f"{name:24} {body['stage']:13} {'да' if blocks else 'нет':10} {'да' if manual else '':7}")

print()
print(f'блокирующих проверок: {blocking}, неблокирующих: {nonblocking}')
sys.exit(0)
