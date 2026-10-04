from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from tis_engine.cli import app
from tis_engine.status_codes import StatusCode


runner = CliRunner()


def _write_minimal_config(path: Path, t1: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "job_id": "cli",
                "mode": "forward",
                "mri": {"t1_nifti": str(t1)},
                "stages": {
                    "convert_dicom": False,
                    "create_head_model": False,
                    "run_solver": False,
                },
            }
        ),
        encoding="utf-8",
    )


def test_cli_validate_accepts_valid_config(tmp_path: Path) -> None:
    t1 = tmp_path / "T1.nii.gz"
    t1.write_text("dummy", encoding="utf-8")
    config = tmp_path / "job.json"
    _write_minimal_config(config, t1)

    result = runner.invoke(app, ["validate", "--config", str(config)])

    assert result.exit_code == 0
    assert "Config is valid" in result.output


def test_cli_schema_writes_file(tmp_path: Path) -> None:
    output = tmp_path / "schema.json"

    result = runner.invoke(app, ["schema", "--output", str(output)])

    assert result.exit_code == 0
    assert output.is_file()
    assert json.loads(output.read_text())["title"] == "JobConfig"


def test_cli_run_writes_failure_manifest_for_invalid_config(tmp_path: Path) -> None:
    config = tmp_path / "bad.json"
    config.write_text("{", encoding="utf-8")
    output = tmp_path / "out"

    result = runner.invoke(
        app,
        ["run", "--config", str(config), "--output-dir", str(output)],
    )

    assert result.exit_code == int(StatusCode.INVALID_CONFIG)
    manifest = json.loads((output / "output_manifest.json").read_text())
    assert manifest["exit_code"] == int(StatusCode.INVALID_CONFIG)


def test_cli_run_success(tmp_path: Path) -> None:
    t1 = tmp_path / "T1.nii.gz"
    t1.write_text("dummy", encoding="utf-8")
    config = tmp_path / "job.json"
    output = tmp_path / "out"
    _write_minimal_config(config, t1)

    result = runner.invoke(
        app,
        ["run", "--config", str(config), "--output-dir", str(output)],
    )

    assert result.exit_code == 0
    assert (output / "output_manifest.json").is_file()

