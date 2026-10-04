from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path

from tis_engine.adapters.base import CommandResult, run_subprocess
from tis_engine.models.config import Dcm2niixConfig
from tis_engine.services.tool_discovery import resolve_executable


@dataclass(frozen=True)
class Dcm2niixOutputs:
    niftis: list[Path]
    sidecars: list[Path]
    primary_nifti: Path | None
    primary_sidecar: Path | None
    expected_primary_sidecar: Path | None


class Dcm2niixAdapter:
    def __init__(self, config: Dcm2niixConfig) -> None:
        self.config = config

    def convert(self, dicom_dir: Path, output_dir: Path) -> CommandResult:
        executable = resolve_executable(self.config.executable, "dcm2niix")
        output_dir.mkdir(parents=True, exist_ok=True)
        command = [
            executable,
            "-b",
            "y" if self.config.bids_sidecar else "n",
            "-o",
            str(output_dir),
            "-f",
            self.config.output_filename,
            *self.config.extra_args,
            str(dicom_dir),
        ]
        result = run_subprocess(
            stage="dcm2niix",
            command=command,
            timeout_seconds=self.config.timeout_seconds,
            artifacts=[output_dir],
        )
        if result.returncode != 0 or result.timed_out:
            return result

        outputs = discover_converted_outputs(output_dir)
        artifacts = [*outputs.niftis, *outputs.sidecars]
        return replace(result, artifacts=artifacts or [output_dir])


def discover_converted_outputs(output_dir: Path) -> Dcm2niixOutputs:
    niftis = sorted(
        {path for pattern in ("*.nii", "*.nii.gz") for path in output_dir.rglob(pattern)}
    )
    sidecars = sorted(output_dir.rglob("*.json"))
    primary_nifti = niftis[0] if niftis else None
    expected_sidecar = sidecar_path_for_nifti(primary_nifti) if primary_nifti else None
    primary_sidecar = (
        expected_sidecar
        if expected_sidecar is not None and expected_sidecar.is_file()
        else None
    )
    return Dcm2niixOutputs(
        niftis=niftis,
        sidecars=sidecars,
        primary_nifti=primary_nifti,
        primary_sidecar=primary_sidecar,
        expected_primary_sidecar=expected_sidecar,
    )


def sidecar_path_for_nifti(nifti_path: Path) -> Path:
    name = nifti_path.name
    if name.endswith(".nii.gz"):
        base = name[: -len(".nii.gz")]
    elif name.endswith(".nii"):
        base = name[: -len(".nii")]
    else:
        base = nifti_path.stem
    return nifti_path.with_name(f"{base}.json")
