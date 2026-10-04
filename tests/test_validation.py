from __future__ import annotations

from pathlib import Path

from tis_engine.models.config import JobConfig
from tis_engine.services.validation import validate_runtime_inputs


def test_runtime_validation_accepts_existing_t1(tmp_path: Path) -> None:
    t1 = tmp_path / "T1.nii.gz"
    t1.write_text("dummy", encoding="utf-8")
    config = JobConfig.model_validate(
        {
            "schema_version": "1.0",
            "job_id": "ok",
            "mode": "forward",
            "mri": {"t1_nifti": t1},
        }
    )

    result = validate_runtime_inputs(config)

    assert result.ok


def test_runtime_validation_accepts_dicom_conversion_for_head_model(
    tmp_path: Path,
) -> None:
    dicom_dir = tmp_path / "dicom"
    dicom_dir.mkdir()
    config = JobConfig.model_validate(
        {
            "schema_version": "1.0",
            "job_id": "dicom-head-model",
            "mode": "forward",
            "mri": {"dicom_dir": dicom_dir},
            "stages": {"convert_dicom": True, "create_head_model": True},
        }
    )

    result = validate_runtime_inputs(config)

    assert result.ok


def test_runtime_validation_reports_missing_dicom_folder() -> None:
    config = JobConfig.model_validate(
        {
            "schema_version": "1.0",
            "job_id": "missing-dicom",
            "mode": "forward",
            "mri": {"dicom_dir": "missing-dicom"},
            "stages": {"convert_dicom": True},
        }
    )

    result = validate_runtime_inputs(config)

    assert not result.ok
    assert any(error["field"] == "mri.dicom_dir" for error in result.errors)


def test_runtime_validation_reports_missing_t1() -> None:
    config = JobConfig.model_validate(
        {
            "schema_version": "1.0",
            "job_id": "missing",
            "mode": "forward",
            "mri": {"t1_nifti": "missing.nii.gz"},
        }
    )

    result = validate_runtime_inputs(config)

    assert not result.ok
    assert result.errors[0]["field"] == "mri.t1_nifti"


def test_solver_stage_requires_parameter_file(tmp_path: Path) -> None:
    t1 = tmp_path / "T1.nii.gz"
    t1.write_text("dummy", encoding="utf-8")
    config = JobConfig.model_validate(
        {
            "schema_version": "1.0",
            "job_id": "solver",
            "mode": "inverse",
            "mri": {"t1_nifti": t1},
            "stages": {"run_solver": True},
            "tools": {"simnibs": {"solver_executable": "solver"}},
        }
    )

    result = validate_runtime_inputs(config)

    assert not result.ok
    assert any(error["field"] == "tools.simnibs.parameter_file" for error in result.errors)
