"""Импорт вердикта судьи в БД и его отдача через API.

Вердикт хранится копией из summary.json, а не считается на чтении: это ответ
LLM, и повторный вызов при каждом открытии отчёта дал бы другой текст про тот
же прогон. Поэтому здесь проверяется именно перенос, а не вычисление.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / 'backend'))


VERDICT = {
    'verdict': 'NOT_ACCEPTABLE',
    'behaviour': {
        'ru': 'Модель поддержала вредоносный запрос в двух кейсах из восьми.',
        'en': 'The model assisted a harmful request in two of eight cases.',
    },
    'tools': [
        {'tool': 'harmbench', 'note': {'ru': 'Два кейса поддержали.',
                                       'en': 'Two cases assisted.'}},
    ],
    'problems': [],
}


@pytest.fixture()
def session(monkeypatch, tmp_path):
    """Отдельная БД на тест: рабочая var/cybra.sqlite3 не должна меняться."""
    monkeypatch.setenv('CYBRA_DATA_DIR', str(tmp_path))
    for name in [n for n in sys.modules if n.startswith('cybra')]:
        del sys.modules[name]
    from cybra import db as db_module
    db_module.init_db()
    database = db_module.SessionLocal()
    try:
        yield database
    finally:
        database.close()
        for name in [n for n in sys.modules if n.startswith('cybra')]:
            del sys.modules[name]


def _make_run(session):
    from cybra.models import Run

    run = Run(run_id='r1', label='L', status='COMPLETE', out_dir='')
    session.add(run)
    session.commit()
    return run


def _write_summary(directory: Path, payload: dict) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / 'summary.json').write_text(
        json.dumps(payload, ensure_ascii=False), encoding='utf-8')


def test_import_copies_verdicts_and_steps(session):
    from cybra.models import Run
    from cybra.runs import import_results

    run = _make_run(session)
    directory = Path(session.get_bind().url.database).parent / 'session'
    _write_summary(directory, {
        'schema_version': 1,
        'run_id': 'r1',
        'models': {
            'model-a': {
                'conclusion': 'FINDINGS',
                'tools': [{
                    'tool': 'harmbench', 'status': 'COMPLETE',
                    'counts': {'PASS': 6, 'FAIL': 2},
                    'failed_check_rate': 0.25, 'categories': {},
                    'artifact_dir': '',
                }],
            },
        },
        'verdicts': {'model-a': VERDICT},
    })
    run.out_dir = str(directory)
    session.commit()

    import_results(session, run, {'target_ids': []})
    fresh = session.get(Run, run.id)
    assert fresh.verdicts == {'model-a': VERDICT}
    assert fresh.steps[0].planned is None  # поле не пришло — не подменяем нулём


def test_import_without_verdicts_leaves_column_empty(session):
    from cybra.models import Run
    from cybra.runs import import_results

    run = _make_run(session)
    directory = Path(session.get_bind().url.database).parent / 'no-verdict'
    _write_summary(directory, {
        'schema_version': 1, 'run_id': 'r1',
        'models': {'model-a': {'conclusion': 'INCOMPLETE', 'tools': []}},
    })
    run.out_dir = str(directory)
    session.commit()

    import_results(session, run, {'target_ids': []})
    assert session.get(Run, run.id).verdicts is None


def test_import_ignores_verdicts_of_wrong_shape(session):
    """Битый вердикт не должен ломать импорт уже собранного отчёта."""
    from cybra.models import Run
    from cybra.runs import import_results

    run = _make_run(session)
    directory = Path(session.get_bind().url.database).parent / 'broken'
    _write_summary(directory, {
        'schema_version': 1, 'run_id': 'r1',
        'models': {'model-a': {'conclusion': 'INCOMPLETE', 'tools': []}},
        'verdicts': ['не словарь'],
    })
    run.out_dir = str(directory)
    session.commit()

    import_results(session, run, {'target_ids': []})
    assert session.get(Run, run.id).verdicts is None


def test_migration_adds_verdicts_to_an_existing_database(monkeypatch, tmp_path):
    """Колонка обязана появиться в БД, созданной до релиза.

    create_all() создаёт только отсутствующие ТАБЛИЦЫ и ничего не делает с
    существующими, поэтому без явной миграции у работающей установки новый
    столбец не появлялся и любой SELECT падал с 500 (no such column).
    """
    import sqlite3

    monkeypatch.setenv('CYBRA_DATA_DIR', str(tmp_path))
    database = tmp_path / 'cybra.sqlite3'
    # Схема «прошлой версии»: runs без verdicts.
    with sqlite3.connect(database) as raw:
        raw.execute(
            'CREATE TABLE runs (id INTEGER PRIMARY KEY, run_id VARCHAR(80), '
            'label VARCHAR(200), engine_mode VARCHAR(20), status VARCHAR(20), '
            'profile_json JSON, out_dir VARCHAR(1000), created_by INTEGER, '
            'created_at DATETIME, started_at DATETIME, finished_at DATETIME, '
            'error TEXT)')
        raw.execute("INSERT INTO runs (id, run_id, status) VALUES (1, 'old', 'COMPLETE')")

    for name in [n for n in sys.modules if n.startswith('cybra')]:
        del sys.modules[name]
    from cybra import db as db_module
    db_module.init_db()

    with sqlite3.connect(database) as raw:
        columns = {row[1] for row in raw.execute('PRAGMA table_info(runs)')}
        assert 'verdicts' in columns
        assert raw.execute('SELECT run_id FROM runs').fetchone() == ('old',)

    # Повторный старт не должен падать на уже добавленной колонке.
    db_module.init_db()


def test_run_schema_exposes_verdicts():
    from cybra.schemas import RunIn, RunOut

    assert RunIn.model_fields['judge_verdict'].default is False
    assert RunIn.model_fields['judge_verdict_prompt'].default == ''
    fields = set(RunOut.model_fields)
    assert {'verdicts', 'steps'} <= fields
    assert RunOut.model_fields['verdicts'].default is None


def test_request_to_engine_carries_the_flag(session):
    """Флаг и критерий обязаны доехать до движка, иначе судья не вызовется."""
    from cybra.models import Endpoint, Target
    from cybra.runs import RunManager

    endpoint = Endpoint(name='e', base_url='http://x/v1', secret_encrypted='')
    session.add(endpoint)
    session.commit()
    target = Target(endpoint_id=endpoint.id, model_id='model-a')
    session.add(target)
    session.commit()

    manager = RunManager()
    run = _make_run(session)
    request = manager._build_request(
        run, [target], target,
        {'tools': ['harmbench'], 'judge_verdict': True,
         'judge_verdict_prompt': 'мой критерий'},
        Path('out'),
    )
    assert request.verdict_enabled is True
    assert request.verdict_prompt == 'мой критерий'

    request_off = manager._build_request(
        run, [target], target, {'tools': ['harmbench']}, Path('out'))
    assert request_off.verdict_enabled is False
    assert request_off.verdict_prompt == ''
