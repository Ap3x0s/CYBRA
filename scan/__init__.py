"""Engine selection and artifact parsing.

``get_engine`` is the single place that decides *how* a run executes. Callers
ask for a mode and never branch on it themselves.
"""
from __future__ import annotations

import json
from pathlib import Path

from .contract import Engine, EngineError, RunRequest

__all__ = [
    'Engine', 'EngineError', 'RunRequest', 'get_engine', 'load_manifest',
    'load_records', 'load_summary', 'read_progress',
]


def get_engine(mode: str = 'subprocess', python: str | None = None) -> Engine:
    """Return the engine for ``mode``.

    Modes: ``subprocess`` (real run.py), ``mock`` (offline fixture).
    """
    if mode == 'mock':
        from .mock_engine import MockEngine
        return MockEngine(python)
    if mode == 'subprocess':
        from .engine import SubprocessEngine
        return SubprocessEngine(python)
    raise EngineError(f'Unknown engine mode: {mode}')


def load_manifest(out_dir: Path) -> dict:
    path = Path(out_dir) / 'manifest.json'
    if not path.exists():
        raise EngineError(f'manifest.json not found in {out_dir}')
    return json.loads(path.read_text(encoding='utf-8'))


def load_summary(out_dir: Path) -> dict:
    path = Path(out_dir) / 'summary.json'
    if not path.exists():
        raise EngineError(f'summary.json not found in {out_dir}')
    return json.loads(path.read_text(encoding='utf-8'))


def load_records(out_dir: Path) -> list[dict]:
    path = Path(out_dir) / 'all_records.jsonl'
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if line:
            try:
                rows.append(json.loads(line))
            except ValueError:
                continue
    return rows


def read_progress(out_dir: Path) -> dict:
    """Read progress straight from artifacts, for when a handle is gone."""
    out = Path(out_dir)
    summary = out / 'summary.json'
    records = out / 'all_records.jsonl'
    return {
        'summary_ready': summary.exists(),
        'records': sum(1 for _ in records.open(encoding='utf-8')) if records.exists() else 0,
    }
