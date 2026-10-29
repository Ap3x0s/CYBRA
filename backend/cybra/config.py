"""Application settings and secret handling.

Secrets (endpoint API keys) are encrypted with a Fernet key derived from
``CYBRA_SECRET_KEY``. On first start a key is generated and written to the data
directory, so a local install works without configuration while a container
deployment can inject a real secret.
"""
from __future__ import annotations

import base64
import hashlib
import os
from functools import lru_cache
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken


def _data_dir() -> Path:
    raw = os.environ.get('CYBRA_DATA_DIR')
    if raw:
        return Path(raw).resolve()
    return Path(__file__).resolve().parents[2] / 'var'


class Settings:
    """Read once at import; tests override via ``configure``."""

    def __init__(self) -> None:
        self.data_dir = _data_dir()
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.data_dir / 'cybra.sqlite3'
        self.out_dir = self.data_dir / 'runs'
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.secret_key = self._secret()
        self.session_ttl_hours = int(os.environ.get('CYBRA_SESSION_TTL_HOURS', '12'))
        self.cookie_name = 'cybra_session'
        self.cookie_secure = os.environ.get('CYBRA_COOKIE_SECURE', '0') == '1'
        self.engine_mode = os.environ.get('CYBRA_ENGINE', 'subprocess')
        self.allow_registration = os.environ.get('CYBRA_ALLOW_REGISTRATION', '0') == '1'
        self.root = Path(__file__).resolve().parents[2]

    def _secret(self) -> str:
        # Prefer an explicit env key; fall back to a persisted local file.
        env = os.environ.get('CYBRA_SECRET_KEY')
        if env:
            return env
        path = self.data_dir / 'secret.key'
        if path.exists():
            return path.read_text(encoding='utf-8').strip()
        generated = base64.urlsafe_b64encode(os.urandom(32)).decode()
        path.write_text(generated, encoding='utf-8')
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
            return ''
        return self.fernet.encrypt(value.encode()).decode()

    def decrypt(self, value: str) -> str:
        if not value:
            return ''
        try:
            return self.fernet.decrypt(value.encode()).decode()
        except InvalidToken:
            # A rotated key must not crash the UI; the operator re-enters it.
            return ''


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
