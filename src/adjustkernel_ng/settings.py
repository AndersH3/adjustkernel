"""Optional TOML settings support.

This is intentionally small: command-line arguments remain explicit and win
over persistent settings.  platformdirs avoids hard-coding ~/.config paths;
tomlkit avoids hand-writing a TOML parser.
"""

from __future__ import annotations

from pathlib import Path

import attrs
from platformdirs import user_config_path
from tomlkit import parse


@attrs.frozen(slots=True)
class Settings:
    source: str = "auto"
    style: str = "comment"
    keep: tuple[str, ...] = ()
    protected: tuple[str, ...] = ("mainbus",)


def default_settings_path() -> Path:
    return user_config_path("adjustkernel-ng", appauthor=False) / "config.toml"


def load_settings(path: Path | None) -> Settings:
    """Load settings if present; missing default settings are not an error."""

    actual = path or default_settings_path()
    if not actual.exists():
        return Settings()

    document = parse(actual.read_text(encoding="utf-8"))
    section = document.get("adjustkernel", {})
    return Settings(
        source=str(section.get("source", "auto")),
        style=str(section.get("style", "comment")),
        keep=tuple(str(x) for x in section.get("keep", [])),
        protected=tuple(str(x) for x in section.get("protected", ["mainbus"])),
    )
