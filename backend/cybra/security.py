"""Password hashing, sessions and role checks.

Threat model: the app runs on a stand reachable by a handful of colleagues, so
the goals are (a) no plaintext passwords, (b) no API keys in responses or logs,
(c) CSRF protection because the session lives in a cookie.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import hmac
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session as OrmSession

from .config import settings
from .db import get_db
from .models import Session, User, utcnow

_hasher = PasswordHasher()

ROLE_ORDER = {'viewer': 1, 'operator': 2, 'admin': 3}


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except VerifyMismatchError:
        return False
    except Exception:
        return False


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create_session(db: OrmSession, user: User, user_agent: str = '') -> tuple[str, Session]:
    token = secrets.token_urlsafe(32)
    expires = utcnow() + dt.timedelta(hours=settings.session_ttl_hours)
    session = Session(
        user_id=user.id,
        token_hash=token_hash(token),
        csrf_token=secrets.token_urlsafe(24),
        expires_at=expires,
        user_agent=user_agent[:255],
    )
    db.add(session)
    user.last_login_at = utcnow()
    db.commit()
    return token, session


def current_session(request: Request, db: OrmSession) -> Session:
    token = request.cookies.get(settings.cookie_name)
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, 'Not authenticated')
    row = db.scalar(select(Session).where(Session.token_hash == token_hash(token)))
    if row is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, 'Session not found')
    expires = row.expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=dt.timezone.utc)
    if expires < utcnow():
        db.delete(row)
        db.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, 'Session expired')
    return row


def require_user(request: Request, db: OrmSession = Depends(get_db)) -> User:
    session = current_session(request, db)
    user = db.get(User, session.user_id)
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, 'Inactive user')
    request.state.session = session
    request.state.user = user
    return user


def require_role(minimum: str):
    """Dependency factory enforcing a minimum role."""

    def dependency(user: User = Depends(require_user)) -> User:
        if ROLE_ORDER.get(user.role, 0) < ROLE_ORDER[minimum]:
            raise HTTPException(status.HTTP_403_FORBIDDEN, f'Requires role {minimum}')
        return user

    return dependency


def check_csrf(request: Request, session: Session) -> None:
    """Double-submit check for state-changing requests.

    A same-site cookie alone is not enough: the app may be published behind a
    proxy on a different site later, so the header token stays.
    """
    if request.method in ('GET', 'HEAD', 'OPTIONS'):
        return
    header = request.headers.get('x-csrf-token', '')
    if not header or not hmac.compare_digest(header, session.csrf_token):
        raise HTTPException(status.HTTP_403_FORBIDDEN, 'CSRF token missing or invalid')
