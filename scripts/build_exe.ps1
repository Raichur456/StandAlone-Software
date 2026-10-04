param(
    [string]$Python = "python",
    [string]$DistPath = "dist"
)

$ErrorActionPreference = "Stop"

& $Python -m pip install --upgrade pip
& $Python -m pip install -e ".[dev]"
& $Python -m PyInstaller `
    --clean `
    --onedir `
    --name tis-engine `
    --distpath $DistPath `
    src\tis_engine\__main__.py

Write-Host "Built $DistPath\tis-engine\tis-engine.exe"

