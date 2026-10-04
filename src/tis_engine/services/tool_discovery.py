from __future__ import annotations

import os
import shutil
from pathlib import Path


class ToolNotFoundError(Exception):
    def __init__(self, executable: str) -> None:
        super().__init__(f"Executable not found: {executable}")
        self.executable = executable


def _is_path_like(command: str) -> bool:
    return (
        os.path.sep in command
        or (os.path.altsep is not None and os.path.altsep in command)
        or command.startswith(".")
        or Path(command).expanduser().is_absolute()
    )


def resolve_executable(executable: str | None, default_name: str | None = None) -> str:
    command = executable or default_name
    if not command:
        raise ToolNotFoundError("<not configured>")

    if _is_path_like(command):
        path = Path(command).expanduser()
        if path.is_file():
            return str(path)
        raise ToolNotFoundError(command)

    resolved = shutil.which(command)
    if resolved:
        return resolved
    raise ToolNotFoundError(command)

