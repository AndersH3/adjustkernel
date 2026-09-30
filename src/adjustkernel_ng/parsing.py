"""Parsers and matchers for NetBSD config and runtime inventory text.

Only the tiny portion of config(5) that this program is willing to modify is
recognized.  This is a deliberate safety property: unknown syntax remains
opaque and is copied byte-for-byte instead of being "understood" incorrectly.
"""

from __future__ import annotations

import re

from pyparsing import (
    Keyword,
    Optional,
    ParseException,
    ParserElement,
    Regex,
    StringEnd,
    StringStart,
    White,
    restOfLine,
)

from .models import AttachmentRule, DeviceEdge

# NetBSD configuration statements are traditionally whitespace-oriented.  For
# our line recognizer, newlines must *not* be treated as ordinary whitespace;
# a multi-line statement is therefore conservatively left untouched.
ParserElement.set_default_whitespace_chars(" \t")

_INSTANCE = Regex(r"[A-Za-z_][A-Za-z0-9_]*(?:\d+|[?*])")
_ATTACHMENT = Keyword("root") | _INSTANCE
_ATTACHMENT_LINE = (
    StringStart()
    + Optional(White(" \t"))
    + _INSTANCE("instance")
    + Keyword("at").suppress()
    + _ATTACHMENT("attachment")
    + Optional(restOfLine)
    + StringEnd()
)

_TOKEN_RE = re.compile(r"\A([A-Za-z_][A-Za-z0-9_]*?)(\d+|[?*])\Z")
_DMESG_TS_RE = re.compile(r"^\s*\[\s*\d+(?:\.\d+)?\s*\]\s*")
_DMESG_ROOT_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*\d+)\s+\(root\)\s*$")
_DMESG_EDGE_RE = re.compile(
    r"^([A-Za-z_][A-Za-z0-9_]*\d+)\s+at\s+"
    r"([A-Za-z_][A-Za-z0-9_]*\d+)\b"
)
_DMESG_DETACH_RE = re.compile(
    r"^([A-Za-z_][A-Za-z0-9_]*\d+):\s+detached\b"
)


def split_instance_token(token: str) -> tuple[str, str] | None:
    """Split ``wm*`` / ``pci?`` / ``com0`` into ``(base, selector)``.

    Bare ``root`` is special and is represented as ``("root", "")``.
    Returning ``None`` instead of guessing is intentional: unexpected syntax
    should cause a conservative keep, not an over-aggressive deletion.
    """

    if token == "root":
        return ("root", "")
    match = _TOKEN_RE.fullmatch(token)
    if match is None:
        return None
    return match.group(1), match.group(2)


def token_base(token: str) -> str:
    """Return the base driver/interface name of a config instance token."""

    split = split_instance_token(token)
    return split[0] if split else token


def token_matches_instance(pattern: str, actual: str) -> bool:
    """Match a config token against a concrete runtime device instance."""

    if pattern == "root":
        return actual == "root"

    p = split_instance_token(pattern)
    a = split_instance_token(actual)
    if p is None or a is None:
        return pattern == actual

    pbase, psel = p
    abase, asel = a
    if pbase != abase:
        return False
    if psel in {"*", "?"}:
        return True
    return psel == asel


def parse_config_rules(text: str) -> list[AttachmentRule]:
    """Recognize active single-line attachment statements.

    Why single-line only?  config(5) permits embedded newlines in statements.
    Correctly deciding where arbitrary multi-line statements end requires the
    full NetBSD grammar and source-description context.  Rather than implement a
    fragile clone of config(1), this tool simply preserves such uncommon forms.
    NetBSD's own config(1) remains the final authority via ``--validate``.
    """

    rules: list[AttachmentRule] = []
    for line_no, raw in enumerate(text.splitlines(keepends=True), start=1):
        logical = raw.rstrip("\r\n")
        if not logical.strip() or logical.lstrip().startswith("#"):
            continue
        if logical.lstrip().startswith("no "):
            continue

        try:
            parsed = _ATTACHMENT_LINE.parse_string(logical, parse_all=True)
        except ParseException:
            continue

        rules.append(
            AttachmentRule(
                line_no=line_no,
                original_line=raw,
                instance=str(parsed["instance"]),
                attachment=str(parsed["attachment"]),
            )
        )
    return rules


def parse_drvctl_tree(text: str) -> list[DeviceEdge]:
    """Parse current NetBSD ``drvctl -t -l`` output into parent/child edges.

    drvctl(8) documents ``-t`` as tree output.  The current implementation uses
    two spaces per depth.  We validate the shape strictly so a future format
    change fails loudly instead of silently fabricating topology.
    """

    edges: list[DeviceEdge] = []
    stack: list[str] = []

    for line_no, raw in enumerate(text.splitlines(), start=1):
        if not raw.strip():
            continue
        if "\t" in raw:
            raise ValueError(f"drvctl line {line_no}: tab indentation is ambiguous")

        leading = len(raw) - len(raw.lstrip(" "))
        if leading % 2:
            raise ValueError(f"drvctl line {line_no}: odd indentation ({leading} spaces)")

        child = raw.strip()
        if any(ch.isspace() for ch in child):
            raise ValueError(f"drvctl line {line_no}: unexpected fields: {raw!r}")

        depth = leading // 2
        if depth > len(stack):
            raise ValueError(f"drvctl line {line_no}: depth jumps to {depth}")

        parent = "root" if depth == 0 else stack[depth - 1]
        edges.append(DeviceEdge(parent=parent, child=child, source="drvctl", raw=raw))

        if depth == len(stack):
            stack.append(child)
        else:
            stack[depth] = child
            del stack[depth + 1 :]

    return edges


def parse_dmesg_edges(text: str) -> list[DeviceEdge]:
    """Parse NetBSD autoconfiguration messages into the latest known topology.

    dmesg input is a history, not necessarily a snapshot.  A device instance
    can be detached and later reattached, and saved logs can even contain more
    than one boot.  Feeding every historical attachment into a graph therefore
    fabricates impossible multiple-parent devices.  Track the most recent
    attachment for each concrete child and discard it on an explicit detach.

    This remains conservative: only the stable leading forms already accepted
    by the parser are interpreted; all other text is ignored.
    """

    latest: dict[str, DeviceEdge] = {}
    order: dict[str, int] = {}
    sequence = 0

    for raw in text.splitlines():
        line = _DMESG_TS_RE.sub("", raw)

        detach_match = _DMESG_DETACH_RE.match(line)
        if detach_match:
            child = detach_match.group(1)
            latest.pop(child, None)
            order.pop(child, None)
            continue

        root_match = _DMESG_ROOT_RE.match(line)
        if root_match:
            child = root_match.group(1)
            latest[child] = DeviceEdge(
                parent="root", child=child, source="dmesg", raw=raw
            )
            order[child] = sequence
            sequence += 1
            continue

        edge_match = _DMESG_EDGE_RE.match(line)
        if edge_match:
            child = edge_match.group(1)
            latest[child] = DeviceEdge(
                parent=edge_match.group(2),
                child=child,
                source="dmesg",
                raw=raw,
            )
            order[child] = sequence
            sequence += 1

    return sorted(latest.values(), key=lambda edge: order[edge.child])
