# Agent Instructions

Project purpose:
Build a standalone TIS compute engine as a separate GitHub repository. The program is packaged as a runnable Windows APP/EXE and called by external host software. It accepts MRI data and config/parameter files, invokes external tools such as dcm2niix and SimNIBS or TI-Toolbox, and writes machine-readable outputs plus a stable process exit code.

Technical choices:
- Python 3.12+
- Typer for CLI
- Pydantic v2 for config models and JSON Schema export
- pytest for tests
- Standard library logging
- `subprocess.run()` with argument lists, timeouts, captured stdout/stderr
- PyInstaller for Windows packaging

Rules:
- Use `src/` layout.
- Keep scientific computation behind adapters; do not reimplement FEM or optimization.
- Do not vendor external binaries into the repo.
- Do not invent undocumented SimNIBS or TI-Toolbox behavior.
- Every code change must include or update tests.
- Update docs/examples if interfaces change.
- Prefer small, composable modules.
- Preserve a stable host-facing contract.
- Mock external tool calls in unit tests.
- At the end, report changed files, commands run, tests run, and unresolved gaps.

