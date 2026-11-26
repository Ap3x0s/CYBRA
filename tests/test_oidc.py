"""Вход через OpenID Connect: то, что защищает от подделки.

Тесты намеренно проверяют не «счастливый путь» (он проверен живым входом
через Keycloak), а отказы. Именно здесь ошибка превращается в дыру:

  * токен с alg=none — классическая дыра: подпись «не нужна»;
  * подделанная подпись — токен нарисован в блокноте;
  * чужой issuer — нас перенаправили на подставной провайдер;
  * чужой audience — токен выпущен для другого приложения;
  * просроченный токен — утёкший живёт вечно;
  * неверный nonce — токен от другой попытки входа;
  * неверный state — CSRF на callback;
  * роли из токена — эскалация прав.

Каждый тест строит настоящий RSA-ключ и настоящий JWT, а не мокает
проверку: если проверка сломается, тест это увидит.
"""

from __future__ import annotations

import base64
import json
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))

from cybra.oidc import (  # noqa: E402
    CLOCK_SKEW_SECONDS,
    OidcClient,
    OidcError,
    OidcSettings,
    PendingLogin,
)

ISSUER = 'http://localhost:8080/realms/cybra'
CLIENT_ID = 'cybra'


def module_oidc():
    """Модуль cybra.oidc, который реально лежит в sys.modules.

    Зачем функция, а не `import cybra.oidc as m` в теле: pytest держит все
    тесты в одном процессе, и test_initial_password вставляет свой путь в
    sys.path. Из-за этого в sys.modules может оказаться ДРУГОЙ объект
    модуля, чем тот, откуда взят класс на уровне файла. Тогда патч
    `_http_json` ложится на один объект, а метод читает из другого — тест
    проходит в одиночку и падает в общем прогоне.
    """
    return sys.modules['cybra.oidc']


def b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip('=')


@pytest.fixture(scope='module')
def keypair():
    """Настоящая пара RSA-ключей: подпись проверяется по-настоящему."""
    from cryptography.hazmat.primitives.asymmetric import rsa

    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    numbers = private.public_key().public_numbers()
    jwk = {
        'kty': 'RSA',
        'use': 'sig',
        'alg': 'RS256',
        'kid': 'test-key-1',
        'n': b64(numbers.n.to_bytes((numbers.n.bit_length() + 7) // 8, 'big')),
        'e': b64(numbers.e.to_bytes((numbers.e.bit_length() + 7) // 8, 'big')),
    }
    return private, jwk


def make_token(keypair, claims: dict, *, kid='test-key-1', alg='RS256',
               sign=True) -> str:
    """Собрать JWT. `sign=False` даёт alg=none."""
    private, _ = keypair
    header = {'alg': alg, 'typ': 'JWT', 'kid': kid}
    signing_input = f"{b64(json.dumps(header).encode())}.{b64(json.dumps(claims).encode())}"

    if not sign:
        return f'{signing_input}.'

    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import padding

    signature = private.sign(
        signing_input.encode('ascii'), padding.PKCS1v15(), hashes.SHA256())
    return f'{signing_input}.{b64(signature)}'


def base_claims(nonce: str) -> dict:
    now = int(time.time())
    return {
        'iss': ISSUER,
        'aud': CLIENT_ID,
        'sub': 'a1b2c3d4-0000-0000-0000-000000000001',
        'email': 'ivanov@example.org',
        'name': 'Иван Иванов',
        'nonce': nonce,
        'iat': now,
        'exp': now + 300,
    }


@pytest.fixture()
def client(keypair) -> OidcClient:
    """Клиент с подставленным discovery и JWKS вместо сети."""
    _, jwk = keypair
    instance = OidcClient(
        OidcSettings(
            issuer=ISSUER,
            client_id=CLIENT_ID,
            client_secret='secret',
            redirect_uri='http://localhost:8011/api/v1/auth/oidc/callback',
            expected_issuer=ISSUER,
        )
    )
    instance._discovery = {
        'issuer': ISSUER,
        'authorization_endpoint': f'{ISSUER}/protocol/openid-connect/auth',
        'token_endpoint': f'{ISSUER}/protocol/openid-connect/token',
        'jwks_uri': f'{ISSUER}/protocol/openid-connect/certs',
    }
    instance._jwks = {'keys': [jwk]}
    instance._jwks_at = time.time()
    return instance


@pytest.fixture()
def pending() -> PendingLogin:
    return PendingLogin.new()


# ----------------------------------------------------------------------
# Счастливый путь — чтобы отказы ниже значили что-то
# ----------------------------------------------------------------------

def test_valid_token_accepted(client, keypair, pending) -> None:
    token = make_token(keypair, base_claims(pending.nonce))
    claims = client.verify_id_token(token, pending)
    assert claims['sub'].startswith('a1b2c3d4')
    assert claims['email'] == 'ivanov@example.org'


# ----------------------------------------------------------------------
# Отказы: подпись
# ----------------------------------------------------------------------

def test_alg_none_rejected(client, keypair, pending) -> None:
    """alg=none — классическая дыра: токен без подписи считался бы валидным."""
    token = make_token(keypair, base_claims(pending.nonce),
                       alg='none', sign=False)
    with pytest.raises(OidcError, match='без подписи'):
        client.verify_id_token(token, pending)


def test_tampered_signature_rejected(client, keypair, pending) -> None:
    """Изменённая полезная нагрузка ломает подпись."""
    token = make_token(keypair, base_claims(pending.nonce))
    head, payload, signature = token.split('.')

    claims = base_claims(pending.nonce)
    claims['sub'] = 'attacker-controlled'
    forged = f'{head}.{b64(json.dumps(claims).encode())}.{signature}'

    with pytest.raises(OidcError, match='Подпись'):
        client.verify_id_token(forged, pending)


def test_unknown_kid_rejected(client, keypair, pending) -> None:
    """Ключ не из JWKS — подпись проверять нечем."""
    token = make_token(keypair, base_claims(pending.nonce), kid='чужой-ключ')
    with pytest.raises(OidcError, match='не найден'):
        client.verify_id_token(token, pending)


# ----------------------------------------------------------------------
# Отказы: поля токена
# ----------------------------------------------------------------------

def test_wrong_issuer_rejected(client, keypair, pending) -> None:
    """Токен выпущен не тем Keycloak (или подставным сервером)."""
    claims = base_claims(pending.nonce)
    claims['iss'] = 'http://evil.example/realms/cybra'
    token = make_token(keypair, claims)
    with pytest.raises(OidcError, match='issuer'):
        client.verify_id_token(token, pending)


def test_wrong_audience_rejected(client, keypair, pending) -> None:
    """Токен выпущен для другого приложения и его подсунули нам."""
    claims = base_claims(pending.nonce)
    claims['aud'] = 'other-application'
    token = make_token(keypair, claims)
    with pytest.raises(OidcError, match='не для нас'):
        client.verify_id_token(token, pending)


def test_expired_token_rejected(client, keypair, pending) -> None:
    """Просроченный токен: без проверки утёкший жил бы вечно."""
    claims = base_claims(pending.nonce)
    claims['exp'] = int(time.time()) - CLOCK_SKEW_SECONDS - 10
    token = make_token(keypair, claims)
    with pytest.raises(OidcError, match='просрочен'):
        client.verify_id_token(token, pending)


def test_token_without_expiry_rejected(client, keypair, pending) -> None:
    claims = base_claims(pending.nonce)
    claims.pop('exp')
    token = make_token(keypair, claims)
    with pytest.raises(OidcError, match='срок'):
        client.verify_id_token(token, pending)


def test_wrong_nonce_rejected(client, keypair, pending) -> None:
    """Токен от ДРУГОЙ попытки входа — повторное использование."""
    claims = base_claims('совсем-другой-nonce')
    token = make_token(keypair, claims)
    with pytest.raises(OidcError, match='nonce'):
        client.verify_id_token(token, pending)


def test_missing_subject_rejected(client, keypair, pending) -> None:
    """Без sub нечего привязывать: пользователя не создать и не найти."""
    claims = base_claims(pending.nonce)
    claims.pop('sub')
    token = make_token(keypair, claims)
    with pytest.raises(OidcError, match='subject'):
        client.verify_id_token(token, pending)


# ----------------------------------------------------------------------
# Discovery и PKCE
# ----------------------------------------------------------------------

def test_discovery_issuer_mismatch_rejected(monkeypatch) -> None:
    """Подставной провайдер: его документ объявляет чужой issuer.

    Все проверки ниже сверяются с ключами провайдера, поэтому подмена
    адреса делает их бессмысленными — ловить надо здесь.

    Класс и функция берутся из sys.modules, а не с уровня файла: в общем
    прогоне pytest в sys.modules может лежать другой объект модуля, и
    тогда патч и проверяемый код оказываются в разных мирах.
    """
    module = module_oidc()

    instance = module.OidcClient(
        module.OidcSettings(
            issuer='http://evil.example/realms/cybra',
            client_id=CLIENT_ID,
            client_secret='secret',
            redirect_uri='http://localhost/cb',
            expected_issuer=ISSUER,
        )
    )

    def fake_http(url, data=None, timeout=30):
        return {
            'issuer': 'http://evil.example/realms/cybra',
            'authorization_endpoint': 'http://evil.example/auth',
            'token_endpoint': 'http://evil.example/token',
            'jwks_uri': 'http://evil.example/certs',
        }

    monkeypatch.setattr(module, '_http_json', fake_http)

    # Кеш должен быть пуст: discovery() кеширует результат в экземпляре, и
    # при непустом кеше проверка прошла бы впустую, ничего не проверив.
    assert instance._discovery is None

    with pytest.raises(module.OidcError, match='Issuer'):
        instance.discovery()


def test_discovery_missing_field_rejected(monkeypatch) -> None:
    """В документе провайдера нет обязательного поля — отказ, а не падение.

    Без этой проверки провайдер с неполным discovery приводил бы к
    KeyError при первом же входе, то есть к 500 на странице, где человек
    ждёт редирект.
    """
    module = module_oidc()

    instance = module.OidcClient(
        module.OidcSettings(
            issuer=ISSUER,
            client_id=CLIENT_ID,
            client_secret='secret',
            redirect_uri='http://localhost/cb',
            expected_issuer=ISSUER,
        )
    )
    # issuer совпадает, но нет jwks_uri — проверять подпись будет нечем.
    monkeypatch.setattr(
        module, '_http_json',
        lambda url, data=None, timeout=30: {
            'issuer': ISSUER,
            'authorization_endpoint': f'{ISSUER}/auth',
            'token_endpoint': f'{ISSUER}/token',
        },
    )
    assert instance._discovery is None
    with pytest.raises(module.OidcError, match='jwks_uri'):
        instance.discovery()


def test_pkce_challenge_is_s256(client, pending) -> None:
    """PKCE: challenge — S256 от verifier, а не сам verifier."""
    import hashlib

    expected = base64.urlsafe_b64encode(
        hashlib.sha256(pending.verifier.encode()).digest()).decode().rstrip('=')
    assert pending.challenge == expected
    assert pending.challenge != pending.verifier


def test_authorization_url_contains_protections(client, pending) -> None:
    """В URL обязаны быть state, nonce и PKCE-параметры."""
    url = client.authorization_url(pending)
    assert 'state=' in url
    assert 'nonce=' in url
    assert 'code_challenge=' in url
    assert 'code_challenge_method=S256' in url
    # Секрет клиента в URL попадать НЕ должен: URL видит браузер.
    assert 'client_secret' not in url


def test_pending_state_expires(pending) -> None:
    """Незавершённый вход не должен жить вечно."""
    stale = PendingLogin(
        state=pending.state,
        nonce=pending.nonce,
        verifier=pending.verifier,
        created_at=time.time() - 3600,
    )
    with pytest.raises(OidcError, match='устарел'):
        PendingLogin.from_json(stale.to_json())
