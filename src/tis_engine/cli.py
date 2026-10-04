from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer

from tis_engine.logging_config import configure_logging
from tis_engine.models.config import JobConfig
from tis_engine.orchestration.pipeline import run_pipeline
from tis_engine.services.outputs import write_failure_manifest
from tis_engine.services.tool_discovery import ToolNotFoundError, resolve_executable
from tis_engine.services.validation import (
    ConfigLoadError,
    load_job_config,
    validate_runtime_inputs,
)
from tis_engine.status_codes import StatusCode

app = typer.Typer(
    no_args_is_help=True,
    pretty_exceptions_show_locals=False,
    help="Standalone TIS compute orchestration engine.",
)


@app.callback()
def callback(
    verbose: Annotated[
        bool,
        typer.Option("--verbose", "-v", help="Enable verbose logging."),
    ] = False,
) -> None:
    configure_logging(verbose)


@app.command("validate")
def validate_command(
    config: Annotated[
        Path,
        typer.Option("--config", "-c", dir_okay=False, help="Path to job JSON config."),
    ],
) -> None:
    try:
        load_job_config(config)
    except ConfigLoadError as exc:
        _print_config_error(exc)
        raise typer.Exit(int(StatusCode.INVALID_CONFIG)) from exc
    typer.echo("Config is valid.")


@app.command("schema")
def schema_command(
    output: Annotated[
        Path,
        typer.Option("--output", "-o", dir_okay=False, help="Path to write JSON Schema."),
    ],
) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(JobConfig.model_json_schema(), indent=2) + "\n",
        encoding="utf-8",
    )
    typer.echo(f"Wrote {output}")


@app.command("doctor")
def doctor_command(
    config: Annotated[
        Path,
        typer.Option("--config", "-c", dir_okay=False, help="Path to job JSON config."),
    ],
) -> None:
    try:
        job_config = load_job_config(config)
    except ConfigLoadError as exc:
        _print_config_error(exc)
        raise typer.Exit(int(StatusCode.INVALID_CONFIG)) from exc

    runtime = validate_runtime_inputs(job_config)
    if not runtime.ok:
        for error in runtime.errors:
            typer.echo(f"{error['field']}: {error['message']}", err=True)
        raise typer.Exit(int(StatusCode.MISSING_OR_INVALID_INPUT))

    try:
        _check_required_tools(job_config)
    except ToolNotFoundError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(int(StatusCode.EXTERNAL_TOOL_NOT_FOUND)) from exc

    typer.echo("Doctor checks passed.")


@app.command("run")
def run_command(
    config: Annotated[
        Path,
        typer.Option("--config", "-c", dir_okay=False, help="Path to job JSON config."),
    ],
    output_dir: Annotated[
        Path,
        typer.Option(
            "--output-dir",
            "-o",
            file_okay=False,
            help="Directory where manifest, metrics, logs, and artifacts are written.",
        ),
    ],
) -> None:
    try:
        job_config = load_job_config(config)
    except ConfigLoadError as exc:
        _print_config_error(exc)
        write_failure_manifest(
            output_dir,
            code=StatusCode.INVALID_CONFIG,
            message=exc.message,
            config_path=config,
            details=exc.details,
        )
        raise typer.Exit(int(StatusCode.INVALID_CONFIG)) from exc

    code = run_pipeline(job_config, output_dir)
    raise typer.Exit(int(code))


def _check_required_tools(config: JobConfig) -> None:
    if config.stages.convert_dicom:
        resolve_executable(config.tools.dcm2niix.executable, "dcm2niix")
    if config.stages.create_head_model:
        resolve_executable(config.tools.simnibs.charm_executable, "charm")
    if config.stages.run_solver:
        if config.solver_backend.value == "simnibs":
            resolve_executable(config.tools.simnibs.solver_executable)
        else:
            resolve_executable(config.tools.ti_toolbox.executable)


def _print_config_error(exc: ConfigLoadError) -> None:
    typer.echo(exc.message, err=True)
    for detail in exc.details:
        loc = detail.get("loc", "<config>")
        msg = detail.get("msg", detail.get("message", "invalid value"))
        typer.echo(f"{loc}: {msg}", err=True)


def main() -> None:
    app()

