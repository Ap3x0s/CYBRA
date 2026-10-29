"""Database models.

SQLite + WAL is a deliberate choice: the product targets a single stand that an
admin installs next to the models, not a multi-tenant SaaS. Avoiding a separate
Postgres server removes an install step without changing the schema shape, so a
later move to Postgres stays a configuration change.
"""
from __future__ import annotations

import datetime as dt

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = 'users'

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(120), default='')
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), default='viewer')  # admin|operator|viewer
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_login_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))

    sessions: Mapped[list['Session']] = relationship(back_populates='user')


class Session(Base):
    __tablename__ = 'sessions'

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    csrf_token: Mapped[str] = mapped_column(String(64), default='')
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    expires_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True))
    user_agent: Mapped[str] = mapped_column(String(255), default='')

    user: Mapped[User] = relationship(back_populates='sessions')


class Endpoint(Base):
    """An OpenAI-compatible API server."""

    __tablename__ = 'endpoints'

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    base_url: Mapped[str] = mapped_column(String(500))
    # Full target URL, e.g. https://host/v1/chat/completions
    chat_url: Mapped[str] = mapped_column(String(500), default='')
    auth_type: Mapped[str] = mapped_column(String(20), default='bearer')  # bearer|header|none
    secret_encrypted: Mapped[str] = mapped_column(Text, default='')
    secret_hint: Mapped[str] = mapped_column(String(40), default='')
    verify_tls: Mapped[bool] = mapped_column(Boolean, default=True)
    ca_pem: Mapped[str] = mapped_column(Text, default='')
    default_headers: Mapped[dict] = mapped_column(JSON, default=dict)
    extra_body: Mapped[dict] = mapped_column(JSON, default=dict)
    notes: Mapped[str] = mapped_column(Text, default='')
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    targets: Mapped[list['Target']] = relationship(back_populates='endpoint')


class Target(Base):
    """A model served by an endpoint, with its own compatibility switches."""

    __tablename__ = 'targets'
    __table_args__ = (UniqueConstraint('endpoint_id', 'model_id', name='uq_target'),)

    id: Mapped[int] = mapped_column(primary_key=True)
    endpoint_id: Mapped[int] = mapped_column(ForeignKey('endpoints.id', ondelete='CASCADE'))
    model_id: Mapped[str] = mapped_column(String(200))
    label: Mapped[str] = mapped_column(String(200), default='')
    temperature: Mapped[float | None] = mapped_column(Float)
    token_parameter: Mapped[str] = mapped_column(String(40), default='max_tokens')
    drop_params: Mapped[list] = mapped_column(JSON, default=list)
    developer_as_system: Mapped[bool] = mapped_column(Boolean, default=False)
    extra_body: Mapped[dict] = mapped_column(JSON, default=dict)
    group_name: Mapped[str] = mapped_column(String(120), default='')
    is_judge: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    endpoint: Mapped[Endpoint] = relationship(back_populates='targets')


class DatasetVersion(Base):
    """Immutable snapshot of a case set. Edits always create a new version."""

    __tablename__ = 'dataset_versions'
    __table_args__ = (UniqueConstraint('name', 'version', name='uq_dataset_version'),)

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), index=True)
    version: Mapped[str] = mapped_column(String(40))
    description: Mapped[str] = mapped_column(Text, default='')
    origin: Mapped[str] = mapped_column(String(20), default='builtin')  # builtin|ui|config
    sha256: Mapped[str] = mapped_column(String(64), default='')
    parent_id: Mapped[int | None] = mapped_column(ForeignKey('dataset_versions.id'))
    changelog: Mapped[str] = mapped_column(Text, default='')
    created_by: Mapped[int | None] = mapped_column(ForeignKey('users.id'))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    cases: Mapped[list['DatasetCase']] = relationship(
        back_populates='version', cascade='all, delete-orphan')


class DatasetCase(Base):
    __tablename__ = 'dataset_cases'

    id: Mapped[int] = mapped_column(primary_key=True)
    version_id: Mapped[int] = mapped_column(ForeignKey('dataset_versions.id', ondelete='CASCADE'))
    case_id: Mapped[str] = mapped_column(String(200), index=True)
    category: Mapped[str] = mapped_column(String(120), default='')
    prompt: Mapped[str] = mapped_column(Text, default='')
    goal: Mapped[str] = mapped_column(Text, default='')
    kind: Mapped[str] = mapped_column(String(40), default='harmful')
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)

    version: Mapped[DatasetVersion] = relationship(back_populates='cases')


class Run(Base):
    __tablename__ = 'runs'

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    label: Mapped[str] = mapped_column(String(200), default='')
    engine_mode: Mapped[str] = mapped_column(String(20), default='subprocess')
    status: Mapped[str] = mapped_column(String(20), default='PENDING')
    # PENDING | RUNNING | COMPLETE | PARTIAL | ERROR | CANCELLED
    profile_json: Mapped[dict] = mapped_column(JSON, default=dict)
    out_dir: Mapped[str] = mapped_column(String(1000), default='')
    created_by: Mapped[int | None] = mapped_column(ForeignKey('users.id'))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    started_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    error: Mapped[str] = mapped_column(Text, default='')

    steps: Mapped[list['RunStep']] = relationship(
        back_populates='run', cascade='all, delete-orphan')


class RunStep(Base):
    __tablename__ = 'run_steps'

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey('runs.id', ondelete='CASCADE'))
    target_id: Mapped[int | None] = mapped_column(ForeignKey('targets.id'))
    model_label: Mapped[str] = mapped_column(String(200), default='')
    tool: Mapped[str] = mapped_column(String(60))
    dataset_version_id: Mapped[int | None] = mapped_column(ForeignKey('dataset_versions.id'))
    completeness: Mapped[str] = mapped_column(String(20), default='PENDING')
    counts: Mapped[dict] = mapped_column(JSON, default=dict)
    failed_check_rate: Mapped[float | None] = mapped_column(Float)
    categories: Mapped[dict] = mapped_column(JSON, default=dict)
    requests: Mapped[dict] = mapped_column(JSON, default=dict)
    error: Mapped[str] = mapped_column(Text, default='')
    artifact_dir: Mapped[str] = mapped_column(String(1000), default='')

    run: Mapped[Run] = relationship(back_populates='steps')


class Finding(Base):
    __tablename__ = 'findings'

    id: Mapped[int] = mapped_column(primary_key=True)
    step_id: Mapped[int] = mapped_column(ForeignKey('run_steps.id', ondelete='CASCADE'))
    case_id: Mapped[str] = mapped_column(String(200), index=True)
    category: Mapped[str] = mapped_column(String(120), default='')
    verdict: Mapped[str] = mapped_column(String(20), index=True)
    prompt: Mapped[str] = mapped_column(Text, default='')
    answer: Mapped[str] = mapped_column(Text, default='')
    reason: Mapped[str] = mapped_column(Text, default='')
    raw_json: Mapped[dict] = mapped_column(JSON, default=dict)
