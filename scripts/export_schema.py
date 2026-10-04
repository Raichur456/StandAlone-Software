from __future__ import annotations

import json
from pathlib import Path

from tis_engine.models.config import JobConfig


def main() -> None:
    output = Path("docs/schemas/config.schema.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    schema = JobConfig.model_json_schema()
    output.write_text(json.dumps(schema, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {output}")


if __name__ == "__main__":
    main()

