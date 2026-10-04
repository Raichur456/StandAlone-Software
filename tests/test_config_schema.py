from __future__ import annotations

import json
from pathlib import Path

from tis_engine.models.config import JobConfig
from tis_engine.services.validation import load_job_config


def test_schema_contains_host_contract_fields() -> None:
    schema = JobConfig.model_json_schema()

    assert schema["properties"]["schema_version"]
    assert schema["properties"]["job_id"]
    assert schema["properties"]["mri"]
    assert schema["properties"]["stages"]
    assert schema["properties"]["solver_backend"]


def test_example_configs_parse() -> None:
    for path in Path("configs/examples").glob("*.json"):
        config = load_job_config(path)
        assert config.job_id


def test_rejects_unknown_fields(tmp_path: Path) -> None:
    config_path = tmp_path / "job.json"
    config_path.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "job_id": "bad",
                "mode": "forward",
                "mri": {"t1_nifti": "T1.nii.gz"},
                "unexpected": True,
            }
        ),
        encoding="utf-8",
    )

    try:
        load_job_config(config_path)
    except Exception as exc:
        assert "validation" in str(exc).lower()
    else:
        raise AssertionError("Unknown field should fail validation")

