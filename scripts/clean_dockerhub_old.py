"""Удалить из Docker Hub устаревшие теги, оставив актуальные.

Раньше скрипт сверялся с захардкоженным списком коммитов — и после каждой
новой публикации хотел удалить именно свежий тег, потому что список
оставался прежним. Признак плохого критерия: правильный ответ меняется
вместе с данными.

Теперь критерий — время, а не имена: оставляем latest и N последних тегов.
Всё, что старше, удаляется.

Токен берётся из DOCKERHUB_TOKEN и в файле не хранится: секрет, попавший в
репозиторий, остаётся в истории даже после удаления файла.

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

# Сколько последних тегов (кроме latest) считать актуальными.
KEEP_RECENT = 2


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
        return {'error': error.code,
                'detail': error.read(300).decode(errors='replace')}


def main() -> int:
    apply = '--apply' in sys.argv
    jwt = auth()
    print('вход в Docker Hub: ок')
    print()

    # API отдаёт теги от новых к старым.
    tags = api(jwt, '/tags?page_size=100')['results']

    keep = {'latest'}
    recent = [tag['name'] for tag in tags if tag['name'] != 'latest'][:KEEP_RECENT]
    keep.update(recent)

    doomed = [tag['name'] for tag in tags if tag['name'] not in keep]

    print(f'всего тегов: {len(tags)}; оставить: {len(keep)}, удалить: {len(doomed)}')
    print()
    print(f'остаются (latest + {KEEP_RECENT} последних):')
    for tag in tags:
        if tag['name'] in keep:
            print(f"  + {tag['name'][:14]:15} {tag['last_updated'][:16]}")
    print()
    print('удаляются (устаревшие сборки):')
    for tag in tags:
        if tag['name'] in doomed:
            print(f"  - {tag['name'][:14]:15} {tag['last_updated'][:16]}")

    if not apply:
        print()
        print('это план. для удаления: --apply')
        return 0

    print()
    removed = failed = 0
    for name in doomed:
        result = api(jwt, f'/tags/{name}/', method='DELETE')
        if result.get('error'):
            print(f'  {name[:14]}: ошибка {result["error"]}')
            failed += 1
        else:
            print(f'  {name[:14]}: удалён')
            removed += 1
    print()
    print(f'удалено: {removed}, ошибок: {failed}')
    return 0 if failed == 0 else 1


if __name__ == '__main__':
    raise SystemExit(main())
