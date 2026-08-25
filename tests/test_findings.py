from __future__ import annotations

import json

import pytest

from swarm.findings import (
    Finding,
    append_to_connections,
    append_to_inbox,
    finding_fingerprint,
    parse_finding,
    prepare_findings,
    rate_finding,
)
from swarm.notebook import Notebook


class TestFindingParsing:
    def test_parses_full_block(self):
        output = "some prose...\n===FINDING===\nTITLE: GoL meets rule30\nTYPE: connection\nPROJECTS: toy-projects/GameOfLife, toy-projects/rule30\nCLAIM: EMPIRICAL: glider guns encode observer automata\nEXPERIMENT: run one observer on glider streams\n"
        finding = parse_finding(output)
        assert finding is not None
        assert finding.title == "GoL meets rule30"
        assert finding.is_connection
        assert len(finding.projects) == 2
        assert finding.experiment == "run one observer on glider streams"

    def test_no_block_returns_none(self):
        assert parse_finding("just chatter") is None

    def test_missing_claim_returns_none(self):
        assert parse_finding("===FINDING===\nTITLE: x\n") is None


class TestPublishing:
    def test_rating_prefers_complete_duplicate(self):
        weak = Finding(
            title="Echo",
            type="idea",
            projects=["p1"],
            claim="EMPIRICAL: same claim",
            experiment=None,
        )
        strong = Finding(
            title=" echo ",
            type="IDEA",
            projects=["p1"],
            claim=" empirical: same   claim ",
            experiment="run it",
        )

        assert finding_fingerprint(weak) == finding_fingerprint(strong)
        assert rate_finding(strong) > rate_finding(weak)
        assert prepare_findings([weak, strong]) == [strong]

    def test_connection_project_order_does_not_duplicate(self):
        first = Finding("Link", "connection", ["a", "b"], "claim", None)
        reverse = Finding("link", "connection", ["b", "a"], "claim", None)

        assert prepare_findings([first, reverse]) == [first]

    def test_append_to_inbox_uses_template(self, tmp_path):
        inbox = tmp_path / "INBOX.md"
        inbox.write_text("# Idea Inbox\n\n---\n", encoding="utf-8")
        finding = Finding(
            title="Test idea",
            type="idea",
            projects=["a", "b"],
            claim="EMPIRICAL: it works",
            experiment="run it",
        )
        entry = append_to_inbox(finding, inbox)
        text = inbox.read_text()
        assert "## Test idea" in text
        assert "- Claim/hypothesis: EMPIRICAL: it works" in text
        assert "- Connects to: a, b" in text
        assert entry.startswith("\n## ")

    def test_append_connection_row(self, tmp_path):
        conns = tmp_path / "CONNECTIONS.md"
        conns.write_text(
            "# Cross-Project Connections\n\n| # | Connection |\n| --- | --- |\n"
            "| C1 | existing |\n\nTrailing note.\n",
            encoding="utf-8",
        )
        finding = Finding(
            title="New link",
            type="connection",
            projects=["p1", "p2"],
            claim="they share X",
            experiment=None,
        )
        row = append_to_connections(finding, conns)
        text = conns.read_text()
        assert row.startswith("| C2 |")
        assert "| C2 | New link | p1 ↔ p2 | they share X | proposed |\n" in text
        assert text.index("| C1 | existing |") < text.index("| C2 |")
        assert "Trailing note." in text

    def test_connection_needs_two_projects(self, tmp_path):
        finding = Finding("t", "connection", ["only-one"], "c", None)
        try:
            append_to_connections(finding, tmp_path / "c.md")
            raised = False
        except ValueError:
            raised = True
        assert raised


class TestNotebook:
    def test_jsonl_roundtrip(self, tmp_path):
        nb = Notebook(tmp_path / "run1")
        nb.log("agent-1", "dispatch", {"kind": "EXPLORE"})
        nb.log("agent-1", "result", {"ok": True})
        entries = nb.entries("agent-1")
        assert [e["type"] for e in entries] == ["dispatch", "result"]
        assert entries[0]["payload"]["kind"] == "EXPLORE"
        with (tmp_path / "run1" / "agent-1.jsonl").open() as fh:
            lines = [json.loads(line) for line in fh]
        assert len(lines) == 2

    @pytest.mark.parametrize("agent", ["../outside", "/outside", r"nested\\agent"])
    def test_path_like_agent_names_cannot_escape_run_directory(
        self, tmp_path, agent
    ):
        nb = Notebook(tmp_path / "run1")

        with pytest.raises(ValueError, match="agent must be a simple filename"):
            nb.path_for(agent)
        with pytest.raises(ValueError, match="agent must be a simple filename"):
            nb.log(agent, "dispatch", {})
        with pytest.raises(ValueError, match="agent must be a simple filename"):
            nb.entries(agent)

        assert list(tmp_path.glob("**/outside.jsonl")) == []
        assert nb.entries() == []
