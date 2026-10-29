"""Offline engine: runs the datasets against a local fixture model.

Why this exists: a fresh clone has no API key and no heavy tools installed, but
the UI, the import pipeline and the charts must still be demonstrable. This
backend produces the same artifact layout as the real one, so everything
downstream is exercised honestly.

The fixture is a *simulated* model. It must never be presented as a security
assessment of anything.
"""
from __future__ import annotations

import json
import random
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

from .contract import EngineHandle, Progress, RunRequest

ROOT = Path(__file__).resolve().parents[1]
MOCK = ROOT / 'tests' / 'mock_server.py'


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


class MockEngine:
    """Deterministic stand-in used by demo mode and tests."""

    name = 'mock'

    def __init__(self, python: str | None = None) -> None:
        self.python = python or sys.executable

    def start(self, request: RunRequest) -> 'MockHandle':
        return MockHandle(request, self.python)


class MockHandle(EngineHandle):
    def __init__(self, request: RunRequest, python: str) -> None:
        self._request = request
        self._python = python
        self._stop = threading.Event()
        self._cancelled = False
        self._progress = Progress()
        self._thread = threading.Thread(target=self._work, daemon=True)
        self._started = time.monotonic()
        self._thread.start()

    # -- the simulated run ---------------------------------------------
    def _work(self) -> None:
        out = self._request.out_dir
        out.mkdir(parents=True, exist_ok=True)
        port = _free_port()
        server = subprocess.Popen(
            [self._python, str(MOCK), '--port', str(port)],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        try:
            time.sleep(0.6)
            manifest = {
                'run_id': self._request.run_id,
                'mode': 'mock',
                'models': [t.model for t in self._request.targets],
                'tools': self._request.tools,
                'warning': 'MOCK ENGINE: fixture output, not a security assessment',
                'config': {'limit': self._request.limit, 'seed': self._request.seed},
            }
            (out / 'manifest.json').write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')

            for target in self._request.targets:
                for tool in self._request.tools:
                    if self._stop.is_set():
                        return
                    self._progress.current_model = target.model
                    self._progress.current_tool = tool
                    self._step(out, target.model, tool, port)
                    self._progress.finished_steps.append(f'{target.model}/{tool}:COMPLETE')
                    self._stop.wait(0.05)
            self._consolidate(out)
        finally:
            server.terminate()
            try:
                server.wait(timeout=5)
            except subprocess.TimeoutExpired:
                server.kill()

    def _step(self, out: Path, model: str, tool: str, port: int) -> None:
        slug = _slug(model)
        step_dir = out / slug / tool
        step_dir.mkdir(parents=True, exist_ok=True)
        # Deterministic per (model, tool) so repeated demos look stable.
        rng = random.Random(f'{model}|{tool}|{self._request.seed}')
        categories = _categories(tool)
        cases = max(1, min(self._request.limit, 12))
        records = []
        counts = {'PASS': 0, 'FAIL': 0}
        for index in range(cases):
            category = categories[index % len(categories)]
            # A deliberately uneven profile: stronger models fail less.
            fail_chance = 0.15 + 0.25 * (len(model) % 3) / 3
            verdict = 'FAIL' if rng.random() < fail_chance else 'PASS'
            counts[verdict] += 1
            records.append({
                'schema_version': 1,
                'model': model,
                'tool': tool,
                'mode': 'mock fixture',
                'case_id': f'{tool}-{index:03d}',
                'category': category,
                'status': verdict,
                'unit': 'case',
                'prompt': f'[fixture] {category} request {index}',
                'answer': '[fixture] simulated assistant answer',
                'reason': 'Mock engine: this verdict is synthetic',
            })
            with (step_dir / 'records.jsonl').open('a', encoding='utf-8') as handle:
                handle.write(json.dumps(records[-1], ensure_ascii=False) + '\n')
            self._progress.requests['target'] = self._progress.requests.get('target', 0) + 2
            self._progress.requests['judge'] = self._progress.requests.get('judge', 0) + 2
        status = {
            'status': 'COMPLETE',
            'error': None,
            'requests': {'target': cases * 2, 'judge': cases * 2},
            'transport_errors': [],
        }
        (step_dir / 'status.json').write_text(
            json.dumps(status, ensure_ascii=False, indent=2), encoding='utf-8')

    def _consolidate(self, out: Path) -> None:
        """Produce summary.json in the same shape report.py writes."""
        manifest = json.loads((out / 'manifest.json').read_text(encoding='utf-8'))
        models = {}
        all_records = []
        for model in manifest['models']:
            tools = []
            for tool in manifest['tools']:
                step_dir = out / _slug(model) / tool
                records_path = step_dir / 'records.jsonl'
                records = []
                if records_path.exists():
                    records = [
                        json.loads(line) for line in
                        records_path.read_text(encoding='utf-8').splitlines() if line.strip()
                    ]
                counts = {'PASS': 0, 'FAIL': 0, 'ERROR': 0, 'UNSCORED': 0, 'SKIPPED': 0}
                categories: dict[str, dict[str, int]] = {}
                for row in records:
                    counts[row['status']] = counts.get(row['status'], 0) + 1
                    bucket = categories.setdefault(
                        row['category'],
                        {'PASS': 0, 'FAIL': 0, 'ERROR': 0, 'UNSCORED': 0, 'SKIPPED': 0},
                    )
                    bucket[row['status']] += 1
                total = counts['PASS'] + counts['FAIL']
                tools.append({
                    'tool': tool,
                    'mode': 'mock fixture',
                    'status': 'COMPLETE',
                    'error': None,
                    'requests': {'target': total * 2, 'judge': total * 2},
                    'transport_errors': [],
                    'counts': counts,
                    'failed_check_rate': (counts['FAIL'] / total) if total else None,
                    'unit': 'case',
                    'categories': categories,
                    'artifact_dir': f'{_slug(model)}/{tool}',
                })
                all_records.extend(records)
            findings = any(item['counts']['FAIL'] for item in tools)
            models[model] = {
                'conclusion': 'FINDINGS' if findings else 'NO_FINDINGS_ON_TESTED_SET',
                'tools': tools,
            }
        summary = {
            'schema_version': 1,
            'run_id': manifest['run_id'],
            'models': models,
            'methodology': {tool: 'mock fixture' for tool in manifest['tools']},
            'warning': 'Mock engine output. Not a security assessment.',
        }
        (out / 'summary.json').write_text(
            json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
        with (out / 'all_records.jsonl').open('w', encoding='utf-8') as handle:
            for row in all_records:
                handle.write(json.dumps(row, ensure_ascii=False) + '\n')

    # -- handle protocol ------------------------------------------------
    def poll(self) -> Progress:
        progress = Progress(
            requests=dict(self._progress.requests),
            current_model=self._progress.current_model,
            current_tool=self._progress.current_tool,
            finished_steps=list(self._progress.finished_steps),
            errors=list(self._progress.errors),
        )
        progress.requests.setdefault('target', 0)
        progress.requests.setdefault('judge', 0)
        progress.requests['elapsed_seconds'] = int(time.monotonic() - self._started)
        return progress

    def wait(self, timeout: float | None = None) -> int:
        self._thread.join(timeout)
        if self._thread.is_alive():
            raise TimeoutError('mock run still in progress')
        return 130 if self._cancelled else 0

    def cancel(self) -> None:
        self._cancelled = True
        self._stop.set()

    @property
    def cancelled(self) -> bool:
        return self._cancelled

    def collect(self):
        return [self._request.out_dir]


def _slug(model: str) -> str:
    import hashlib
    import re
    safe = re.sub(r'[^a-zA-Z0-9._-]', '_', model)[:60]
    return safe + '-' + hashlib.sha256(model.encode()).hexdigest()[:10]


def _categories(tool: str) -> list[str]:
    return {
        'harmbench': ['standard', 'contextual', 'copyright'],
        'jailbreakbench': ['harmful/harassment', 'harmful/malware', 'benign'],
        'bipia': ['email/injection', 'table/injection', 'email/utility'],
        'security-regression': ['injection', 'secret_leak', 'pii'],
        'promptfoo': ['direct_injection', 'indirect_injection', 'secret_leak', 'benign'],
        'garak': ['dan', 'promptinject', 'encoding'],
        'pyrit': ['multiturn/direct', 'multiturn/roleplay'],
        'agentdojo': ['workspace/baseline', 'workspace/injection'],
    }.get(tool, ['default'])
