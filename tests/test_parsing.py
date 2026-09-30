from pathlib import Path

from adjustkernel_ng.parsing import (
    parse_config_rules,
    parse_dmesg_edges,
    parse_drvctl_tree,
    token_matches_instance,
)

FIXTURES = Path(__file__).parent / "fixtures"


def test_token_matching() -> None:
    assert token_matches_instance("wm*", "wm0")
    assert token_matches_instance("pci?", "pci12")
    assert token_matches_instance("com0", "com0")
    assert not token_matches_instance("com0", "com1")


def test_drvctl_tree_parses_parent_edges() -> None:
    edges = parse_drvctl_tree((FIXTURES / "drvctl-tree.txt").read_text())
    assert any(e.parent == "pci0" and e.child == "wm0" for e in edges)
    assert any(e.parent == "azalia0" and e.child == "audio0" for e in edges)


def test_dmesg_timestamps_are_accepted() -> None:
    edges = parse_dmesg_edges((FIXTURES / "dmesg.txt").read_text())
    assert any(e.parent == "root" and e.child == "mainbus0" for e in edges)
    assert any(e.parent == "azalia0" and e.child == "audio0" for e in edges)


def test_config_recognizer_only_takes_active_attachment_lines() -> None:
    text = "# wm* at pci?\nno re* at pci?\nwm* at pci? dev ? function ?\noptions INET\n"
    rules = parse_config_rules(text)
    assert [(r.instance, r.attachment) for r in rules] == [("wm*", "pci?")]


def test_dmesg_reattach_keeps_latest_parent() -> None:
    text = (
        "[ 1.0] uhub3 at uhub0 port 3: first attachment\n"
        "[ 2.0] uhub3: detached\n"
        "[ 3.0] uhub3 at uhub1 port 3: reattached\n"
    )
    edges = parse_dmesg_edges(text)
    matching = [e for e in edges if e.child == "uhub3"]
    assert len(matching) == 1
    assert matching[0].parent == "uhub1"


def test_dmesg_repeated_boot_last_attachment_wins() -> None:
    text = (
        "[ 1.0] mainbus0 (root)\n"
        "[ 2.0] uhub4 at uhub1 port 3: old boot\n"
        "[ 1.0] mainbus0 (root)\n"
        "[ 2.0] uhub4 at uhub0 port 3: new boot\n"
    )
    edges = parse_dmesg_edges(text)
    matching = [e for e in edges if e.child == "uhub4"]
    assert len(matching) == 1
    assert matching[0].parent == "uhub0"


def test_dmesg_detached_device_is_not_current_inventory() -> None:
    text = (
        "[ 1.0] uhub3 at uhub0 port 3: attachment\n"
        "[ 2.0] uhub3: detached\n"
    )
    assert all(e.child != "uhub3" for e in parse_dmesg_edges(text))
