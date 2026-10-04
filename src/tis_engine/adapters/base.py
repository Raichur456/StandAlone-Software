from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from tis_engine.services.tool_discovery import ToolNotFoundError


@dataclass(frozen=True)
class CommandResult:
    stage: str
    command: list[str]
    cwd: str | None
    returncode: int
    stdout: str
    stderr: str
    started_at: str
    finished_at: str
    duration_seconds: float
    timed_out: bool = False
    artifacts: list[Path] = field(default_factory=list)


def run_subprocess(
    *,
    stage: str,
    command: list[str],
    timeout_seconds: int,
    cwd: Path | None = None,
    artifacts: list[Path] | None = None,
) -> CommandResult:
    started_at = _utc_now()
    started = time.monotonic()
    cwd_text = str(cwd) if cwd else None

    try:
        completed = subprocess.run(
            command,
            cwd=cwd_text,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
        return CommandResult(
            stage=stage,
            command=command,
            cwd=cwd_text,
            returncode=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
            started_at=started_at,
            finished_at=_utc_now(),
            duration_seconds=round(time.monotonic() - started, 3),
            artifacts=artifacts or [],
        )
    except subprocess.TimeoutExpired as exc:
        return CommandResult(
            stage=stage,
            command=command,
            cwd=cwd_text,
            returncode=-1,
            stdout=_decode_timeout_stream(exc.stdout),
            stderr=_decode_timeout_stream(exc.stderr),
            started_at=started_at,
            finished_at=_utc_now(),
            duration_seconds=round(time.monotonic() - started, 3),
            timed_out=True,
            artifacts=artifacts or [],
        )
    except FileNotFoundError as exc:
        raise ToolNotFoundError(command[0]) from exc


def _decode_timeout_stream(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode(errors="replace")
    return value


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()
