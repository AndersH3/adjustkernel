import pytest

from adjustkernel_ng.inventory import InventoryError, build_graph
from adjustkernel_ng.models import DeviceEdge


def test_multiple_parents_are_rejected() -> None:
    edges = [
        DeviceEdge("pci0", "wm0", "drvctl"),
        DeviceEdge("pci1", "wm0", "drvctl"),
    ]
    with pytest.raises(InventoryError):
        build_graph(edges)


def test_drvctl_tree_validation_failure_retries_recursive(monkeypatch) -> None:
    import adjustkernel_ng.inventory as inventory

    monkeypatch.setattr(inventory.shutil, "which", lambda _program: "/sbin/drvctl")

    def fake_run(command: list[str]) -> str:
        args = command[1:]
        if args == ["-t", "-l"]:
            # The tree presentation is syntactically valid but gives wm0 two
            # parents, so inventory_from_drvctl must retry via -n -l.
            return "pci0\n  wm0\npci1\n  wm0\n"
        if args == ["-n", "-l"]:
            return "pci0\npci1\n"
        if args == ["-n", "-l", "pci0"]:
            return "wm0\n"
        if args == ["-n", "-l", "pci1"]:
            return "wm1\n"
        if args in (["-n", "-l", "wm0"], ["-n", "-l", "wm1"]):
            return ""
        raise AssertionError(f"unexpected command: {command!r}")

    monkeypatch.setattr(inventory, "_run", fake_run)

    edges, graph = inventory.inventory_from_drvctl()

    assert DeviceEdge("pci0", "wm0", "drvctl", "wm0") in edges
    assert DeviceEdge("pci1", "wm1", "drvctl", "wm1") in edges
    assert graph.in_degree("wm0") == 1
    assert graph.in_degree("wm1") == 1
