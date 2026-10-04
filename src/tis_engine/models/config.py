from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class RunMode(str, Enum):
    FORWARD = "forward"
    INVERSE = "inverse"


class SolverBackend(str, Enum):
    SIMNIBS = "simnibs"
    TI_TOOLBOX = "ti_toolbox"


class MRIInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dicom_dir: Path | None = None
    t1_nifti: Path | None = None
    t2_nifti: Path | None = None

    @model_validator(mode="after")
    def require_some_mri_input(self) -> "MRIInput":
        if not self.dicom_dir and not self.t1_nifti:
            raise ValueError("mri must include dicom_dir or t1_nifti")
        return self


class StageToggles(BaseModel):
    model_config = ConfigDict(extra="forbid")

    convert_dicom: bool = False
    create_head_model: bool = False
    run_solver: bool = False


class OutputConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    work_dir: Path | None = None


class Dcm2niixConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    executable: str | None = None
    output_filename: str = "converted"
    bids_sidecar: bool = True
    extra_args: list[str] = Field(default_factory=list)
    timeout_seconds: int = Field(default=1800, ge=1)


class SimNIBSConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    charm_executable: str | None = None
    subject_id: str = Field(default="subject", min_length=1)
    subject_dir: Path | None = None
    charm_extra_args: list[str] = Field(default_factory=list)
    solver_executable: str | None = None
    parameter_file: Path | None = None
    solver_extra_args: list[str] = Field(default_factory=list)
    timeout_seconds: int = Field(default=7200, ge=1)


class TIToolboxConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    executable: str | None = None
    parameter_file: Path | None = None
    extra_args: list[str] = Field(default_factory=list)
    timeout_seconds: int = Field(default=7200, ge=1)


class ToolsConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dcm2niix: Dcm2niixConfig = Field(default_factory=Dcm2niixConfig)
    simnibs: SimNIBSConfig = Field(default_factory=SimNIBSConfig)
    ti_toolbox: TIToolboxConfig = Field(default_factory=TIToolboxConfig)


class JobConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = "1.0"
    job_id: str = Field(min_length=1)
    mode: RunMode
    mri: MRIInput
    outputs: OutputConfig = Field(default_factory=OutputConfig)
    stages: StageToggles = Field(default_factory=StageToggles)
    tools: ToolsConfig = Field(default_factory=ToolsConfig)
    solver_backend: SolverBackend = SolverBackend.SIMNIBS

    @model_validator(mode="after")
    def validate_stage_requirements(self) -> "JobConfig":
        if self.stages.convert_dicom and not self.mri.dicom_dir:
            raise ValueError("stages.convert_dicom requires mri.dicom_dir")
        if self.stages.create_head_model and not (
            self.mri.t1_nifti or self.stages.convert_dicom
        ):
            raise ValueError(
                "stages.create_head_model requires mri.t1_nifti or DICOM conversion"
            )
        return self
