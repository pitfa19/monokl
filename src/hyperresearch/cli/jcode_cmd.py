"""Jcode install/uninstall commands for Monokl."""

from __future__ import annotations

from pathlib import Path

import typer

from hyperresearch.cli._output import output
from hyperresearch.jcode.install import (
    JcodeInstallError,
    install_jcode_payload,
    uninstall_jcode_payload,
)
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
