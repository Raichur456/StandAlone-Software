from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from tis_engine.adapters.base import CommandResult, run_subprocess
from tis_engine.models.config import MRIInput, SimNIBSConfig
from tis_engine.services.tool_discovery import resolve_executable


@dataclass(frozen=True)
class CharmOutputs:
    work_dir: Path
    m2m_dir: Path
    mesh_file: Path

    @property
    def expected_paths(self) -> list[Path]:
        return [self.m2m_dir, self.mesh_file]

    def missing_paths(self) -> list[Path]:
        return [path for path in self.expected_paths if not path.exists()]


class SimNIBSAdapter:
    def __init__(self, config: SimNIBSConfig) -> None:
        self.config = config

    def create_head_model(self, mri: MRIInput, work_dir: Path) -> CommandResult:
        if not mri.t1_nifti:
            raise ValueError("SimNIBS charm requires a T1 NIfTI path")

        executable = resolve_executable(self.config.charm_executable, "charm")
        outputs = self.expected_head_model_outputs(work_dir)
        outputs.work_dir.mkdir(parents=True, exist_ok=True)

        command = [
            executable,
            self.config.subject_id,
            str(mri.t1_nifti),
        ]
        if mri.t2_nifti:
            command.append(str(mri.t2_nifti))
        command.extend(self.config.charm_extra_args)

        return run_subprocess(
            stage="simnibs_charm",
            command=command,
            timeout_seconds=self.config.timeout_seconds,
            cwd=outputs.work_dir,
            artifacts=outputs.expected_paths,
        )

    def expected_head_model_outputs(self, work_dir: Path) -> CharmOutputs:
        charm_work_dir = self.config.subject_dir or (work_dir / "simnibs")
        return CharmOutputs(
            work_dir=charm_work_dir,
            m2m_dir=charm_work_dir / f"m2m_{self.config.subject_id}",
            mesh_file=charm_work_dir / f"{self.config.subject_id}.msh",
        )

    def run_solver(self, work_dir: Path) -> CommandResult:
        executable = resolve_executable(self.config.solver_executable)
        if not self.config.parameter_file:
            raise ValueError("SimNIBS solver requires a parameter_file")

        solver_dir = work_dir / "simnibs_solver"
        solver_dir.mkdir(parents=True, exist_ok=True)
        command = [
            executable,
            str(self.config.parameter_file),
            *self.config.solver_extra_args,
        ]
        return run_subprocess(
            stage="simnibs_solver",
            command=command,
            timeout_seconds=self.config.timeout_seconds,
            cwd=solver_dir,
            artifacts=[solver_dir],
        )
