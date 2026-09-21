"""Jcode install/uninstall commands for Monokl."""

from __future__ import annotations

import json
from pathlib import Path

import typer

from hyperresearch.cli._output import output
from hyperresearch.jcode.install import (
    JcodeInstallError,
    install_jcode_payload,
    uninstall_jcode_payload,
)
from hyperresearch.jcode.routes import doctor as run_doctor
from hyperresearch.jcode.routes import load_model_routes
from hyperresearch.models.output import error, success

app = typer.Typer(help="Install or remove Jcode skill payloads.")


@app.command("install")
def install(
    home: Path | None = typer.Option(None, "--home", help="Jcode home owner HOME. Defaults to $HOME."),
    project: Path | None = typer.Option(None, "--project", help="Optional project root for .jcode/skills step reference."),
    json_output: bool = typer.Option(False, "--json", "-j", help="JSON output"),
) -> None:
    """Safely install the global /monokl skill and optional project step skill."""
    try:
        receipt = install_jcode_payload(home=home, project=project)
    except JcodeInstallError as exc:
        output(error(str(exc), "JCODE_INSTALL_ERROR"), json_mode=json_output)
        raise typer.Exit(1) from exc
    output(success(receipt, vault=None), json_mode=json_output)


@app.command("uninstall")
def uninstall(
    home: Path | None = typer.Option(None, "--home", help="Jcode home owner HOME. Defaults to $HOME."),
    json_output: bool = typer.Option(False, "--json", "-j", help="JSON output"),
) -> None:
    """Remove only receipt-owned Monokl Jcode payload files."""
    try:
        result = uninstall_jcode_payload(home=home)
    except JcodeInstallError as exc:
        output(error(str(exc), "JCODE_UNINSTALL_ERROR"), json_mode=json_output)
        raise typer.Exit(1) from exc
    output(success(result, vault=None), json_mode=json_output)


@app.command("routes")
def routes(json_output: bool = typer.Option(False, "--json", "-j", help="JSON output")) -> None:
    """Validate and print the configured Jcode stage model routes."""
    try:
        result = load_model_routes()
    except JcodeInstallError as exc:
        output(error(str(exc), "JCODE_ROUTE_ERROR"), json_mode=json_output)
        raise typer.Exit(1) from exc
    output(success({"routes": result, "authority": "provenance_only"}, vault=None), json_mode=json_output)


@app.command("doctor")
def doctor(
    home: Path | None = typer.Option(None, "--home", help="Jcode home owner HOME. Defaults to $HOME."),
    project: Path | None = typer.Option(None, "--project", help="Optional project root to check stage skills."),
    json_output: bool = typer.Option(False, "--json", "-j", help="JSON output"),
) -> None:
    """Check that Monokl can start in Jcode without running research."""
    resolved_home = Path.home() if home is None else home
    result = run_doctor(resolved_home, project)
    output(success(result, vault=None) if result["state"] == "ready" else error(json.dumps(result, sort_keys=True), "BLOCKED_CAPABILITY"), json_mode=json_output)
    if result["state"] != "ready":
        raise typer.Exit(1)
