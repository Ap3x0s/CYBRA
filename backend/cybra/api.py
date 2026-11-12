"""HTTP API. One router per resource, mounted under /api/v1."""
from __future__ import annotations

import json
import secrets
from pathlib import Path

from fastapi import (
    APIRouter,
    Body,
    Depends,
    File,
    HTTPException,
    Query,
    Request,
    Response,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session as OrmSession

from . import datasets as dataset_service
from .config import settings
from .db import get_db
from .models import (
    DatasetCase,
    DatasetVersion,
    Endpoint,
    Finding,
    Run,
    RunStep,
    Target,
    User,
)
from .runs import manager
from .schemas import (
    CaseEditIn,
    DatasetCaseOut,
    DatasetVersionOut,
    EndpointIn,
    EndpointOut,
    FindingOut,
    LoginIn,
    MeOut,
    PasswordIn,
    ProgressOut,
    RunIn,
    RunOut,
    TargetIn,
    TargetOut,
    UserIn,
    UserOut,
)
from .security import (
    ROLE_ORDER,
    check_csrf,
    create_session,
    current_session,
    hash_password,
    require_role,
    require_user,
    verify_password,
)

DEFAULT_USER_AGENT = (
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
    '(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'
)


router = APIRouter(prefix='/api/v1')
TOOL_LIST = ('garak', 'promptfoo', 'pyrit', 'harmbench', 'jailbreakbench', 'bipia',
             'agentdojo', 'security-regression')


# ---------------------------------------------------------------- auth
def _public_user(user: User) -> dict:
    return {
        'id': user.id, 'email': user.email, 'display_name': user.display_name,
        'role': user.role, 'is_active': user.is_active,
        'last_login_at': user.last_login_at,
    }


@router.post('/auth/login')
def login(payload: LoginIn, request: Request, response: Response,
          db: OrmSession = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == payload.email.lower().strip()))
    if user is None or not user.is_active or not verify_password(user.password_hash, payload.password):
        # Same message for both cases: do not leak which emails exist.
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, 'Неверный email или пароль')
    token, session = create_session(db, user, request.headers.get('user-agent', ''))
    response.set_cookie(
        settings.cookie_name, token,
        httponly=True, samesite='lax', secure=settings.cookie_secure,
        max_age=settings.session_ttl_hours * 3600, path='/',
    )
    return {**_public_user(user), 'csrf_token': session.csrf_token}


@router.post('/auth/logout')
def logout(response: Response, request: Request, db: OrmSession = Depends(get_db)):
    try:
        session = current_session(request, db)
        db.delete(session)
        db.commit()
    except HTTPException:
        pass
    response.delete_cookie(settings.cookie_name, path='/')
    return {'ok': True}


@router.get('/auth/me', response_model=MeOut)
def me(request: Request, user: User = Depends(require_user)):
    session = getattr(request.state, 'session', None)
    return {**_public_user(user), 'csrf_token': session.csrf_token if session else ''}


@router.post('/auth/password')
def change_password(payload: PasswordIn, request: Request,
                    user: User = Depends(require_user), db: OrmSession = Depends(get_db)):
    check_csrf(request, request.state.session)
    if not verify_password(user.password_hash, payload.current_password):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, 'Текущий пароль неверен')
    user.password_hash = hash_password(payload.new_password)
    db.commit()
    return {'ok': True}


# ---------------------------------------------------------------- users
@router.get('/users', response_model=list[UserOut])
def list_users(_user: User = Depends(require_role('admin')), db: OrmSession = Depends(get_db)):
    return db.scalars(select(User).order_by(User.id)).all()


@router.post('/users', response_model=UserOut, status_code=201)
def create_user(payload: UserIn, request: Request,
                _admin: User = Depends(require_role('admin')),
                db: OrmSession = Depends(get_db)):
    check_csrf(request, request.state.session)
    if payload.role not in ROLE_ORDER:
        raise HTTPException(400, 'Неизвестная роль')
    email = payload.email.lower().strip()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(409, 'Пользователь с таким email уже существует')
    user = User(
        email=email,
        display_name=payload.display_name or email.split('@')[0],
        password_hash=hash_password(payload.password),
        role=payload.role,
    )
    db.add(user)
    db.commit()
    return user


@router.patch('/users/{user_id}', response_model=UserOut)
def update_user(user_id: int, request: Request, payload: dict = Body(...),
                _admin: User = Depends(require_role('admin')),
                db: OrmSession = Depends(get_db)):
    check_csrf(request, request.state.session)
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(404, 'Пользователь не найден')
    if 'role' in payload and payload['role'] in ROLE_ORDER:
        user.role = payload['role']
    if 'is_active' in payload:
        user.is_active = bool(payload['is_active'])
    if payload.get('password'):
        user.password_hash = hash_password(payload['password'])
    db.commit()
    return user


# ---------------------------------------------------------------- endpoints
def _endpoint_out(row: Endpoint) -> dict:
    """Serialise an endpoint without ever touching the stored secret."""
    return {
        'id': row.id, 'name': row.name, 'base_url': row.base_url,
        'chat_url': row.chat_url, 'auth_type': row.auth_type,
        'secret_hint': row.secret_hint, 'has_secret': bool(row.secret_encrypted),
        'verify_tls': row.verify_tls, 'default_headers': row.default_headers or {},
        'extra_body': row.extra_body or {}, 'notes': row.notes,
        'created_at': row.created_at,
    }


@router.get('/endpoints', response_model=list[EndpointOut])
def list_endpoints(_user: User = Depends(require_user), db: OrmSession = Depends(get_db)):
    rows = db.scalars(select(Endpoint).order_by(Endpoint.id)).all()
    return [_endpoint_out(row) for row in rows]


@router.post('/endpoints', response_model=EndpointOut, status_code=201)
def create_endpoint(payload: EndpointIn, request: Request,
                    _user: User = Depends(require_role('operator')),
                    db: OrmSession = Depends(get_db)):
    check_csrf(request, request.state.session)
    endpoint = Endpoint(
        name=payload.name,
        base_url=payload.base_url.rstrip('/'),
        chat_url=payload.chat_url,
        auth_type=payload.auth_type,
        secret_encrypted=settings.encrypt(payload.api_key),
        secret_hint=(payload.api_key[-4:] if payload.api_key else ''),
        verify_tls=payload.verify_tls,
        ca_pem=payload.ca_pem,
        default_headers=payload.default_headers,
        extra_body=payload.extra_body,
        notes=payload.notes,
    )
    db.add(endpoint)
    db.commit()
    return _endpoint_out(endpoint)


@router.put('/endpoints/{endpoint_id}', response_model=EndpointOut)
def update_endpoint(endpoint_id: int, payload: EndpointIn, request: Request,
                    _user: User = Depends(require_role('operator')),
                    db: OrmSession = Depends(get_db)):
    check_csrf(request, request.state.session)
    endpoint = db.get(Endpoint, endpoint_id)
    if endpoint is None:
        raise HTTPException(404, 'Эндпоинт не найден')
    endpoint.name = payload.name
    endpoint.base_url = payload.base_url.rstrip('/')
    endpoint.chat_url = payload.chat_url
    endpoint.auth_type = payload.auth_type
    endpoint.verify_tls = payload.verify_tls
    endpoint.ca_pem = payload.ca_pem
    endpoint.default_headers = payload.default_headers
    endpoint.extra_body = payload.extra_body
    endpoint.notes = payload.notes
    if payload.api_key:
        endpoint.secret_encrypted = settings.encrypt(payload.api_key)
        endpoint.secret_hint = payload.api_key[-4:]
    db.commit()
    return _endpoint_out(endpoint)


@router.delete('/endpoints/{endpoint_id}', status_code=204)
def delete_endpoint(endpoint_id: int, request: Request,
                    _user: User = Depends(require_role('admin')),
                    db: OrmSession = Depends(get_db)):
    check_csrf(request, request.state.session)
    endpoint = db.get(Endpoint, endpoint_id)
    if endpoint is None:
        raise HTTPException(404, 'Эндпоинт не найден')
    db.delete(endpoint)
    db.commit()
    return Response(status_code=204)


@router.post('/endpoints/{endpoint_id}/probe')
def probe_endpoint(endpoint_id: int, request: Request,
                   _user: User = Depends(require_role('operator')),
                   db: OrmSession = Depends(get_db)):
    """Send one minimal request so the admin sees a real error before a run."""
    check_csrf(request, request.state.session)
    import urllib.error
    import urllib.request
    endpoint = db.get(Endpoint, endpoint_id)
    if endpoint is None:
        raise HTTPException(404, 'Эндпоинт не найден')
    target = db.scalar(select(Target).where(Target.endpoint_id == endpoint_id))
    if target is None:
        raise HTTPException(400, 'Сначала добавьте модель для этого эндпоинта')
    url = endpoint.chat_url or endpoint.base_url.rstrip('/') + '/chat/completions'
    payload = {
        'model': target.model_id,
        'messages': [{'role': 'user', 'content': 'ping'}],
        'max_tokens': 8,
        'stream': False,
        **(endpoint.extra_body or {}),
    }
    # User-Agent обязателен: urllib подставляет `Python-urllib/3.x`, и
    # Cloudflare (например у api.commandcode.ai) отвечает 403 error 1010 —
    # блокировкой по подписи клиента, ещё до проверки ключа. С обычным UA
    # запрос доходит до авторизации, и ошибка становится осмысленной.
    headers = {
        'Content-Type': 'application/json',
        'User-Agent': DEFAULT_USER_AGENT,
    }
    key = settings.decrypt(endpoint.secret_encrypted)
    if key:
        headers['Authorization'] = 'Bearer ' + key
    headers.update(endpoint.default_headers or {})
    request_obj = urllib.request.Request(
        url, data=json.dumps(payload).encode(), headers=headers)
    try:
        with urllib.request.urlopen(request_obj, timeout=30) as response:
            body = json.load(response)
        choices = body.get('choices') or []
        if not choices:
            return {'ok': False, 'detail': 'Ответ без choices — это не Chat Completions'}
        return {'ok': True, 'model': body.get('model'), 'latency_hint': 'ok'}
    except urllib.error.HTTPError as error:
        return {'ok': False, 'detail': f'HTTP {error.code}: ' + error.read(600).decode(errors='replace')}
    except Exception as error:  # noqa: BLE001 - report to operator verbatim
        return {'ok': False, 'detail': f'{type(error).__name__}: {error}'}


# ---------------------------------------------------------------- targets
@router.get('/targets', response_model=list[TargetOut])
def list_targets(_user: User = Depends(require_user), db: OrmSession = Depends(get_db)):
    rows = db.scalars(select(Target).order_by(Target.id)).all()
    result = []
    for row in rows:
        endpoint = db.get(Endpoint, row.endpoint_id)
        result.append({
            'id': row.id, 'endpoint_id': row.endpoint_id, 'model_id': row.model_id,
            'label': row.label, 'temperature': row.temperature,
            'token_parameter': row.token_parameter, 'drop_params': row.drop_params or [],
            'developer_as_system': row.developer_as_system,
            'extra_body': row.extra_body or {}, 'group_name': row.group_name,
            'is_judge': row.is_judge,
            'endpoint_name': endpoint.name if endpoint else '',
        })
    return result


@router.post('/targets', response_model=TargetOut, status_code=201)
def create_target(payload: TargetIn, request: Request,
                  _user: User = Depends(require_role('operator')),
                  db: OrmSession = Depends(get_db)):
    check_csrf(request, request.state.session)
    if db.get(Endpoint, payload.endpoint_id) is None:
        raise HTTPException(404, 'Эндпоинт не найден')
    target = Target(**payload.model_dump())
    db.add(target)
    db.commit()
    return {**payload.model_dump(), 'id': target.id,
            'endpoint_name': db.get(Endpoint, payload.endpoint_id).name}


@router.delete('/targets/{target_id}', status_code=204)
def delete_target(target_id: int, request: Request,
                  _user: User = Depends(require_role('operator')),
                  db: OrmSession = Depends(get_db)):
    check_csrf(request, request.state.session)
    target = db.get(Target, target_id)
    if target is None:
        raise HTTPException(404, 'Модель не найдена')
    db.delete(target)
    db.commit()
    return Response(status_code=204)


# ---------------------------------------------------------------- datasets
def _version_out(db: OrmSession, row: DatasetVersion) -> dict:
    count = db.scalar(
        select(func.count()).select_from(DatasetCase).where(DatasetCase.version_id == row.id)
    )
    return {
        'id': row.id, 'name': row.name, 'version': row.version,
        'description': row.description, 'origin': row.origin, 'sha256': row.sha256,
        'parent_id': row.parent_id, 'changelog': row.changelog,
        'case_count': count or 0, 'created_at': row.created_at,
    }


@router.get('/datasets', response_model=list[DatasetVersionOut])
def list_datasets(_user: User = Depends(require_user), db: OrmSession = Depends(get_db)):
    rows = db.scalars(
        select(DatasetVersion).order_by(DatasetVersion.name, DatasetVersion.id.desc())
    ).all()
    return [_version_out(db, row) for row in rows]


@router.get('/datasets/templates')
def dataset_templates(_user: User = Depends(require_user)):
    """Which builtin sources can be seeded, so the UI offers real names."""
    return [{'name': name, 'file': source[0]}
            for name, source in dataset_service.BUILTIN_SOURCES.items()]


@router.post('/datasets/seed', response_model=DatasetVersionOut, status_code=201)
def seed_dataset(request: Request, payload: dict = Body(...),
                 user: User = Depends(require_role('operator')),
                 db: OrmSession = Depends(get_db)):
    check_csrf(request, request.state.session)
    name = payload.get('name', '')
    try:
        version = dataset_service.import_builtin(
            db, settings.root / 'datasets', name, created_by=user.id)
    except (ValueError, FileNotFoundError) as error:
        raise HTTPException(400, str(error)) from error
    return _version_out(db, version)


@router.post('/datasets/import', response_model=DatasetVersionOut, status_code=201)
async def import_dataset(request: Request, name: str = Query(...),
                         file: UploadFile = File(...),
                         user: User = Depends(require_role('operator')),
                         db: OrmSession = Depends(get_db)):
    check_csrf(request, request.state.session)
    suffix = Path(file.filename or 'bundle.jsonl').suffix.lower()
    if suffix not in dataset_service.SUPPORTED_BUNDLE_SUFFIXES:
        raise HTTPException(400, f'Неподдерживаемый тип файла: {suffix}')
    temp_dir = settings.data_dir / 'imports'
    temp_dir.mkdir(parents=True, exist_ok=True)
    destination = temp_dir / f'{name}-{secrets.token_hex(4)}{suffix}'
    destination.write_bytes(await file.read())
    try:
        version = dataset_service.import_bundle(
            db, name, destination, origin='config', created_by=user.id,
            changelog=f'Импорт файла {file.filename}')
    except ValueError as error:
        raise HTTPException(400, str(error)) from error
    finally:
        destination.unlink(missing_ok=True)
    return _version_out(db, version)


@router.get('/datasets/{version_id}/cases', response_model=list[DatasetCaseOut])
def list_cases(version_id: int, _user: User = Depends(require_user),
               db: OrmSession = Depends(get_db)):
    if db.get(DatasetVersion, version_id) is None:
        raise HTTPException(404, 'Версия не найдена')
    return dataset_service.cases_of(db, version_id)


@router.post('/datasets/{version_id}/fork', response_model=DatasetVersionOut, status_code=201)
def fork_version(version_id: int, request: Request, payload: dict = Body(default={}),
                 user: User = Depends(require_role('operator')),
                 db: OrmSession = Depends(get_db)):
    """Create a new editable version from an existing one."""
    check_csrf(request, request.state.session)
    parent = db.get(DatasetVersion, version_id)
    if parent is None:
        raise HTTPException(404, 'Версия не найдена')
    cases = dataset_service.cases_of(db, version_id)
    version = dataset_service.create_version(
        db, name=parent.name, cases=cases, origin='ui',
        description=payload.get('description', parent.description),
        changelog=payload.get('changelog', f'Ветка от {parent.version}'),
        parent_id=parent.id, created_by=user.id,
    )
    return _version_out(db, version)


@router.put('/datasets/{version_id}/cases/{case_id}', response_model=DatasetVersionOut)
def update_case(version_id: int, case_id: int, payload: CaseEditIn, request: Request,
                user: User = Depends(require_role('operator')),
                db: OrmSession = Depends(get_db)):
    """Edit one case. Immutability means this forks a new version."""
    check_csrf(request, request.state.session)
    parent = db.get(DatasetVersion, version_id)
    if parent is None:
        raise HTTPException(404, 'Версия не найдена')
    rows = dataset_service.cases_of(db, version_id)
    updated = []
    found = False
    for row in rows:
        if row['id'] == case_id:
            found = True
            updated.append({**payload.model_dump(), 'metadata': payload.metadata})
        else:
            updated.append(row)
    if not found:
        raise HTTPException(404, 'Кейс не найден')
    version = dataset_service.create_version(
        db, name=parent.name, cases=updated, origin='ui',
        description=parent.description,
        changelog=f'Правка кейса в {parent.version}',
        parent_id=parent.id, created_by=user.id,
    )
    return _version_out(db, version)


@router.get('/datasets/diff')
def diff_datasets(left: int = Query(...), right: int = Query(...),
                  _user: User = Depends(require_user), db: OrmSession = Depends(get_db)):
    if db.get(DatasetVersion, left) is None or db.get(DatasetVersion, right) is None:
        raise HTTPException(404, 'Версия не найдена')
    return dataset_service.diff_versions(db, left, right)


@router.get('/datasets/{version_id}/export')
def export_dataset(version_id: int, _user: User = Depends(require_user),
                   db: OrmSession = Depends(get_db)):
    version = db.get(DatasetVersion, version_id)
    if version is None:
        raise HTTPException(404, 'Версия не найдена')
    export_dir = settings.data_dir / 'exports'
    path = dataset_service.export_version(
        db, version_id, export_dir / f'{version.name}-{version.version}.jsonl')
    return FileResponse(path, filename=path.name, media_type='application/jsonl')


# ---------------------------------------------------------------- runs
def _run_out(db: OrmSession, run: Run, with_steps: bool = True) -> dict:
    steps = []
    if with_steps:
        for step in db.scalars(select(RunStep).where(RunStep.run_id == run.id)).all():
            steps.append({
                'id': step.id, 'model_label': step.model_label, 'tool': step.tool,
                'completeness': step.completeness, 'counts': step.counts or {},
                'failed_check_rate': step.failed_check_rate,
                'categories': step.categories or {}, 'requests': step.requests or {},
                'error': step.error, 'artifact_dir': step.artifact_dir,
            })
    # Длительность считаем на сервере: started_at и finished_at приходят с
    # часовым поясом UTC, и повторять эту арифметику в каждом клиенте (список,
    # деталь, отчёт) значило бы получить три источника правды.
    duration = None
    if run.started_at and run.finished_at:
        duration = round((run.finished_at - run.started_at).total_seconds(), 1)

    return {
        'id': run.id, 'run_id': run.run_id, 'label': run.label,
        'engine_mode': run.engine_mode, 'status': run.status,
        'created_at': run.created_at, 'started_at': run.started_at,
        'finished_at': run.finished_at, 'duration_seconds': duration,
        'error': run.error, 'steps': steps,
    }


@router.get('/runs', response_model=list[RunOut])
def list_runs(limit: int = 50, _user: User = Depends(require_user),
              db: OrmSession = Depends(get_db)):
    rows = db.scalars(select(Run).order_by(Run.id.desc()).limit(limit)).all()
    return [_run_out(db, row) for row in rows]


@router.get('/runs/{run_pk}', response_model=RunOut)
def get_run(run_pk: int, _user: User = Depends(require_user),
            db: OrmSession = Depends(get_db)):
    run = db.get(Run, run_pk)
    if run is None:
        raise HTTPException(404, 'Прогон не найден')
    return _run_out(db, run)


@router.post('/runs', response_model=RunOut, status_code=201)
def create_run(payload: RunIn, request: Request,
               user: User = Depends(require_role('operator')),
               db: OrmSession = Depends(get_db)):
    check_csrf(request, request.state.session)
    unknown = [tool for tool in payload.tools if tool not in TOOL_LIST]
    if unknown:
        raise HTTPException(400, f'Неизвестные инструменты: {", ".join(unknown)}')
    if not payload.tools:
        raise HTTPException(400, 'Выберите хотя бы один инструмент')
    spec = payload.model_dump()
    try:
        run = manager.start(db, spec, user.id)
    except ValueError as error:
        raise HTTPException(409, str(error)) from error
    return _run_out(db, run)


@router.post('/runs/{run_pk}/cancel')
def cancel_run(run_pk: int, request: Request,
               _user: User = Depends(require_role('operator')),
               db: OrmSession = Depends(get_db)):
    check_csrf(request, request.state.session)
    if not manager.cancel(run_pk):
        raise HTTPException(409, 'Этот прогон не выполняется')
    return {'ok': True}


@router.get('/runs/{run_pk}/progress', response_model=ProgressOut)
def run_progress(run_pk: int, _user: User = Depends(require_user),
                 db: OrmSession = Depends(get_db)):
    run = db.get(Run, run_pk)
    if run is None:
        raise HTTPException(404, 'Прогон не найден')
    from scan import read_progress
    handle = manager._handle if manager.active_run_pk() == run_pk else None
    if handle is not None:
        progress = handle.poll()
        return {
            'status': run.status, 'requests': progress.requests,
            'current_model': progress.current_model, 'current_tool': progress.current_tool,
            'finished_steps': progress.finished_steps, 'errors': progress.errors,
        }
    if run.out_dir:
        snapshot = read_progress(Path(run.out_dir))
        return {
            'status': run.status,
            'requests': {'records': snapshot['records']},
            'finished_steps': [],
            'errors': [run.error] if run.error else [],
        }
    return {'status': run.status}


@router.get('/runs/{run_pk}/findings', response_model=list[FindingOut])
def run_findings(run_pk: int, verdict: str | None = None, tool: str | None = None,
                 step_id: int | None = None, limit: int = 200,
                 _user: User = Depends(require_user),
                 db: OrmSession = Depends(get_db)):
    query = (select(Finding).join(RunStep, Finding.step_id == RunStep.id)
             .where(RunStep.run_id == run_pk))
    if verdict:
        query = query.where(Finding.verdict == verdict)
    if tool:
        query = query.where(RunStep.tool == tool)
    if step_id:
        query = query.where(Finding.step_id == step_id)
    return db.scalars(query.limit(limit)).all()


@router.get('/runs/{run_pk}/report')
def run_report(run_pk: int, fmt: str = Query('json', pattern='^(json|md|html)$'),
               _user: User = Depends(require_user), db: OrmSession = Depends(get_db)):
    run = db.get(Run, run_pk)
    if run is None:
        raise HTTPException(404, 'Прогон не найден')
    out_dir = Path(run.out_dir)
    if fmt == 'md' and (out_dir / 'report.md').exists():
        return FileResponse(out_dir / 'report.md', filename=f'{run.run_id}.md')
    if fmt == 'html' and (out_dir / 'report.html').exists():
        return FileResponse(out_dir / 'report.html', filename=f'{run.run_id}.html')
    summary = out_dir / 'summary.json'
    if summary.exists():
        return JSONResponse(json.loads(summary.read_text(encoding='utf-8')))
    return JSONResponse({'error': 'Отчёт ещё не готов'}, status_code=404)


# ---------------------------------------------------------------- misc
@router.get('/capabilities')
def get_capabilities(_user: User = Depends(require_user)):
    from scan.capabilities import capabilities
    return capabilities()


@router.get('/metrics/catalog')
def metrics_catalog(_user: User = Depends(require_user)):
    """Definitions shown as tooltips next to every number in the UI."""
    from .metrics import CATALOG
    return CATALOG


@router.get('/metrics/series')
def metrics_series(model: str | None = None, tool: str | None = None,
                   metric: str = 'failed_check_rate', limit: int = 100,
                   _user: User = Depends(require_user), db: OrmSession = Depends(get_db)):
    from .metrics import series
    return series(db, model=model, tool=tool, metric=metric, limit=limit)


@router.get('/health')
def health():
    return {'status': 'ok', 'version': '0.1.0'}
