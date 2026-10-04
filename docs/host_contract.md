# Host Contract

The host software treats `tis-engine` as a compute backend. The host is
responsible for display, persistence, history loading, and user interaction.

## Invocation

```text
tis-engine.exe run --config <job.json> --output-dir <output-dir>
```

The process returns a stable exit code. Once `--output-dir` is known, the engine
attempts to write `output_manifest.json`, including failed jobs.

## Required Outputs

- `output_manifest.json`: authoritative job result and artifact list
- `metrics.json`: timing and stage summary
- `logs/<stage>.stdout.log`: captured standard output
- `logs/<stage>.stderr.log`: captured standard error

## Exit Codes

| Code | Name | Meaning |
| ---: | --- | --- |
| 0 | `SUCCESS` | Completed successfully |
| 2 | `INVALID_CONFIG` | JSON could not be parsed or failed schema validation |
| 3 | `MISSING_OR_INVALID_INPUT` | Required input paths or parameter files are missing |
| 4 | `EXTERNAL_TOOL_NOT_FOUND` | Required external executable was not found |
| 5 | `DICOM_CONVERSION_FAILED` | `dcm2niix` returned a failure |
| 6 | `HEAD_MODEL_FAILED` | Head model creation returned a failure |
| 7 | `SOLVER_FAILED` | Solver command returned a failure |
| 8 | `TIMEOUT` | An external command exceeded its configured timeout |
| 9 | `INTERNAL_ERROR` | Unexpected engine failure |

## Manifest Shape

The manifest includes job id, config schema version, status, exit code,
timestamps, per-stage records, command metadata, artifact references, and
structured errors. Artifact paths are relative to the output directory whenever
the artifact lives under that directory.



## First Real Preprocessing Outputs

For DICOM conversion, top-level manifest artifacts include:

- `converted_nifti`
- `converted_bids_sidecar`

For SimNIBS CHARM, top-level manifest artifacts include:

- `simnibs_m2m_dir`
- `simnibs_mesh`

Artifacts include a `status` field. A missing optional sidecar is reported as
`missing`. Missing required CHARM outputs fail the head-model stage.
