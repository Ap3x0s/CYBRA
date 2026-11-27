"""Application settings and secret handling.

Secrets (endpoint API keys) are encrypted with a Fernet key derived from
``CYBRA_SECRET_KEY``. On first start a key is generated and written to the data
directory, so a local install works without configuration while a container
deployment can inject a real secret.
"""

from __future__ import annotations

import base64
import hashlib
import logging
import os
from functools import lru_cache
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken


def _data_dir() -> Path:
    raw = os.environ.get("CYBRA_DATA_DIR")
    if raw:
        return Path(raw).resolve()
    return Path(__file__).resolve().parents[2] / "var"


class Settings:
    """Read once at import; tests override via ``configure``."""

    def __init__(self) -> None:
        self.data_dir = _data_dir()
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.data_dir / "cybra.sqlite3"
        self.out_dir = self.data_dir / "runs"
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.secret_key = self._secret()
        self.session_ttl_hours = int(os.environ.get("CYBRA_SESSION_TTL_HOURS", "12"))
        self.cookie_name = "cybra_session"
        self.cookie_secure = os.environ.get("CYBRA_COOKIE_SECURE", "0") == "1"
        self.engine_mode = os.environ.get("CYBRA_ENGINE", "subprocess")
        self.allow_registration = os.environ.get("CYBRA_ALLOW_REGISTRATION", "0") == "1"

        # --- Вход через OpenID Connect (корпоративный SSO) -------------
        #
        # Пусто = OIDC выключен, приложение работает на локальном пароле.
        # Это важно для установок без Keycloak: появление настроек не
        # должно требовать внешнего провайдера.
        self.oidc_issuer = os.environ.get("CYBRA_OIDC_ISSUER", "").rstrip("/")
        self.oidc_client_id = os.environ.get("CYBRA_OIDC_CLIENT_ID", "")
        # Секрет клиента. Только на сервере: уходит в Keycloak при обмене
        # code на токены и никогда не попадает в браузер. Именно поэтому
        # OIDC-вход невозможен в чистом SPA — секрету негде жить.
        self.oidc_client_secret = os.environ.get("CYBRA_OIDC_CLIENT_SECRET", "")
        # Полный внешний адрес callback. Keycloak сверяет его с белым
        # списком в настройках клиента: расхождение в одном символе —
        # отказ на этапе редиректа, а не при обмене кода.
        self.oidc_redirect_uri = os.environ.get("CYBRA_OIDC_REDIRECT_URI", "")
        # За прокси Keycloak виден под другим именем, и issuer в токене не
        # совпадёт с тем адресом, куда приложение ходит. Тогда issuer
        # проверяется по этому значению, а запросы идут по oidc_issuer.
        self.oidc_issuer_override = os.environ.get("CYBRA_OIDC_ISSUER_OVERRIDE", "")
        # Роль, которая выдаётся при первом входе через SSO. Минимальная по
        # умолчанию: промах в настройках Keycloak не должен давать админку.
        self.oidc_default_role = os.environ.get("CYBRA_OIDC_DEFAULT_ROLE", "viewer")
        # Разрешить ли локальный пароль при включённом OIDC. По умолчанию
        # да: это аварийный вход, иначе сломанный Keycloak блокирует
        # починку самого Keycloak.
        self.oidc_allow_local = os.environ.get("CYBRA_OIDC_ALLOW_LOCAL", "1") == "1"
        # Куда вернуть человека после успешного входа. Только относительный
        # путь: абсолютный URL был бы открытым редиректом.
        self.oidc_post_login_path = os.environ.get("CYBRA_OIDC_POST_LOGIN", "/")

        # ------------------------------------------------------------------
        # Роли из каталога.
        #
        # Провайдер присылает claim `groups` — список групп LDAP, в которых
        # состоит человек. Здесь задаётся, какая группа даёт какую роль:
        #
        #   CYBRA_OIDC_GROUP_ROLES=cybra-admins=admin,cybra-operators=operator
        #
        # Не задано — роли из каталога не применяются, поведение прежнее
        # (первый вход получает oidc_default_role, дальше решает локальный
        # админ). Это важно для стендов, где групп ещё нет: включение
        # маппинга не должно молча понижать всех до viewer.
        self.oidc_group_roles_raw = os.environ.get("CYBRA_OIDC_GROUP_ROLES", "")
        # Синхронизировать ли роль при каждом входе. Выключить можно, чтобы
        # каталог перестал перезаписывать роли, выставленные в приложении.
        self.oidc_sync_roles = os.environ.get("CYBRA_OIDC_SYNC_ROLES", "1") == "1"

        self.root = Path(__file__).resolve().parents[2]

    @property
    def oidc_enabled(self) -> bool:
        """OIDC включается только когда заданы все обязательные поля."""
        return bool(
            self.oidc_issuer
            and self.oidc_client_id
            and self.oidc_client_secret
            and self.oidc_redirect_uri
        )

    @property
    def oidc_expected_issuer(self) -> str:
        """Issuer, который ожидается внутри токена."""
        return self.oidc_issuer_override or self.oidc_issuer

    @property
    def oidc_group_roles(self) -> dict[str, str]:
        """Разобрать «группа=роль» в словарь.

        Формат — через запятую, пары через `=`. Неразобранные пары
        пропускаются, а не роняют старт: опечатка в одной группе не должна
        мешать приложению подняться. Но и молчать нельзя — поэтому
        предупреждение пишется в лог, см. `log_group_roles`.
        """
        result: dict[str, str] = {}
        for pair in self.oidc_group_roles_raw.split(","):
            pair = pair.strip()
            if not pair or "=" not in pair:
                continue
            group, _, role = pair.partition("=")
            group = group.strip()
            role = role.strip()
            if group and role:
                result[group] = role
        return result

    def log_group_roles(self) -> None:
        """Предупредить о паре, которая не разберётся.

        Без этого опечатка `cybra-admins:admin` (двоеточие вместо равно)
        выглядела бы как «маппинг включён, но не работает»: роль молча
        остаётся прежней, и искать причину никто не станет.
        """
        for pair in self.oidc_group_roles_raw.split(","):
            pair = pair.strip()
            if pair and "=" not in pair:
                logging.getLogger("cybra.oidc").warning(
                    "CYBRA_OIDC_GROUP_ROLES: пара %r пропущена — ожидается формат «группа=роль»",
                    pair,
                )

    def _secret(self) -> str:
        # Prefer an explicit env key; fall back to a persisted local file.
        env = os.environ.get("CYBRA_SECRET_KEY")
        if env:
            return env
        path = self.data_dir / "secret.key"
        if path.exists():
            return path.read_text(encoding="utf-8").strip()
        generated = base64.urlsafe_b64encode(os.urandom(32)).decode()
        path.write_text(generated, encoding="utf-8")
        try:
            path.chmod(0o600)
        except OSError:
            pass
        return generated

    @property
    def fernet(self) -> Fernet:
        digest = hashlib.sha256(self.secret_key.encode()).digest()
        return Fernet(base64.urlsafe_b64encode(digest))

    def encrypt(self, value: str) -> str:
        if not value:
            return ""
        return self.fernet.encrypt(value.encode()).decode()

    def decrypt(self, value: str) -> str:
        if not value:
            return ""
        try:
            return self.fernet.decrypt(value.encode()).decode()
        except InvalidToken:
            # A rotated key must not crash the UI; the operator re-enters it.
            return ""


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
