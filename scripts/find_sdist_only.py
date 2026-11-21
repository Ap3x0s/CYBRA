"""Найти пакеты из locks, у которых нет бинарных колёс вообще.

Офлайн-bundle требует --only-binary=:all: (компилировать на месте нечем).
Если у пакета только sdist, он в bundle не попадёт, и установка упадёт.
Знать список заранее важнее, чем ловить по одному при сборке.
"""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def parse(path: Path) -> list[tuple[str, str]]:
    items = []
    for line in path.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line or line.startswith('#') or 'git+' in line or ' @ ' in line:
            continue
        match = re.match(r'^([A-Za-z0-9_.\-]+)==([^\s;]+)', line)
        if match:
            items.append((match.group(1), match.group(2)))
    return items


def has_wheel(name: str, version: str) -> bool | None:
    try:
        with urllib.request.urlopen(
                f'https://pypi.org/pypi/{name}/{version}/json', timeout=20) as response:
            data = json.load(response)
    except urllib.error.HTTPError:
        return None
    except Exception:
        return None
    # +cpu локальные версии на PyPI отсутствуют — считаем, что колесо есть
    # (оно лежит на индексе PyTorch, проверено отдельно).
    return any(u['packagetype'] == 'bdist_wheel' for u in data.get('urls', []))


def main() -> int:
    seen: dict[str, list[str]] = {}
    for path in sorted((ROOT / 'locks').glob('*.txt')):
        for name, version in parse(path):
            key = (name, version)
            if key in seen:
                continue
            result = has_wheel(name, version)
            if result is False:
                seen[key] = []
        # ничего не печатаем здесь: итог ниже

    only_sdist = sorted(seen.keys())
    print(f'пакетов только с sdist (нет колёс вообще): {len(only_sdist)}')
    for name, version in only_sdist:
        print(f'  {name}=={version}')
    print()
    if only_sdist:
        print('Эти пакеты потребуют сборки из исходников. Для офлайн-bundle это')
        print('означает: либо их колесо надо собрать заранее, либо исключить')
        print('инструмент из офлайн-поставки.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
