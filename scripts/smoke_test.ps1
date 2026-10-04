param(
    [string]$Exe = "dist\tis-engine\tis-engine.exe"
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path $Exe)) {
    throw "Executable not found: $Exe"
}

$SmokeRoot = Join-Path $env:TEMP "tis-engine-smoke"
$InputRoot = Join-Path $SmokeRoot "input"
$OutputRoot = Join-Path $SmokeRoot "output"
$ConfigPath = Join-Path $SmokeRoot "job.json"
$SchemaPath = Join-Path $SmokeRoot "schema.json"

New-Item -ItemType Directory -Force -Path $InputRoot | Out-Null
New-Item -ItemType Directory -Force -Path $OutputRoot | Out-Null
Set-Content -Path (Join-Path $InputRoot "T1.nii.gz") -Value "dummy"

@"
{
  "schema_version": "1.0",
  "job_id": "smoke-test",
  "mode": "forward",
  "mri": {
    "t1_nifti": "$((Join-Path $InputRoot "T1.nii.gz").Replace("\", "\\"))"
  },
  "stages": {
    "convert_dicom": false,
    "create_head_model": false,
    "run_solver": false
  }
}
"@ | Set-Content -Path $ConfigPath

& $Exe --help
& $Exe schema --output $SchemaPath
& $Exe validate --config $ConfigPath
& $Exe run --config $ConfigPath --output-dir $OutputRoot

if (-not (Test-Path (Join-Path $OutputRoot "output_manifest.json"))) {
    throw "Missing output_manifest.json"
}

Write-Host "Smoke test passed: $OutputRoot"

