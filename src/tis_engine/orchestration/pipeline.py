from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from tis_engine.adapters.base import CommandResult
from tis_engine.adapters.dcm2niix import Dcm2niixAdapter, discover_converted_outputs
from tis_engine.adapters.simnibs import SimNIBSAdapter
from tis_engine.adapters.ti_toolbox import TIToolboxAdapter
from tis_engine.models.config import JobConfig, MRIInput, SolverBackend
from tis_engine.services.outputs import (
    command_stage_record,
    relative_to_output,
    utc_now,
    write_json,
)
from tis_engine.services.tool_discovery import ToolNotFoundError
from tis_engine.services.validation import validate_runtime_inputs
from tis_engine.status_codes import StatusCode, status_message


class PipelineFailure(Exception):
    def __init__(
        self,
        code: StatusCode,
        stage: str,
        message: str,
        details: list[dict[str, Any]] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.stage = stage
        self.message = message
        self.details = details or [{"stage": stage, "message": message}]


def run_pipeline(config: JobConfig, output_dir: Path) -> StatusCode:
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    work_dir = (config.outputs.work_dir or (output_dir / "work")).resolve()
    work_dir.mkdir(parents=True, exist_ok=True)

    started = time.monotonic()
    started_at = utc_now()
    stages: list[dict[str, Any]] = []
    artifacts: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    exit_code = StatusCode.SUCCESS
    status = "success"

    manifest: dict[str, Any] = {
        "manifest_version": "1.0",
        "schema_version": config.schema_version,
        "job_id": config.job_id,
        "mode": config.mode.value,
        "status": status,
        "exit_code": int(exit_code),
        "exit_message": status_message(exit_code),
        "started_at": started_at,
        "finished_at": None,
        "duration_seconds": None,
        "stages": stages,
        "artifacts": artifacts,
        "errors": errors,
    }

    try:
        _preflight(config, stages)

        current_mri = config.mri
        if config.stages.convert_dicom:
            current_mri = _convert_dicom(config, current_mri, output_dir, stages, artifacts)

        if config.stages.create_head_model:
            _create_head_model(config, current_mri, work_dir, output_dir, stages, artifacts)

        if config.stages.run_solver:
            result = _run_solver(config, work_dir)
            _record_command_or_fail(
                output_dir,
                stages,
                result,
                StatusCode.SOLVER_FAILED,
                "Solver failed",
            )
            artifacts.extend(
                _artifact("solver_output", path, output_dir)
                for path in _artifact_paths(result, output_dir)
            )

    except ToolNotFoundError as exc:
        exit_code = StatusCode.EXTERNAL_TOOL_NOT_FOUND
        status = "failed"
        errors.append({"stage": "tool_discovery", "message": str(exc)})
    except PipelineFailure as exc:
        exit_code = exc.code
        status = "failed"
        errors.extend(exc.details)
    except Exception as exc:
        exit_code = StatusCode.INTERNAL_ERROR
        status = "failed"
        errors.append({"stage": "internal", "message": str(exc)})
    finally:
        finished_at = utc_now()
        duration = round(time.monotonic() - started, 3)
        manifest.update(
            {
                "status": status,
                "exit_code": int(exit_code),
                "exit_message": status_message(exit_code),
                "finished_at": finished_at,
                "duration_seconds": duration,
            }
        )
        artifacts.append({"name": "output_manifest", "path": "output_manifest.json"})
        artifacts.append({"name": "metrics", "path": "metrics.json"})
        write_json(output_dir / "output_manifest.json", manifest)
        write_json(
            output_dir / "metrics.json",
            {
                "job_id": config.job_id,
                "status": status,
                "exit_code": int(exit_code),
                "duration_seconds": duration,
                "stage_durations_seconds": {
                    stage["name"]: stage.get("duration_seconds")
                    for stage in stages
                    if stage.get("duration_seconds") is not None
                },
            },
        )

    return exit_code


def _preflight(config: JobConfig, stages: list[dict[str, Any]]) -> None:
    started_at = utc_now()
    validation = validate_runtime_inputs(config)
    stages.append(
        {
            "name": "preflight",
            "status": "success" if validation.ok else "failed",
            "started_at": started_at,
            "finished_at": utc_now(),
            "duration_seconds": 0,
            "error": None if validation.ok else "Runtime validation failed",
        }
    )
    if not validation.ok:
        raise PipelineFailure(
            StatusCode.MISSING_OR_INVALID_INPUT,
            "preflight",
            "Runtime validation failed",
            validation.errors,
        )


def _convert_dicom(
    config: JobConfig,
    current_mri: MRIInput,
    output_dir: Path,
    stages: list[dict[str, Any]],
    artifacts: list[dict[str, Any]],
) -> MRIInput:
    if not current_mri.dicom_dir:
        raise PipelineFailure(
            StatusCode.MISSING_OR_INVALID_INPUT,
            "preflight",
            "DICOM conversion requires mri.dicom_dir",
        )

    converted_dir = output_dir / "converted"
    result = Dcm2niixAdapter(config.tools.dcm2niix).convert(
        current_mri.dicom_dir,
        converted_dir,
    )
    _raise_for_command_failure(
        output_dir,
        stages,
        result,
        StatusCode.DICOM_CONVERSION_FAILED,
        "DICOM conversion failed",
    )

    converted_outputs = discover_converted_outputs(converted_dir)
    if not converted_outputs.primary_nifti:
        message = "dcm2niix completed without producing a NIfTI file"
        stages.append(command_stage_record(output_dir, result, "failed", message))
        raise PipelineFailure(
            StatusCode.DICOM_CONVERSION_FAILED,
            "dcm2niix",
            message,
        )

    stages.append(command_stage_record(output_dir, result, "success"))
    artifacts.append(_artifact("converted_nifti", converted_outputs.primary_nifti, output_dir))
    if converted_outputs.primary_sidecar:
        artifacts.append(
            _artifact(
                "converted_bids_sidecar",
                converted_outputs.primary_sidecar,
                output_dir,
            )
        )
    elif converted_outputs.expected_primary_sidecar:
        artifacts.append(
            _artifact(
                "converted_bids_sidecar",
                converted_outputs.expected_primary_sidecar,
                output_dir,
                status="missing",
            )
        )

    return current_mri.model_copy(update={"t1_nifti": converted_outputs.primary_nifti})


def _create_head_model(
    config: JobConfig,
    current_mri: MRIInput,
    work_dir: Path,
    output_dir: Path,
    stages: list[dict[str, Any]],
    artifacts: list[dict[str, Any]],
) -> None:
    adapter = SimNIBSAdapter(config.tools.simnibs)
    result = adapter.create_head_model(current_mri, work_dir)
    _raise_for_command_failure(
        output_dir,
        stages,
        result,
        StatusCode.HEAD_MODEL_FAILED,
        "Head model creation failed",
    )

    outputs = adapter.expected_head_model_outputs(work_dir)
    missing = outputs.missing_paths()
    if missing:
        missing_text = ", ".join(str(path) for path in missing)
        message = f"SimNIBS CHARM completed but expected outputs are missing: {missing_text}"
        stages.append(command_stage_record(output_dir, result, "failed", message))
        for path in outputs.expected_paths:
            artifacts.append(
                _artifact(
                    _head_model_artifact_name(path, outputs.mesh_file),
                    path,
                    output_dir,
                    status="present" if path.exists() else "missing",
                )
            )
        raise PipelineFailure(
            StatusCode.HEAD_MODEL_FAILED,
            "simnibs_charm",
            message,
            [{"stage": "simnibs_charm", "message": message, "missing_paths": missing_text}],
        )

    stages.append(command_stage_record(output_dir, result, "success"))
    artifacts.append(_artifact("simnibs_m2m_dir", outputs.m2m_dir, output_dir))
    artifacts.append(_artifact("simnibs_mesh", outputs.mesh_file, output_dir))


def _run_solver(config: JobConfig, work_dir: Path) -> CommandResult:
    if config.solver_backend == SolverBackend.SIMNIBS:
        return SimNIBSAdapter(config.tools.simnibs).run_solver(work_dir)
    return TIToolboxAdapter(config.tools.ti_toolbox).run_solver(work_dir)


def _record_command_or_fail(
    output_dir: Path,
    stages: list[dict[str, Any]],
    result: CommandResult,
    failure_code: StatusCode,
    failure_message: str,
) -> None:
    _raise_for_command_failure(output_dir, stages, result, failure_code, failure_message)
    stages.append(command_stage_record(output_dir, result, "success"))


def _raise_for_command_failure(
    output_dir: Path,
    stages: list[dict[str, Any]],
    result: CommandResult,
    failure_code: StatusCode,
    failure_message: str,
) -> None:
    if result.timed_out:
        stages.append(
            command_stage_record(output_dir, result, "failed", "Command timed out")
        )
        raise PipelineFailure(
            StatusCode.TIMEOUT,
            result.stage,
            f"{result.stage} timed out",
        )
    if result.returncode != 0:
        message = f"{failure_message} with exit code {result.returncode}"
        stages.append(command_stage_record(output_dir, result, "failed", message))
        raise PipelineFailure(failure_code, result.stage, message)


def _artifact(
    name: str,
    path: Path | str,
    output_dir: Path,
    *,
    status: str = "present",
) -> dict[str, Any]:
    path_obj = Path(path)
    return {
        "name": name,
        "path": relative_to_output(path_obj, output_dir),
        "status": status,
    }


def _artifact_paths(result: CommandResult, output_dir: Path) -> list[str]:
    return [relative_to_output(path, output_dir) for path in result.artifacts]


def _head_model_artifact_name(path: Path, mesh_file: Path) -> str:
    if path == mesh_file:
        return "simnibs_mesh"
    return "simnibs_m2m_dir"
