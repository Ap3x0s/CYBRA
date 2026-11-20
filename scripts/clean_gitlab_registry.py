"""Удалить из registry GitLab теги, собранные старым способом.

В registry GitLab накопилось 26 тегов: :<sha> от каждой сборки, начиная с
18 ноября, плюс версионные v0.2.0…v0.2.3. Теги от старых прогонов (docker
build) текущим конвейером не воспроизводятся и только занимают место.

Оставляем: latest, версионные v0.2.3 (единственный полностью прошедший
релиз), и :<sha> пяти последних kaniko-сборок.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('cg', ROOT / 'scripts' / 'check_gitlab_jobs.py')
cg = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cg)

KEEP = {
    'latest',
    'v0.2.3',
    'e57529d6039fd2', 'df2befa5b09ebf', 'f16d26e2e79910',
    '03dcf2c3ff560c', 'de0ccf236764c0',
}


def main() -> int:
    apply = '--apply' in sys.argv

    repos = cg.api('/registry/repositories')
    repo = next((r for r in repos if r['path'] == 'ap3x0/cybra'), None)
    if repo is None:
        print('репозиторий ap3x0/cybra не найден в registry')
        return 1

    tags = cg.api(f"/registry/repositories/{repo['id']}/tags?per_page=100")
    doomed = [t for t in tags if not any(t['name'].startswith(k) for k in KEEP)]

    print(f"всего тегов: {len(tags)}; оставить: {len(tags) - len(doomed)}, удалить: {len(doomed)}")
    print()
    print('остаются:')
    for t in tags:
        if t not in doomed:
            print(f"  + {t['name'][:16]}")
    print()
    print('удаляются:')
    for t in doomed:
        print(f"  - {t['name'][:16]}")

    if not apply:
        print()
        print('это план. для удаления: --apply')
        return 0

    print()
    removed = failed = 0
    for t in doomed:
        try:
            cg.api(f"/registry/repositories/{repo['id']}/tags/{t['name']}", method='DELETE')
            print(f"  {t['name'][:16]}: удалён")
            removed += 1
        except SystemExit as error:
            print(f"  {t['name'][:16]}: {error}")
            failed += 1
    print()
    print(f'удалено: {removed}, ошибок: {failed}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
