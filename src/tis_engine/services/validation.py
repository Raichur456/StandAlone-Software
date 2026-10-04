from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from tis_engine.models.config import JobConfig, SolverBackend


class ConfigLoadError(Exception):
    def __init__(self, message: str, details: list[dict[str, Any]] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or []


@dataclass(frozen=True)
class RuntimeValidationResult:
    errors: list[dict[str, str]]

    @property
    def ok(self) -> bool:
        return not self.errors


def load_job_config(config_path: Path) -> JobConfig:
    try:
        raw = config_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ConfigLoadError(f"Could not read config: {exc}") from exc

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ConfigLoadError(
            f"Config is not valid JSON: {exc.msg}",
            [{"loc": f"line {exc.lineno}, column {exc.colno}", "msg": exc.msg}],
        ) from exc

    try:
        config = JobConfig.model_validate(data)
    except ValidationError as exc:
        raise ConfigLoadError("Config failed validation", exc.errors()) from exc

    return resolve_config_paths(config, config_path.parent)


def resolve_config_paths(config: JobConfig, base_dir: Path) -> JobConfig:
    mri = config.mri.model_copy(
        update={
            "dicom_dir": _resolve_optional_path(config.mri.dicom_dir, base_dir),
            "t1_nifti": _resolve_optional_path(config.mri.t1_nifti, base_dir),
            "t2_nifti": _resolve_optional_path(config.mri.t2_nifti, base_dir),
        }
    )
    outputs = config.outputs.model_copy(
        update={"work_dir": _resolve_optional_path(config.outputs.work_dir, base_dir)}
    )
    simnibs = config.tools.simnibs.model_copy(
        update={
            "subject_dir": _resolve_optional_path(
                config.tools.simnibs.subject_dir, base_dir
            ),
            "parameter_file": _resolve_optional_path(
                config.tools.simnibs.parameter_file, base_dir
            ),
        }
    )
    ti_toolbox = config.tools.ti_toolbox.model_copy(
        update={
            "parameter_file": _resolve_optional_path(
                config.tools.ti_toolbox.parameter_file, base_dir
            )
        }
    )
    tools = config.tools.model_copy(
        update={"simnibs": simnibs, "ti_toolbox": ti_toolbox}
    )
    return config.model_copy(update={"mri": mri, "outputs": outputs, "tools": tools})


def validate_runtime_inputs(config: JobConfig) -> RuntimeValidationResult:
    errors: list[dict[str, str]] = []

    dicom_exists = bool(config.mri.dicom_dir and config.mri.dicom_dir.is_dir())
    t1_exists = bool(config.mri.t1_nifti and config.mri.t1_nifti.is_file())

    if config.mri.dicom_dir and not dicom_exists:
        errors.append(
            {
                "field": "mri.dicom_dir",
                "message": f"Directory does not exist: {config.mri.dicom_dir}",
            }
        )
    if config.mri.t1_nifti and not t1_exists:
        errors.append(
            {
                "field": "mri.t1_nifti",
                "message": f"File does not exist: {config.mri.t1_nifti}",
            }
        )
    if config.mri.t2_nifti and not config.mri.t2_nifti.is_file():
        errors.append(
            {
                "field": "mri.t2_nifti",
                "message": f"File does not exist: {config.mri.t2_nifti}",
            }
        )

    if config.stages.convert_dicom and not dicom_exists:
        errors.append(
            {
                "field": "mri.dicom_dir",
                "message": "DICOM conversion requires an existing DICOM directory",
            }
        )

    has_head_model_input = t1_exists or (config.stages.convert_dicom and dicom_exists)
    if config.stages.create_head_model and not has_head_model_input:
        errors.append(
            {
                "field": "mri.t1_nifti",
                "message": "Head model creation requires an existing T1 NIfTI or an existing DICOM directory with conversion enabled",
            }
        )

    if config.stages.run_solver:
        errors.extend(_solver_parameter_errors(config))

    return RuntimeValidationResult(_dedupe_errors(errors))


def _solver_parameter_errors(config: JobConfig) -> list[dict[str, str]]:
    if config.solver_backend == SolverBackend.SIMNIBS:
        parameter_file = config.tools.simnibs.parameter_file
        executable = config.tools.simnibs.solver_executable
        prefix = "tools.simnibs"
    else:
        parameter_file = config.tools.ti_toolbox.parameter_file
        executable = config.tools.ti_toolbox.executable
        prefix = "tools.ti_toolbox"

    errors: list[dict[str, str]] = []
    if not executable:
        errors.append(
            {
                "field": f"{prefix}.executable",
                "message": "Solver stage requires an explicit backend executable",
            }
        )
    if not parameter_file:
        errors.append(
            {
                "field": f"{prefix}.parameter_file",
                "message": "Solver stage requires a backend parameter file",
            }
        )
    elif not parameter_file.is_file():
        errors.append(
            {
                "field": f"{prefix}.parameter_file",
                "message": f"File does not exist: {parameter_file}",
            }
        )
    return errors


def _resolve_optional_path(path: Path | None, base_dir: Path) -> Path | None:
    if path is None:
        return None
    expanded = Path(path).expanduser()
    if expanded.is_absolute():
        return expanded
    return (base_dir / expanded).resolve()


def _dedupe_errors(errors: list[dict[str, str]]) -> list[dict[str, str]]:
    seen: set[tuple[str, str]] = set()
    deduped: list[dict[str, str]] = []
    for error in errors:
        key = (error["field"], error["message"])
        if key not in seen:
            deduped.append(error)
            seen.add(key)
    return deduped
