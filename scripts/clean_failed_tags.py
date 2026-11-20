"""Удалить git-теги неудавшихся релизов на GitHub и GitLab.

Теги v0.2.0, v0.2.1, v0.2.2 — прогоны, где конвейер падал. Их архивы
скачиваются (HTTP 200), но содержат те же исходники, что и коммиты в
истории: тег — это указатель, удаление тега ничего не стирает.

Оставляем v0.1.0 (первый выпуск) и v0.2.3 (первый полностью прошедший).

Печатает план; удаляет с --apply.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOOMED = ['v0.2.0', 'v0.2.1', 'v0.2.2']


def gitlab_token() -> str:
    url = subprocess.run(['git', 'remote', 'get-url', 'gitlab'],
                         cwd=ROOT, capture_output=True, text=True).stdout
    match = re.search(r'glpat-[^@]+', url)
    return match.group(0) if match else ''


def github_token() -> str:
    result = subprocess.run(
        ['git', 'credential', 'fill'],
        input='protocol=https\nhost=github.com\n\n',
        cwd=ROOT, capture_output=True, text=True)
    for line in result.stdout.splitlines():
        if line.startswith('password='):
            return line.split('=', 1)[1]
    return ''


def delete_github(tag: str) -> tuple[bool, str]:
    request = urllib.request.Request(
        f'https://api.github.com/repos/Ap3x0s/CYBRA/git/refs/tags/{tag}',
        method='DELETE',
        headers={'Authorization': f'token {github_token()}',
                 'User-Agent': 'cybra',
                 'Accept': 'application/vnd.github+json'})
    try:
        with urllib.request.urlopen(request, timeout=40) as response:
            return response.status in (204, 200), str(response.status)
    except urllib.error.HTTPError as error:
        return False, f'{error.code} {error.read(200).decode(errors="replace")}'


def delete_gitlab(tag: str) -> tuple[bool, str]:
    request = urllib.request.Request(
        f'https://gitlab.com/api/v4/projects/89104466/repository/tags/{tag}',
        method='DELETE',
        headers={'PRIVATE-TOKEN': gitlab_token()})
    try:
        with urllib.request.urlopen(request, timeout=40) as response:
            return response.status in (204, 200), str(response.status)
    except urllib.error.HTTPError as error:
        return False, f'{error.code} {error.read(200).decode(errors="replace")}'


def main() -> int:
    apply = '--apply' in sys.argv

    print('теги, помеченные к удалению:')
    for tag in DOOMED:
        print(f'  - {tag}')
    print()
    print('остаются: v0.1.0 (первый выпуск), v0.2.3 (первый прошедший)')
    print()
    print('важно: тег — указатель на коммит. Исходники удаляемого тега')
    print('остаются в истории и доступны по SHA коммита. Удаление тега')
    print('убирает только имя, а не код.')
    print()

    if not apply:
        print('это план. для удаления: --apply')
        return 0

    failed = 0
    for tag in DOOMED:
        ok_gitlab, detail_gitlab = delete_gitlab(tag)
        print(f'  GitLab {tag}: {"удалён" if ok_gitlab else detail_gitlab}')
        ok_github, detail_github = delete_github(tag)
        print(f'  GitHub {tag}: {"удалён" if ok_github else detail_github}')
        if not (ok_gitlab and ok_github):
            failed += 1

    # Локальные теги тоже убираем, иначе следующий push вернёт их обратно.
    for tag in DOOMED:
        subprocess.run(['git', 'tag', '-d', tag], cwd=ROOT, capture_output=True)

    print()
    print(f'проблем: {failed}')
    return 0 if failed == 0 else 1


if __name__ == '__main__':
    raise SystemExit(main())
