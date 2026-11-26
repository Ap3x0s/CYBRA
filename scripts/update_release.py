"""Заполнить release-манифест реальными digest из артефактов сборки.

Зачем: манифест — единственное место, где сказано «что развёрнуто», но
digest появляется только после сборки. Вписывать его руками — значит
однажды вписать не тот, и никто этого не заметит: сборка пройдёт, деплой
«успешно» развернёт вчерашний образ.

Скрипт берёт digest из файлов, которые пишет kaniko (--digest-file), и
подставляет в infra/releases/<release_id>.yml. PLACEHOLDER исчезает — и
проверка check_release.py начинает пропускать манифест.

Запуск:
    python scripts/update_release.py \\
        --release cybra-0.1.0 \\
        --backend-digest image-digest.txt \\
        --frontend-digest frontend-digest.txt

    # или из переменных окружения (так делает CI)
    BACKEND_DIGEST=sha256:... FRONTEND_DIGEST=sha256:... \\
        python scripts/update_release.py --release cybra-0.1.0
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
RELEASES = ROOT / 'infra' / 'releases'

DIGEST_PATTERN = re.compile(r'sha256:[0-9a-f]{64}')


def read_digest(path: Path | None, env_name: str) -> str | None:
    """Digest из файла kaniko или из переменной окружения.

    kaniko пишет в файл голый digest вида `sha256:abc…`. Переменная может
    содержать его же. Оба варианта нормализуем к одному виду.
    """
    value = ''
    if path and path.exists():
        value = path.read_text(encoding='utf-8').strip()
    if not value:
        value = os.environ.get(env_name, '').strip()
    if not value:
        return None

    match = DIGEST_PATTERN.search(value)
    return match.group(0) if match else None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--release', required=True, help='release_id, например cybra-0.1.0')
    parser.add_argument('--backend-digest', type=Path, default=None,
                        help='файл с digest бэкенда (--digest-file у kaniko)')
    parser.add_argument('--frontend-digest', type=Path, default=None,
                        help='файл с digest фронтенда')
    parser.add_argument('--registry', default=None,
                        help='registry для образов; по умолчанию из манифеста')
    parser.add_argument('--config-ref', default=None,
                        help='commit SHA configurations; по умолчанию CI_COMMIT_SHA')
    args = parser.parse_args()

    path = RELEASES / f'{args.release}.yml'
    if not path.exists():
        print(f'манифест не найден: {path.relative_to(ROOT).as_posix()}')
        return 1

    data = yaml.safe_load(path.read_text(encoding='utf-8')) or {}
    services = data.get('services') or {}

    backend = read_digest(args.backend_digest, 'BACKEND_DIGEST')
    frontend = read_digest(args.frontend_digest, 'FRONTEND_DIGEST')

    if not backend or not frontend:
        missing = [name for name, value in
                   (('backend', backend), ('frontend', frontend)) if not value]
        print(f'не найден digest: {", ".join(missing)}')
        print('передайте --backend-digest/--frontend-digest или переменные '
              'BACKEND_DIGEST/FRONTEND_DIGEST')
        return 1

    # Подставляем точечно, а не пересобираем YAML целиком.
    #
    # Первая версия делала yaml.safe_load + safe_dump, и это оказалось
    # потерей: safe_dump не умеет комментарии, а в манифесте их больше, чем
    # самого содержимого — ровно там объяснено, почему digest, а не тег, и
    # что именно проверяет smoke. Молча стереть это при первом же
    # заполнении — худший вариант: файл выглядит рабочим, но больше ничего
    # не объясняет.
    #
    # Поэтому работаем текстом: правим только строки image и config_ref.
    text = path.read_text(encoding='utf-8')
    changed = 0

    for name, digest in (('backend', backend), ('frontend', frontend)):
        current = str(services.get(name, {}).get('image', ''))
        repository = (f'{args.registry}/{name}' if args.registry
                      else current.split('@', 1)[0] or f'cybra/{name}')
        new_image = f'{repository}@{digest}'

        # Ищем строку вида `    image: "..."` внутри блока нужного сервиса.
        pattern = re.compile(
            rf'(\n  {name}:\n(?:.*\n)*?    image:\s*)("[^"]*"|\S+)')
        text, count = pattern.subn(rf'\1"{new_image}"', text, count=1)
        if count == 0:
            print(f'не удалось найти image для {name} в манифесте')
            return 1
        changed += count
        print(f'  {name}: {digest}')

    config_ref = args.config_ref or os.environ.get('CI_COMMIT_SHA', '')
    if config_ref:
        text, count = re.subn(r'(?m)^config_ref:.*$',
                              f'config_ref: "{config_ref}"', text, count=1)
        if count == 0:
            print('не удалось найти config_ref в манифесте')
            return 1
        print(f'  config_ref: {config_ref[:12]}')

    path.write_text(text, encoding='utf-8', newline='\n')
    print(f'обновлён: {path.relative_to(ROOT).as_posix()} '
          f'(замен: {changed + 1})')
    return 0


if __name__ == '__main__':
    sys.exit(main())
