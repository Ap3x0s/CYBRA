"""Process supervisor over the existing ``run.py``.

Design note: CYBRA deliberately does not re-implement scoring. ``run.py`` and
``security_suite`` already encode the judge criteria, the relay budget and the
verdict semantics, and they are validated against real models. Re-expressing
that logic as a library would risk silent changes in what PASS and FAIL mean.
So this module owns only the boring, observable part: spawn, watch, cancel.

The child contract is a directory of files:

    <out>/manifest.json     what was run and with which settings
    <out>/summary.json      consolidated per-model results
    <out>/all_records.jsonl every normalised case
    <out>/<model>/<tool>/   per-step artifacts (records, http log, status)
"""
from __future__ import annotations

import json
import os
import re
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

from .contract import EngineError, EngineHandle, Progress, RunRequest

ROOT = Path(__file__).resolve().parents[1]


class SubprocessEngine:
    """Runs ``python run.py run ...`` and follows its artifact directory."""

    name = 'subprocess'

    def __init__(self, python: str | None = None) -> None:
        self.python = python or sys.executable

    def start(self, request: RunRequest) -> 'SubprocessHandle':
        request.out_dir.mkdir(parents=True, exist_ok=True)
        command = self._command(request)
        env = self._environment(request)
        log_path = request.out_dir / 'engine.log'
        log = log_path.open('w', encoding='utf-8')
        try:
            process = subprocess.Popen(
                command,
                cwd=str(ROOT),
                env=env,
                stdout=log,
                stderr=subprocess.STDOUT,
                start_new_session=(os.name == 'posix'),
                creationflags=(
                    subprocess.CREATE_NEW_PROCESS_GROUP if os.name == 'nt' else 0
                ),
            )
        except OSError as error:
            log.close()
            raise EngineError(f'Cannot start engine: {error}') from error
        return SubprocessHandle(process, request, log)

    def _command(self, request: RunRequest) -> list[str]:
        command = [
            self.python, 'run.py', 'run',
            '--endpoint', request.targets[0].endpoint,
            '--models', *[target.model for target in request.targets],
            '--judge-endpoint', request.judge.endpoint,
            '--judge-model', request.judge.model,
            '--tools', *request.tools,
            '--limit', str(request.limit),
            '--seed', str(request.seed),
            '--variants', *request.variants,
            '--max-requests', str(request.max_requests),
            '--max-tokens', str(request.max_tokens),
            '--judge-max-tokens', str(request.judge.max_tokens),
            '--timeout', str(request.timeout),
            '--tool-timeout', str(request.tool_timeout),
            '--token-parameter', request.token_parameter,
            '--out', str(request.out_dir),
        ]
        command += ['--temperature', 'omit' if request.temperature is None else str(request.temperature)]
        if request.developer_as_system:
            command.append('--developer-as-system')
        if request.drop_params:
            command += ['--drop-params', *request.drop_params]
        if not request.verify_tls:
            command.append('--insecure-skip-tls-verify')
        if request.garak_probes:
            command += ['--garak-probes', request.garak_probes]
        if request.bipia_attacks:
            command += ['--bipia-attacks', str(request.bipia_attacks)]

        # Endpoint-level request decoration travels through files, never argv:
        # argv is visible in the process list and in logs.
        if request.targets[0].extra_body:
            path = request.out_dir / 'extra-body.json'
            path.write_text(json.dumps(request.targets[0].extra_body), encoding='utf-8')
            command += ['--extra-body', str(path)]
        if request.targets[0].headers:
            path = request.out_dir / 'headers.json'
            path.write_text(json.dumps(request.targets[0].headers), encoding='utf-8')
            command += ['--headers', str(path)]
        if request.judge.extra_body:
            path = request.out_dir / 'judge-extra-body.json'
            path.write_text(json.dumps(request.judge.extra_body), encoding='utf-8')
            command += ['--judge-extra-body', str(path)]
        return command

    def _environment(self, request: RunRequest) -> dict:
        env = os.environ.copy()
        env['TARGET_API_KEY'] = request.targets[0].api_key or ''
        env['JUDGE_API_KEY'] = request.judge.api_key or request.targets[0].api_key or ''
        env['PYTHONPATH'] = str(ROOT)
        env['PYTHONIOENCODING'] = 'utf-8'
        env['NO_PROXY'] = 'localhost,127.0.0.1'
        env['no_proxy'] = 'localhost,127.0.0.1'
        env['PROMPTFOO_DISABLE_TELEMETRY'] = '1'
        env['TOKENIZERS_PARALLELISM'] = 'false'
        for name in ('http_proxy', 'https_proxy', 'all_proxy',
                     'HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY'):
            env.pop(name, None)
        return env


class SubprocessHandle(EngineHandle):
    """Follows one child run."""

    _COUNT = re.compile(r'requests=\{' + "'target': (\\d+), 'judge': (\\d+)" + r'\}')
    _STARTING = re.compile(r'^\[(.+?)\] (.+?): starting$')
    _FINISHED = re.compile(r'^\[(.+?)\] (.+?): (\w+)$')

    def __init__(self, process: subprocess.Popen, request: RunRequest, log) -> None:
        self._process = process
        self._request = request
        self._log = log
        self._lock = threading.Lock()
        self._progress = Progress()
        self._finished_codes: dict[tuple[str, str], str] = {}
        self._cancelled = False

    # -- progress -------------------------------------------------------
    def poll(self) -> Progress:
        self._drain_log()
        with self._lock:
            progress = Progress(
                requests=dict(self._progress.requests),
                current_model=self._progress.current_model,
                current_tool=self._progress.current_tool,
                finished_steps=list(self._progress.finished_steps),
                errors=list(self._progress.errors),
            )
        progress.requests.setdefault('target', 0)
        progress.requests['elapsed_seconds'] = int(time.monotonic() - self._started_at)
        return progress

    def _drain_log(self) -> None:
        """Parse whatever the child has appended since the last call."""
        path = self._request.out_dir / 'engine.log'
        try:
            text = path.read_text(encoding='utf-8', errors='replace')
        except OSError:
            return
        seen = getattr(self, '_log_offset', 0)
        if len(text) <= seen:
            return
        self._log_offset = len(text)
        for line in text[seen:].splitlines():
            match = self._STARTING.match(line)
            if match:
                with self._lock:
                    self._progress.current_model = match.group(1)
                    self._progress.current_tool = match.group(2)
                continue
            match = self._FINISHED.match(line)
            if match:
                model, tool, status = match.groups()
                with self._lock:
                    self._progress.finished_steps.append(f'{model}/{tool}:{status}')
                    self._finished_codes[(model, tool)] = status
                    if status in ('ERROR', 'PARTIAL'):
                        self._progress.errors.append(f'{model}/{tool}: {status}')
                continue
            match = self._COUNT.search(line)
            if match:
                with self._lock:
                    self._progress.requests['target'] = int(match.group(1))
                    self._progress.requests['judge'] = int(match.group(2))

    # -- lifecycle ------------------------------------------------------
    @property
    def _started_at(self) -> float:
        if not hasattr(self, '_start_monotonic'):
            self._start_monotonic = time.monotonic()
        return self._start_monotonic

    def wait(self, timeout: float | None = None) -> int:
        try:
            code = self._process.wait(timeout=timeout)
        finally:
            self._close_log()
        self._drain_log()
        return code

    def cancel(self) -> None:
        if self._process.poll() is not None:
            return
        self._cancelled = True
        if os.name == 'posix':
            try:
                os.killpg(self._process.pid, signal.SIGTERM)
            except ProcessLookupError:
                return
        else:
            self._process.terminate()
        try:
            self._process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            if os.name == 'posix':
                os.killpg(self._process.pid, signal.SIGKILL)
            else:
                self._process.kill()
            self._process.wait()

    def collect(self):
        return [self._request.out_dir]

    @property
    def cancelled(self) -> bool:
        return self._cancelled

    def _close_log(self) -> None:
        try:
            if not self._log.closed:
                self._log.flush()
                self._log.close()
        except OSError:
            pass

    def __del__(self):
        self._close_log()
