#!/usr/bin/env python3
"""Build a source/data distribution; exclude environments, logs, keys and test runs."""
from pathlib import Path
import hashlib
import zipfile
ROOT=Path(__file__).resolve().parent
DIRS=('security_suite','datasets','vendor','licenses','locks','docs','examples','tests')
FILES=('README.md','NOTICE.md','run.py','generate_datasets.py','build_zip.py','package.json','package-lock.json','sources.lock.json','.gitignore','.env.example')
paths=[ROOT/name for name in FILES]
for name in DIRS:
    paths.extend(p for p in (ROOT/name).rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc')
paths=sorted(paths)
checksums=ROOT/'CHECKSUMS.sha256'
checksums.write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.relative_to(ROOT).as_posix()+'\n' for p in paths),encoding='utf-8')
paths.append(checksums)
archive=ROOT.parent/'llm-security-suite.zip'
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
    for p in paths:z.write(p,Path(ROOT.name)/p.relative_to(ROOT))
with zipfile.ZipFile(archive) as z:
    assert z.testzip() is None
    for p in paths:
        assert z.read(str(Path(ROOT.name)/p.relative_to(ROOT)))==p.read_bytes()
print(f'{archive}\n{len(paths)} files; {archive.stat().st_size} bytes')
