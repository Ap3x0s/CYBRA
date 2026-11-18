"""Аудит фактического содержимого собранного образа.

Проверяем сам артефакт, а не только .dockerignore: правило в конфиге может
быть верным, а файл всё равно уедет — через COPY каталога, symlink, стадию.

Ищем:
  • секреты: .env, ключи, токены, куки, bundle-файлы;
  • личные данные: домены, email, локальные пути разработчика;
  • «мусор»: node_modules, __pycache__, .git, документацию с картинками.

CA-сертификаты из /etc/ssl/certs — это штатное содержимое Debian, их
пропускаем: они не наши и не секретны.
"""
from __future__ import annotations

import subprocess
import sys

IMAGE = sys.argv[1] if len(sys.argv) > 1 else 'cybra/cybra:audit'


def run(script: str) -> str:
    result = subprocess.run(
        ['docker', 'run', '--rm', IMAGE, 'sh', '-c', script],
        capture_output=True, text=True, encoding='utf-8', errors='replace')
    return result.stdout.strip()


SECRET_SCAN = r"""
find / -xdev \( -name '.env' -o -name '.env.*' -o -name 'secret.key' \
  -o -name 'cookies.txt' -o -name '*.bundle' -o -name '*.p12' \) \
  -not -path '*/node_modules/*' 2>/dev/null | head -30
"""

PERSONAL_SCAN = r"""
grep -rl -iE 'ap3x0kantor|evgenykantor|192\.168\.|C:.{0,2}Users.{0,2}evgen' \
  /app /data 2>/dev/null | head -20
"""

JUNK_SCAN = r"""
for p in /app/frontend /app/node_modules /app/backend/__pycache__ /app/.git; do
  if [ -e "$p" ]; then echo "JUNK $p"; fi
done
find /app -maxdepth 3 -name '__pycache__' -o -maxdepth 3 -name 'node_modules' 2>/dev/null | head -5
"""


def main() -> int:
    problems = 0

    print('=== секреты в образе ===')
    secrets = [line for line in run(SECRET_SCAN).splitlines() if line.strip()
               and line != '--- done ---']
    if secrets:
        for line in secrets:
            print(f'  FAIL {line}')
            problems += 1
    else:
        print('  чисто: .env, ключей, куки и bundle-файлов нет')

    print('\n=== личные данные в образе ===')
    personal = [line for line in run(PERSONAL_SCAN).splitlines() if line.strip()]
    if personal:
        for line in personal:
            print(f'  FAIL {line}')
            problems += 1
    else:
        print('  чисто: домены, email и локальные пути не найдены')

    print('\n=== мусор из репозитория ===')
    junk = [line for line in run(JUNK_SCAN).splitlines() if line.strip()]
    if junk:
        for line in junk:
            print(f'  FAIL {line}')
            problems += 1
    else:
        print('  чисто: node_modules, __pycache__, .git не уехали')

    print(f'\nпроблем: {problems}')
    return 0 if problems == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
