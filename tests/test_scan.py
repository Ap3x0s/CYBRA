"""Tests for the scan layer: engine selection, capabilities and mock artifacts."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from scan import get_engine, load_manifest, load_records, load_summary  # noqa: E402
from scan.contract import EngineError, JudgeConfig, RunRequest, Target  # noqa: E402


def _request(tmp_path: Path, tools=('harmbench',)) -> RunRequest:
    return RunRequest(
        run_id='test-run-001',
        out_dir=tmp_path / 'run',
        targets=[Target(endpoint='http://127.0.0.1:1/v1/chat/completions',
                        model='model-a')],
        tools=list(tools),
        judge=JudgeConfig(endpoint='http://127.0.0.1:1/v1/chat/completions',
                          model='judge-a'),
        datasets_dir=REPO_ROOT / 'datasets',
        limit=3,
    )


def test_unknown_engine_rejected():
    with pytest.raises(EngineError):
        get_engine('telepathy')


def test_mock_engine_writes_the_real_artifact_contract(tmp_path):
    """The mock must produce the same files the importer reads."""
    request = _request(tmp_path, tools=['harmbench', 'security-regression'])
    handle = get_engine('mock').start(request)
    code = handle.wait(timeout=120)
    assert code == 0

    manifest = load_manifest(request.out_dir)
    assert manifest['mode'] == 'mock'
    assert manifest['models'] == ['model-a']

    summary = load_summary(request.out_dir)
    assert 'model-a' in summary['models']
    tools = {step['tool'] for step in summary['models']['model-a']['tools']}
    assert tools == {'harmbench', 'security-regression'}
    for step in summary['models']['model-a']['tools']:
        assert step['status'] == 'COMPLETE'
        assert step['counts']['PASS'] + step['counts']['FAIL'] > 0
        assert step['failed_check_rate'] is not None

    records = load_records(request.out_dir)
    assert records
    assert all(row['status'] in ('PASS', 'FAIL') for row in records)


def test_mock_progress_reports_steps(tmp_path):
    request = _request(tmp_path, tools=['harmbench'])
    handle = get_engine('mock').start(request)
    handle.wait(timeout=120)
    progress = handle.poll()
    assert progress.requests['target'] > 0
    assert any('COMPLETE' in step for step in progress.finished_steps)


def test_mock_engine_writes_the_reports_not_only_the_summary(tmp_path):
    """Демо-прогон обязан давать report.md и report.html.

    Раньше мок заканчивался на summary.json: кнопки «Скачать .md» и «Отчёт
    для печати» в демо-режиме отдавали 404, а общий вердикт судьи негде было
    показать. Отчёт демо должен быть тем же документом, что и настоящий.
    """
    request = _request(tmp_path, tools=['harmbench'])
    handle = get_engine('mock').start(request)
    assert handle.wait(timeout=120) == 0

    markdown = request.out_dir / 'report.md'
    html = request.out_dir / 'report.html'
    assert markdown.exists() and html.exists()
    text = markdown.read_text(encoding='utf-8')
    assert 'model-a' in text
    assert '| Инструмент |' in text, 'таблица не собралась'
    # Отчёт демо не должен выглядеть настоящим: в .md стоит русская врезка,
    # в .html — та же мысль, поэтому проверяем смысл, а не слово «mock».
    assert 'демонстрационном режиме' in text
    assert 'синтетические' in text


def test_mock_manifest_marks_the_demo_mode(tmp_path):
    """engine_mode в manifest: по нему отчёт ставит врезку «синтетика»."""
    request = _request(tmp_path, tools=['harmbench'])
    handle = get_engine('mock').start(request)
    handle.wait(timeout=120)
    manifest = load_manifest(request.out_dir)
    assert manifest['engine_mode'] == 'mock'
    assert 'model_dirs' in manifest


def test_mock_engine_handles_models_sharing_a_prefix(tmp_path):
    """model-a и model-b не должны читать один каталог.

    Без model_dirs отчёт восстанавливал каталоги по префиксу слага, и две
    модели с общим началом имени валились с Model/tool mismatch.
    """
    request = RunRequest(
        run_id='prefixes',
        out_dir=tmp_path / 'run',
        targets=[
            Target(endpoint='http://127.0.0.1:1/v1/chat/completions', model='model-a'),
            Target(endpoint='http://127.0.0.1:1/v1/chat/completions', model='model-b'),
        ],
        tools=['harmbench'],
        judge=JudgeConfig(endpoint='http://127.0.0.1:1/v1/chat/completions',
                          model='judge-a'),
        datasets_dir=REPO_ROOT / 'datasets',
        limit=2,
    )
    handle = get_engine('mock').start(request)
    assert handle.wait(timeout=120) == 0

    summary = load_summary(request.out_dir)
    assert set(summary['models']) == {'model-a', 'model-b'}
    for result in summary['models'].values():
        assert result['tools'][0]['counts']['PASS'] >= 0
    assert (request.out_dir / 'report.md').exists()


def test_cancel_stops_the_mock_run(tmp_path):
    request = _request(tmp_path, tools=['garak', 'pyrit', 'agentdojo', 'promptfoo'])
    handle = get_engine('mock').start(request)
    handle.cancel()
    assert handle.cancelled
    assert handle.wait(timeout=30) == 130
    # Cancelling early must leave a partial directory, not a crash.
    assert request.out_dir.exists()


def test_capabilities_cover_every_tool():
    from scan.capabilities import TOOLS, capabilities

    rows = capabilities()
    assert {row['tool'] for row in rows} == set(TOOLS)
    for row in rows:
        assert isinstance(row['available'], bool)
        if not row['available']:
            assert row['install_hint']


def test_subprocess_engine_command_is_assembled_without_secrets(tmp_path):
    """API keys must travel through the environment, never argv."""
    from scan.engine import SubprocessEngine

    request = _request(tmp_path)
    object.__setattr__(request.targets[0], 'api_key', 'sk-should-not-appear')
    engine = SubprocessEngine(python='python')
    command = engine._command(request)
    assert 'sk-should-not-appear' not in ' '.join(command)
    assert '--judge-model' in command
    assert 'judge-a' in command
