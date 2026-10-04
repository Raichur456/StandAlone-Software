# Packaging

The first Windows packaging target is a PyInstaller one-folder bundle.

One-folder mode is preferred for the initial milestone because it is easier to
debug and works better with external files and separately installed scientific
binaries.

## Build

```powershell
.\scripts\build_exe.ps1
```

The script installs development dependencies into the active Python environment
and builds `dist\tis-engine\tis-engine.exe`.

## Smoke Test

```powershell
.\scripts\smoke_test.ps1
```

The smoke test checks basic executable startup, schema export, config
validation, and a minimal no-op run with local dummy input data.

## Third-Party Binaries

External tools such as SimNIBS, TI-Toolbox, and `dcm2niix` are not vendored.
They should be installed separately and referenced through config paths or
available on `PATH`.

