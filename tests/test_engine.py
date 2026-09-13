from pathlib import Path

from adjustkernel_ng.engine import DecisionEngine
from adjustkernel_ng.inventory import build_graph
from adjustkernel_ng.parsing import parse_config_rules, parse_drvctl_tree
from adjustkernel_ng.rendering import render_comment_style, render_overlay_style

FIXTURES = Path(__file__).parent / "fixtures"


def _case():
    config = (FIXTURES / "GENERIC.sample").read_text()
    rules = parse_config_rules(config)
    edges = parse_drvctl_tree((FIXTURES / "drvctl-tree.txt").read_text())
    decisions = DecisionEngine(build_graph(edges)).classify(rules)
    return config, rules, decisions


def test_absent_driver_is_disabled() -> None:
    _, _, decisions = _case()
    by_instance = {d.rule.instance: d for d in decisions}
    assert by_instance["re*"].action == "disable"


def test_interface_attribute_is_kept_when_child_exists() -> None:
    _, _, decisions = _case()
    audio = next(d for d in decisions if d.rule.instance == "audio*")
    assert audio.action == "keep"
    assert "interface" in audio.reason


def test_wrong_concrete_parent_is_disabled() -> None:
    _, _, decisions = _case()
    puc = next(d for d in decisions if d.rule.attachment == "puc?")
    assert puc.action == "disable"


def test_comment_renderer_preserves_unrelated_text() -> None:
    config, _, decisions = _case()
    out = render_comment_style(config, decisions)
    assert "# adjustkernel-ng: absent: re* at pci?" in out
    assert "audio* at audiobus?" in out


def test_overlay_emits_safe_no_statement() -> None:
    _, rules, decisions = _case()
    out = render_overlay_style("arch/amd64/conf/GENERIC", rules, decisions, version="test")
    assert 'include "arch/amd64/conf/GENERIC"' in out
    assert "no re* at pci?" in out
