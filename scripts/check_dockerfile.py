#!/usr/bin/env python
"""Static checks for the Dockerfile.

Docker Desktop's Linux engine does not start on this machine (the same problem
is recorded in TRANSFER.md), so the image could not be built here. This script
verifies what can be verified without a daemon: every COPY source exists, the
final CMD imports, and the build does not reference files excluded by
.dockerignore.

Run this in CI where a daemon is available; here it is a guard against typos.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCKERFILE = ROOT / 'docker' / 'Dockerfile'


def sources(dockerfile: Path) -> list[str]:
    found = []
    for line in dockerfile.read_text(encoding='utf-8').splitlines():
        stripped = line.strip()
        if not stripped.upper().startswith('COPY'):
            continue
        if '--from=' in stripped:
            continue  # comes from a previous build stage, not the context
        parts = stripped.split()
        found.extend(parts[1:-1])  # last token is the destination
    return found


def main() -> int:
    problems = []

    if not DOCKERFILE.exists():
        print('FAIL: Dockerfile missing')
        return 1

    ignored = set()
    ignore_file = ROOT / '.dockerignore'
    if ignore_file.exists():
        ignored = {
            line.strip() for line in ignore_file.read_text(encoding='utf-8').splitlines()
            if line.strip() and not line.startswith('#')
        }

    for source in sources(DOCKERFILE):
        relative = source.lstrip('./').rstrip('/')
        if relative.endswith('*'):
            # Globs are legal in COPY; verify at least one match exists.
            matches = list(ROOT.glob(relative))
            if not matches:
                problems.append(f'COPY glob matches nothing: {source}')
            continue
        if not (ROOT / relative).exists():
            problems.append(f'COPY source does not exist: {source}')
            continue
        top = relative.split('/')[0]
        if top in ignored:
            problems.append(f'COPY source is excluded by .dockerignore: {source}')

    text = DOCKERFILE.read_text(encoding='utf-8')
    if 'USER cybra' not in text:
        problems.append('Container runs as root: add a USER directive')
    if 'HEALTHCHECK' not in text:
        problems.append('No HEALTHCHECK defined')
    if not re.search(r'^CMD ', text, re.MULTILINE):
        problems.append('No CMD defined')

    # Entry point must be importable; a typo here breaks the image only at run time.
    sys.path.insert(0, str(ROOT / 'backend'))
    try:
        from cybra.main import create_app  # noqa: F401
    except Exception as error:  # noqa: BLE001
        problems.append(f'cybra.main cannot be imported: {error}')

    if problems:
        for problem in problems:
            print('FAIL:', problem)
        return 1
    print('Dockerfile static checks passed')
    print(f'  COPY sources: {len(sources(DOCKERFILE))} verified')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
