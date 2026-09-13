"""JSON report serialization."""

from __future__ import annotations

import json
from pathlib import Path

import cattrs

from .io_utils import atomic_write_text
from .models import RunReport


def write_json_report(path: Path, report: RunReport) -> None:
    """Serialize attrs models through cattrs and write stable, atomic JSON."""

    converter = cattrs.Converter()
    payload = converter.unstructure(report)
    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    atomic_write_text(path, text)
