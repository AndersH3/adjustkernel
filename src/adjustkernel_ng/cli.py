"""Command-line interface for adjustkernel-ng."""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from . import __version__
from .engine import DecisionEngine
from .inventory import InventoryError, acquire_inventory
from .io_utils import atomic_write_text, replace_with_backup
from .models import RunReport, ValidationResult
from .parsing import parse_config_rules
from .rendering import render_comment_style, render_overlay_style, unified_diff
from .reporting import write_json_report
from .settings import load_settings
from .validation import infer_srcdir, validate_config

console = Console()
err_console = Console(stderr=True)


def _derive_include_path(config: Path, srcdir: Path | None) -> str:
    """Derive a config(5) include path relative to the kernel source tree."""

    source_dir = srcdir or infer_srcdir(config)
    if source_dir is None:
        raise typer.BadParameter(
            "overlay style needs --include-path or a config below .../sys/arch/*/conf"
        )
    try:
        return config.resolve().relative_to(source_dir.resolve()).as_posix()
    except ValueError as exc:
        raise typer.BadParameter(
            "config is outside --srcdir; specify --include-path explicitly"
        ) from exc


def _print_decisions(decisions: list) -> None:
    """Render a compact audit table without mixing it into generated stdout."""

    table = Table(title="adjustkernel-ng decisions")
    table.add_column("Line", justify="right")
    table.add_column("Action")
    table.add_column("Rule")
    table.add_column("Reason")
    for decision in decisions:
        table.add_row(
            str(decision.rule.line_no),
            decision.action,
            f"{decision.rule.instance} at {decision.rule.attachment}",
            decision.reason,
        )
    err_console.print(table)


def _version_callback(value: bool) -> None:
    if value:
        console.print(f"adjustkernel-ng {__version__}")
        raise typer.Exit()


def main(
    config: Annotated[
        Path,
        typer.Argument(
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
            resolve_path=True,
            help="NetBSD kernel configuration to reduce (typically GENERIC).",
        ),
    ],
    output: Annotated[
        Path | None,
        typer.Option("-o", "--output", help="Write generated configuration here."),
    ] = None,
    style: Annotated[
        str | None,
        typer.Option(help="Output style: comment or overlay."),
    ] = None,
    source: Annotated[
        str | None,
        typer.Option(help="Inventory source: auto, drvctl, or dmesg."),
    ] = None,
    dmesg_file: Annotated[
        Path | None,
        typer.Option(help="Read dmesg text from this file instead of the live command."),
    ] = None,
    include_path: Annotated[
        str | None,
        typer.Option(help="config(5) include path used by overlay style."),
    ] = None,
    srcdir: Annotated[
        Path | None,
        typer.Option(help="Top of NetBSD kernel source tree, e.g. /usr/src/sys."),
    ] = None,
    keep: Annotated[
        list[str],
        typer.Option(help="Always retain this device base; may be repeated."),
    ] = [],
    protected: Annotated[
        list[str],
        typer.Option(help="Protected structural base device; may be repeated."),
    ] = [],
    remove: Annotated[
        bool,
        typer.Option(help="Delete absent rules instead of commenting them (comment style only)."),
    ] = False,
    inplace: Annotated[
        bool,
        typer.Option("--in-place", help="Replace CONFIG atomically after making a backup."),
    ] = False,
    backup_suffix: Annotated[
        str,
        typer.Option(help="Suffix for --in-place backup."),
    ] = ".bak",
    validate: Annotated[
        bool,
        typer.Option("--validate/--no-validate", help="Run NetBSD config(1) before writing."),
    ] = True,
    config_tool: Annotated[
        str,
        typer.Option(help="config(1) executable name or path."),
    ] = "config",
    force: Annotated[
        bool,
        typer.Option(help="Write even when config(1) validation fails."),
    ] = False,
    show_diff: Annotated[
        bool,
        typer.Option("--diff", help="Print a unified diff to stderr."),
    ] = False,
    show_decisions: Annotated[
        bool,
        typer.Option(help="Print an audit table of every recognized attachment rule."),
    ] = False,
    json_report: Annotated[
        Path | None,
        typer.Option(help="Write a machine-readable JSON decision report."),
    ] = None,
    settings_file: Annotated[
        Path | None,
        typer.Option(help="Optional TOML settings file (otherwise platform default is used)."),
    ] = None,
    drvctl_program: Annotated[
        str,
        typer.Option(help="drvctl executable name or path."),
    ] = "drvctl",
    dmesg_program: Annotated[
        str,
        typer.Option(help="dmesg executable name or path."),
    ] = "dmesg",
    dry_run: Annotated[
        bool,
        typer.Option(help="Do not modify files; generated config still goes to stdout."),
    ] = False,
    version: Annotated[
        bool | None,
        typer.Option("--version", callback=_version_callback, is_eager=True),
    ] = None,
) -> None:
    """Generate a conservative machine-specific NetBSD kernel configuration.

    The live device tree is evidence, not a complete description of config(5).
    Ambiguous attachment rules are deliberately retained.
    """

    del version  # handled eagerly by Typer callback

    settings = load_settings(settings_file)
    selected_style = style or settings.style
    selected_source = source or settings.source

    if selected_style not in {"comment", "overlay"}:
        raise typer.BadParameter("--style must be 'comment' or 'overlay'")
    if selected_source not in {"auto", "drvctl", "dmesg"}:
        raise typer.BadParameter("--source must be 'auto', 'drvctl', or 'dmesg'")
    if inplace and output is not None:
        raise typer.BadParameter("--in-place and --output are mutually exclusive")
    if selected_style == "overlay" and inplace:
        raise typer.BadParameter("overlay style cannot replace the included source in-place")
    if selected_style == "overlay" and remove:
        raise typer.BadParameter("--remove applies only to comment style")

    source_text = config.read_text(encoding="utf-8", errors="strict")
    rules = parse_config_rules(source_text)
    if not rules:
        raise typer.BadParameter("no active single-line 'instance at attachment' rules found")

    try:
        inventory_name, edges, graph = acquire_inventory(
            selected_source,  # type: ignore[arg-type]
            dmesg_file=dmesg_file,
            drvctl_program=drvctl_program,
            dmesg_program=dmesg_program,
        )
    except InventoryError as exc:
        err_console.print(f"[bold red]inventory error:[/bold red] {exc}")
        raise typer.Exit(2) from exc

    keep_bases = set(settings.keep) | set(keep)
    protected_bases = set(protected) if protected else set(settings.protected)
    engine = DecisionEngine(
        graph,
        keep_bases=keep_bases,
        protected_bases=protected_bases,
    )
    decisions = engine.classify(rules)

    if selected_style == "comment":
        generated = render_comment_style(source_text, decisions, remove=remove)
    else:
        actual_include = include_path or _derive_include_path(config, srcdir)
        generated = render_overlay_style(
            actual_include,
            rules,
            decisions,
            version=__version__,
        )

    if show_decisions:
        _print_decisions(decisions)

    if show_diff:
        diff = unified_diff(
            source_text if selected_style == "comment" else "",
            generated,
            old_name=str(config),
            new_name=str(output or "generated-config"),
        )
        err_console.print(diff or "[dim](no differences)[/dim]", markup=False)

    validation_result = ValidationResult(attempted=False, ok=False)
    if validate:
        validation_result = validate_config(
            generated,
            source_config=config,
            srcdir=srcdir,
            config_tool=config_tool,
        )
        if not validation_result.attempted:
            err_console.print(
                "[yellow]warning:[/yellow] config(1) not found; output was not validated"
            )
        elif not validation_result.ok:
            err_console.print("[bold red]config(1) rejected the generated configuration.[/bold red]")
            if validation_result.stderr:
                err_console.print(validation_result.stderr.rstrip())
            if not force:
                err_console.print("Nothing written. Use --force only after reviewing the failure.")
                raise typer.Exit(3)
        else:
            err_console.print("[green]config(1) validation passed.[/green]")

    counts = Counter(d.action for d in decisions)
    report = RunReport(
        version=__version__,
        inventory_source=inventory_name,
        edge_count=len(edges),
        rule_count=len(rules),
        kept_count=counts["keep"],
        disabled_count=counts["disable"],
        decisions=tuple(decisions),
        validation=validation_result,
    )

    if json_report is not None and not dry_run:
        write_json_report(json_report, report)

    # stdout is the Unix-friendly default.  Diagnostics always go to stderr so
    # "adjustkernel GENERIC > MYKERNEL" remains safe and predictable.
    if dry_run or (output is None and not inplace):
        sys.stdout.write(generated)
        return

    if inplace:
        backup = replace_with_backup(config, generated, backup_suffix)
        err_console.print(f"wrote {config}; backup: {backup}")
    else:
        assert output is not None
        atomic_write_text(output, generated)
        err_console.print(f"wrote {output}")


def app() -> None:
    """Console-script entry point used by pyproject.toml."""

    typer.run(main)


if __name__ == "__main__":  # pragma: no cover - convenience for source checkout
    app()
