#!/usr/pkg/bin/python3.14
"""Configure and build the reviewed NetBSD ADJUSTED kernel safely.

Run as the normal user from the repository root:

    python3.14 build_adjusted.py

The build is written below netbsd/build-ADJUSTED and does not replace /netbsd.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent
CONFIG = REPO / "netbsd" / "ADJUSTED"
SRCDIR = Path("/usr/src/sys")
BUILDDIR = REPO / "netbsd" / "build-ADJUSTED"
LOG = REPO / "netbsd" / "build_adjusted.log"
CONFIG_TOOL = Path("/usr/bin/config")
MAKE = Path("/usr/bin/make")
JOBS = str(max(1, min(4, os.cpu_count() or 1)))


def run_logged(cmd: list[str], log) -> int:
    line = "$ " + " ".join(cmd)
    print(line)
    log.write(line + "\n")
    log.flush()

    proc = subprocess.Popen(
        cmd,
        cwd=BUILDDIR if BUILDDIR.exists() else REPO,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    assert proc.stdout is not None
    for output in proc.stdout:
        sys.stdout.write(output)
        log.write(output)
    return proc.wait()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> int:
    if os.geteuid() == 0:
        print("Do not build as root; run this as the normal user.", file=sys.stderr)
        return 1
    if not CONFIG.is_file():
        print(f"Missing generated config: {CONFIG}", file=sys.stderr)
        return 2
    if not SRCDIR.is_dir():
        print(f"Missing NetBSD source tree: {SRCDIR}", file=sys.stderr)
        return 2
    if not CONFIG_TOOL.is_file() or not MAKE.is_file():
        print("NetBSD config(1) or make(1) is missing.", file=sys.stderr)
        return 2

    # Reconfigure from a clean build tree so changed kernel options cannot
    # leave stale generated headers or object files from a previous attempt.
    if BUILDDIR.exists():
        shutil.rmtree(BUILDDIR)
    BUILDDIR.mkdir(parents=True, exist_ok=True)

    with LOG.open("w", encoding="utf-8") as log:
        print(f"Building with -j{JOBS}")
        log.write(f"Config: {CONFIG}\nSource: {SRCDIR}\nBuild: {BUILDDIR}\nJobs: {JOBS}\n\n")

        config_cmd = [
            str(CONFIG_TOOL),
            "-s",
            str(SRCDIR),
            "-b",
            str(BUILDDIR),
            str(CONFIG),
        ]
        if run_logged(config_cmd, log) != 0:
            print(f"config(1) failed. See {LOG}", file=sys.stderr)
            return 3

        if run_logged([str(MAKE), f"-j{JOBS}", "depend"], log) != 0:
            print(f"make depend failed. See {LOG}", file=sys.stderr)
            return 4

        if run_logged([str(MAKE), f"-j{JOBS}"], log) != 0:
            print(f"kernel build failed. See {LOG}", file=sys.stderr)
            return 5

    kernel = BUILDDIR / "netbsd"
    if not kernel.is_file():
        print(f"Build completed but kernel was not found at {kernel}", file=sys.stderr)
        return 6

    checksum = sha256(kernel)
    print()
    print("BUILD SUCCESS")
    print(f"Kernel: {kernel}")
    print(f"Size: {kernel.stat().st_size} bytes")
    print(f"SHA256: {checksum}")
    print(f"Build log: {LOG}")
    print()
    print("The running /netbsd kernel has NOT been modified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
