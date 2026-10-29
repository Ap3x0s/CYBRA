"""Dataset versioning: import, edit, diff, rollback.

Rule that shapes this module: a version is immutable once created. Editing a
case or importing a bundle produces a *new* version that points at its parent.
That is what makes a historical run reproducible: it references a version id,
not "the current file on disk".

Four sources are supported, matching the two channels from the brief:
  * ``builtin``  — the benchmark files that ship with the suite
  * ``config``   — a YAML/JSON bundle committed to the repository (versioned in git)
  * ``ui``       — edits made in the web editor
  * ``upload``   — an uploaded JSONL/CSV
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
from pathlib import Path

import yaml
from sqlalchemy import select
from sqlalchemy.orm import Session as OrmSession

from .models import DatasetCase, DatasetVersion, utcnow

SUPPORTED_BUNDLE_SUFFIXES = {'.json', '.jsonl', '.yaml', '.yml', '.csv'}

# Which benchmark file feeds which logical dataset name. Kept explicit so the
# UI can show "builtin: harmbench" without guessing.
BUILTIN_SOURCES = {
    'harmbench': ('harmbench.csv', 'csv'),
    'jailbreakbench-harmful': ('jbb-harmful-behaviors.csv', 'csv'),
    'jailbreakbench-benign': ('jbb-benign-behaviors.csv', 'csv'),
    'corporate': ('corporate.jsonl', 'jsonl'),
    'multiturn': ('multiturn.jsonl', 'jsonl'),
    'security-injection': ('security_regression/injection.jsonl', 'jsonl'),
    'security-pii': ('security_regression/pii.jsonl', 'jsonl'),
    'security-secrets': ('security_regression/secrets.jsonl', 'jsonl'),
    'bipia-email': ('bipia/email/test.jsonl', 'jsonl'),
    'bipia-table': ('bipia/table/test.jsonl', 'jsonl'),
}


def digest_cases(cases: list[dict]) -> str:
    payload = json.dumps(cases, sort_keys=True, ensure_ascii=False).encode()
    return hashlib.sha256(payload).hexdigest()


def next_version(db: OrmSession, name: str) -> str:
    """Return a semver patch bump after the highest existing version."""
    versions = db.scalars(
        select(DatasetVersion.version).where(DatasetVersion.name == name)
    ).all()
    highest = (0, 0, 0)
    for raw in versions:
        try:
            parts = tuple(int(p) for p in str(raw).split('.'))
            if len(parts) == 3 and parts > highest:
                highest = parts
        except ValueError:
            continue
    return f'{highest[0]}.{highest[1]}.{highest[2] + 1}'


def normalise_case(raw: dict, index: int) -> dict:
    """Map heterogeneous benchmark rows onto one case shape."""
    case_id = str(
        raw.get('case_id') or raw.get('id') or raw.get('BehaviorID')
        or raw.get('Index') or f'case-{index:04d}'
    )
    prompt = str(
        raw.get('prompt') or raw.get('messages') and '' or raw.get('Behavior')
        or raw.get('Goal') or raw.get('question') or raw.get('text') or ''
    )
    if isinstance(raw.get('messages'), list):
        prompt = '\n'.join(
            str(message.get('content', '')) for message in raw['messages']
            if isinstance(message, dict)
        ) or prompt
    return {
        'case_id': case_id,
        'category': str(raw.get('category') or raw.get('SemanticCategory')
                        or raw.get('Category') or raw.get('FunctionalCategory') or ''),
        'prompt': prompt,
        'goal': str(raw.get('goal') or raw.get('Goal') or raw.get('Behavior') or ''),
        'kind': str(raw.get('kind') or 'harmful'),
        'metadata': {k: v for k, v in raw.items()
                     if k not in {'prompt', 'goal', 'kind', 'category', 'case_id'}},
    }


def parse_bundle(path: Path) -> list[dict]:
    """Read one bundle file into normalised cases."""
    suffix = path.suffix.lower()
    if suffix not in SUPPORTED_BUNDLE_SUFFIXES:
        raise ValueError(f'Unsupported file type: {suffix}')
    text = path.read_text(encoding='utf-8-sig')
    if suffix == '.jsonl':
        rows = [json.loads(line) for line in text.splitlines() if line.strip()]
    elif suffix == '.json':
        data = json.loads(text)
        if isinstance(data, dict) and 'cases' in data:
            rows = data['cases']
        elif isinstance(data, list):
            rows = data
        elif isinstance(data, dict):
            rows = [data]
        else:
            raise ValueError('JSON bundle must be a list or {"cases": [...]}')
    elif suffix in {'.yaml', '.yml'}:
        data = yaml.safe_load(text)
        if isinstance(data, dict) and 'cases' in data:
            rows = data['cases']
        elif isinstance(data, list):
            rows = data
        else:
            raise ValueError('YAML bundle must be a list or {"cases": [...]}')
    else:
        rows = list(csv.DictReader(io.StringIO(text)))
    return [normalise_case(row, index) for index, row in enumerate(rows)]


def create_version(
    db: OrmSession,
    *,
    name: str,
    cases: list[dict],
    origin: str,
    description: str = '',
    changelog: str = '',
    parent_id: int | None = None,
    created_by: int | None = None,
    version: str | None = None,
) -> DatasetVersion:
    """Persist an immutable snapshot and its cases."""
    payload = [normalise_case(case, index) for index, case in enumerate(cases)]
    row = DatasetVersion(
        name=name,
        version=version or next_version(db, name),
        description=description,
        origin=origin,
        sha256=digest_cases(payload),
        parent_id=parent_id,
        changelog=changelog,
        created_by=created_by,
        created_at=utcnow(),
    )
    db.add(row)
    db.flush()
    for case in payload:
        db.add(DatasetCase(
            version_id=row.id,
            case_id=case['case_id'],
            category=case['category'],
            prompt=case['prompt'],
            goal=case['goal'],
            kind=case['kind'],
            metadata_json=case['metadata'],
        ))
    db.commit()
    return row


def cases_of(db: OrmSession, version_id: int) -> list[dict]:
    rows = db.scalars(
        select(DatasetCase).where(DatasetCase.version_id == version_id)
        .order_by(DatasetCase.case_id)
    ).all()
    return [{
        'id': case.id,
        'case_id': case.case_id,
        'category': case.category,
        'prompt': case.prompt,
        'goal': case.goal,
        'kind': case.kind,
        'metadata': case.metadata_json or {},
    } for case in rows]


def diff_versions(db: OrmSession, left_id: int, right_id: int) -> dict:
    """Structural diff between two versions, by case_id."""
    left = {case['case_id']: case for case in cases_of(db, left_id)}
    right = {case['case_id']: case for case in cases_of(db, right_id)}
    added = sorted(set(right) - set(left))
    removed = sorted(set(left) - set(right))
    changed = []
    for case_id in sorted(set(left) & set(right)):
        before, after = left[case_id], right[case_id]
        fields = [field for field in ('prompt', 'goal', 'category', 'kind')
                  if before.get(field) != after.get(field)]
        if fields:
            changed.append({'case_id': case_id, 'fields': fields})
    return {'added': added, 'removed': removed, 'changed': changed}


def import_builtin(db: OrmSession, datasets_dir: Path, name: str,
                   created_by: int | None = None) -> DatasetVersion:
    """Seed a dataset from the benchmark files shipped with the suite."""
    if name not in BUILTIN_SOURCES:
        raise ValueError(f'Unknown builtin dataset: {name}')
    relative, kind = BUILTIN_SOURCES[name]
    path = datasets_dir / relative
    if not path.exists():
        raise FileNotFoundError(f'Builtin file missing: {path}')
    cases = parse_bundle(path)
    return create_version(
        db, name=name, cases=cases, origin='builtin',
        description=f'Импортировано из {relative}',
        changelog='Первичный импорт из комплекта',
        created_by=created_by,
    )


def import_bundle(db: OrmSession, name: str, path: Path, *,
                  origin: str = 'config', created_by: int | None = None,
                  description: str = '', changelog: str = '') -> DatasetVersion:
    cases = parse_bundle(path)
    if not cases:
        raise ValueError('Bundle contains no cases')
    latest = db.scalars(
        select(DatasetVersion).where(DatasetVersion.name == name)
        .order_by(DatasetVersion.id.desc())
    ).first()
    return create_version(
        db, name=name, cases=cases, origin=origin, description=description,
        changelog=changelog or f'Импорт из {path.name}',
        parent_id=latest.id if latest else None, created_by=created_by,
    )


def materialise(db: OrmSession, version_ids: list[int], destination: Path) -> dict[str, str]:
    """Write selected versions to disk in the layout the engine expects.

    Returns a mapping ``dataset name -> file path`` so the caller can log what
    a run actually consumed.
    """
    destination.mkdir(parents=True, exist_ok=True)
    written: dict[str, str] = {}
    for version_id in version_ids:
        version = db.get(DatasetVersion, version_id)
        if version is None:
            continue
        cases = cases_of(db, version_id)
        relative = f'{version.name}-{version.version}.jsonl'
        path = destination / relative
        with path.open('w', encoding='utf-8') as handle:
            for case in cases:
                handle.write(json.dumps({
                    'case_id': case['case_id'],
                    'category': case['category'],
                    'prompt': case['prompt'],
                    'goal': case['goal'],
                    'kind': case['kind'],
                    **(case['metadata'] or {}),
                }, ensure_ascii=False) + '\n')
        written[version.name] = str(path)
    return written


def export_version(db: OrmSession, version_id: int, destination: Path) -> Path:
    """Dump a version as a portable JSONL bundle."""
    version = db.get(DatasetVersion, version_id)
    if version is None:
        raise ValueError('Version not found')
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open('w', encoding='utf-8') as handle:
        for case in cases_of(db, version_id):
            handle.write(json.dumps(case, ensure_ascii=False) + '\n')
    return destination
