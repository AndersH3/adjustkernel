#!/usr/bin/env python3
"""Run adjustkernel-ng directly from an unpacked source tree."""
from pathlib import Path
import sys

# The project uses a standard src/ layout.  Add it only for this convenience
# launcher; installed console scripts do not modify sys.path.
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from adjustkernel_ng.cli import app

if __name__ == "__main__":
    app()
