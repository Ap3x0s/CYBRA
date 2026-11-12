"""Run orchestration: queue a run, supervise the engine, import the result.

Only one run executes at a time. That is intentional: the engine already issues
sequential requests, and letting two runs share a target would make rate-limit
errors indistinguishable from real findings.
"""
from __future__ import annotations

import datetime as dt
import json

# scan/ lives one level above backend/, so it is importable when the app is run
# from the repository root or installed as a package.
import sys
import threading
import traceback
import uuid
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session as OrmSession

from .config import settings
from .db import SessionLocal
from .models import Endpoint, Finding, Run, RunStep, Target, utcnow

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scan import get_engine  # noqa: E402
from scan.contract import JudgeConfig, RunRequest  # noqa: E402
from scan.contract import Target as EngineTarget  # noqa: E402


class RunManager:
    """Owns the single worker thread and the live handle."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._handle = None
        self._run_pk: int | None = None
        self._cancelled = False

    # -- public API -----------------------------------------------------
    def is_busy(self) -> bool:
        with self._lock:
            return self._handle is not None

    def active_run_pk(self) -> int | None:
        with self._lock:
            return self._run_pk

    def cancel(self, run_pk: int) -> bool:
        with self._lock:
            if self._run_pk != run_pk or self._handle is None:
                return False
            self._cancelled = True
            handle = self._handle
        handle.cancel()
        return True

    def start(self, db: OrmSession, request_spec: dict, user_id: int | None) -> Run:
        """Validate, persist and launch a run."""
        if self.is_busy():
            raise ValueError('Another run is already in progress')
        targets = db.scalars(
            select(Target).where(Target.id.in_(request_spec['target_ids']))
        ).all()
        if not targets:
            raise ValueError('No targets selected')
        judge_target = db.get(Target, request_spec.get('judge_target_id') or targets[0].id)
        if judge_target is None:
            raise ValueError('Judge model not found')

        run_id = dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid.uuid4().hex[:8]
        out_dir = settings.out_dir / run_id
        run = Run(
            run_id=run_id,
            label=request_spec.get('label') or f'Run {run_id[:15]}',
            engine_mode=request_spec.get('engine_mode') or settings.engine_mode,
            status='PENDING',
            profile_json=request_spec,
            out_dir=str(out_dir),
            created_by=user_id,
            created_at=utcnow(),
        )
        db.add(run)
        db.commit()

        engine_request = self._build_request(run, targets, judge_target, request_spec, out_dir)
        thread = threading.Thread(
            target=self._execute, args=(run.id, engine_request, request_spec),
            daemon=True, name=f'cybra-run-{run.id}',
        )
        thread.start()
        return run

    # -- internals ------------------------------------------------------
    def _build_request(self, run: Run, targets: list[Target], judge: Target,
                       spec: dict, out_dir: Path) -> RunRequest:
        def endpoint_for(target: Target) -> Endpoint:
            endpoint = target.endpoint
            return endpoint

        first = targets[0]
        first_endpoint = endpoint_for(first)
        judge_endpoint = judge.endpoint
        engine_targets = []
        for target in targets:
            endpoint = endpoint_for(target)
            engine_targets.append(EngineTarget(
                endpoint=self._chat_url(endpoint),
                model=target.model_id,
                api_key=settings.decrypt(endpoint.secret_encrypted),
                extra_body={**(endpoint.extra_body or {}), **(target.extra_body or {})},
                headers=endpoint.default_headers or {},
            ))
        return RunRequest(
            run_id=run.run_id,
            out_dir=out_dir,
            targets=engine_targets,
            tools=list(spec['tools']),
            judge=JudgeConfig(
                endpoint=self._chat_url(judge_endpoint),
                model=judge.model_id,
                api_key=settings.decrypt(judge_endpoint.secret_encrypted),
                extra_body=judge_endpoint.extra_body or {},
                max_tokens=int(spec.get('judge_max_tokens', 4096)),
            ),
            datasets_dir=settings.root / 'datasets',
            limit=int(spec.get('limit', 10)),
            seed=int(spec.get('seed', 42)),
            variants=tuple(spec.get('variants') or ('direct', 'roleplay', 'authority')),
            max_requests=int(spec.get('max_requests', 1000)),
            max_tokens=int(spec.get('max_tokens', 2048)),
            temperature=spec.get('temperature', 0.0),
            timeout=int(spec.get('timeout', 120)),
            tool_timeout=int(spec.get('tool_timeout', 3600)),
            token_parameter=first.token_parameter or 'max_tokens',
            drop_params=tuple(first.drop_params or ()),
            developer_as_system=bool(first.developer_as_system),
            verify_tls=bool(first_endpoint.verify_tls and judge_endpoint.verify_tls),
            garak_probes=spec.get('garak_probes', ''),
            bipia_attacks=int(spec.get('bipia_attacks', 4)),
        )

    @staticmethod
    def _chat_url(endpoint: Endpoint) -> str:
        if endpoint.chat_url:
            return endpoint.chat_url
        base = endpoint.base_url.rstrip('/')
        if base.endswith('/chat/completions'):
            return base
        return base + '/chat/completions'

    def _execute(self, run_pk: int, request: RunRequest, spec: dict) -> None:
        db = SessionLocal()
        handle = None
        try:
            run = db.get(Run, run_pk)
            run.status = 'RUNNING'
            run.started_at = utcnow()
            db.commit()

            engine = get_engine(run.engine_mode)
            handle = engine.start(request)
            with self._lock:
                self._handle = handle
                self._run_pk = run_pk

            code = handle.wait()
            cancelled = self._cancelled
            with self._lock:
                self._cancelled = False
                self._handle = None
                self._run_pk = None

            run = db.get(Run, run_pk)
            if cancelled:
                run.status = 'CANCELLED'
            elif code == 0:
                run.status = 'COMPLETE'
            elif code == 2:
                run.status = 'PARTIAL'
            else:
                run.status = 'ERROR'
            run.finished_at = utcnow()
            db.commit()
            import_results(db, run, spec)
        except Exception as error:  # noqa: BLE001 - must never kill the worker
            traceback.print_exc()
            run = db.get(Run, run_pk)
            if run is not None:
                run.status = 'ERROR'
                run.error = f'{type(error).__name__}: {error}'
                run.finished_at = utcnow()
                db.commit()
            with self._lock:
                self._handle = None
                self._run_pk = None
        finally:
            db.close()


manager = RunManager()


# -- result import ------------------------------------------------------
def _find_session_dir(out_dir: Path) -> Path | None:
    """Каталог, в котором run.py оставил summary.json.

    run.py создаёт внутри --out ещё один каталог сессии:
        dest = Path(args.out).resolve() / run_id
    Поэтому summary.json лежит либо прямо в out_dir (старые версии, mock),
    либо в единственном вложенном каталоге. Без этого поиска импорт молча не
    срабатывал: прогон получал PARTIAL и «Engine produced no summary.json»,
    хотя все данные были на диске.
    """
    direct = out_dir / 'summary.json'
    if direct.exists():
        return out_dir

    # Каталоги сессий: ровно один уровень вглубь, с summary.json внутри.
    candidates = [
        child for child in out_dir.iterdir()
        if child.is_dir() and (child / 'summary.json').exists()
    ] if out_dir.exists() else []

    if not candidates:
        return None
    # Если сессий несколько (переиспользованный каталог) — берём свежайшую.
    candidates.sort(key=lambda p: (p / 'summary.json').stat().st_mtime, reverse=True)
    return candidates[0]


def import_results(db: OrmSession, run: Run, spec: dict) -> None:
    """Copy summary.json and records into normalised tables."""
    out_dir = Path(run.out_dir)
    session_dir = _find_session_dir(out_dir)
    if session_dir is None:
        run.error = run.error or 'Engine produced no summary.json'
        db.commit()
        return
    summary = json.loads((session_dir / 'summary.json').read_text(encoding='utf-8'))
    # summary найден — прошлая ошибка о его отсутствии больше не актуальна.
    if run.error in ('Engine produced no summary.json',):
        run.error = ''

    # Replace previous steps for idempotent re-import.
    for old in db.scalars(select(RunStep).where(RunStep.run_id == run.id)).all():
        for finding in db.scalars(select(Finding).where(Finding.step_id == old.id)).all():
            db.delete(finding)
        db.delete(old)
    db.commit()

    target_by_model = {}
    for target_id in spec.get('target_ids', []):
        target = db.get(Target, target_id)
        if target is not None:
            target_by_model[target.model_id] = target

    for model_name, model_result in summary.get('models', {}).items():
        target = target_by_model.get(model_name)
        for tool_result in model_result.get('tools', []):
            step = RunStep(
                run_id=run.id,
                target_id=target.id if target else None,
                model_label=model_name,
                tool=tool_result['tool'],
                completeness=tool_result.get('status', 'ERROR'),
                counts=tool_result.get('counts', {}),
                failed_check_rate=tool_result.get('failed_check_rate'),
                categories=tool_result.get('categories', {}),
                requests=tool_result.get('requests', {}),
                error=tool_result.get('error') or '',
                # Храним путь вместе с каталогом сессии: иначе по этому полю
                # нельзя открыть артефакты, потому что summary пишет пути
                # относительно сессии, а run.out_dir на уровень выше.
                artifact_dir=str(
                    session_dir / tool_result['artifact_dir']
                    if tool_result.get('artifact_dir') else ''
                ),
            )
            db.add(step)
            db.flush()
            # Пути в summary относительны каталога сессии, а не out_dir.
            _import_findings(db, step, session_dir, tool_result)

    db.commit()


def _import_findings(db: OrmSession, step: RunStep, out_dir: Path, tool_result: dict) -> None:
    artifact = tool_result.get('artifact_dir') or ''
    records_path = out_dir / artifact / 'records.jsonl' if artifact else None
    if records_path is None or not records_path.exists():
        return
    for line in records_path.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except ValueError:
            continue
        db.add(Finding(
            step_id=step.id,
            case_id=str(row.get('case_id', ''))[:200],
            category=str(row.get('category', ''))[:120],
            verdict=str(row.get('status', 'UNSCORED')),
            prompt=str(row.get('prompt', ''))[:20000],
            answer=str(row.get('answer', ''))[:20000],
            reason=str(row.get('reason', ''))[:4000],
            raw_json={k: v for k, v in row.items()
                      if k not in {'prompt', 'answer', 'reason'}},
        ))
