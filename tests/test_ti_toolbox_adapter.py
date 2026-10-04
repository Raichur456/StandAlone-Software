from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from tis_engine.adapters.ti_toolbox import TIToolboxAdapter
from tis_engine.models.config import TIToolboxConfig


def test_ti_toolbox_solver_passes_parameter_file(monkeypatch, tmp_path: Path) -> None:
    calls = {}

    def fake_run(command, **kwargs):
        calls["command"] = command
        return subprocess.CompletedProcess(command, 0, "ok", "")

    monkeypatch.setattr("tis_engine.adapters.base.subprocess.run", fake_run)
    params = tmp_path / "params.json"
    params.write_text("{}", encoding="utf-8")
    adapter = TIToolboxAdapter(
        TIToolboxConfig(executable=sys.executable, parameter_file=params)
    )

    result = adapter.run_solver(tmp_path / "work")

    assert result.returncode == 0
    assert calls["command"][:2] == [sys.executable, str(params)]

