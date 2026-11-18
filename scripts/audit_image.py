"""Аудит содержимого образа — выполняется ИЗНУТРИ него.

Проверяем сам артефакт, а не только .dockerignore: правило в конфиге может
быть верным, а файл всё равно уедет — через COPY каталога, symlink, стадию.

Два режима:

  • `--self <образ>` — запуск внутри образа (так делает CI):
        docker run --rm -v "$PWD/scripts:/audit:ro" --entrypoint python \
          <образ> /audit/audit_image.py --self <образ>
    Проверяет собственную файловую систему: секреты, личные данные, мусор.

  • без аргументов — снаружи, через docker run (локальная проверка).

Почему так: первый вариант проверки стоял в job'е на образе docker:29, где
Python отсутствует, и падал с «python: not found» (exit 127) — проверка не
выполнялась ни разу. Теперь питон берётся из самого проверяемого образа.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

# Пути, которых в приложении быть не должно.
FORBIDDEN_GLOBS = [
    '.env', '.env.*', 'secret.key', 'cookies.txt', '*.bundle', '*.p12',
    '*.pem', '*.key', 'id_rsa',
]

# Корни, которые осматриваем: приложение и данные. /etc/ssl/certs не трогаем —
# там CA-сертификаты Debian, они не наши и не секретны.
SCAN_ROOTS = ['/app', '/data', '/usr/local/lib/python3.12/site-packages/cybra']

# Личные данные и мусор репозитория.
PERSONAL = ['ap3x0kantor', 'evgenykantor', 'C:\\Users\\evgen', '192.168.1.']
JUNK = ['node_modules', '__pycache__', '.git', '.pytest_cache', '.venv']


def _walk_inside() -> list[Path]:
    """Файлы внутри образа по тем же правилам, что и снаружи."""
    found: list[Path] = []
    for root in SCAN_ROOTS:
        base = Path(root)
        if not base.exists():
            continue
        for path in base.rglob('*'):
            if path.is_file():
                found.append(path)
    return found


def _check_files_inside() -> list[str]:
    problems: list[str] = []
    for path in _walk_inside():
        name = path.name
        # CA-сертификаты Debian — штатное содержимое, не наши.
        if '/etc/ssl/' in str(path):
            continue
        for glob in FORBIDDEN_GLOBS:
            if path.match(glob):
                problems.append(f'секрет: {path}')
                break
    return problems


def _check_text_inside() -> list[str]:
    problems: list[str] = []
    for path in _walk_inside():
        if path.suffix not in {'.py', '.js', '.json', '.md', '.txt', '.yml', '.yaml', ''}:
            continue
        try:
            text = path.read_text(encoding='utf-8', errors='ignore')
        except OSError:
            continue
        for needle in PERSONAL:
            if needle in text:
                problems.append(f'личные данные «{needle}»: {path}')
    return problems


def _check_junk_inside() -> list[str]:
    problems: list[str] = []
    for root in SCAN_ROOTS:
        base = Path(root)
        if not base.exists():
            continue
        for part in base.rglob('*'):
            if part.name in JUNK:
                problems.append(f'мусор: {part}')
    return problems


def audit_inside() -> int:
    print('=== содержимое образа ===')
    problems = _check_files_inside()
    if problems:
        for p in problems[:20]:
            print(f'  FAIL {p}')
    else:
        print('  секреты: чисто')

    personal = _check_text_inside()
    if personal:
        for p in personal[:20]:
            print(f'  FAIL {p}')
        problems += personal
    else:
        print('  личные данные: чисто')

    junk = _check_junk_inside()
    if junk:
        for p in junk[:20]:
            print(f'  FAIL {p}')
        problems += junk
    else:
        print('  мусор репозитория: чисто')

    print(f'\nпроблем: {len(problems)}')
    return 0 if not problems else 1


def audit_outside(image: str) -> int:
    """Локальная проверка: вызываем этот же скрипт внутри образа."""
    script = Path(__file__).resolve()
    result = subprocess.run(
        ['docker', 'run', '--rm',
         '-v', f'{script.parent}:/audit:ro',
         '--entrypoint', 'python', image,
         '/audit/audit_image.py', '--self', image],
        capture_output=True, text=True, encoding='utf-8', errors='replace')
    print(result.stdout.strip())
    if result.stderr.strip():
        print(result.stderr.strip(), file=sys.stderr)
    return result.returncode


def main() -> int:
    args = sys.argv[1:]
    if args and args[0] == '--self':
        return audit_inside()
    image = args[0] if args else 'cybra/cybra:audit'
    return audit_outside(image)


if __name__ == '__main__':
    sys.exit(main())
