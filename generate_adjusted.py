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
from pathlib import Path

REPO = Path(__file__).resolve().parent
ADJUST = REPO / ".venv" / "bin" / "adjustkernel"
GENERIC = Path("/usr/src/sys/arch/amd64/conf/GENERIC")
SRCDIR = Path("/usr/src/sys")

OUT = REPO / "netbsd" / "ADJUSTED"
REPORT = REPO / "netbsd" / "ADJUSTED.adjustkernel.json"
LOG = REPO / "netbsd" / "adjustkernel_run.log"

KEEP = ["umass", "sd", "cd", "ukbd", "ums", "uhid"]


def fail(message: str) -> int:
    print(f"ERROR: {message}", file=sys.stderr)
    return 1


def main() -> int:
    if not GENERIC.is_file():
        return fail(f"NetBSD GENERIC config not found: {GENERIC}")
    if not SRCDIR.is_dir():
        return fail(f"NetBSD source tree not found: {SRCDIR}")
    if not ADJUST.is_file():
        return fail(
            f"{ADJUST} not found. Create the venv and run 'python -m pip install .' first."
        )

    cmd = [
        str(ADJUST),
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

    print()
    print("SUCCESS")
    print(f"Generated overlay: {OUT}")
    print(f"JSON audit report: {REPORT}")
    print(f"Full run log: {LOG}")
    print()
    print("Next: inspect the generated overlay and report before compiling.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
