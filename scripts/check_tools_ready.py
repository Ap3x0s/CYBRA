"""Есть ли реально установленные бенчмарки для полноценного прогона."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scan.capabilities import capabilities  # noqa: E402


def main() -> int:
    rows = capabilities()
    ready = [r for r in rows if r['available']]
    print(f'готовы: {len(ready)} из {len(rows)}')
    print()
    for row in rows:
        mark = 'OK  ' if row['available'] else 'НЕТ '
        hint = (row.get('install_hint') or '')[:60]
        print(f"{mark}{row['tool']:20} {hint}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
