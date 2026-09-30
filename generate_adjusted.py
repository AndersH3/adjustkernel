#!/usr/pkg/bin/python3.14
"""Generate the first conservative NetBSD kernel overlay for this machine.

Run as the normal user from the repository root:

    python3.14 generate_adjusted.py

The script invokes the project's venv-installed adjustkernel command with the
known-good options, writes the generated overlay and JSON audit report under
netbsd/, and captures the full diagnostic output in a log file.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent
VENV_PYTHON = REPO / ".venv" / "bin" / "python"
SOURCE_LAUNCHER = REPO / "adjustkernel.py"
GENERIC = Path("/usr/src/sys/arch/amd64/conf/GENERIC")
SRCDIR = Path("/usr/src/sys")

OUT = REPO / "netbsd" / "ADJUSTED"
REPORT = REPO / "netbsd" / "ADJUSTED.adjustkernel.json"
LOG = REPO / "netbsd" / "adjustkernel_run.log"

KEEP = ["umass", "sd", "cd", "ukbd", "ums", "uhid"]

# This machine uses a Swedish physical keyboard.  Keep the wscons map built
# into the kernel as well as configuring it later from /etc/wscons.conf.
EXTRA_OPTIONS = ["PCKBD_LAYOUT=KB_SV"]


def fail(message: str) -> int:
    print(f"ERROR: {message}", file=sys.stderr)
    return 1


def add_local_options(text: str) -> str:
    """Add machine-local kernel options after the GENERIC include."""

    additions = [
        f"options {option}"
        for option in EXTRA_OPTIONS
        if f"options {option}" not in text
    ]
    if not additions:
        return text

    lines = text.splitlines()
    insert_at = 0
    for index, line in enumerate(lines):
        if line.startswith('include "arch/amd64/conf/GENERIC"'):
            insert_at = index + 1
            break

    block = [
        "",
        "# Machine-local options added by generate_adjusted.py.",
        *additions,
        "",
    ]
    lines[insert_at:insert_at] = block
    return "\n".join(lines) + "\n"


def validate_final_overlay(text: str) -> tuple[bool, str]:
    """Validate the post-processed overlay with NetBSD config(1)."""

    config_tool = Path("/usr/bin/config")
    if not config_tool.is_file():
        return False, "/usr/bin/config not found"

    with tempfile.TemporaryDirectory(prefix="adjustkernel-final-") as temp:
        tempdir = Path(temp)
        candidate = tempdir / "ADJUSTED"
        builddir = tempdir / "build"
        candidate.write_text(text, encoding="utf-8")

        proc = subprocess.run(
            [
                str(config_tool),
                "-s",
                str(SRCDIR),
                "-b",
                str(builddir),
                str(candidate),
            ],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        return proc.returncode == 0, proc.stdout


def main() -> int:
    if not GENERIC.is_file():
        return fail(f"NetBSD GENERIC config not found: {GENERIC}")
    if not SRCDIR.is_dir():
        return fail(f"NetBSD source tree not found: {SRCDIR}")
    if not VENV_PYTHON.is_file():
        return fail(
            f"{VENV_PYTHON} not found. Create the venv and install dependencies first."
        )
    if not SOURCE_LAUNCHER.is_file():
        return fail(f"Source launcher not found: {SOURCE_LAUNCHER}")

    # Run the checkout directly with the venv Python.  This keeps the wrapper
    # in sync with newly pulled source changes without requiring a reinstall
    # of the package after every Git update.
    cmd = [
        str(VENV_PYTHON),
        str(SOURCE_LAUNCHER),
        str(GENERIC),
        "--style",
        "overlay",
        "--srcdir",
        str(SRCDIR),
    ]
    for name in KEEP:
        cmd += ["--keep", name]

    cmd += [
        "--show-decisions",
        "--diff",
        "--json-report",
        str(REPORT),
        "-o",
        str(OUT),
    ]

    print("Running:")
    print(" ".join(cmd))
    print()

    proc = subprocess.run(
        cmd,
        cwd=REPO,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )

    LOG.write_text(proc.stdout, encoding="utf-8")
    print(proc.stdout, end="")

    if proc.returncode != 0:
        print()
        print(f"adjustkernel failed with exit code {proc.returncode}.")
        print(f"Full output saved to: {LOG}")
        return proc.returncode

    # Add the few machine-local options that are intentionally outside
    # adjustkernel's device-tree decision engine, then validate the exact file
    # that will later be compiled.
    final_text = add_local_options(OUT.read_text(encoding="utf-8"))
    OUT.write_text(final_text, encoding="utf-8")
    final_ok, final_validation = validate_final_overlay(final_text)

    with LOG.open("a", encoding="utf-8") as handle:
        handle.write("\n\n=== final overlay validation ===\n")
        handle.write(final_validation)
        handle.write(
            "\nFinal overlay validation: "
            + ("PASSED\n" if final_ok else "FAILED\n")
        )

    if not final_ok:
        print()
        print("Final overlay validation FAILED after adding local options.")
        print(final_validation, end="")
        print(f"Full output saved to: {LOG}")
        return 3

    print()
    print("Final overlay validation passed.")
    print("SUCCESS")
    print(f"Generated overlay: {OUT}")
    print(f"JSON audit report: {REPORT}")
    print(f"Full run log: {LOG}")
    print()
    print("Next: inspect the generated overlay and report before compiling.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
