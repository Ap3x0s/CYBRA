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
import logging

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy import func, select
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
        #
        # `import logging` здесь НЕ ставить: импорт внутри функции делает
        # `logging` локальной переменной для всей функции, и любое
        # обращение к нему ВЫШЕ по коду падает с UnboundLocalError. Именно
        # так ломался вход через SSO: предупреждение на строке ниже
        # импорта работало, а то, что выше, — нет.
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
        # Логируем причину: без этого отказ выглядит как немой 401, и
        # искать приходится наугад. В лог попадает только текст ошибки —
        # ни токенов, ни утверждений, они чувствительны.
        logging.getLogger("cybra.oidc").warning("callback отклонён: %s", error)
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            f"Проверка токена не прошла: {error}",
        ) from error

    subject = str(claims["sub"])
    email = str(claims.get("email") or "").strip().lower()
    display = str(
        claims.get("name") or claims.get("preferred_username") or email.split("@")[0] or subject
    )

    # Группы каталога. Keycloak кладёт их в claim `groups`, когда в realm
    # включён соответствующий маппер. Терпим и к строке через запятую:
    # некоторые провайдеры отдают так, и падать из-за формата незачем.
    raw_groups = claims.get("groups") or []
    if isinstance(raw_groups, str):
        raw_groups = [part.strip() for part in raw_groups.split(",")]
    groups = [str(item) for item in raw_groups if str(item).strip()]

    user = _resolve_user(db, subject, email, display, groups)

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


def _role_from_groups(groups: list[str]) -> str | None:
    """Роль по группам из токена. None — групп нет или маппинг не настроен.

    Ищем самую сильную роль из всех совпавших групп, а не первую.

    Почему: человек может состоять в нескольких группах сразу, и порядок
    групп в токене не определён — Keycloak волен вернуть их как угодно.
    «Первая совпавшая» давала бы разный результат между входами на одних и
    тех же данных, то есть роль прыгала бы на ровном месте. Выбор
    сильнейшей делает результат предсказуемым и совпадает с житейской
    логикой: если ты в группе админов, ты админ, даже если ещё и в группе
    наблюдателей.
    """
    mapping = settings.oidc_group_roles
    if not mapping or not groups:
        return None

    from .security import ROLE_ORDER

    best: str | None = None
    best_weight = 0
    for raw in groups:
        group = str(raw).strip()
        if not group:
            continue
        # Ищем и полный путь LDAP (`cn=cybra-admins,ou=groups,dc=...`), и
        # короткое имя (`cybra-admins`).
        #
        # Зачем оба: Keycloak умеет отдавать группу в двух видах, и какой
        # выбран, зависит от маппера в realm — настройка вне нашего кода.
        # Если искать только одно, маппинг тихо не сработает при смене этой
        # настройки у заказчика, и искать причину будут в приложении.
        candidates = [group]
        if group.startswith("cn="):
            short = group[3:].split(",", 1)[0]
            if short:
                candidates.append(short)
        elif "cn=" in group:
            short = group.split("cn=", 1)[1].split(",", 1)[0]
            if short:
                candidates.append(short)

        role = next((mapping[name] for name in candidates if name in mapping), None)
        if not role:
            continue
        # Неизвестную роль из конфига игнорируем: опечатка не должна
        # выдавать права, которых нет в системе.
        weight = ROLE_ORDER.get(role, 0)
        if weight > best_weight:
            best, best_weight = role, weight
    return best


def _resolve_user(
    db: OrmSession,
    subject: str,
    email: str,
    display: str,
    groups: list[str] | None = None,
) -> User:
    """Найти или завести пользователя по subject.

    Привязка идёт по `sub`, а не по email. Email сотрудник может сменить в
    каталоге (или его переиспользуют после увольнения), и привязка по email
    отдала бы чужой аккаунт вместе с ролями.

    Роли: каталог управляет теми, кто пришёл из каталога. Локальные учётки
    он не трогает никогда — см. `_sync_role`.
    """
    user = db.scalar(select(User).where(User.oidc_sub == subject))
    if user is not None:
        # Имя в каталоге могло измениться — подтягиваем.
        if display and user.display_name != display:
            user.display_name = display[:120]
            db.commit()
        _sync_role(db, user, groups or [])
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
            _sync_role(db, existing, groups or [])
            return existing

    role_from_ldap = _role_from_groups(groups or [])
    # Член группы «неприкосновенных» становится админом сразу, при первом же
    # входе, и роль закрепляется.
    #
    # Почему проверяем и здесь, а не только в _sync_role: при первом входе
    # пользователя ещё нет, поэтому синхронизация не вызывается вовсе —
    # учётка создаётся с ролью из маппинга и без закрепления. То есть
    # защита включалась бы только со второго входа, а до него root-админа
    # мог снять кто угодно.
    root_group = settings.oidc_root_group.strip()
    is_root = bool(root_group) and any(str(group).strip() == root_group for group in (groups or []))

    user = User(
        email=email or f"{subject}@oidc.local",
        display_name=display[:120],
        # Пароля нет вовсе: вход только через провайдера. Пустой хеш argon2
        # не примет, то есть случайно пустить по пустому паролю нельзя.
        password_hash="",
        # Роль из группы каталога, если маппинг настроен; иначе минимальная
        # из настроек. Роли из claim `roles` НЕ читаются: кто может
        # выпустить токен для нашего клиента, получил бы админку. Группы
        # отличаются тем, что их состав ведёт администратор каталога, а не
        # владелец клиента.
        role="admin" if is_root else (role_from_ldap or settings.oidc_default_role),
        # Член root-группы сразу закреплён: каталог не сможет его снять.
        role_pinned=is_root,
        is_active=True,
        oidc_sub=subject,
        auth_source="oidc",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _sync_role(db: OrmSession, user: User, groups: list[str]) -> None:
    """Привести роль к тому, что говорит каталог. С защитой админа.

    Правила, и каждое существует из-за конкретной поломки:

    1. Локальные учётки не трогаем. У них `auth_source == "local"`, пароль
       в нашей базе, и каталог про них ничего не знает. Иначе первый же
       вход сторожа через SSO снёс бы роль, выставленную вручную.

    2. Владельца учётки не понижаем. Если в приложении нет НИ ОДНОГО
       активного админа, роль поднимается до admin. Это защита от
       блокировки: каталог — внешняя система, и ошибка в её группах
       (переименовали, удалили, рассинхронизировали) оставила бы стенд
       без единого человека, способного войти в настройки.

    3. Синхронизацию можно выключить целиком через CYBRA_OIDC_SYNC_ROLES=0.
       Тогда каталог перестаёт перезаписывать роли, но вход продолжает
       работать.

    4. Если маппинг групп не настроен — роль не меняем вовсе. Иначе
       включение SSO на стенде без групп молча понизило бы всех до viewer,
       включая того, кто это включил.

    5. Зафиксированную вручную роль не трогаем. Админ поставил её в
       приложении — каталог уступает. Без этого правила ручная правка
       отменялась при следующем входе сотрудника: интерфейс показывал
       успех, а через час роль была прежней.
    """
    if not settings.oidc_sync_roles:
        return
    if user.auth_source != "oidc":
        return
    if user.role_pinned:
        return

    # Группа «неприкосновенных» админов: роль из неё закрепляется навсегда.
    #
    # Почему автоматически, а не «админ потом нажмёт кнопку»: смысл группы
    # в том, что она работает, даже когда локального админа снять уже
    # успели. Если бы требовалось ручное закрепление, защита появлялась бы
    # ровно тогда, когда её уже некому включить.
    root_group = settings.oidc_root_group.strip()
    if root_group and any(str(g).strip() == root_group for g in groups):
        if user.role != "admin" or not user.role_pinned:
            logging.getLogger("cybra.oidc").info(
                "роль %s закреплена: состоит в группе %r", user.email, root_group
            )
            user.role = "admin"
            user.role_pinned = True
            db.commit()
        return

    desired = _role_from_groups(groups)
    if desired is None or desired == user.role:
        return

    # Не даём каталогу оставить систему без администратора.
    if user.role == "admin" and desired != "admin":
        other_admins = db.scalar(
            select(func.count(User.id)).where(
                User.role == "admin",
                User.is_active.is_(True),
                User.id != user.id,
            )
        )
        if not other_admins:
            logging.getLogger("cybra.oidc").warning(
                "каталог понижает %s до %r, но других админов нет — "
                "роль оставлена admin, чтобы не заблокировать настройки",
                user.email,
                desired,
            )
            return

    logging.getLogger("cybra.oidc").info(
        "роль %s изменена каталогом: %s → %s", user.email, user.role, desired
    )
    user.role = desired
    db.commit()


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
