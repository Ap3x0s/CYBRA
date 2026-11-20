"""Удалить из Docker Hub теги, собранные старым способом (docker build).

Оставляем собранные kaniko: latest и :<sha> от прогонов после перехода на
kaniko. Остальные — артефакты прежней сборки: они не воспроизводятся
текущим конвейером и только путают, какой образ актуален.

Токен НЕ хранится в файле: он берётся из DOCKERHUB_TOKEN. Токен, попавший
в репозиторий, остаётся в истории даже после удаления файла — и GitHub
справедливо блокирует такой push секрет-сканером.

Печатает план; удаляет только с --apply.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

USER = os.environ.get('DOCKERHUB_USER', 'ap3x0')
REPO = os.environ.get('DOCKERHUB_REPO', 'cybra')

# Коммиты, собранные kaniko (прогоны после перехода).
KANIKO_COMMITS = {
    'e57529d6039fd217f696b399b1471a23c0fe8459',
    'df2befa5b09ebff238a8d0c856be30a576806725',
    'f16d26e2e799102a986d7ea767b6c4e174c04d4a',
    '03dcf2c3ff560cc2949c9f6690963784d9faeeb1',
    'de0ccf236764c0b888849c9e7b5e27e861a6e343',
}
KEEP = KANIKO_COMMITS | {'latest'}


def token() -> str:
    value = os.environ.get('DOCKERHUB_TOKEN', '')
    if not value:
        raise SystemExit(
            'нужен DOCKERHUB_TOKEN в окружении.\n'
            '  PowerShell: $env:DOCKERHUB_TOKEN = "<токен>"\n'
            '  bash:       export DOCKERHUB_TOKEN=<токен>')
    return value


def auth() -> str:
    request = urllib.request.Request(
        'https://hub.docker.com/v2/users/login',
        data=json.dumps({'username': USER, 'password': token()}).encode(),
        headers={'Content-Type': 'application/json'})
    return json.load(urllib.request.urlopen(request))['token']


def api(jwt: str, path: str, method: str = 'GET'):
    request = urllib.request.Request(
        f'https://hub.docker.com/v2/repositories/{USER}/{REPO}{path}',
        method=method,
        headers={'Authorization': f'Bearer {jwt}',
                 'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(request, timeout=40) as response:
            body = response.read().decode()
            return json.loads(body) if body else {}
    except urllib.error.HTTPError as error:
        return {'error': error.code, 'detail': error.read(300).decode(errors='replace')}


def main() -> int:
    apply = '--apply' in sys.argv
    jwt = auth()
    print('вход в Docker Hub: ок')
    print()

    tags = api(jwt, '/tags?page_size=100')['results']
    keep = [t['name'] for t in tags if t['name'] in KEEP]
    doomed = [t['name'] for t in tags if t['name'] not in KEEP]

    print(f'всего тегов: {len(tags)}; оставить: {len(keep)}, удалить: {len(doomed)}')
    print()
    print('остаются (kaniko):')
    for name in keep:
        print(f'  + {name[:14]}')
    print()
    print('удаляются (docker build, старый способ):')
    for name in doomed:
        print(f'  - {name[:14]}')

    if not apply:
        print()
        print('это план. для удаления: --apply')
        return 0

    print()
    removed = failed = 0
    for name in doomed:
        result = api(jwt, f'/tags/{name}/', method='DELETE')
        if result.get('error'):
            print(f'  {name[:14]}: ошибка {result["error"]} {result.get("detail", "")[:60]}')
            failed += 1
        else:
            print(f'  {name[:14]}: удалён')
            removed += 1
    print()
    print(f'удалено: {removed}, ошибок: {failed}')
    return 0 if failed == 0 else 1


if __name__ == '__main__':
    raise SystemExit(main())
