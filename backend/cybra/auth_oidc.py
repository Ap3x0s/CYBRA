"""Эндпоинты входа через OpenID Connect.

Два маршрута, и оба — серверные:

  GET /auth/oidc/login      → редирект браузера в Keycloak
  GET /auth/oidc/callback   → принять `code`, обменять, выдать НАШУ сессию

Ключевая мысль: после успешной проверки токена вызывается тот же
`create_session()`, что и при входе по паролю. Дальше приложение живёт
ровно как раньше — cookie, CSRF, роли. OIDC не заменяет авторизацию, а
добавляет второй способ дойти до неё.

Почему callback серверный, а не в SPA: `client_secret` нельзя отдать в
браузер. Он уходит только в запросе приложения к Keycloak, с сервера.
"""

from __future__ import annotations

import hmac

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session as OrmSession

from .config import settings
from .db import get_db
from .models import User, utcnow
from .oidc import OidcClient, OidcError, OidcSettings, PendingLogin
from .security import create_session

router = APIRouter(prefix="/api/v1/auth/oidc", tags=["auth"])

# Cookie с состоянием незавершённого входа: state, nonce, PKCE-verifier.
# HttpOnly — JS читать не должен. SameSite=lax — должен пережить переход
# с Keycloak обратно на наш домен; при strict браузер её не отдаст на
# возврате, и вход сломается.
PENDING_COOKIE = "cybra_oidc_pending"


def _client() -> OidcClient:
    if not settings.oidc_enabled:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            "Вход через SSO не настроен на этом стенде",
        )
    return OidcClient(
        OidcSettings(
            issuer=settings.oidc_issuer,
            client_id=settings.oidc_client_id,
            client_secret=settings.oidc_client_secret,
            redirect_uri=settings.oidc_redirect_uri,
            expected_issuer=settings.oidc_expected_issuer,
        )
    )


def _safe_redirect_setting() -> str:
    """Куда вернуть человека после входа.

    Только относительный путь. Абсолютный URL означал бы открытый редирект:
    `?next=https://evil.example` увёл бы сотрудника на чужой сайт сразу
    после успешного входа — идеальный момент для фишинга.
    """
    target = settings.oidc_post_login_path or "/"
    if not target.startswith("/") or target.startswith("//"):
        return "/"
    return target


@router.get("/enabled")
def oidc_enabled() -> dict:
    """Публичный признак: показывать ли кнопку «Войти через корпоративный аккаунт».

    Ничего секретного: сам факт, что SSO настроен, виден и по редиректу.
    Нужен он фронтенду, чтобы не рисовать нерабочую кнопку.
    """
    return {
        "enabled": settings.oidc_enabled,
        "local_allowed": settings.oidc_allow_local,
        "provider": settings.oidc_issuer if settings.oidc_enabled else None,
    }


@router.get("/login")
def oidc_login() -> RedirectResponse:
    """Шаг 1: отправить браузер в провайдер.

    Пароль вводится на стороне Keycloak. Наше приложение его не видит —
    это и есть главная выгода схемы.
    """
    client = _client()
    pending = PendingLogin.new()
    try:
        url = client.authorization_url(pending)
    except OidcError as error:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            f"Провайдер входа недоступен: {error}",
        ) from error

    response = RedirectResponse(url, status_code=status.HTTP_303_SEE_OTHER)
    # Состояние кладём в подписанную cookie. В памяти процесса нельзя: у
    # uvicorn несколько воркеров, и callback придёт в другой.
    #
    # path="/" — не оптимизация, а исправление. С path="/api/v1/auth/oidc"
    # браузер отдаёт cookie только под этим префиксом, и всё работает ровно
    # до того момента, когда вход начат на `127.0.0.1`, а redirect_uri
    # настроен на `localhost` (или наоборот). Это разные хосты для cookie,
    # и браузер молча не присылает её на callback: 400 «нет состояния
    # входа», хотя человек сделал всё правильно. С path="/" cookie живёт на
    # всём хосте, и расхождение localhost/127.0.0.1 в пути перестаёт
    # влиять — хотя в проде адрес всё равно должен быть один.
    response.set_cookie(
        PENDING_COOKIE,
        _sign(pending.to_json()),
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
        max_age=600,
        path="/",
    )
    return response


@router.get("/callback")
def oidc_callback(
    request: Request,
    response: Response,
    code: str = "",
    state: str = "",
    error: str = "",
    db: OrmSession = Depends(get_db),
):
    """Шаг 2: принять код, проверить токен, выдать нашу сессию."""
    if error:
        # Провайдер сам сообщил об отказе (например, пользователь нажал
        # «Отмена»). Это не наша ошибка, но и входить нельзя.
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            f"Провайдер отклонил вход: {error}",
        )

    if not code or not state:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "В callback нет code или state",
        )

    raw_pending = request.cookies.get(PENDING_COOKIE, "")
    if not raw_pending:
        # Диагностика обязательна: без неё непонятно, ЧТО именно пришло.
        # Браузер мог не отдать cookie по пути, мог отдать пустую, мог
        # отдать чужую. Молчаливый 400 здесь стоит часа поиска.
        import logging

        logging.getLogger("cybra.oidc").warning(
            "callback без cookie %s; получены: %s; path запроса: %s",
            PENDING_COOKIE,
            list(request.cookies.keys()),
            request.url.path,
        )
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Нет состояния входа в cookie — вход начат не с этого браузера",
        )

    try:
        pending = PendingLogin.from_json(_unsign(raw_pending))
    except OidcError as error:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(error)) from error

    # Проверка state. Без неё злоумышленник подсовывает свой `code` в чужой
    # браузер, и человек входит в ЕГО учётку (CSRF на callback).
    #
    # Сравниваем байты: compare_digest для str требует ASCII, а state
    # приходит из URL и контролируется вызывающей стороной. Кириллица в
    # state дала бы не отказ, а необработанное исключение — 500 вместо 401.
    if not state or not hmac.compare_digest(state.encode("utf-8"), pending.state.encode("utf-8")):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "state не совпал: вход начат в другом браузере или подделан",
        )

    client = _client()
    try:
        tokens = client.exchange(code, pending)
        claims = client.verify_id_token(tokens["id_token"], pending)
    except OidcError as error:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            f"Проверка токена не прошла: {error}",
        ) from error

    subject = str(claims["sub"])
    email = str(claims.get("email") or "").strip().lower()
    display = str(
        claims.get("name") or claims.get("preferred_username") or email.split("@")[0] or subject
    )

    user = _resolve_user(db, subject, email, display)

    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Учётная запись отключена")

    token, session = create_session(db, user, request.headers.get("user-agent", "")[:255])
    user.last_login_at = utcnow()
    db.commit()

    # Cookie ставим и на ответ-редирект: браузер уйдёт на страницу, уже
    # будучи авторизованным. Отдельный JSON здесь не годится — человека
    # вернул браузер, а не fetch.
    redirect = RedirectResponse(_safe_redirect_setting(), status_code=status.HTTP_303_SEE_OTHER)
    redirect.set_cookie(
        settings.cookie_name,
        token,
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
        max_age=settings.session_ttl_hours * 3600,
        path="/",
    )
    # Состояние входа больше не нужно: повторный callback с тем же code
    # провайдер и так отклонит, но чистить надо.
    redirect.delete_cookie(PENDING_COOKIE, path="/")
    return redirect


def _resolve_user(db: OrmSession, subject: str, email: str, display: str) -> User:
    """Найти или завести пользователя по subject.

    Привязка идёт по `sub`, а не по email. Email сотрудник может сменить в
    каталоге (или его переиспользуют после увольнения), и привязка по email
    отдала бы чужой аккаунт вместе с ролями.
    """
    user = db.scalar(select(User).where(User.oidc_sub == subject))
    if user is not None:
        # Имя в каталоге могло измениться — подтягиваем, но роли НЕ трогаем:
        # они наши, а не провайдера.
        if display and user.display_name != display:
            user.display_name = display[:120]
            db.commit()
        return user

    # Первый вход. Если такая почта уже есть в локальной базе — привязываем
    # к ней, но ТОЛЬКО если она ещё не привязана к другому subject.
    if email:
        existing = db.scalar(select(User).where(User.email == email))
        if existing is not None:
            if existing.oidc_sub and existing.oidc_sub != subject:
                raise HTTPException(
                    status.HTTP_409_CONFLICT,
                    "Эта почта уже привязана к другому корпоративному аккаунту",
                )
            existing.oidc_sub = subject
            existing.auth_source = "oidc"
            db.commit()
            return existing

    user = User(
        email=email or f"{subject}@oidc.local",
        display_name=display[:120],
        # Пароля нет вовсе: вход только через провайдера. Пустой хеш argon2
        # не примет, то есть случайно пустить по пустому паролю нельзя.
        password_hash="",
        # Минимальная роль из настроек. Роли из токена НЕ читаются: кто
        # может выпустить токен для нашего клиента, получил бы админку.
        role=settings.oidc_default_role,
        is_active=True,
        oidc_sub=subject,
        auth_source="oidc",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


# ----------------------------------------------------------------------
# Подпись cookie с состоянием входа
#
# Читать её браузеру не нужно, но подделывать — нужно мешать: подменив
# nonce в cookie, атакующий сделал бы проверку nonce бессмысленной.
# Подпись даёт HMAC от того же ключа, что шифрует секреты приложения.
# ----------------------------------------------------------------------


def _sign(payload: str) -> str:
    signature = hmac.new(settings.secret_key.encode(), payload.encode(), "sha256").hexdigest()
    return f"{signature}.{payload}"


def _unsign(signed: str) -> str:
    # Значение cookie приходит в кавычках, если содержит символы, которые
    # RFC 6265 не разрешает в unquoted-значении (у нас это точка в подписи
    # и `{` в payload). Starlette ставит их сам, а браузер снимает — но
    # НЕ все клиенты: curl и cookie-jar Python отдают строку как есть, и
    # тогда HMAC считается от `"<signature>...`, подпись не сходится, и
    # вход падает с 400 на ровном месте.
    #
    # Снимаем кавычки до проверки: они часть транспортной обёртки, а не
    # подписанных данных.
    signed = signed.strip().strip('"')

    signature, _, payload = signed.partition(".")
    if not signature or not payload:
        raise OidcError("Cookie состояния повреждена")
    expected = hmac.new(settings.secret_key.encode(), payload.encode(), "sha256").hexdigest()
    if not hmac.compare_digest(signature.encode("utf-8"), expected.encode("utf-8")):
        raise OidcError("Подпись cookie состояния неверна")
    return payload
