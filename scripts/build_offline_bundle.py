#!/usr/bin/env python3
"""Собрать офлайн-bundle: колёса, git-исходники и npm-архив.

Зачем: на серверах заказчика нет интернета. Всё, что тянется из сети при
`cybra setup`, надо привезти заранее одним каталогом.

Что собирается:

  offline-bundle/
  ├── wheels/       колёса Python-пакетов под целевую платформу
  ├── sources/      исходники инструментов, которые ставятся с git
  ├── npm/          архив promptfoo для `npm ci --offline`
  ├── MANIFEST.json перечень файлов с SHA256 и версиями
  └── README.txt    короткая памятка, которую отдают вместе с bundle

Решения, найденные на практике:

  * Колёса качаются под ЦЕЛЕВУЮ платформу, а не под ту, где запущен скрипт.
    Windows-колесо на Linux не встанет.

  * Нужно НЕСКОЛЬКО тегов платформы сразу. Одного не хватает: numpy
    публикуется только как manylinux_2_28, а hf-xet — только как
    manylinux2014.manylinux_2_17. С одним тегом pip не находит один из них.

  * Пакеты качаются поодиночке, а не одним `pip download -r`. Один
    недоступный пакет прерывает весь вызов — на практике ecoji без колёс
    не давал скачать остальные 173, и ошибка была тихой.

  * torch берётся с индекса PyTorch, а не с PyPI: сборки с суффиксом +cpu
    там не публикуются.

  * Пакеты только с sdist (чистый Python) собираются локально: в bundle им
    тоже нужно колесо, иначе установка у заказчика упадёт.

Использование:

    python scripts/build_offline_bundle.py --platform linux
    python scripts/build_offline_bundle.py --platform windows --tools garak

Проверка перед отправкой заказчику — на ЧИСТОЙ машине без сети:
    CYBRA_OFFLINE_DIR=./offline-bundle cybra setup --tools garak
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYTORCH_CPU = 'https://download.pytorch.org/whl/cpu'

# Build-backend'ы. В lock-файлах их нет: это не зависимости проекта, а
# инструменты сборки, которые pip подтягивает сам при установке из sdist.
# На машине без интернета он их не найдёт, и установка git-инструментов
# упадёт с «Could not find a version that satisfies the requirement
# flit_core». Проверено: именно так и произошло с garak.
#
# Список — типовые backend'ы популярных проектов. Лишние колёса весят
# килобайты, их отсутствие стоит сорванной установки.
# Пакеты, которые нужны ТОЛЬКО на Windows и поэтому отсутствуют в lock,
# снятом на Linux. pip при установке видит маркер sys_platform == "win32"
# в зависимостях пакета и требует их, а в bundle их нет — установка падает
# с «Could not find a version that satisfies the requirement pyreadline3».
#
# Список пополняется по мере выявления: гарантировать полноту нельзя, lock
# для Windows и lock для Linux — разные наборы.
WINDOWS_ONLY = [
    'pyreadline3',       # cmd2: интерактивный ввод в консоли
    'pywin32',           # доступ к Win32 API
    'colorama',          # ANSI-цвета в терминале
    'tzdata',            # pandas: часовые пояса без системной базы
    'python-magic-bin',  # garak: определение типа файла
]

BUILD_BACKENDS = [
    'flit_core>=3.11,<4',
    'setuptools>=68',
    'wheel',
    'hatchling',
    'poetry-core',
    'pdm-backend',
]

# Платформа -> набор pip-тегов и abi для скачивания.
#
# Один тег не работает. Пакеты публикуются в разных формах имён, и они
# несовместимы между собой одним значением --platform:
#
#   numpy 2.5.3   -> manylinux_2_27_x86_64.manylinux_2_28_x86_64, cp312
#   hf-xet 1.6.0  -> manylinux2014_x86_64.manylinux_2_17_x86_64, cp38-abi3
#
# С одним manylinux_2_28 pip не находит hf-xet, с одним manylinux2014 —
# numpy. pip принимает --platform и --abi несколько раз и объединяет их в
# один набор, поэтому передаём оба тега и три abi: cp312 для обычных колёс,
# abi3 и none для универсальных.
#
# Требование к системе: glibc >= 2.28 (Debian 10+, Ubuntu 20.04+, RHEL 8+),
# Python 3.12. Проверка: ldd --version и python --version.
PLATFORMS = {
    'linux': {
        'platforms': ['manylinux_2_28_x86_64', 'manylinux2014_x86_64'],
        'abis': ['cp312', 'abi3', 'none'],
        'python': '312',
    },
    'windows': {
        'platforms': ['win_amd64'],
        'abis': ['cp312', 'abi3', 'none'],
        'python': '312',
    },
}

def lock_for(tool: str, platform: str) -> Path:
    name = f'{tool}-win.txt' if platform == 'windows' and (ROOT / 'locks' / f'{tool}-win.txt').exists() else f'{tool}.txt'
    return ROOT / 'locks' / name


def run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
    print('$', ' '.join(cmd[:6]), '...' if len(cmd) > 6 else '')
    return subprocess.run(cmd, check=True, **kwargs)


def download_wheels(lock: Path, out_dir: Path, platform: str, pyver: str) -> list[str]:
    """Скачать колёса по lock-файлу, обрабатывая пакеты поодиночке.

    Почему не одним `pip download -r`: при недоступности хотя бы одного
    пакета pip прерывает ВЕСЬ вызов. На практике один пакет без колёс
    (ecoji) не давал скачать остальные 173, а сборка при этом завершалась
    «успешно» — в bundle лежало 6 файлов вместо 174. Ошибка была тихой,
    потому что код ловил CalledProcessError и шёл дальше.

    Возвращает список git-ссылок: их pip не понимает, обрабатываем отдельно.
    """
    config = PLATFORMS[platform]
    out_dir.mkdir(parents=True, exist_ok=True)

    pinned: list[str] = []
    git_sources: list[str] = []
    for line in lock.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        if 'git+' in line:
            git_sources.append(line)
        else:
            pinned.append(line)

    failed: list[str] = []
    for spec in pinned:
        cmd = [
            sys.executable, '-m', 'pip', 'download',
            '--only-binary=:all:',
            '--python-version', pyver,
            '--implementation', 'cp',
            '--dest', str(out_dir),
            '--extra-index-url', PYTORCH_CPU,
            '--no-deps',
            spec,
        ]
        for tag in config['platforms']:
            cmd += ['--platform', tag]
        for abi in config['abis']:
            cmd += ['--abi', abi]

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            failed.append(spec)

    if failed:
        print(f'  без готового колеса: {len(failed)} из {len(pinned)}')
        build_missing_wheels(failed, out_dir, pyver)

    return git_sources


def wheels_only(packages: list[str], pyver: str) -> list[str]:
    """Вернуть пакеты, для которых нет бинарного колеса."""
    probe = Path('.wheel-probe')
    probe.mkdir(exist_ok=True)
    missing = []
    for spec in packages:
        result = subprocess.run(
            [sys.executable, '-m', 'pip', 'download', '--only-binary=:all:',
             '--no-deps', '--python-version', pyver, '--implementation', 'cp',
             '--dest', str(probe), spec],
            capture_output=True, text=True)
        if result.returncode != 0:
            missing.append(spec)
    return missing


def build_missing_wheels(packages: list[str], out_dir: Path, pyver: str) -> None:
    """Собрать колёса для пакетов, у которых нет готового колеса.

    Два разных случая, и путать их дорого:

    * Пакет с индексом версии (+cpu, +cu118) лежит не на PyPI, а на отдельном
      индексе. Его НЕ надо собирать: torch из исходников — это часы и
      десятки гигабайт. Его надо скачать с правильного индекса, и это уже
      сделано выше (--extra-index-url PYTORCH_CPU), а сюда он попал только
      потому, что --platform не совпал с именем файла на том индексе.

    * Пакет только с sdist (обычно чистый Python). Вот такие собираем: это
      секунды, и без них установка у заказчика упадёт.
    """
    buildable = []
    for spec in packages:
        name = spec.split('==')[0].strip()
        if name in ('torch', 'torchvision', 'torchaudio'):
            print(f'  {spec}: колёса только на индексе PyTorch, сборка из '
                  f'исходников не делается — см. --extra-index-url', file=sys.stderr)
            continue
        buildable.append(spec)

    missing = wheels_only(buildable, pyver)
    for spec in missing:
        print(f'  сборка из исходников: {spec}')
        result = subprocess.run(
            [sys.executable, '-m', 'pip', 'wheel', '--no-deps',
             '--wheel-dir', str(out_dir), spec],
            capture_output=True, text=True)
        if result.returncode != 0:
            print(f'    НЕ УДАЛОСЬ: {spec}', file=sys.stderr)
            for line in result.stderr.splitlines():
                if 'error' in line.lower():
                    print(f'      {line.strip()[:120]}', file=sys.stderr)
        else:
            print(f'    собрано: {spec}')
    for path in Path('.wheel-probe').glob('*'):
        path.unlink()
    Path('.wheel-probe').rmdir()


def download_platform_extras(out_dir: Path, pyver: str, platform: str) -> None:
    """Скачать пакеты, которые есть только на целевой платформе.

    Для Windows это pyreadline3 и подобные: lock снят на Linux, и таких
    зависимостей в нём нет вовсе. Без них установка garak на Windows
    падает на этапе разрешения зависимостей.
    """
    if platform != 'windows':
        return
    out_dir.mkdir(parents=True, exist_ok=True)
    config = PLATFORMS['windows']
    for spec in WINDOWS_ONLY:
        cmd = [sys.executable, '-m', 'pip', 'download', '--only-binary=:all:',
               '--python-version', pyver, '--implementation', 'cp',
               '--dest', str(out_dir), '--no-deps', spec]
        for tag in config['platforms']:
            cmd += ['--platform', tag]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f'  платформенный пакет {spec}: не скачался', file=sys.stderr)


def download_build_backends(out_dir: Path, pyver: str) -> None:
    """Скачать build-backend'ы, без которых не собрать git-инструменты.

    Каждый качается отдельно: один недоступный пакет не должен срывать
    остальные — та же ловушка, что была с основными зависимостями.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    for spec in BUILD_BACKENDS:
        result = subprocess.run(
            [sys.executable, '-m', 'pip', 'download', '--only-binary=:all:',
             '--python-version', pyver, '--implementation', 'cp',
             '--dest', str(out_dir), '--no-deps', spec],
            capture_output=True, text=True)
        if result.returncode != 0:
            print(f'  build-backend {spec}: не скачался', file=sys.stderr)


def clone_git_sources(entries: list[str], out_dir: Path) -> list[dict]:
    """Скачать исходники инструментов, которые ставятся с git.

    Строка вида: garak @ git+https://github.com/NVIDIA/garak.git@<sha>

    Клонируем по ревизии и упаковываем в tar: pip умеет ставить из архива
    без обращения к сети, если указать путь к файлу.

    Разбор: отрезаем префикс «git+», затем делим по последнему @ — ревизия
    всегда в конце. rsplit на всей строке не работает, если в URL есть @
    (токен или user@host): тогда ревизией окажется кусок токена.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    saved = []
    for entry in entries:
        if ' @ git+' not in entry:
            continue
        name, rest = entry.split(' @ git+', 1)
        name = name.strip()

        if '@' not in rest:
            # URL без ревизии: клонируем ветку по умолчанию и фиксируем
            # фактический коммит, чтобы bundle был воспроизводим.
            url, revision = rest, ''
        else:
            url, revision = rest.rsplit('@', 1)

        work = out_dir.parent / f'.clone-{name}'
        try:
            run(['git', 'clone', '--quiet', url, str(work)])
            if revision:
                run(['git', '-C', str(work), 'checkout', '--quiet', revision])
            else:
                revision = subprocess.check_output(
                    ['git', '-C', str(work), 'rev-parse', 'HEAD'],
                    text=True).strip()

            target = out_dir / f'{name}-{revision[:12]}.tar.gz'
            run(['git', '-C', str(work), 'archive', '--format=tar.gz',
                 f'--output={target}', revision])
            saved.append({'name': name, 'revision': revision,
                          'file': target.name, 'url': url})
            print(f'  {name}: {target.name}')
        except subprocess.CalledProcessError as error:
            print(f'  {name}: не удалось получить исходники ({error})',
                  file=sys.stderr)
        finally:
            shutil.rmtree(work, ignore_errors=True)
    return saved


def pack_npm(out_dir: Path) -> dict | None:
    """Собрать npm-кеш для офлайн-установки promptfoo.

    Почему не `npm pack`: в корне репозитория он упаковывает ВСЁ содержимое,
    включая сам offline-bundle. На практике это дало 552 файла на 682 МБ и
    рекурсию — bundle внутри bundle. При этом установщику нужен не архив
    репозитория, а кеш пакетов.

    Поэтому: ставим зависимости во временный каталог с --cache, направленным
    в bundle. npm складывает туда все скачанные tarball'ы и метаданные.
    На месте `npm ci --offline --cache=<bundle>/npm` берёт их оттуда.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    package = ROOT / 'package.json'
    if not package.exists():
        return None

    work = out_dir.parent / '.npm-build'
    shutil.rmtree(work, ignore_errors=True)
    work.mkdir(parents=True)
    shutil.copyfile(package, work / 'package.json')
    lock = ROOT / 'package-lock.json'
    if lock.exists():
        shutil.copyfile(lock, work / 'package-lock.json')

    # На Windows npm — это npm.cmd, а не npm.exe. Прямой вызов из
    # subprocess его не находит: [WinError 2] «не удаётся найти файл».
    # which() возвращает полный путь к .cmd, и вызов работает.
    npm = shutil.which('npm')
    if not npm:
        print('  npm не найден в PATH — promptfoo не попадёт в bundle',
              file=sys.stderr)
        return None

    try:
        run([npm, 'install', '--no-audit', '--no-fund',
             '--cache', str(out_dir)], cwd=work)
    except (subprocess.CalledProcessError, FileNotFoundError) as error:
        print(f'  npm install не удался: {error}', file=sys.stderr)
        return None
    finally:
        shutil.rmtree(work, ignore_errors=True)

    # Проверяем, что кеш наполнился. npm кладёт его в _cacache внутри
    # указанного каталога; искать *.tgz в корне бессмысленно — их там нет.
    cacache = out_dir / '_cacache'
    if not cacache.exists():
        print('  npm-кеш не создан — офлайн-установка promptfoo не сработает',
              file=sys.stderr)
        return None

    size = sum(p.stat().st_size for p in out_dir.rglob('*') if p.is_file())
    if size < 1_048_576:
        print(f'  npm-кеш подозрительно мал: {size} байт', file=sys.stderr)
        return None
    print(f'  npm-кеш: {size / 1_048_576:.1f} МБ')
    return {'cache_size': size}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b''):
            digest.update(chunk)
    return digest.hexdigest()


def write_manifest(bundle: Path, platform: str, tools: list[str],
                   sources: list[dict], npm: dict | None) -> None:
    files = []
    for path in sorted(bundle.rglob('*')):
        if path.is_file() and path.name != 'MANIFEST.json':
            files.append({
                'path': path.relative_to(bundle).as_posix(),
                'size': path.stat().st_size,
                'sha256': sha256(path),
            })
    manifest = {
        'platform': platform,
        'python': PLATFORMS[platform]['python'],
        'tools': tools,
        'sources': sources,
        'npm': npm,
        'files': files,
        'total_size': sum(item['size'] for item in files),
    }
    (bundle / 'MANIFEST.json').write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')

    print()
    print(f'файлов в bundle: {len(files)}')
    print(f'общий вес: {manifest["total_size"] / 1_048_576:.1f} МБ')


def write_readme(bundle: Path, platform: str) -> None:
    """Инструкция, которую отдают вместе с bundle.

    Пишется на русском: получатель — администратор заказчика, а документация
    проекта двуязычна. Формулировки короткие: это памятка на одну страницу,
    а не замена docs/OFFLINE.md.
    """
    text = (
        f"Офлайн-bundle CYBRA ({platform})\n"
        "\n"
        "Установка на машине без интернета:\n"
        "\n"
        "  export CYBRA_OFFLINE_DIR=/путь/к/offline-bundle\n"
        "  cybra setup --tools garak pyrit agentdojo promptfoo\n"
        "\n"
        "Проверка целостности перед установкой:\n"
        "\n"
        "  cd offline-bundle\n"
        "  sha256sum -c SHA256SUMS\n"
        "\n"
        "Что внутри:\n"
        "  wheels/   колёса Python под платформу " + platform + "\n"
        "  sources/  исходники инструментов из git\n"
        "  npm/      архив promptfoo\n"
        "\n"
        "Если установка не идёт, проверьте три вещи:\n"
        "  1. Платформа колёс совпадает с машиной: " + platform + "\n"
        "  2. Версия Python — 3.12 (колёса собраны под cp312)\n"
        "  3. glibc >= 2.28 на Linux: ldd --version\n"
        "\n"
        "Подробнее: docs/OFFLINE.md в репозитории проекта.\n"
    )
    (bundle / 'README.txt').write_text(text, encoding='utf-8')

    # SHA256SUMS в формате, который понимает `sha256sum -c`.
    lines = []
    for path in sorted(bundle.rglob('*')):
        if path.is_file() and path.name not in ('MANIFEST.json', 'SHA256SUMS'):
            lines.append(f'{sha256(path)}  {path.relative_to(bundle).as_posix()}')
    (bundle / 'SHA256SUMS').write_text('\n'.join(lines) + '\n', encoding='utf-8')


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--platform', choices=sorted(PLATFORMS), required=True)
    parser.add_argument('--tools', nargs='+', default=['garak', 'pyrit', 'agentdojo', 'bipia', 'promptfoo'])
    parser.add_argument('--out', type=Path, default=ROOT / 'offline-bundle')
    parser.add_argument('--python-version', default=None)
    args = parser.parse_args()

    default_py = PLATFORMS[args.platform]['python']
    pyver = args.python_version or default_py
    bundle = args.out.resolve()
    bundle.mkdir(parents=True, exist_ok=True)

    print(f'платформа: {args.platform}, python cp{pyver}')
    print(f'каталог:   {bundle}')
    print(f'инструменты: {", ".join(args.tools)}')
    print()

    all_sources: list[dict] = []
    npm_info = None

    # Build-backend'ы качаем всегда: они нужны, если в наборе есть хоть один
    # инструмент из git (garak, pyrit, agentdojo). Без них установка из
    # архива падает на этапе сборки — проверено на garak.
    print('--- build-backends ---')
    download_build_backends(bundle / 'wheels', pyver)

    # Windows-only пакеты: lock снят на Linux, и их там нет.
    download_platform_extras(bundle / 'wheels', pyver, args.platform)

    for tool in args.tools:
        if tool == 'promptfoo':
            print('--- promptfoo (npm) ---')
            npm_info = pack_npm(bundle / 'npm')
            continue

        lock = lock_for(tool, args.platform)
        if not lock.exists():
            print(f'--- {tool}: lock не найден ({lock.name}), пропускаю ---')
            continue

        print(f'--- {tool} ({lock.name}) ---')
        git_entries = download_wheels(lock, bundle / 'wheels', args.platform, pyver)
        if git_entries:
            all_sources.extend(clone_git_sources(git_entries, bundle / 'sources'))

    write_manifest(bundle, args.platform, args.tools, all_sources, npm_info)
    write_readme(bundle, args.platform)
    print()
    print(f'готово: {bundle}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
