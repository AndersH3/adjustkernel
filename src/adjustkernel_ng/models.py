"""Small immutable data models used throughout adjustkernel-ng.

The models intentionally contain no I/O or policy.  Keeping them boring makes
it much easier to test parsing, matching, rendering, and reporting separately.
"""

from __future__ import annotations

from typing import Literal

import attrs

Action = Literal["keep", "disable"]
InventorySource = Literal["drvctl", "dmesg"]


@attrs.frozen(slots=True)
class DeviceEdge:
    """One observed parent -> child edge in NetBSD autoconfiguration."""

    parent: str
    child: str
    source: InventorySource
    raw: str = ""


@attrs.frozen(slots=True)
class AttachmentRule:
    """One active ``instance at attachment ...`` statement in a kernel config."""

    line_no: int
    original_line: str
    instance: str
    attachment: str

    @property
    def key_without_locators(self) -> tuple[str, str]:
        """Key used by ``no instance at attachment`` overlay statements.

        NetBSD config(5) says that two instances differing only by locators are
        both removed by such a ``no`` statement.  We therefore group rules on
        exactly these two fields before generating overlays.
        """

        return (self.instance, self.attachment)


@attrs.frozen(slots=True)
class Decision:
    """The engine's auditable decision for one attachment rule."""

    rule: AttachmentRule
    action: Action
    reason: str


@attrs.frozen(slots=True)
class ValidationResult:
    """Result of asking NetBSD's own config(1) to validate generated output."""

    attempted: bool
    ok: bool
    command: tuple[str, ...] = ()
    stdout: str = ""
    stderr: str = ""


@attrs.frozen(slots=True)
class RunReport:
    """Machine-readable report emitted with ``--json-report``."""

    version: str
    inventory_source: str
    edge_count: int
    rule_count: int
    kept_count: int
    disabled_count: int
    decisions: tuple[Decision, ...]
    validation: ValidationResult
