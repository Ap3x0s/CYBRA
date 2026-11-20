"""Статусы job'ов конкретного пайплайна по id."""
from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('cg', ROOT / 'scripts' / 'check_gitlab_jobs.py')
cg = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cg)

pipeline_id = sys.argv[1]
info = cg.api(f'/pipelines/{pipeline_id}')
print(f"пайплайн {pipeline_id}: {info['status']} ({info['ref']}, {info['sha'][:7]})")
print()

jobs = cg.api(f'/pipelines/{pipeline_id}/jobs?per_page=100')
for job in sorted(jobs, key=lambda j: j['id']):
    dur = f"{job['duration']:6.1f}s" if job.get('duration') else "     —"
    print(f"  {job['stage']:14} {job['name']:22} {job['status']:10} {dur}")

print()
if '--logs' in sys.argv:
    for job in jobs:
        if job['status'] == 'failed':
            trace = cg.api(f"/jobs/{job['id']}/trace", raw=True)
            clean = re.sub(r'\x1b\[[0-9;]*[A-Za-z]', '', trace)
            lines = [l.split('Z 0', 1)[-1] if 'Z 0' in l else l for l in clean.splitlines()]
            lines = [l for l in lines if l.strip()]
            print(f"===== {job['name']} =====")
            for line in lines[-40:]:
                print(line[:200])
