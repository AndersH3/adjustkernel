"""Validation using NetBSD's authoritative config(1) implementation."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

from .models import ValidationResult


def infer_srcdir(config_path: Path) -> Path | None:
    """Infer .../sys from .../sys/arch/MACHINE/conf/CONFIG when possible."""

    resolved = config_path.resolve()
    parts = resolved.parts
    try:
        sys_index = max(i for i, part in enumerate(parts) if part == "sys")
    except ValueError:
        return None

    tail = parts[sys_index + 1 :]
    if len(tail) >= 4 and tail[0] == "arch" and tail[2] == "conf":
        return Path(*parts[: sys_index + 1])
    return None


def validate_config(
    text: str,
    *,
    source_config: Path,
    srcdir: Path | None,
    config_tool: str = "config",
) -> ValidationResult:
    """Run ``config -s SRC -b TMP CONFIG`` against generated text."""

    executable = shutil.which(config_tool) if "/" not in config_tool else config_tool
    if not executable:
        return ValidationResult(attempted=False, ok=False)

    source_dir = srcdir or infer_srcdir(source_config)
    if source_dir is None:
        return ValidationResult(
            attempted=True,
            ok=False,
            stderr="cannot infer kernel source directory; pass --srcdir",
        )

    with tempfile.TemporaryDirectory(prefix="adjustkernel-config-") as temp:
        tempdir = Path(temp)
        candidate = tempdir / source_config.name
        builddir = tempdir / "build"
        candidate.write_text(text, encoding="utf-8")

        command = [
            str(executable),
            "-s",
            str(source_dir.resolve()),
            "-b",
            str(builddir),
            str(candidate),
        ]
        completed = subprocess.run(
            command,
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        return ValidationResult(
            attempted=True,
            ok=completed.returncode == 0,
            command=tuple(command),
            stdout=completed.stdout,
            stderr=completed.stderr,
        )
