"""Detect which benchmark tools are actually usable on this machine.

The exe distribution cannot bundle garak, PyRIT or promptfoo: they pull a torch
stack or a Node binary. Instead of failing a run halfway, CYBRA asks first and
renders an honest "not installed" card with the exact command to install it.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# tool -> (kind, human name, install hint)
TOOLS = {
    'harmbench': ('pure', 'HarmBench', 'Входит в поставку'),
    'jailbreakbench': ('pure', 'JailbreakBench', 'Входит в поставку'),
    'bipia': ('vendored', 'BIPIA', 'Входит в поставку'),
    'security-regression': ('pure', 'Security Regression', 'Входит в поставку'),
    'promptfoo': ('node', 'Promptfoo', 'npm install, затем node .tools/promptfoo'),
    'garak': ('python', 'garak', 'cybra setup --tools garak'),
    'pyrit': ('python', 'PyRIT', 'cybra setup --tools pyrit'),
    'agentdojo': ('python', 'AgentDojo', 'cybra setup --tools agentdojo'),
}


def python_for(tool: str) -> str:
    """Mirror security_suite.setup_tools.python_for without importing it."""
    # BIPIA в этом списке намеренно: это vendored-библиотека плюс четыре
    # пакета в основном venv, отдельного .tools/bipia не существует. Без неё
    # проверка наличия файла в run.py давала «Dependencies not installed».
    if tool in ('promptfoo', 'harmbench', 'jailbreakbench',
                'security-regression', 'bipia'):
        return sys.executable
    env = ROOT / '.tools' / tool
    return str(env / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python'))


def _promptfoo_ready() -> bool:
    node_modules = ROOT / '.tools' / 'promptfoo' / 'node_modules'
    return node_modules.exists() and shutil.which('npm') is not None


def _installed(tool: str) -> bool:
    kind = TOOLS[tool][0]
    if kind in ('pure', 'vendored'):
        return True
    if tool == 'promptfoo':
        return _promptfoo_ready()
    return Path(python_for(tool)).exists()


def _version(tool: str) -> str | None:
    """Best-effort version string; never raises."""
    try:
        if tool == 'promptfoo':
            manifest = ROOT / '.tools' / 'promptfoo' / 'node_modules' / 'promptfoo' / 'package.json'
            if manifest.exists():
                return json.loads(manifest.read_text(encoding='utf-8')).get('version')
            return None
        if TOOLS[tool][0] in ('pure', 'vendored'):
            lock_path = ROOT / 'sources.lock.json'
            if lock_path.exists():
                lock = json.loads(lock_path.read_text(encoding='utf-8'))
                entry = lock.get(tool, {})
                return entry.get('revision', '')[:12] or None
            return None
        python = python_for(tool)
        if not Path(python).exists():
            return None
        out = subprocess.run(
            [python, '-c', 'import importlib.metadata as m; print(m.version("garak" if "' + tool + '"=="garak" else "' + tool + '"))'],
            capture_output=True, text=True, timeout=20,
        )
        return out.stdout.strip() or None
    except Exception:
        return None


def capabilities() -> list[dict]:
    """Return a JSON-serialisable status list for every tool."""
    result = []
    for tool, (kind, name, hint) in TOOLS.items():
        ready = _installed(tool)
        result.append({
            'tool': tool,
            'name': name,
            'kind': kind,
            'available': ready,
            'version': _version(tool) if ready else None,
            'install_hint': None if ready else hint,
        })
    return result


def missing(requested: list[str]) -> list[str]:
    """Return requested tools that are not available."""
    ready = {c['tool'] for c in capabilities() if c['available']}
    return [t for t in requested if t not in ready]


if __name__ == '__main__':
    print(json.dumps(capabilities(), ensure_ascii=False, indent=2))
