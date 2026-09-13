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
