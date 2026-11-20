"""Pydantic schemas for the public API."""
from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, Field, field_validator


class LoginIn(BaseModel):
    email: str
    password: str


class UserOut(BaseModel):
    id: int
    email: str
    display_name: str
    role: str
    is_active: bool
    last_login_at: dt.datetime | None = None

    model_config = {'from_attributes': True}


class MeOut(UserOut):
    csrf_token: str = ''


class UserIn(BaseModel):
    email: str
    password: str = Field(min_length=10)
    display_name: str = ''
    role: str = 'viewer'


class PasswordIn(BaseModel):
    current_password: str
    new_password: str = Field(min_length=10)


class EndpointIn(BaseModel):
    name: str
    base_url: str
    chat_url: str = ''
    auth_type: str = 'bearer'
    api_key: str = ''
    verify_tls: bool = True
    ca_pem: str = ''
    default_headers: dict = Field(default_factory=dict)
    extra_body: dict = Field(default_factory=dict)
    notes: str = ''


class EndpointOut(BaseModel):
    id: int
    name: str
    base_url: str
    chat_url: str
    auth_type: str
    secret_hint: str
    has_secret: bool
    verify_tls: bool
    default_headers: dict
    extra_body: dict
    notes: str
    created_at: dt.datetime

    @field_validator('created_at', mode='after')
    @classmethod
    def _tz_aware(cls, value):
        return _as_utc(value)

class TargetIn(BaseModel):
    endpoint_id: int
    model_id: str
    label: str = ''
    temperature: float | None = 0.0
    token_parameter: str = 'max_tokens'
    drop_params: list[str] = Field(default_factory=list)
    developer_as_system: bool = False
    extra_body: dict = Field(default_factory=dict)
    group_name: str = ''
    is_judge: bool = False


class TargetOut(BaseModel):
    id: int
    endpoint_id: int
    model_id: str
    label: str
    temperature: float | None
    token_parameter: str
    drop_params: list
    developer_as_system: bool
    extra_body: dict
    group_name: str
    is_judge: bool
    endpoint_name: str = ''

    model_config = {'from_attributes': True}


class DatasetVersionOut(BaseModel):
    id: int
    name: str
    version: str
    description: str
    origin: str
    sha256: str
    parent_id: int | None
    changelog: str
    case_count: int = 0
    created_at: dt.datetime

    @field_validator('created_at', mode='after')
    @classmethod
    def _tz_aware(cls, value):
        return _as_utc(value)

class DatasetCaseOut(BaseModel):
    id: int
    case_id: str
    category: str
    prompt: str
    goal: str
    kind: str
    metadata: dict


class CaseEditIn(BaseModel):
    case_id: str
    category: str = ''
    prompt: str = ''
    goal: str = ''
    kind: str = 'harmful'
    metadata: dict = Field(default_factory=dict)


class RunIn(BaseModel):
    label: str = ''
    target_ids: list[int]
    judge_target_id: int | None = None
    tools: list[str]
    dataset_version_ids: list[int] = Field(default_factory=list)
    engine_mode: str | None = None
    limit: int = 10
    seed: int = 42
    variants: list[str] = Field(default_factory=lambda: ['direct', 'roleplay', 'authority'])
    max_requests: int = 1000
    # 8192, а не 2048: у моделей с цепочкой рассуждений квота completion
    # уходит в reasoning_tokens, и на текст не остаётся ничего. Замер на
    # реальном промпте garak: при 2048 и 4096 reasoning забирает ВСЁ
    # (text_tokens=0, finish_reason=length), при 8192 приходит 579 символов
    # ответа. С прежним дефолтом 111 из 123 запросов garak были обрезаны.
    max_tokens: int = 8192
    # Судье нужно ещё больше: он получает выдержки из ответов модели и
    # разбирает каждый инструмент, то есть его собственный ответ длинный.
    judge_max_tokens: int = 16384
    temperature: float | None = 0.0
    timeout: int = 120
    # Стенной бюджет инструмента. Час (3600) был мал для garak с 12 кейсами
    # на reasoning-модели: он честно исчерпал бюджет на третьей пробе из
    # трёх и завершился ERROR. Два часа покрывают прогон целиком.
    tool_timeout: int = 7200
    garak_probes: str = ''
    bipia_attacks: int = 4
    # Общий вердикт судьи — опциональная надстройка над обычными метриками.
    # Стоит одного запроса на модель, поэтому по умолчанию выключен.
    judge_verdict: bool = False
    judge_verdict_prompt: str = ''


class RunStepOut(BaseModel):
    id: int
    model_label: str
    tool: str
    completeness: str
    counts: dict
    failed_check_rate: float | None
    categories: dict
    requests: dict
    error: str
    artifact_dir: str


def _as_utc(value: dt.datetime | None) -> dt.datetime | None:
    """Пометить наивное время как UTC.

    SQLite не хранит tzinfo, поэтому из БД приходит наивный datetime с
    UTC-семантикой. Если отдать его как есть, Pydantic напишет строку без
    суффикса Z, и браузер (по ES5) прочтёт её как локальное время — метка
    уедет на смещение пояса. Наивное время у нас всегда UTC, поэтому
    проставляем зону явно.
    """
    if value is None:
        return None
    return value.replace(tzinfo=dt.timezone.utc) if value.tzinfo is None else value


class RunOut(BaseModel):
    id: int
    run_id: str
    label: str
    engine_mode: str
    status: str
    created_at: dt.datetime
    started_at: dt.datetime | None
    finished_at: dt.datetime | None
    # Длительность считает API: клиенту не нужно повторять арифметику с
    # часовыми поясами, а в отчёте время должно быть одинаковым везде.
    duration_seconds: float | None = None
    error: str = ''
    # Вердикт судьи по каждой модели: {model_label: {verdict, behaviour, ...}}.
    # Пусто, если функция была выключена или прогон архивный.
    verdicts: dict | None = None
    steps: list[RunStepOut] = Field(default_factory=list)

    @field_validator('created_at', 'started_at', 'finished_at', mode='after')
    @classmethod
    def _tz_aware(cls, value):
        return _as_utc(value)

class FindingOut(BaseModel):
    id: int
    case_id: str
    category: str
    verdict: str
    prompt: str
    answer: str
    reason: str

    model_config = {'from_attributes': True}


class ProgressOut(BaseModel):
    status: str
    requests: dict = Field(default_factory=dict)
    current_model: str = ''
    current_tool: str = ''
    finished_steps: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
