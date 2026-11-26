"""Вход через OpenID Connect: обмен кода и проверка id_token.

Почему свой код, а не готовая библиотека. Задачу решают три вещи, и каждая
тянет своё: `authlib` умеет весь OAuth и тянет зависимость ради одного
потока; `python-keycloak` тянет админ-API Keycloak, который нам не нужен;
`fastapi-sso` навязывает свою модель сессии поверх нашей. Между тем
`cryptography` в зависимостях уже есть — подпись проверять есть чем, а
остальное это два HTTP-запроса и сверка полей.

Главное здесь не «получить токен», а **не поверить подделке**. Поэтому
каждая проверка ниже — не формальность:

  * подпись по JWKS — иначе токен можно нарисовать в блокноте;
  * `iss` — токен выпущен не тем Keycloak (или подставным сервером);
  * `aud` — токен выпущен для другого приложения, и его подсунули нам;
  * `exp` / `iat` / `nbf` — сроки; без них утёкший токен живёт вечно;
  * `nonce` — токен от другой попытки входа (повторное использование);
  * `state` — CSRF на callback: подсунули чужой `code`.

Плюс PKCE: для конфиденциального клиента формально не требуется, но
стоит одной пары строк и закрывает перехват кода на стороне браузера.
"""

from __future__ import annotations

import base64
import hashlib
import json
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

# Допустимое расхождение часов при проверке сроков. Без него токен,
# выпущенный секунду назад на сервере с чуть другим временем, отклонялся бы
# как «ещё не действительный».
CLOCK_SKEW_SECONDS = 60

# Сколько живёт незавершённый вход. Человек может задуматься на странице
# пароля, но не на полчаса.
PENDING_TTL_SECONDS = 600


class OidcError(Exception):
    """Ошибка обмена или проверки. Текст показывается оператору."""


@dataclass
class PendingLogin:
    """Состояние незавершённого входа, привязанное к браузеру.

    `state` и `nonce` выдаются на каждый вход заново и сверяются на
    callback. Хранятся в подписанной cookie, а не в памяти процесса: у
    uvicorn несколько воркеров, и callback может прийти в другой.
    """

    state: str
    nonce: str
    verifier: str
    created_at: float

    @property
    def challenge(self) -> str:
        """S256-преобразование verifier для PKCE."""
        digest = hashlib.sha256(self.verifier.encode()).digest()
        return base64.urlsafe_b64encode(digest).decode().rstrip("=")

    def is_fresh(self) -> bool:
        return time.time() - self.created_at < PENDING_TTL_SECONDS

    def to_json(self) -> str:
        return json.dumps(
            {
                "state": self.state,
                "nonce": self.nonce,
                "verifier": self.verifier,
                "created_at": self.created_at,
            },
            separators=(",", ":"),
        )

    @classmethod
    def new(cls) -> "PendingLogin":
        return cls(
            state=secrets.token_urlsafe(24),
            nonce=secrets.token_urlsafe(24),
            # 43..128 символов по RFC 7636; token_urlsafe(48) даёт около 64.
            verifier=secrets.token_urlsafe(48),
            created_at=time.time(),
        )

    @classmethod
    def from_json(cls, raw: str) -> "PendingLogin":
        try:
            data = json.loads(raw)
            pending = cls(
                state=str(data["state"]),
                nonce=str(data["nonce"]),
                verifier=str(data["verifier"]),
                created_at=float(data["created_at"]),
            )
        except (ValueError, KeyError, TypeError) as error:
            raise OidcError("Повреждённое состояние входа, начните заново") from error
        if not pending.is_fresh():
            raise OidcError("Вход устарел, начните заново")
        return pending


def _http_json(url: str, data: dict | None = None, timeout: int = 30) -> dict:
    """GET или POST с urlencoded-телом. Возвращает разобранный JSON."""
    if data is None:
        request = urllib.request.Request(url, headers={"Accept": "application/json"})
    else:
        request = urllib.request.Request(
            url,
            data=urllib.parse.urlencode(data).encode(),
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json",
            },
            method="POST",
        )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        detail = error.read(600).decode("utf-8", "replace")
        raise OidcError(f"Провайдер вернул HTTP {error.code}: {detail}") from error
    except urllib.error.URLError as error:
        raise OidcError(f"Провайдер недоступен: {error.reason}") from error
    except json.JSONDecodeError as error:
        raise OidcError("Провайдер вернул не JSON") from error


@dataclass
class OidcSettings:
    issuer: str
    client_id: str
    client_secret: str
    redirect_uri: str
    expected_issuer: str


class OidcClient:
    """Минимальный клиент authorization-code flow для FastAPI.

    Экземпляр не хранит состояния между запросами: всё, что нужно на
    callback, приходит в подписанной cookie. Так несколько воркеров и
    несколько параллельных входов не мешают друг другу.
    """

    def __init__(self, settings: OidcSettings) -> None:
        self.settings = settings
        self._discovery: dict | None = None
        self._jwks: dict | None = None
        # Ключи провайдера меняются редко, но при ротации старый кеш даст
        # ложный отказ. Держим недолго.
        self._jwks_at = 0.0

    # --- discovery и ключи ------------------------------------------

    def discovery(self) -> dict:
        """Документ `.well-known/openid-configuration`, кешируется."""
        if self._discovery is None:
            url = f"{self.settings.issuer}/.well-known/openid-configuration"
            document = _http_json(url)
            issuer = str(document.get("issuer", "")).rstrip("/")
            # Issuer из документа обязан совпасть с ожидаемым: иначе нас
            # перенаправили на чужой провайдер, и все проверки ниже
            # бессмысленны — они сверяются с его же ключами.
            if issuer != self.settings.expected_issuer.rstrip("/"):
                raise OidcError(
                    "Issuer провайдера не совпал с ожидаемым: "
                    f"{issuer!r} != {self.settings.expected_issuer!r}"
                )
            for field in ("authorization_endpoint", "token_endpoint", "jwks_uri"):
                if not document.get(field):
                    raise OidcError(f"В discovery нет поля {field}")
            self._discovery = document
        return self._discovery

    def jwks(self, force: bool = False) -> dict:
        if force or self._jwks is None or time.time() - self._jwks_at > 300:
            self._jwks = _http_json(self.discovery()["jwks_uri"])
            self._jwks_at = time.time()
        return self._jwks

    # --- шаг 1: отправка в провайдер --------------------------------

    def authorization_url(self, pending: PendingLogin) -> str:
        """Адрес, на который уходит браузер. Пароль вводится там, не у нас."""
        query = urllib.parse.urlencode(
            {
                "client_id": self.settings.client_id,
                "redirect_uri": self.settings.redirect_uri,
                "response_type": "code",
                "scope": "openid email profile",
                "state": pending.state,
                "nonce": pending.nonce,
                "code_challenge": pending.challenge,
                "code_challenge_method": "S256",
            }
        )
        return f"{self.discovery()['authorization_endpoint']}?{query}"

    # --- шаг 2: обмен кода на токены --------------------------------

    def exchange(self, code: str, pending: PendingLogin) -> dict:
        """Обменять `code` на токены. Секрет клиента уходит отсюда, с сервера."""
        tokens = _http_json(
            self.discovery()["token_endpoint"],
            {
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": self.settings.redirect_uri,
                "client_id": self.settings.client_id,
                "client_secret": self.settings.client_secret,
                "code_verifier": pending.verifier,
            },
        )
        if not tokens.get("id_token"):
            raise OidcError("Провайдер не вернул id_token")
        return tokens

    # --- шаг 3: проверка id_token -----------------------------------

    def verify_id_token(self, token: str, pending: PendingLogin) -> dict:
        """Проверить подпись и поля. Возвращает полезную нагрузку.

        Порядок важен: сначала подпись, потом поля. Если проверять поля
        неподписанного токена, злоумышленник подставит любые значения.
        """
        header, payload, signature = self._split(token)

        algorithm = str(header.get("alg", ""))
        # `none` — алгоритм «без подписи». Некоторые библиотеки его
        # принимают, и это классическая дыра: токен с alg=none считается
        # валидным без всякой проверки.
        if algorithm.lower() == "none":
            raise OidcError("Токен без подписи (alg=none) отклонён")

        key = self._find_key(header.get("kid"), algorithm)
        self._check_signature(token, key, algorithm)

        now = time.time()
        issuer = str(payload.get("iss", "")).rstrip("/")
        if issuer != self.settings.expected_issuer.rstrip("/"):
            raise OidcError(f"Неверный issuer в токене: {issuer!r}")

        audience = payload.get("aud")
        audiences = audience if isinstance(audience, list) else [audience]
        if self.settings.client_id not in audiences:
            raise OidcError(
                f"Токен выпущен не для нас: aud={audience!r}, ожидался {self.settings.client_id!r}"
            )

        expires = payload.get("exp")
        if not isinstance(expires, (int, float)):
            raise OidcError("В токене нет срока действия (exp)")
        if now > expires + CLOCK_SKEW_SECONDS:
            raise OidcError("Токен просрочен")

        issued = payload.get("iat")
        if isinstance(issued, (int, float)) and issued > now + CLOCK_SKEW_SECONDS:
            raise OidcError("Токен выпущен в будущем")

        not_before = payload.get("nbf")
        if isinstance(not_before, (int, float)) and now < not_before - CLOCK_SKEW_SECONDS:
            raise OidcError("Токен ещё не действителен")

        # nonce связывает токен с КОНКРЕТНОЙ попыткой входа. Без проверки
        # токен, полученный в другой раз (или украденный), принимается
        # повторно.
        #
        # Сравниваем байты, а не строки: `secrets.compare_digest` для str
        # требует ASCII и падает с TypeError на любом не-ASCII символе.
        # А nonce в токене контролируется тем, кто токен выпустил, — то
        # есть подставной провайдер мог прислать кириллицу и получить не
        # «отказ», а необработанное исключение (500 вместо 401).
        nonce = payload.get("nonce")
        if not nonce or not secrets.compare_digest(
            str(nonce).encode("utf-8"), pending.nonce.encode("utf-8")
        ):
            raise OidcError("nonce не совпал — токен от другой попытки входа")

        if not payload.get("sub"):
            raise OidcError("В токене нет subject (sub)")

        return payload

    # --- внутреннее -------------------------------------------------

    @staticmethod
    def _split(token: str) -> tuple[dict, dict, bytes]:
        parts = token.split(".")
        if len(parts) != 3:
            raise OidcError("id_token не является JWT из трёх частей")
        try:
            header = json.loads(_b64decode(parts[0]))
            payload = json.loads(_b64decode(parts[1]))
        except (ValueError, json.JSONDecodeError) as error:
            raise OidcError("Не разбирается заголовок или payload токена") from error
        return header, payload, _b64decode_bytes(parts[2])

    def _find_key(self, kid: str | None, algorithm: str) -> dict:
        """Найти ключ по kid. При промахе — один раз обновить JWKS.

        Обновление нужно при ротации ключей у провайдера: старый кеш дал бы
        ложный отказ на совершенно правильном токене.
        """
        for attempt in (0, 1):
            keys = self.jwks(force=attempt == 1).get("keys", [])
            usable = [
                key
                for key in keys
                if str(key.get("use", "sig")) == "sig" and (kid is None or key.get("kid") == kid)
            ]
            if usable:
                return usable[0]
        raise OidcError(f"Ключ {kid!r} не найден в JWKS провайдера")

    def _check_signature(self, token: str, key: dict, algorithm: str) -> None:
        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import padding, rsa

        if algorithm not in ("RS256", "RS384", "RS512"):
            # Хеши и размер ключа поддержаны, а HMAC и ES256 — нет намеренно:
            # поддерживать половину алгоритмов хуже, чем один и честно.
            raise OidcError(f"Алгоритм подписи {algorithm!r} не поддерживается")

        hash_map = {
            "RS256": hashes.SHA256,
            "RS384": hashes.SHA384,
            "RS512": hashes.SHA512,
        }

        try:
            modulus = int.from_bytes(_b64decode_bytes(key["n"]), "big")
            exponent = int.from_bytes(_b64decode_bytes(key["e"]), "big")
            public_key = rsa.RSAPublicNumbers(exponent, modulus).public_key()
        except (KeyError, ValueError) as error:
            raise OidcError("Не разобрать публичный ключ провайдера") from error

        signing_input, signature = token.rsplit(".", 1)
        try:
            public_key.verify(
                _b64decode_bytes(signature),
                signing_input.encode("ascii"),
                padding.PKCS1v15(),
                hash_map[algorithm](),
            )
        except InvalidSignature as error:
            raise OidcError("Подпись id_token неверна") from error


def _b64decode(value: str) -> str:
    return _b64decode_bytes(value).decode("utf-8")


def _b64decode_bytes(value: str) -> bytes:
    """base64url без выравнивания — так JWT кодирует поля."""
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)
