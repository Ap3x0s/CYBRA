"""SHA256SUMS для артефактов релиза.

Этап 13 схемы DevSecOps: подписание артефактов. Полноценный cosign keyless
требует OIDC-провайдера, которого у проекта нет, но контрольные суммы —
работающая часть того же этапа: по ним получатель проверяет, что скачанный
образ и SBOM не подменены по дороге.

Что кладём в сумму: SBOM, digest образа, сам файл sums и перечень лицензий
зависимостей (этап 9 схемы — «проверка лицензий»).
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b''):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    out_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / 'security-reports'
    out_dir.mkdir(parents=True, exist_ok=True)

    targets = [p for p in sorted(out_dir.rglob('*'))
               if p.is_file() and p.name not in ('SHA256SUMS', 'SHA256SUMS.minisig')]

    if not targets:
        print(f'нет артефактов в {out_dir} — суммы не создаются')
        return 0

    lines = [f'{sha256(p)}  {p.relative_to(out_dir).as_posix()}' for p in targets]
    sums = out_dir / 'SHA256SUMS'
    # Перевод строки LF: файл читают на Linux-машинах.
    sums.write_text('\n'.join(lines) + '\n', encoding='utf-8', newline='\n')

    print(f'SHA256SUMS: {len(lines)} файлов в {out_dir}')
    for line in lines:
        print(f'  {line[:110]}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
