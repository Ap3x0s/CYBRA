"""Contract shared by every CYBRA engine backend.

The engine abstraction exists so the API and UI never learn how a benchmark run
is physically executed. Today the only real implementation starts the existing
``run.py`` as a child process; later one could reimplement ``Engine`` in-process
without touching the HTTP layer.
"""
from __future__ import annotations

import dataclasses
from pathlib import Path
from typing import Iterable, Protocol


@dataclasses.dataclass(frozen=True)
class Target:
    """One model behind one endpoint."""

    endpoint: str
    model: str
    api_key: str = ''
    extra_body: dict | None = None
    headers: dict | None = None


@dataclasses.dataclass(frozen=True)
class JudgeConfig:
    endpoint: str
    model: str
    api_key: str = ''
    extra_body: dict | None = None
    max_tokens: int = 4096


@dataclasses.dataclass(frozen=True)
class RunRequest:
    """Everything the engine needs to execute one run."""

    run_id: str
    out_dir: Path
    targets: list[Target]
    tools: list[str]
    judge: JudgeConfig
    datasets_dir: Path
    limit: int = 10
    seed: int = 42
    variants: tuple[str, ...] = ('direct', 'roleplay', 'authority')
    max_requests: int = 1000
    max_tokens: int = 2048
    temperature: float | None = 0.0
    timeout: int = 120
    tool_timeout: int = 3600
    token_parameter: str = 'max_tokens'
    drop_params: tuple[str, ...] = ()
    developer_as_system: bool = False
    verify_tls: bool = True
    garak_probes: str = ''
    bipia_attacks: int = 4


@dataclasses.dataclass
class Progress:
    """A snapshot of a running scan."""

    requests: dict[str, int] = dataclasses.field(default_factory=dict)
    current_model: str = ''
    current_tool: str = ''
    finished_steps: list[str] = dataclasses.field(default_factory=list)
    errors: list[str] = dataclasses.field(default_factory=list)


class EngineError(RuntimeError):
    """Raised when the engine cannot start or produce a result."""


class Engine(Protocol):
    """Minimal surface the backend depends on."""

    name: str

    def start(self, request: RunRequest) -> 'EngineHandle':
        ...


class EngineHandle(Protocol):
    """A started run."""

    @property
    def cancelled(self) -> bool:
        """True once ``cancel`` was requested."""
        ...

    def poll(self) -> Progress:
        """Return current progress; safe to call often."""

    def wait(self, timeout: float | None = None) -> int:
        """Block until the run ends and return its exit code."""

    def cancel(self) -> None:
        """Stop the run and release every child process."""

    def collect(self) -> Iterable[Path]:
        """Yield artifact directories produced by the run."""
