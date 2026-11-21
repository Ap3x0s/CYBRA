"""Оценить вес офлайн-bundle: сколько займут колёса для тяжёлых бенчмарков.

Читает locks/*.txt, запрашивает у PyPI размер каждого пакета для нужной
платформы и складывает. Это оценка, а не точный расчёт: часть пакетов
зависит от ОС и версии Python, поэтому считается по linux/cp312 — целевой
платформе загрузки.
"""
from __future__ import annotations

import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
METADATA = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else ROOT / 'locks'


def parse_lock(path: Path) -> list[tuple[str, str]]:
    """Версии из lock-файла; git-ссылки пропускаем, их размер неизвестен."""
    packages = []
    for line in path.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        if 'git+' in line or ' @ ' in line:
            continue
        match = re.match(r'^([A-Za-z0-9_.\-]+)==([^\s;]+)', line)
        if match:
            packages.append((match.group(1), match.group(2)))
    return packages


def wheel_size(name: str, version: str) -> int | None:
    """Размер подходящего wheel для linux x86_64 cp312."""
    url = f'https://pypi.org/pypi/{name}/{version}/json'
    try:
        with urllib.request.urlopen(url, timeout=20) as response:
            data = json.load(response)
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError):
        return None

    candidates = data.get('urls') or []
    # Приоритет: manylinux x86_64 cp312, потом просто wheel, потом sdist.
    for wanted in ('manylinux', 'musllinux', 'any.whl', ''):
        for item in candidates:
            filename = item['filename']
            if wanted and wanted not in filename:
                continue
            if 'cp312' in filename or 'abi3' in filename or 'py3-none' in filename or not wanted:
                if 'x86_64' in filename or 'any.whl' in filename or not wanted:
                    return item['size']
    for item in candidates:
        if 'x86_64' in item['filename'] or 'any.whl' in item['filename']:
            return item['size']
    return candidates[0]['size'] if candidates else None


def main() -> int:
    files = sorted(METADATA.glob('*.txt'))
    if not files:
        print(f'в {METADATA} нет lock-файлов')
        return 1

    total = 0
    print(f'{"файл":18} {"пакетов":9} {"вес":>10}')
    print('-' * 42)
    for path in files:
        packages = parse_lock(path)
        size = 0
        missing = 0
        for name, version in packages:
            got = wheel_size(name, version)
            if got is None:
                missing += 1
            else:
                size += got
        total += size
        note = f'  (+{missing} без размера)' if missing else ''
        print(f'{path.name:18} {len(packages):9} {size / 1_048_576:9.1f} МБ{note}')

    print('-' * 42)
    print(f'{"ИТОГО":18} {"":9} {total / 1_048_576:9.1f} МБ')
    print()
    print('Оценка для linux/cp312. Windows-сборка займёт сравнимо:')
    print('различаются колёса, но не состав пакетов.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
