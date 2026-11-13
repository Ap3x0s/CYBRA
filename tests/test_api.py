"""End-to-end API tests against a temporary database.

These tests use the mock engine on purpose: they must pass on a machine with no
API key, no garak and no network access to a model.
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

# Configure the app before importing it.
_TEMP = tempfile.mkdtemp(prefix='cybra-test-')
os.environ['CYBRA_DATA_DIR'] = _TEMP
os.environ['CYBRA_ENGINE'] = 'mock'
os.environ['CYBRA_SECRET_KEY'] = 'test-secret-key'

REPO_ROOT = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(REPO_ROOT / 'backend'))
sys.path.insert(0, str(REPO_ROOT))

from fastapi.testclient import TestClient  # noqa: E402

from cybra.main import bootstrap_admin, create_app  # noqa: E402


@pytest.fixture(scope='session')
def client():
    app = create_app()
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(scope='session')
def admin_user(client):
    """Create one admin account for the whole test session."""
    from cybra.db import SessionLocal
    from cybra.models import User
    from cybra.security import hash_password

    db = SessionLocal()
    existing = db.query(User).filter(User.email == 'tester@example.com').first()
    if existing is None:
        db.add(User(email='tester@example.com', display_name='Tester',
                    password_hash=hash_password('correct-horse-battery'), role='admin'))
        db.commit()
    db.close()
    return {'email': 'tester@example.com', 'password': 'correct-horse-battery'}


@pytest.fixture
def admin(client, admin_user):
    """Log in fresh per test: the CSRF token is bound to one session."""
    response = client.post('/api/v1/auth/login', json=admin_user)
    assert response.status_code == 200, response.text
    return response.json()


@pytest.fixture
def headers(admin):
    return {'x-csrf-token': admin['csrf_token']}


def test_health(client):
    assert client.get('/api/v1/health').json()['status'] == 'ok'


def test_requires_auth(client):
    assert client.get('/api/v1/runs').status_code == 401


def test_login_rejects_wrong_password(client):
    response = client.post('/api/v1/auth/login',
                           json={'email': 'tester@example.com', 'password': 'nope'})
    assert response.status_code == 401


def test_csrf_required_for_mutating_requests(client, admin):
    client.post('/api/v1/auth/login',
                json={'email': 'tester@example.com', 'password': 'correct-horse-battery'})
    response = client.post('/api/v1/endpoints', json={
        'name': 'x', 'base_url': 'http://127.0.0.1:9'})
    assert response.status_code == 403


def test_capabilities_listed(client, admin):
    rows = client.get('/api/v1/capabilities').json()
    names = {row['tool'] for row in rows}
    assert {'harmbench', 'jailbreakbench', 'bipia'} <= names

    # Контракт, а не состояние машины: раньше тест требовал непустой
    # install_hint хотя бы у одного инструмента. Но hint появляется ТОЛЬКО у
    # неустановленных, поэтому после установки всех восьми тест падал, хотя
    # API работал верно. Проверяем инвариант: поля есть всегда, а hint связан
    # с доступностью.
    for row in rows:
        assert 'tool' in row and 'available' in row
        assert 'install_hint' in row
        assert (row['install_hint'] is None) == bool(row['available']), row


def test_metrics_catalog_explains_every_metric(client, admin):
    catalog = client.get('/api/v1/metrics/catalog').json()
    assert len(catalog) >= 8
    for entry in catalog:
        assert entry['description']
        assert entry['formula']
        assert entry['caveat']


def test_dataset_seed_and_versions(client, admin, headers):
    templates = client.get('/api/v1/datasets/templates').json()
    assert any(item['name'] == 'corporate' for item in templates)

    response = client.post('/api/v1/datasets/seed', json={'name': 'corporate'},
                           headers=headers)
    assert response.status_code == 201, response.text
    version = response.json()
    assert version['case_count'] > 0

    cases = client.get(f"/api/v1/datasets/{version['id']}/cases").json()
    assert cases
    assert 'prompt' in cases[0]


def test_dataset_edit_forks_new_version(client, admin, headers):
    versions = client.get('/api/v1/datasets').json()
    corporate = [v for v in versions if v['name'] == 'corporate']
    parent = corporate[0]
    cases = client.get(f"/api/v1/datasets/{parent['id']}/cases").json()
    target = cases[0]

    response = client.put(
        f"/api/v1/datasets/{parent['id']}/cases/{target['id']}",
        json={'case_id': target['case_id'], 'category': 'edited',
              'prompt': 'изменённый промпт', 'goal': 'g', 'kind': 'harmful'},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    child = response.json()
    assert child['parent_id'] == parent['id']
    assert child['origin'] == 'ui'
    assert child['sha256'] != parent['sha256']

    diff = client.get(f"/api/v1/datasets/diff?left={parent['id']}&right={child['id']}").json()
    assert diff['changed'], diff

    # The parent must be untouched: that is the point of immutability.
    unchanged = client.get(f"/api/v1/datasets/{parent['id']}/cases").json()
    assert unchanged[0]['prompt'] == target['prompt']


def test_endpoint_never_returns_secret(client, admin, headers):
    response = client.post('/api/v1/endpoints', json={
        'name': 'Local', 'base_url': 'http://127.0.0.1:8765/v1',
        'api_key': 'super-secret-value',
    }, headers=headers)
    assert response.status_code == 201, response.text
    body = response.json()
    assert 'api_key' not in body
    assert 'super-secret-value' not in response.text
    assert body['secret_hint'] == 'alue'
    assert body['has_secret'] is True


def test_full_mock_run_produces_report(client, admin, headers):
    # The run manager is process-wide: wait for any previous run to settle so a
    # stale "busy" state cannot make this test flaky.
    import time
    from cybra.runs import manager
    for _ in range(80):
        if not manager.is_busy():
            break
        time.sleep(0.25)

    # Build endpoint -> target -> seed dataset -> run.
    endpoint = client.post('/api/v1/endpoints', json={
        'name': 'Mock', 'base_url': 'http://127.0.0.1:8765/v1',
    }, headers=headers).json()
    target = client.post('/api/v1/targets', json={
        'endpoint_id': endpoint['id'], 'model_id': 'mock-model-a',
    }, headers=headers)
    assert target.status_code == 201, target.text
    target = target.json()

    seeded = client.get('/api/v1/datasets').json()
    version = [v for v in seeded if v['name'] == 'corporate'][0]

    created = client.post('/api/v1/runs', json={
        'label': 'pytest run',
        'target_ids': [target['id']],
        'judge_target_id': target['id'],
        'tools': ['harmbench', 'security-regression'],
        'dataset_version_ids': [version['id']],
        'engine_mode': 'mock',
        'limit': 4,
    }, headers=headers)
    assert created.status_code == 201, created.text
    run = created.json()

    # Wait for the worker thread to finish (mock is fast).
    for _ in range(200):
        current = client.get(f"/api/v1/runs/{run['id']}").json()
        if current['status'] in ('COMPLETE', 'PARTIAL', 'ERROR', 'CANCELLED'):
            break
        time.sleep(0.25)

    final = client.get(f"/api/v1/runs/{run['id']}").json()
    assert final['status'] == 'COMPLETE', final
    assert len(final['steps']) == 2, final
    assert all(step['completeness'] == 'COMPLETE' for step in final['steps'])
    assert all(step['counts']['PASS'] + step['counts']['FAIL'] > 0 for step in final['steps'])

    findings = client.get(f"/api/v1/runs/{run['id']}/findings").json()
    assert findings
    assert {finding['verdict'] for finding in findings} <= {'PASS', 'FAIL'}

    report = client.get(f"/api/v1/runs/{run['id']}/report?fmt=json")
    assert report.status_code == 200
    assert 'models' in report.json()

    series = client.get(
        f"/api/v1/metrics/series?metric=failed_check_rate&limit=10").json()
    assert series
    assert 0.0 <= series[0]['value'] <= 1.0
