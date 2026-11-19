"""Критерий вердикта приходит на языке интерфейса.

Заготовок две, и это не перевод ради галочки: человек в EN-интерфейсе должен
прочитать критерий, который включает, на своём языке. Плюс важная деталь —
если поле не трогали, в прогон уходит ровно тот текст, который был на экране.
Раньше отправлялась пустая строка, и сервер подставлял РУССКИЙ критерий даже
в английском интерфейсе.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / 'backend'))


def _client(monkeypatch, tmp_path):
    monkeypatch.setenv('CYBRA_DATA_DIR', str(tmp_path))
    for name in [n for n in sys.modules if n.startswith('cybra')]:
        del sys.modules[name]
    from cybra.main import app
    from fastapi.testclient import TestClient

    return TestClient(app)


def _auth(client):
    """Первый запуск создаёт администратора; логинимся под ним же."""
    from cybra import main as main_module
    from cybra.config import settings

    # bootstrap_admin выполняется в lifespan; TestClient запускает его сам.
    with client:
        pass
    marker = settings.data_dir / 'initial-password'
    assert marker.exists(), 'маркер первого пароля не создан'
    password = marker.read_text(encoding='utf-8').strip()
    response = client.post('/api/v1/auth/login',
                           json={'email': 'admin@cybra.local', 'password': password})
    assert response.status_code == 200, response.text
    return main_module


def test_criterion_follows_the_language(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)
    _auth(client)

    ru = client.get('/api/v1/judge/criterion', params={'lang': 'ru'})
    en = client.get('/api/v1/judge/criterion', params={'lang': 'en'})
    assert ru.status_code == 200 and en.status_code == 200

    ru_text = ru.json()['criterion']
    en_text = en.json()['criterion']
    assert ru_text != en_text, 'язык не влияет на заготовку'

    # Русская заготовка — кириллицей, английская — без неё в начале текста.
    assert any('а' <= char.lower() <= 'я' for char in ru_text[:120])
    assert not any('а' <= char.lower() <= 'я' for char in en_text[:120])

    # Обе заготовки обязаны содержать ключевые правила, иначе они не эквивалентны.
    for text in (ru_text, en_text):
        assert 'INSUFFICIENT_EVIDENCE' in text
        assert 'NOT_ACCEPTABLE' in text
        assert 'ACCEPTABLE_WITH_CAVEATS' in text


def test_default_language_is_russian(monkeypatch, tmp_path):
    """Без параметра — русский: он язык по умолчанию у продукта."""
    client = _client(monkeypatch, tmp_path)
    _auth(client)
    from security_suite.verdict import DEFAULT_CRITERION

    payload = client.get('/api/v1/judge/criterion').json()
    assert payload['criterion'] == DEFAULT_CRITERION
    assert payload['lang'] == 'ru'


def test_unknown_language_is_rejected(monkeypatch, tmp_path):
    """Опечатка в языке не должна молча отдавать русский текст."""
    client = _client(monkeypatch, tmp_path)
    _auth(client)
    response = client.get('/api/v1/judge/criterion', params={'lang': 'de'})
    assert response.status_code == 422


def test_english_criterion_is_not_a_transliteration():
    """Английская заготовка должна быть самостоятельным текстом."""
    from security_suite.verdict import DEFAULT_CRITERION, DEFAULT_CRITERION_EN

    assert len(DEFAULT_CRITERION_EN) > 1500, 'заготовка подозрительно короткая'
    assert not any('а' <= char.lower() <= 'я' for char in DEFAULT_CRITERION_EN)

    # Обе заготовки описывают одни и те же правила.
    for phrase in ('garak', 'roleplay', 'PASS'):
        assert phrase in DEFAULT_CRITERION
        assert phrase in DEFAULT_CRITERION_EN

    # Язык письма разный: в русской заготовке требуется писать по-русски,
    # в английской — по-английски.
    assert 'по-русски' in DEFAULT_CRITERION
    assert 'English' in DEFAULT_CRITERION_EN


def test_verdict_prompt_limit_applies_to_both():
    """Критерий приходит из JSON профиля прогона и не должен его раздувать."""
    from security_suite.verdict import (
        DEFAULT_CRITERION,
        DEFAULT_CRITERION_EN,
        PROMPT_LIMIT,
        effective_criterion,
    )

    assert len(DEFAULT_CRITERION) < PROMPT_LIMIT
    assert len(DEFAULT_CRITERION_EN) < PROMPT_LIMIT
    assert len(effective_criterion('x' * (PROMPT_LIMIT + 10))) == PROMPT_LIMIT


if __name__ == '__main__':
    raise SystemExit(pytest.main([__file__, '-v']))
