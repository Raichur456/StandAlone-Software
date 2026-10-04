from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from tis_engine.adapters.dcm2niix import (
    Dcm2niixAdapter,
    discover_converted_outputs,
    sidecar_path_for_nifti,
)
from tis_engine.models.config import Dcm2niixConfig


def test_dcm2niix_adapter_builds_command_and_discovers_outputs(
    monkeypatch,
    tmp_path: Path,
) -> None:
    calls = {}

    def fake_run(command, **kwargs):
        calls["command"] = command
        calls["kwargs"] = kwargs
        output_dir = Path(command[command.index("-o") + 1])
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "scan.nii.gz").write_text("nifti", encoding="utf-8")
        (output_dir / "scan.json").write_text("{}", encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, "ok", "")

    monkeypatch.setattr("tis_engine.adapters.base.subprocess.run", fake_run)
    adapter = Dcm2niixAdapter(
        Dcm2niixConfig(executable=sys.executable, output_filename="scan")
    )

    result = adapter.convert(tmp_path, tmp_path / "out")

    assert result.returncode == 0
    assert calls["command"][0] == sys.executable
    assert calls["command"][:3] == [sys.executable, "-b", "y"]
    assert "-o" in calls["command"]
    assert "scan" in calls["command"]
    assert calls["kwargs"]["capture_output"] is True
    assert calls["kwargs"]["text"] is True
    assert tmp_path / "out" / "scan.nii.gz" in result.artifacts
    assert tmp_path / "out" / "scan.json" in result.artifacts


def test_discover_converted_outputs_pairs_nii_gz_sidecar(tmp_path: Path) -> None:
    nifti = tmp_path / "sub-001_T1w.nii.gz"
    sidecar = tmp_path / "sub-001_T1w.json"
    nifti.write_text("nifti", encoding="utf-8")
    sidecar.write_text("{}", encoding="utf-8")

    outputs = discover_converted_outputs(tmp_path)

    assert outputs.primary_nifti == nifti
    assert outputs.primary_sidecar == sidecar
    assert sidecar_path_for_nifti(nifti) == sidecar


def test_discover_converted_outputs_reports_missing_sidecar(tmp_path: Path) -> None:
    nifti = tmp_path / "sub-001_T1w.nii"
    nifti.write_text("nifti", encoding="utf-8")

    outputs = discover_converted_outputs(tmp_path)

    assert outputs.primary_nifti == nifti
    assert outputs.primary_sidecar is None
    assert outputs.expected_primary_sidecar == tmp_path / "sub-001_T1w.json"
