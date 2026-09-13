"""Conservative rule-classification engine."""

from __future__ import annotations

import networkx as nx

from .models import AttachmentRule, Decision
from .parsing import token_base, token_matches_instance


class DecisionEngine:
    """Decide which active attachment rules are unsupported by this machine.

    The important word is *conservative*.  False keeps cost kernel size; false
    removals can cost bootability or hardware support.  Ambiguous cases are
    therefore retained.
    """

    def __init__(
        self,
        graph: nx.DiGraph,
        *,
        keep_bases: set[str] | None = None,
        protected_bases: set[str] | None = None,
    ) -> None:
        self.graph = graph
        self.keep_bases = keep_bases or set()
        self.protected_bases = protected_bases or {"mainbus"}

    def classify(self, rules: list[AttachmentRule]) -> list[Decision]:
        """Classify every recognized attachment rule."""

        concrete_bases = {token_base(rule.instance) for rule in rules}
        runtime_children = set(self.graph.nodes) - {"root"}
        decisions: list[Decision] = []

        for rule in rules:
            child_base = token_base(rule.instance)
            parent_base = token_base(rule.attachment)

            if child_base in self.keep_bases:
                decisions.append(Decision(rule, "keep", "explicit --keep"))
                continue
            if child_base in self.protected_bases:
                decisions.append(Decision(rule, "keep", "protected base device"))
                continue

            matching_children = sorted(
                child for child in runtime_children if token_matches_instance(rule.instance, child)
            )
            if not matching_children:
                decisions.append(
                    Decision(rule, "disable", "no matching runtime child instance")
                )
                continue

            if rule.attachment == "root":
                if any(self.graph.has_edge("root", child) for child in matching_children):
                    decisions.append(Decision(rule, "keep", "runtime root attachment matched"))
                else:
                    decisions.append(Decision(rule, "disable", "child exists but not at root"))
                continue

            # An attachment name absent from all LHS rules is commonly an
            # interface attribute (audiobus, mii, ...), or may come from an
            # included config we did not expand.  NetBSD explicitly warns that
            # runtime parent names then differ from configuration attachment
            # names.  Keeping the rule is safer than guessing.
            if parent_base not in concrete_bases:
                decisions.append(
                    Decision(rule, "keep", "observed child via interface/unknown attachment")
                )
                continue

            matched_edge = False
            for child in matching_children:
                for parent in self.graph.predecessors(child):
                    if token_matches_instance(rule.attachment, parent):
                        matched_edge = True
                        break
                if matched_edge:
                    break

            if matched_edge:
                decisions.append(Decision(rule, "keep", "runtime child/parent edge matched"))
            else:
                decisions.append(
                    Decision(rule, "disable", "child exists only on another concrete attachment")
                )

        return decisions
