# Architecture

`tis-engine` is a thin orchestration engine. It owns the host-facing process
contract, config validation, logging, status codes, and output manifests. It
does not implement segmentation, meshing, FEM, or optimization.

## Data Flow

1. Host software writes a JSON job config and chooses an output directory.
2. Host launches `tis-engine run --config <job.json> --output-dir <dir>`.
3. Engine validates config and runtime inputs.
4. Engine optionally calls `dcm2niix` to convert DICOM to NIfTI.
5. Engine optionally calls SimNIBS `charm` to create a head model.
6. Engine optionally calls an explicit SimNIBS or TI-Toolbox solver command.
7. Engine writes `output_manifest.json`, `metrics.json`, stage logs, and
   artifact references.
8. Host reads the exit code and manifest.

## Adapter Boundary

Adapters only translate validated config into external process calls. They use
argument lists, captured output, and timeouts. Domain-specific scientific
settings stay in backend parameter files and are passed through to the chosen
backend command.



## Backend Integration MVP

The first real backend integration path is intentionally narrow:

- `dcm2niix` converts a real DICOM directory into `output/converted/`.
- The pipeline selects the first converted `.nii` or `.nii.gz` file as the T1
  input for downstream CHARM.
- The matching BIDS JSON sidecar is recorded when present and marked missing
  when absent.
- SimNIBS CHARM runs in the configured or default work directory and must
  produce `m2m_<subject_id>/` and `<subject_id>.msh`.

The engine fails the stage when required backend outputs are absent. It does not
create fake NIfTI, mesh, field, or optimization artifacts.
