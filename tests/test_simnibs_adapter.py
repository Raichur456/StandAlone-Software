from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from tis_engine.adapters.simnibs import SimNIBSAdapter
from tis_engine.models.config import MRIInput, SimNIBSConfig


def test_simnibs_charm_uses_t1_t2_and_expected_outputs(
    monkeypatch,
    tmp_path: Path,
) -> None:
    calls = {}

    def fake_run(command, **kwargs):
        calls["command"] = command
        calls["kwargs"] = kwargs
        return subprocess.CompletedProcess(command, 0, "ok", "")

    monkeypatch.setattr("tis_engine.adapters.base.subprocess.run", fake_run)
    t1 = tmp_path / "T1.nii.gz"
    t2 = tmp_path / "T2.nii.gz"
    t1.write_text("dummy", encoding="utf-8")
    t2.write_text("dummy", encoding="utf-8")

    adapter = SimNIBSAdapter(
        SimNIBSConfig(charm_executable=sys.executable, subject_id="sub-001")
    )
    result = adapter.create_head_model(
        MRIInput(t1_nifti=t1, t2_nifti=t2),
        tmp_path / "work",
    )

    expected = adapter.expected_head_model_outputs(tmp_path / "work")
    assert result.returncode == 0
    assert calls["command"][:3] == [sys.executable, "sub-001", str(t1)]
    assert str(t2) in calls["command"]
    assert calls["kwargs"]["cwd"] == str(expected.work_dir)
    assert result.artifacts == [expected.m2m_dir, expected.mesh_file]


def test_simnibs_solver_passes_parameter_file(monkeypatch, tmp_path: Path) -> None:
    calls = {}

    def fake_run(command, **kwargs):
        calls["command"] = command
        return subprocess.CompletedProcess(command, 0, "ok", "")

    monkeypatch.setattr("tis_engine.adapters.base.subprocess.run", fake_run)
    params = tmp_path / "params.json"
    params.write_text("{}", encoding="utf-8")
    adapter = SimNIBSAdapter(
        SimNIBSConfig(solver_executable=sys.executable, parameter_file=params)
    )

    result = adapter.run_solver(tmp_path / "work")

    assert result.returncode == 0
    assert calls["command"][:2] == [sys.executable, str(params)]
