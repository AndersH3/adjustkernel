"""Runtime-device inventory acquisition and graph validation."""

from __future__ import annotations

import shutil
import subprocess
from collections import deque
from pathlib import Path
from typing import Literal

import networkx as nx

from .models import DeviceEdge
from .parsing import parse_dmesg_edges, parse_drvctl_tree

SourceChoice = Literal["auto", "drvctl", "dmesg"]


class InventoryError(RuntimeError):
    """Raised when no trustworthy runtime inventory can be obtained."""


def _run(command: list[str]) -> str:
    """Run one trusted local utility and return stdout.

    shell=False is deliberate: kernel config paths and arguments must never be
    reinterpreted by a shell.  stderr is retained in the exception to make
    NetBSD-side failures actionable.
    """

    completed = subprocess.run(
        command,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if completed.returncode != 0:
        raise InventoryError(
            f"command failed ({completed.returncode}): {' '.join(command)}\n{completed.stderr}"
        )
    return completed.stdout


def build_graph(edges: list[DeviceEdge]) -> nx.DiGraph:
    """Build and sanity-check the runtime autoconfiguration graph."""

    graph = nx.DiGraph()
    graph.add_node("root")
    graph.add_edges_from((edge.parent, edge.child) for edge in edges)

    if not nx.is_directed_acyclic_graph(graph):
        raise InventoryError("runtime device topology unexpectedly contains a cycle")

    # A NetBSD autoconfiguration instance has one parent.  Multiple observed
    # parents usually means that mixed/stale dmesg content was supplied.
    ambiguous = [node for node in graph if node != "root" and graph.in_degree(node) > 1]
    if ambiguous:
        raise InventoryError(
            "runtime inventory gives multiple parents for: " + ", ".join(sorted(ambiguous))
        )
    return graph


def _inventory_from_drvctl_recursive(executable: str) -> list[DeviceEdge]:
    """Traverse drvctl with documented ``-n -l [device]`` operations.

    This is slower than tree mode because it starts one drvctl process per
    device, but it does not depend on tree indentation.  It is therefore an
    excellent compatibility fallback if the presentation format of ``-t`` ever
    changes.
    """

    roots = [line.strip() for line in _run([executable, "-n", "-l"]).splitlines() if line.strip()]
    edges = [DeviceEdge("root", child, "drvctl", child) for child in roots]
    queue = deque(roots)
    expanded: set[str] = set()

    while queue:
        parent = queue.popleft()
        if parent in expanded:
            continue
        expanded.add(parent)

        output = _run([executable, "-n", "-l", parent])
        for line in output.splitlines():
            child = line.strip()
            if not child:
                continue
            if any(ch.isspace() for ch in child):
                raise InventoryError(f"unexpected drvctl -n -l output for {parent}: {line!r}")
            edges.append(DeviceEdge(parent, child, "drvctl", line))
            if child not in expanded:
                queue.append(child)

    return edges


def inventory_from_drvctl(program: str = "drvctl") -> tuple[list[DeviceEdge], nx.DiGraph]:
    """Acquire topology from drvctl, with a format-independent fallback."""

    executable = shutil.which(program) if "/" not in program else program
    if not executable:
        raise InventoryError(f"{program!r} was not found")

    try:
        edges = parse_drvctl_tree(_run([executable, "-t", "-l"]))
    except (InventoryError, ValueError):
        edges = _inventory_from_drvctl_recursive(executable)

    if not edges:
        raise InventoryError("drvctl returned an empty device tree")
    return edges, build_graph(edges)


def inventory_from_dmesg(
    *, dmesg_file: Path | None = None, program: str = "dmesg"
) -> tuple[list[DeviceEdge], nx.DiGraph]:
    """Acquire topology from dmesg text, preferably /var/run/dmesg.boot."""

    if dmesg_file is not None:
        text = dmesg_file.read_text(encoding="utf-8", errors="replace")
    else:
        boot_log = Path("/var/run/dmesg.boot")
        if boot_log.is_file():
            text = boot_log.read_text(encoding="utf-8", errors="replace")
        else:
            executable = shutil.which(program) if "/" not in program else program
            if not executable:
                raise InventoryError(f"{program!r} was not found")
            text = _run([executable])

    edges = parse_dmesg_edges(text)
    if not edges:
        raise InventoryError("no NetBSD attachment records were recognized in dmesg input")
    return edges, build_graph(edges)


def acquire_inventory(
    source: SourceChoice,
    *,
    dmesg_file: Path | None = None,
    drvctl_program: str = "drvctl",
    dmesg_program: str = "dmesg",
) -> tuple[str, list[DeviceEdge], nx.DiGraph]:
    """Acquire inventory with a conservative automatic fallback policy."""

    if source == "drvctl":
        edges, graph = inventory_from_drvctl(drvctl_program)
        return "drvctl", edges, graph
    if source == "dmesg":
        edges, graph = inventory_from_dmesg(dmesg_file=dmesg_file, program=dmesg_program)
        return "dmesg", edges, graph

    # auto: drvctl is semantically better because it is an actual device tree,
    # not a human-readable boot transcript.  Only fall back if acquisition or
    # strict parsing fails.
    try:
        edges, graph = inventory_from_drvctl(drvctl_program)
        return "drvctl", edges, graph
    except InventoryError:
        edges, graph = inventory_from_dmesg(dmesg_file=dmesg_file, program=dmesg_program)
        return "dmesg", edges, graph
