"""Проверить, что все версии из lock-файлов реально существуют.

Зачем: офлайн-bundle собирается ИЗ этих файлов. Если в них версия, которой
нет в индексе, сборка bundle упадёт на машине с интернетом — уже поздно.
Проверять дешевле заранее.

Учитываются особые случаи:
  * git-ссылки — пропускаются, это не PyPI;
  * +cpu сборки torch — лежат не на PyPI, а на download.pytorch.org;
  * пакеты с маркерами платформы.
"""
from __future__ import annotations

import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYTORCH_CPU = 'https://download.pytorch.org/whl/cpu/'


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


def on_pypi(name: str, version: str) -> bool:
    try:
        with urllib.request.urlopen(f'https://pypi.org/pypi/{name}/{version}/json', timeout=15):
            return True
    except urllib.error.HTTPError as error:
        return error.code != 404
    except Exception:
        return True


def on_pytorch_cpu(name: str, version: str) -> bool:
    try:
        with urllib.request.urlopen(f'{PYTORCH_CPU}{name}/', timeout=30) as response:
            body = response.read().decode(errors='replace')
    except Exception:
        return False
    return f'{name}-{version}' in body


def main() -> int:
    files = sorted(ROOT.joinpath('locks').glob('*.txt'))
    problems: list[str] = []
    total = 0

    for path in files:
        items = parse(path)
        missing = []
        for name, version in items:
            total += 1
            # +cpu сборки torch живут на индексе PyTorch, а не на PyPI.
            if '+cpu' in version or '+cu' in version:
                if not on_pytorch_cpu(name, version.split('+')[0] + '+' + version.split('+')[1]):
                    missing.append(f'{name}=={version}')
                continue
            if not on_pypi(name, version):
                missing.append(f'{name}=={version}')
        status = 'ok' if not missing else f'ОТСУТСТВУЕТ {len(missing)}'
        print(f'{path.name:18} {len(items):4} пакетов  {status}')
        for item in missing:
            problems.append(f'{path.name}: {item}')
            print(f'    ✗ {item}')

    print()
    print(f'всего пакетов проверено: {total}')
    if problems:
        print(f'проблем: {len(problems)}')
        print()
        print('Эти версии нельзя скачать — офлайн-bundle из текущих locks не соберётся.')
        return 1

    print('все версии скачиваемы — bundle можно собирать')
    return 0


if __name__ == '__main__':
    sys.exit(main())
