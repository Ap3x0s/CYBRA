#!/usr/bin/env python3
"""РЎРѕР±СЂР°С‚СЊ РѕС„Р»Р°Р№РЅ-bundle: РєРѕР»С‘СЃР°, git-РёСЃС…РѕРґРЅРёРєРё Рё npm-Р°СЂС…РёРІ.

Р—Р°С‡РµРј: РЅР° СЃРµСЂРІРµСЂР°С… Р·Р°РєР°Р·С‡РёРєР° РЅРµС‚ РёРЅС‚РµСЂРЅРµС‚Р°. Р’СЃС‘, С‡С‚Рѕ С‚СЏРЅРµС‚СЃСЏ РёР· СЃРµС‚Рё РїСЂРё
`cybra setup`, РЅР°РґРѕ РїСЂРёРІРµР·С‚Рё Р·Р°СЂР°РЅРµРµ РѕРґРЅРёРј РєР°С‚Р°Р»РѕРіРѕРј.

Р§С‚Рѕ СЃРѕР±РёСЂР°РµС‚СЃСЏ:

  offline-bundle/
  в”њв”Ђв”Ђ wheels/       РєРѕР»С‘СЃР° Python-РїР°РєРµС‚РѕРІ РїРѕРґ С†РµР»РµРІСѓСЋ РїР»Р°С‚С„РѕСЂРјСѓ
  в”њв”Ђв”Ђ sources/      РёСЃС…РѕРґРЅРёРєРё РёРЅСЃС‚СЂСѓРјРµРЅС‚РѕРІ, РєРѕС‚РѕСЂС‹Рµ СЃС‚Р°РІСЏС‚СЃСЏ СЃ git
  в”њв”Ђв”Ђ npm/          Р°СЂС…РёРІ promptfoo РґР»СЏ `npm ci --offline`
  в”њв”Ђв”Ђ MANIFEST.json РїРµСЂРµС‡РµРЅСЊ С„Р°Р№Р»РѕРІ СЃ SHA256 Рё РІРµСЂСЃРёСЏРјРё
  в””в”Ђв”Ђ README.txt    РєР°Рє СЌС‚РёРј РїРѕР»СЊР·РѕРІР°С‚СЊСЃСЏ РЅР° РјРµСЃС‚Рµ

РљР»СЋС‡РµРІС‹Рµ СЂРµС€РµРЅРёСЏ, РєРѕС‚РѕСЂС‹Рµ Р·РґРµСЃСЊ Р·Р°С€РёС‚С‹:

  * РљРѕР»С‘СЃР° РєР°С‡Р°СЋС‚СЃСЏ РїРѕРґ Р¦Р•Р›Р•Р’РЈР® РїР»Р°С‚С„РѕСЂРјСѓ, Р° РЅРµ РїРѕРґ С‚Сѓ, РіРґРµ Р·Р°РїСѓС‰РµРЅ СЃРєСЂРёРїС‚.
    Windows-wheel РЅР° Linux РЅРµ РІСЃС‚Р°РЅРµС‚. РџРѕСЌС‚РѕРјСѓ --platform Рё --python-version
    РѕР±СЏР·Р°С‚РµР»СЊРЅС‹, Р° РЅРµ В«РїРѕ СѓРјРѕР»С‡Р°РЅРёСЋ РєР°Рє Р»РѕРєР°Р»СЊРЅРѕВ».

  * torch Р±РµСЂС‘С‚СЃСЏ СЃ РёРЅРґРµРєСЃР° PyTorch (download.pytorch.org/whl/cpu), Р° РЅРµ СЃ
    PyPI: СЃР±РѕСЂРєРё СЃ СЃСѓС„С„РёРєСЃРѕРј +cpu С‚Р°Рј РЅРµ РїСѓР±Р»РёРєСѓСЋС‚СЃСЏ. Р‘РµР· --extra-index-url
    pip РёС… РїСЂРѕСЃС‚Рѕ РЅРµ РЅР°Р№РґС‘С‚.

  * РўРѕР»СЊРєРѕ Р±РёРЅР°СЂРЅС‹Рµ РєРѕР»С‘СЃР° (--only-binary=:all:). sdist РїСЂРёС€Р»РѕСЃСЊ Р±С‹
    РєРѕРјРїРёР»РёСЂРѕРІР°С‚СЊ РЅР° РјРµСЃС‚Рµ, Р° С‚Р°Рј РЅРµС‚ РЅРё РєРѕРјРїРёР»СЏС‚РѕСЂР°, РЅРё РёРЅС‚РµСЂРЅРµС‚Р° РґР»СЏ
    Р·Р°РіРѕР»РѕРІРєРѕРІ.

  * MANIFEST СЃ SHA256 РїРѕ РєР°Р¶РґРѕРјСѓ С„Р°Р№Р»Сѓ: РЅР° РїСЂРёС‘РјРєРµ РІРёРґРЅРѕ, С‡С‚Рѕ РїСЂРёРІРµР·Р»Рё
    РёРјРµРЅРЅРѕ С‚Рѕ, Рё РїРѕРґРјРµРЅРёС‚СЊ С„Р°Р№Р» РїРѕ РґРѕСЂРѕРіРµ РЅРµР·Р°РјРµС‚РЅРѕ РЅРµ РІС‹Р№РґРµС‚.

РСЃРїРѕР»СЊР·РѕРІР°РЅРёРµ:

    python scripts/build_offline_bundle.py --platform linux
    python scripts/build_offline_bundle.py --platform windows --tools garak

РџСЂРѕРІРµСЂРєР° РїРµСЂРµРґ РѕС‚РїСЂР°РІРєРѕР№ Р·Р°РєР°Р·С‡РёРєСѓ вЂ” РЅР° Р§РРЎРўРћР™ РјР°С€РёРЅРµ Р±РµР· СЃРµС‚Рё:
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

# РџР»Р°С‚С„РѕСЂРјР° -> РЅР°Р±РѕСЂ pip-С‚РµРіРѕРІ Рё abi РґР»СЏ СЃРєР°С‡РёРІР°РЅРёСЏ.
#
# РћРґРёРЅ С‚РµРі РЅРµ СЂР°Р±РѕС‚Р°РµС‚. РџР°РєРµС‚С‹ РїСѓР±Р»РёРєСѓСЋС‚СЃСЏ РІ СЂР°Р·РЅС‹С… С„РѕСЂРјР°С… РёРјС‘РЅ, Рё РѕРЅРё
# РЅРµСЃРѕРІРјРµСЃС‚РёРјС‹ РјРµР¶РґСѓ СЃРѕР±РѕР№ РѕРґРЅРёРј Р·РЅР°С‡РµРЅРёРµРј --platform:
#
#   numpy 2.5.3   -> manylinux_2_27_x86_64.manylinux_2_28_x86_64, cp312
#   hf-xet 1.6.0  -> manylinux2014_x86_64.manylinux_2_17_x86_64, cp38-abi3
#
# РЎ РѕРґРЅРёРј manylinux_2_28 pip РЅРµ РЅР°С…РѕРґРёС‚ hf-xet (В«No matching distributionВ»),
# СЃ РѕРґРЅРёРј manylinux2014 вЂ” numpy. pip РїСЂРёРЅРёРјР°РµС‚ --platform Рё --abi РЅРµСЃРєРѕР»СЊРєРѕ
# СЂР°Р· Рё РѕР±СЉРµРґРёРЅСЏРµС‚ РёС… РІ РѕРґРёРЅ РЅР°Р±РѕСЂ, РїРѕСЌС‚РѕРјСѓ РїРµСЂРµРґР°С‘Рј РѕР±Р° С‚РµРіР° Рё РІСЃРµ abi:
# cp312 РґР»СЏ РѕР±С‹С‡РЅС‹С… РєРѕР»С‘СЃ, abi3/none РґР»СЏ СѓРЅРёРІРµСЂСЃР°Р»СЊРЅС‹С….
#
# РС‚РѕРіРѕРІРѕРµ С‚СЂРµР±РѕРІР°РЅРёРµ Рє СЃРёСЃС‚РµРјРµ: glibc >= 2.28 (Debian 10+, Ubuntu 20.04+,
# RHEL 8+); manylinux2014-РєРѕР»С‘СЃР° РІ СЌС‚РѕС‚ РЅР°Р±РѕСЂ С‚РѕР¶Рµ РІС…РѕРґСЏС‚. РџСЂРѕРІРµСЂРєР° РЅР°
# РјРµСЃС‚Рµ: `ldd --version`.
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

# РљР°РєРёРµ lock-С„Р°Р№Р»С‹ Р±СЂР°С‚СЊ РїРѕРґ РєР°РєСѓСЋ РїР»Р°С‚С„РѕСЂРјСѓ.
def lock_for(tool: str, platform: str) -> Path:
    name = f'{tool}-win.txt' if platform == 'windows' and (ROOT / 'locks' / f'{tool}-win.txt').exists() else f'{tool}.txt'
    return ROOT / 'locks' / name


def run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
    print('$', ' '.join(cmd[:6]), '...' if len(cmd) > 6 else '')
    return subprocess.run(cmd, check=True, **kwargs)


def download_wheels(lock: Path, out_dir: Path, platform: str, pyver: str) -> list[str]:
    """РЎРєР°С‡Р°С‚СЊ РєРѕР»С‘СЃР° РїРѕ lock-С„Р°Р№Р»Сѓ РїРѕРґ СѓРєР°Р·Р°РЅРЅСѓСЋ РїР»Р°С‚С„РѕСЂРјСѓ."""
    config = PLATFORMS[platform]
    out_dir.mkdir(parents=True, exist_ok=True)

    # git-СЃСЃС‹Р»РєРё pip download РЅРµ РїРѕРЅРёРјР°РµС‚ вЂ” РёС… РѕР±СЂР°Р±Р°С‚С‹РІР°РµРј РѕС‚РґРµР»СЊРЅРѕ.
    pinned = []
    git_sources = []
    for line in lock.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        if 'git+' in line:
            git_sources.append(line)
        else:
            pinned.append(line)

    tmp_lock = out_dir.parent / f'.lock-{lock.stem}-{platform}.txt'
    tmp_lock.write_text('\n'.join(pinned) + '\n', encoding='utf-8')

    # pip, Р° РЅРµ uv: Сѓ uv РЅРµС‚ РєРѕРјР°РЅРґС‹ download.
    cmd = [
        sys.executable, '-m', 'pip', 'download',
        '--only-binary=:all:',
        '--python-version', pyver,
        '--implementation', 'cp',
        '--dest', str(out_dir),
        '--extra-index-url', PYTORCH_CPU,
        '--requirement', str(tmp_lock),
    ]
    for tag in config['platforms']:
        cmd += ['--platform', tag]
    for abi in config['abis']:
        cmd += ['--abi', abi]

    try:
        run(cmd)
    except subprocess.CalledProcessError as error:
        print(f'  Р·Р°РіСЂСѓР·РєР° РЅРµ СѓРґР°Р»Р°СЃСЊ: {error}', file=sys.stderr)
        return git_sources
    finally:
        tmp_lock.unlink(missing_ok=True)

    return git_sources


def clone_git_sources(entries: list[str], out_dir: Path) -> list[dict]:
    """РЎРєР°С‡Р°С‚СЊ РёСЃС…РѕРґРЅРёРєРё РёРЅСЃС‚СЂСѓРјРµРЅС‚РѕРІ, РєРѕС‚РѕСЂС‹Рµ СЃС‚Р°РІСЏС‚СЃСЏ СЃ git.

    РЎС‚СЂРѕРєР° РІРёРґР°: garak @ git+https://github.com/NVIDIA/garak.git@<sha>
    РљР»РѕРЅРёСЂСѓРµРј РїРѕ СЂРµРІРёР·РёРё Рё СѓРїР°РєРѕРІС‹РІР°РµРј РІ tar вЂ” pip СѓРјРµРµС‚ СЃС‚Р°РІРёС‚СЊ РёР· Р°СЂС…РёРІР°
    Р±РµР· РѕР±СЂР°С‰РµРЅРёСЏ Рє СЃРµС‚Рё.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    saved = []
    for entry in entries:
        # Р Р°Р·Р±РёСЂР°РµРј В«РёРјСЏ @ git+URL@СЂРµРІРёР·РёСЏВ»
        if ' @ git+' not in entry:
            continue
        name, rest = entry.split(' @ git+', 1)
        name = name.strip()
        if '@' not in rest:
            print(f'  {name}: РЅРµС‚ СЂРµРІРёР·РёРё, РїСЂРѕРїСѓСЃРєР°СЋ')
            continue
        url, revision = rest.rsplit('@', 1)
        target = out_dir / f'{name}-{revision[:12]}.tar.gz'

        work = out_dir.parent / f'.clone-{name}'
        try:
            run(['git', 'clone', '--quiet', url, str(work)])
            run(['git', '-C', str(work), 'checkout', '--quiet', revision])
            run(['git', '-C', str(work), 'archive', '--format=tar.gz',
                 f'--output={target}', revision])
            saved.append({'name': name, 'revision': revision,
                          'file': target.name, 'url': url})
            print(f'  {name}: {target.name}')
        except subprocess.CalledProcessError as error:
            print(f'  {name}: РѕС€РёР±РєР° {error}', file=sys.stderr)
        finally:
            shutil.rmtree(work, ignore_errors=True)
    return saved


def pack_npm(out_dir: Path) -> dict | None:
    """РЈРїР°РєРѕРІР°С‚СЊ promptfoo РґР»СЏ РѕС„Р»Р°Р№РЅ-СѓСЃС‚Р°РЅРѕРІРєРё npm."""
    out_dir.mkdir(parents=True, exist_ok=True)
    package = ROOT / 'package.json'
    if not package.exists():
        return None
    try:
        run(['npm', 'pack', '--pack-destination', str(out_dir)], cwd=ROOT)
    except (subprocess.CalledProcessError, FileNotFoundError) as error:
        print(f'  npm pack РЅРµ СѓРґР°Р»СЃСЏ: {error}', file=sys.stderr)
        return None
    tarballs = sorted(out_dir.glob('*.tgz'))
    return {'file': tarballs[-1].name} if tarballs else None


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
    print(f'С„Р°Р№Р»РѕРІ РІ bundle: {len(files)}')
    print(f'РѕР±С‰РёР№ РІРµСЃ: {manifest["total_size"] / 1_048_576:.1f} РњР‘')


def write_readme(bundle: Path, platform: str) -> None:
    (bundle / 'README.txt').write_text(
        f"""РћС„Р»Р°Р№РЅ-bundle CYBRA ({platform})

РЈСЃС‚Р°РЅРѕРІРєР° РЅР° РјР°С€РёРЅРµ Р±РµР· РёРЅС‚РµСЂРЅРµС‚Р°:

  export CYBRA_OFFLINE_DIR=/РїСѓС‚СЊ/Рє/offline-bundle
  cybra setup --tools garak pyrit agentdojo promptfoo

РџСЂРѕРІРµСЂРєР° С†РµР»РѕСЃС‚РЅРѕСЃС‚Рё РїРµСЂРµРґ СѓСЃС‚Р°РЅРѕРІРєРѕР№:

  cd offline-bundle
  sha256sum -c SHA256SUMS   # РёР»Рё СЃРІРµСЂСЊС‚Рµ СЃ MANIFEST.json

Р§С‚Рѕ РІРЅСѓС‚СЂРё:
  wheels/   РєРѕР»С‘СЃР° Python РїРѕРґ {platform}
  sources/  РёСЃС…РѕРґРЅРёРєРё РёРЅСЃС‚СЂСѓРјРµРЅС‚РѕРІ РёР· git (РЅР° СЃР»СѓС‡Р°Р№, РµСЃР»Рё pip РЅРµ РІРѕР·СЊРјС‘С‚)
  npm/      Р°СЂС…РёРІ promptfoo

Р•СЃР»Рё СѓСЃС‚Р°РЅРѕРІРєР° РЅРµ РёРґС‘С‚, РїСЂРѕРІРµСЂСЊС‚Рµ:
  1. РџР»Р°С‚С„РѕСЂРјР° РєРѕР»С‘СЃ СЃРѕРІРїР°РґР°РµС‚ СЃ РјР°С€РёРЅРѕР№ ({platform})
  2. Р’РµСЂСЃРёСЏ Python вЂ” cp312
  3. РќРё РѕРґРЅРѕРіРѕ РѕР±СЂР°С‰РµРЅРёСЏ РІ РёРЅС‚РµСЂРЅРµС‚ РЅРµС‚: СѓСЃС‚Р°РЅРѕРІРєР° РёРґС‘С‚ СЃ --no-index
""", encoding='utf-8')

    # SHA256SUMS РІ С„РѕСЂРјР°С‚Рµ, РєРѕС‚РѕСЂС‹Р№ РїРѕРЅРёРјР°РµС‚ `sha256sum -c`.
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
    print(f'РєР°С‚Р°Р»РѕРі:   {bundle}')
    print(f'РёРЅСЃС‚СЂСѓРјРµРЅС‚С‹: {", ".join(args.tools)}')
    print()

    all_sources: list[dict] = []
    npm_info = None
    for tool in args.tools:
        if tool == 'promptfoo':
            print('--- promptfoo (npm) ---')
            npm_info = pack_npm(bundle / 'npm')
            continue

        lock = lock_for(tool, args.platform)
        if not lock.exists():
            print(f'--- {tool}: lock РЅРµ РЅР°Р№РґРµРЅ ({lock.name}), РїСЂРѕРїСѓСЃРєР°СЋ ---')
            continue

        print(f'--- {tool} ({lock.name}) ---')
        git_entries = download_wheels(lock, bundle / 'wheels', args.platform, pyver)
        if git_entries:
            all_sources.extend(clone_git_sources(git_entries, bundle / 'sources'))

    write_manifest(bundle, args.platform, args.tools, all_sources, npm_info)
    write_readme(bundle, args.platform)
    print()
    print(f'РіРѕС‚РѕРІРѕ: {bundle}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
