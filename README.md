# TIS Standalone Engine

`tis-engine` is a standalone orchestration layer for temporal interference
stimulation compute workflows. It is designed to be launched by external host
software as a Windows executable or CLI process.

The engine validates a JSON job config, runs external tools such as `dcm2niix`,
SimNIBS, or TI-Toolbox through adapters, and writes machine-readable outputs
for the host to display, save, and reload. The first real integration path is
DICOM or T1/T2 NIfTI input through SimNIBS CHARM head-model creation.

## Host Contract

The host calls:

```powershell
tis-engine.exe run --config C:\jobs\job.json --output-dir C:\jobs\out
```

The host reads:

- process exit code
- `output_manifest.json`
- `metrics.json`
- `logs/<stage>.stdout.log`
- `logs/<stage>.stderr.log`
- derived artifacts listed in the manifest

Stable exit codes:

| Code | Meaning |
| ---: | --- |
| 0 | Success |
| 2 | Invalid config |
| 3 | Missing or invalid input |
| 4 | External tool not found |
| 5 | DICOM conversion failed |
| 6 | Head model failed |
| 7 | Solver failed |
| 8 | Timeout |
| 9 | Internal error |

## Development

Create an environment with Python 3.12+ and install the package:

```bash
python -m pip install -e ".[dev]"
```

Run tests:

```bash
pytest
```

Export the JSON Schema:

```bash
python scripts/export_schema.py
```

## CLI

```bash
tis-engine --help
tis-engine validate --config configs/examples/forward_minimal.json
tis-engine schema --output docs/schemas/config.schema.json
tis-engine doctor --config path/to/job.json
tis-engine run --config path/to/job.json --output-dir path/to/output
```

## Packaging

The first packaging target is a Windows PyInstaller one-folder bundle. External
scientific binaries are not vendored by this repository.

```powershell
.\scripts\build_exe.ps1
.\scripts\smoke_test.ps1
```



## First Backend Integration

The currently supported real preprocessing path is:

1. Optional DICOM conversion with `dcm2niix`.
2. SimNIBS CHARM head-model creation from the T1 NIfTI produced by conversion or
   from an existing `mri.t1_nifti`.
3. Manifest, metrics, stdout, and stderr output for the host.

This is research-only orchestration software. It does not implement FEM solving,
TIS envelope calculation, inverse optimization, or clinical decision logic.

### Head Model From Existing NIfTI

Edit `configs/examples/head_model_from_nifti.json` so `mri.t1_nifti`,
optional `mri.t2_nifti`, and `tools.simnibs.charm_executable` point to real
local files/tools. Then run:

```bash
tis-engine doctor --config configs/examples/head_model_from_nifti.json
tis-engine run --config configs/examples/head_model_from_nifti.json --output-dir output/head-model-nifti
```

Expected real SimNIBS outputs are recorded in `output_manifest.json`:

- `work/simnibs/m2m_<subject_id>/`
- `work/simnibs/<subject_id>.msh`

If CHARM exits successfully but those paths are missing, the stage is marked
failed with exit code `6`; the engine does not invent placeholder results.

### Head Model From DICOM

Edit `configs/examples/head_model_from_dicom.json` so `mri.dicom_dir`,
`tools.dcm2niix.executable`, and `tools.simnibs.charm_executable` point to real
local inputs/tools. Then run:

```bash
tis-engine doctor --config configs/examples/head_model_from_dicom.json
tis-engine run --config configs/examples/head_model_from_dicom.json --output-dir output/head-model-dicom
```

The manifest records the selected converted NIfTI as `converted_nifti` and the
matching BIDS JSON path as `converted_bids_sidecar`. If the sidecar is missing,
the artifact is marked `missing`; if no NIfTI is produced, conversion fails with
exit code `5`.
