from __future__ import annotations

from pathlib import Path

from tis_engine.adapters.base import CommandResult, run_subprocess
from tis_engine.models.config import TIToolboxConfig
from tis_engine.services.tool_discovery import resolve_executable


class TIToolboxAdapter:
    def __init__(self, config: TIToolboxConfig) -> None:
        self.config = config

    def run_solver(self, work_dir: Path) -> CommandResult:
        executable = resolve_executable(self.config.executable)
        if not self.config.parameter_file:
            raise ValueError("TI-Toolbox solver requires a parameter_file")

        solver_dir = work_dir / "ti_toolbox_solver"
        solver_dir.mkdir(parents=True, exist_ok=True)
        command = [
            executable,
            str(self.config.parameter_file),
            *self.config.extra_args,
        ]
        return run_subprocess(
            stage="ti_toolbox_solver",
            command=command,
            timeout_seconds=self.config.timeout_seconds,
            cwd=solver_dir,
            artifacts=[solver_dir],
        )

