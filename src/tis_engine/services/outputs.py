from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from tis_engine.adapters.base import CommandResult
from tis_engine.status_codes import StatusCode, status_message


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def write_command_logs(output_dir: Path, result: CommandResult) -> dict[str, str]:
    logs_dir = output_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    stdout_path = logs_dir / f"{result.stage}.stdout.log"
    stderr_path = logs_dir / f"{result.stage}.stderr.log"
    stdout_path.write_text(result.stdout or "", encoding="utf-8")
    stderr_path.write_text(result.stderr or "", encoding="utf-8")

    return {
        "stdout_log": relative_to_output(stdout_path, output_dir),
        "stderr_log": relative_to_output(stderr_path, output_dir),
    }


def command_stage_record(
    output_dir: Path,
    result: CommandResult,
    status: str,
    error: str | None = None,
) -> dict[str, Any]:
    logs = write_command_logs(output_dir, result)
    return {
        "name": result.stage,
        "status": status,
        "started_at": result.started_at,
        "finished_at": result.finished_at,
        "duration_seconds": result.duration_seconds,
        "exit_code": result.returncode,
        "command": result.command,
        "cwd": result.cwd,
        "timed_out": result.timed_out,
        "stdout_log": logs["stdout_log"],
        "stderr_log": logs["stderr_log"],
        "artifacts": [
            relative_to_output(artifact, output_dir) for artifact in result.artifacts
        ],
        "error": error,
    }


def write_failure_manifest(
    output_dir: Path,
    *,
    code: StatusCode,
    message: str,
    config_path: Path | None = None,
    details: list[dict[str, Any]] | None = None,
) -> None:
    started_at = utc_now()
    manifest = {
        "manifest_version": "1.0",
        "schema_version": None,
        "job_id": None,
        "mode": None,
        "status": "failed",
        "exit_code": int(code),
        "exit_message": status_message(code),
        "started_at": started_at,
        "finished_at": started_at,
        "duration_seconds": 0,
        "config_path": str(config_path) if config_path else None,
        "stages": [
            {
                "name": "config",
                "status": "failed",
                "error": message,
            }
        ],
        "artifacts": [],
        "errors": details or [{"message": message}],
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(output_dir / "output_manifest.json", manifest)
    write_json(
        output_dir / "metrics.json",
        {
            "status": "failed",
            "exit_code": int(code),
            "duration_seconds": 0,
            "stage_durations_seconds": {},
        },
    )


def relative_to_output(path: Path, output_dir: Path) -> str:
    try:
        return str(path.resolve().relative_to(output_dir.resolve()))
    except ValueError:
        return str(path)

