from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from tis_engine.models.config import JobConfig
from tis_engine.orchestration.pipeline import run_pipeline
from tis_engine.status_codes import StatusCode


def test_pipeline_writes_manifest_for_success(tmp_path: Path) -> None:
    t1 = tmp_path / "T1.nii.gz"
    t1.write_text("dummy", encoding="utf-8")
    config = JobConfig.model_validate(
        {
            "schema_version": "1.0",
            "job_id": "success",
            "mode": "forward",
            "mri": {"t1_nifti": t1},
            "stages": {
                "convert_dicom": False,
                "create_head_model": False,
                "run_solver": False,
            },
        }
    )

    code = run_pipeline(config, tmp_path / "out")

    manifest = _read_manifest(tmp_path)
    assert code == StatusCode.SUCCESS
    assert manifest["status"] == "success"
    assert manifest["exit_code"] == 0
    assert manifest["stages"][0]["name"] == "preflight"


def test_pipeline_converts_dicom_and_records_nifti_and_sidecar(
    monkeypatch,
    tmp_path: Path,
) -> None:
    def fake_run(command, **kwargs):
        output_dir = Path(command[command.index("-o") + 1])
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "converted.nii.gz").write_text("nifti", encoding="utf-8")
        (output_dir / "converted.json").write_text("{}", encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, "converted", "")

    monkeypatch.setattr("tis_engine.adapters.base.subprocess.run", fake_run)
    dicom_dir = tmp_path / "dicom"
    dicom_dir.mkdir()
    config = JobConfig.model_validate(
        {
            "schema_version": "1.0",
            "job_id": "dicom",
            "mode": "forward",
            "mri": {"dicom_dir": dicom_dir},
            "stages": {"convert_dicom": True},
            "tools": {"dcm2niix": {"executable": sys.executable}},
        }
    )

    code = run_pipeline(config, tmp_path / "out")

    manifest = _read_manifest(tmp_path)
    assert code == StatusCode.SUCCESS
    assert _artifact(manifest, "converted_nifti")["path"].replace("\\", "/") == "converted/converted.nii.gz"
    assert _artifact(manifest, "converted_bids_sidecar")["path"].replace("\\", "/") == "converted/converted.json"


def test_pipeline_converts_dicom_then_runs_charm(monkeypatch, tmp_path: Path) -> None:
    charm_command = {}

    def fake_run(command, **kwargs):
        if "-o" in command:
            output_dir = Path(command[command.index("-o") + 1])
            output_dir.mkdir(parents=True, exist_ok=True)
            (output_dir / "converted.nii.gz").write_text("nifti", encoding="utf-8")
            (output_dir / "converted.json").write_text("{}", encoding="utf-8")
            return subprocess.CompletedProcess(command, 0, "converted", "")

        charm_command["command"] = command
        work_dir = Path(kwargs["cwd"])
        subject_id = command[1]
        (work_dir / f"m2m_{subject_id}").mkdir(parents=True)
        (work_dir / f"{subject_id}.msh").write_text("mesh", encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, "charm", "")

    monkeypatch.setattr("tis_engine.adapters.base.subprocess.run", fake_run)
    dicom_dir = tmp_path / "dicom"
    dicom_dir.mkdir()
    config = JobConfig.model_validate(
        {
            "schema_version": "1.0",
            "job_id": "dicom-to-charm",
            "mode": "forward",
            "mri": {"dicom_dir": dicom_dir},
            "stages": {"convert_dicom": True, "create_head_model": True},
            "tools": {
                "dcm2niix": {"executable": sys.executable},
                "simnibs": {
                    "charm_executable": sys.executable,
                    "subject_id": "sub-001",
                },
            },
        }
    )

    code = run_pipeline(config, tmp_path / "out")

    manifest = _read_manifest(tmp_path)
    assert code == StatusCode.SUCCESS
    assert charm_command["command"][2].replace("\\", "/").endswith("converted/converted.nii.gz")
    assert _artifact(manifest, "converted_nifti")["status"] == "present"
    assert _artifact(manifest, "simnibs_mesh")["status"] == "present"


def test_pipeline_marks_missing_dicom_folder_as_invalid_input(tmp_path: Path) -> None:
    config = JobConfig.model_validate(
        {
            "schema_version": "1.0",
            "job_id": "missing-dicom",
            "mode": "forward",
            "mri": {"dicom_dir": tmp_path / "missing"},
            "stages": {"convert_dicom": True},
        }
    )

    code = run_pipeline(config, tmp_path / "out")

    assert code == StatusCode.MISSING_OR_INVALID_INPUT
    assert _read_manifest(tmp_path)["exit_code"] == int(StatusCode.MISSING_OR_INVALID_INPUT)


def test_pipeline_marks_missing_t1_as_invalid_input(tmp_path: Path) -> None:
    config = JobConfig.model_validate(
        {
            "schema_version": "1.0",
            "job_id": "missing-t1",
            "mode": "forward",
            "mri": {"t1_nifti": tmp_path / "missing.nii.gz"},
            "stages": {"create_head_model": True},
        }
    )

    code = run_pipeline(config, tmp_path / "out")

    assert code == StatusCode.MISSING_OR_INVALID_INPUT


def test_pipeline_runs_charm_and_records_expected_outputs(
    monkeypatch,
    tmp_path: Path,
) -> None:
    def fake_run(command, **kwargs):
        work_dir = Path(kwargs["cwd"])
        subject_id = command[1]
        (work_dir / f"m2m_{subject_id}").mkdir(parents=True)
        (work_dir / f"{subject_id}.msh").write_text("mesh", encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, "charm", "")

    monkeypatch.setattr("tis_engine.adapters.base.subprocess.run", fake_run)
    t1 = tmp_path / "T1.nii.gz"
    t1.write_text("dummy", encoding="utf-8")
    config = JobConfig.model_validate(
        {
            "schema_version": "1.0",
            "job_id": "charm",
            "mode": "forward",
            "mri": {"t1_nifti": t1},
            "stages": {"create_head_model": True},
            "tools": {
                "simnibs": {
                    "charm_executable": sys.executable,
                    "subject_id": "sub-001",
                }
            },
        }
    )

    code = run_pipeline(config, tmp_path / "out")

    manifest = _read_manifest(tmp_path)
    assert code == StatusCode.SUCCESS
    assert _artifact(manifest, "simnibs_m2m_dir")["path"].replace("\\", "/") == "work/simnibs/m2m_sub-001"
    assert _artifact(manifest, "simnibs_mesh")["path"].replace("\\", "/") == "work/simnibs/sub-001.msh"


def test_pipeline_fails_charm_when_expected_outputs_are_missing(
    monkeypatch,
    tmp_path: Path,
) -> None:
    def fake_run(command, **kwargs):
        return subprocess.CompletedProcess(command, 0, "charm", "")

    monkeypatch.setattr("tis_engine.adapters.base.subprocess.run", fake_run)
    t1 = tmp_path / "T1.nii.gz"
    t1.write_text("dummy", encoding="utf-8")
    config = _charm_config(tmp_path, t1)

    code = run_pipeline(config, tmp_path / "out")

    manifest = _read_manifest(tmp_path)
    assert code == StatusCode.HEAD_MODEL_FAILED
    assert manifest["stages"][-1]["status"] == "failed"
    assert "expected outputs are missing" in manifest["stages"][-1]["error"]
    assert _artifact(manifest, "simnibs_mesh")["status"] == "missing"


def test_pipeline_maps_charm_failure(monkeypatch, tmp_path: Path) -> None:
    def fake_run(command, **kwargs):
        return subprocess.CompletedProcess(command, 22, "", "charm failed")

    monkeypatch.setattr("tis_engine.adapters.base.subprocess.run", fake_run)
    t1 = tmp_path / "T1.nii.gz"
    t1.write_text("dummy", encoding="utf-8")
    config = _charm_config(tmp_path, t1)

    code = run_pipeline(config, tmp_path / "out")

    manifest = _read_manifest(tmp_path)
    assert code == StatusCode.HEAD_MODEL_FAILED
    assert manifest["exit_code"] == int(StatusCode.HEAD_MODEL_FAILED)
    assert manifest["stages"][-1]["name"] == "simnibs_charm"
    assert (tmp_path / "out" / "logs" / "simnibs_charm.stderr.log").is_file()


def test_pipeline_maps_missing_charm_executable(tmp_path: Path) -> None:
    t1 = tmp_path / "T1.nii.gz"
    t1.write_text("dummy", encoding="utf-8")
    config = JobConfig.model_validate(
        {
            "schema_version": "1.0",
            "job_id": "missing-charm",
            "mode": "forward",
            "mri": {"t1_nifti": t1},
            "stages": {"create_head_model": True},
            "tools": {
                "simnibs": {
                    "charm_executable": "definitely-not-a-real-charm-tool",
                    "subject_id": "sub-001",
                }
            },
        }
    )

    code = run_pipeline(config, tmp_path / "out")

    manifest = _read_manifest(tmp_path)
    assert code == StatusCode.EXTERNAL_TOOL_NOT_FOUND
    assert manifest["exit_code"] == int(StatusCode.EXTERNAL_TOOL_NOT_FOUND)


def test_pipeline_maps_charm_timeout(monkeypatch, tmp_path: Path) -> None:
    def fake_run(command, **kwargs):
        raise subprocess.TimeoutExpired(command, timeout=1, output="partial")

    monkeypatch.setattr("tis_engine.adapters.base.subprocess.run", fake_run)
    t1 = tmp_path / "T1.nii.gz"
    t1.write_text("dummy", encoding="utf-8")
    config = _charm_config(tmp_path, t1)

    code = run_pipeline(config, tmp_path / "out")

    assert code == StatusCode.TIMEOUT


def test_pipeline_maps_solver_failure(monkeypatch, tmp_path: Path) -> None:
    def fake_run(command, **kwargs):
        return subprocess.CompletedProcess(command, 22, "", "failed")

    monkeypatch.setattr("tis_engine.adapters.base.subprocess.run", fake_run)
    t1 = tmp_path / "T1.nii.gz"
    params = tmp_path / "params.json"
    t1.write_text("dummy", encoding="utf-8")
    params.write_text("{}", encoding="utf-8")
    config = JobConfig.model_validate(
        {
            "schema_version": "1.0",
            "job_id": "solver-fail",
            "mode": "inverse",
            "mri": {"t1_nifti": t1},
            "stages": {"run_solver": True},
            "tools": {
                "simnibs": {
                    "solver_executable": sys.executable,
                    "parameter_file": params,
                }
            },
        }
    )

    code = run_pipeline(config, tmp_path / "out")

    manifest = _read_manifest(tmp_path)
    assert code == StatusCode.SOLVER_FAILED
    assert manifest["exit_code"] == int(StatusCode.SOLVER_FAILED)
    assert manifest["stages"][-1]["name"] == "simnibs_solver"
    assert (tmp_path / "out" / "logs" / "simnibs_solver.stderr.log").is_file()


def test_pipeline_maps_timeout(monkeypatch, tmp_path: Path) -> None:
    def fake_run(command, **kwargs):
        raise subprocess.TimeoutExpired(command, timeout=1, output="partial")

    monkeypatch.setattr("tis_engine.adapters.base.subprocess.run", fake_run)
    t1 = tmp_path / "T1.nii.gz"
    params = tmp_path / "params.json"
    t1.write_text("dummy", encoding="utf-8")
    params.write_text("{}", encoding="utf-8")
    config = JobConfig.model_validate(
        {
            "schema_version": "1.0",
            "job_id": "timeout",
            "mode": "inverse",
            "mri": {"t1_nifti": t1},
            "stages": {"run_solver": True},
            "tools": {
                "simnibs": {
                    "solver_executable": sys.executable,
                    "parameter_file": params,
                }
            },
        }
    )

    code = run_pipeline(config, tmp_path / "out")

    assert code == StatusCode.TIMEOUT


def test_pipeline_maps_missing_tool(tmp_path: Path) -> None:
    t1 = tmp_path / "T1.nii.gz"
    params = tmp_path / "params.json"
    t1.write_text("dummy", encoding="utf-8")
    params.write_text("{}", encoding="utf-8")
    config = JobConfig.model_validate(
        {
            "schema_version": "1.0",
            "job_id": "missing-tool",
            "mode": "inverse",
            "mri": {"t1_nifti": t1},
            "stages": {"run_solver": True},
            "tools": {
                "simnibs": {
                    "solver_executable": "definitely-not-a-real-tis-tool",
                    "parameter_file": params,
                }
            },
        }
    )

    code = run_pipeline(config, tmp_path / "out")

    manifest = _read_manifest(tmp_path)
    assert code == StatusCode.EXTERNAL_TOOL_NOT_FOUND
    assert manifest["exit_code"] == int(StatusCode.EXTERNAL_TOOL_NOT_FOUND)


def _charm_config(tmp_path: Path, t1: Path) -> JobConfig:
    return JobConfig.model_validate(
        {
            "schema_version": "1.0",
            "job_id": "charm",
            "mode": "forward",
            "mri": {"t1_nifti": t1},
            "stages": {"create_head_model": True},
            "tools": {
                "simnibs": {
                    "charm_executable": sys.executable,
                    "subject_id": "sub-001",
                }
            },
        }
    )


def _read_manifest(tmp_path: Path) -> dict:
    return json.loads((tmp_path / "out" / "output_manifest.json").read_text())


def _artifact(manifest: dict, name: str) -> dict:
    return next(artifact for artifact in manifest["artifacts"] if artifact["name"] == name)
