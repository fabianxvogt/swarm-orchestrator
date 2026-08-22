from __future__ import annotations

import pytest

from swarm import safety
from swarm.missions import MISSION_TYPES, build_brief
from swarm.registry import Project, apply_filters, parse_inventory
from swarm.runner import make_mission
from swarm.config import SwarmConfig

INVENTORY_SAMPLE = """
# Project Inventory

## Tier A — core portfolio

| Project | Rating | What it is | Publish? |
| --- | --- | --- | --- |
| `trading/trader` (SceneTrader) | 8 | LLM-driven trading research. | Sanitize first |
| `apps/cancer-ca` | 7.5 | Tumor CA model. | Yes |
| `toy-projects/rule30` | 7 | Rule 30 attack. | Yes |

## Tier B — polish

| `apps/kotcumber` | 4 | Game. | Yes |
"""


class TestInventoryParsing:
    def test_tier_a_rows_only(self):
        projects = parse_inventory(INVENTORY_SAMPLE)
        paths = [p.path for p in projects]
        assert paths == ["trading/trader", "apps/cancer-ca", "toy-projects/rule30"]

    def test_filters_apply_exclude(self):
        projects = parse_inventory(INVENTORY_SAMPLE)
        filtered = apply_filters(projects, exclude=["apps/cancer-ca"])
        assert [p.path for p in filtered] == ["trading/trader", "toy-projects/rule30"]

    def test_override_replaces_list(self):
        projects = parse_inventory(INVENTORY_SAMPLE)
        overridden = apply_filters(projects, override=["research/aixi"])
        assert [p.path for p in overridden] == ["research/aixi"]


class TestMissionBriefs:
    def test_all_types_generate_briefs(self):
        for kind in MISSION_TYPES:
            brief = build_brief(kind, "toy-projects/GameOfLife")
            assert "===FINDING===" in brief
        assert build_brief("CONNECT", "a", "b") != build_brief("CONNECT", "b", "b")

    def test_connect_names_both_projects(self):
        brief = build_brief("CONNECT", "toy-projects/rule30", "apps/cancer-ca")
        assert "`toy-projects/rule30`" in brief
        assert "`apps/cancer-ca`" in brief

    def test_unknown_type_raises(self):
        with pytest.raises(ValueError):
            build_brief("DESTROY", "x")

    def test_safety_preamble_present(self):
        assert "NEVER" in build_brief("EXPLORE", "x")

    def test_mission_rotation_covers_projects(self):
        config = SwarmConfig(build_allowlist=["apps/cancer-ca"])
        projects = [
            Project(path="toy-projects/rule30", name="rule30"),
            Project(path="apps/cancer-ca", name="cancer-ca"),
        ]
        kinds = set()
        targets = set()
        for i in range(12):
            mission = make_mission(i, projects, config)
            kinds.add(mission.kind)
            if mission.kind == "BUILD":
                assert mission.project == "apps/cancer-ca"
            targets.add(mission.project)
        assert kinds == set(MISSION_TYPES)
        assert targets == {p.path for p in projects}

    def test_build_mission_denied_outside_allowlist(self):
        config = SwarmConfig(build_allowlist=["toy-projects/GameOfLife"])
        projects = [Project(path="apps/cancer-ca", name="cancer-ca")]
        with pytest.raises(safety.SafetyViolation):
            make_mission(5, projects, config)

    def test_build_mission_allowed_inside_allowlist(self):
        config = SwarmConfig(build_allowlist=["toy-projects/rule30"])
        projects = [Project(path="toy-projects/rule30", name="rule30")]
        mission = make_mission(5, projects, config)
        assert mission.kind == "BUILD"

    def test_no_project_named_sokra_ever_dispatched(self):
        config = SwarmConfig()
        projects = [Project(path="Sokra/evil", name="evil")]
        with pytest.raises(safety.SafetyViolation):
            make_mission(0, projects, config)
