from __future__ import annotations

import pytest

from swarm import safety
from swarm.config import SwarmConfig, config_from_mapping, parse_yaml_subset
from swarm.orchestrator import _effective_config, build_parser, main
from swarm.registry import Project


class TestDenyList:
    def test_sokra_path_rejected(self):
        with pytest.raises(safety.SafetyViolation):
            safety.check_path("Sokra/anything")

    def test_sokra_recovered_variant_rejected(self):
        with pytest.raises(safety.SafetyViolation):
            safety.check_path("/Users/fabian/Development/sokra-step-7-99995-recovered")

    def test_denied_symlink_target_rejected(self, tmp_path):
        denied = tmp_path / "Sokra-target"
        denied.mkdir()
        alias = tmp_path / "benign-alias"
        alias.symlink_to(denied, target_is_directory=True)

        with pytest.raises(safety.SafetyViolation):
            safety.check_path(str(alias))

    def test_sokra_in_task_text_rejected(self):
        with pytest.raises(safety.SafetyViolation):
            safety.check_task("please read Sokra-step-28b-6r and summarize")

    def test_env_file_rejected(self):
        with pytest.raises(safety.SafetyViolation):
            safety.check_path("trading/trader/.env")

    def test_service_account_key_rejected(self):
        with pytest.raises(safety.SafetyViolation):
            safety.check_path(
                "research/context-engines/context-ai/sokra-477315-key.json"
            )

    def test_benign_path_allowed(self):
        safety.check_path("toy-projects/GameOfLife")
        safety.check_task("explore toy-projects/rule30", cwd="toy-projects/rule30")

    def test_build_allowlist_enforced(self):
        allow = ["toy-projects/GameOfLife"]
        safety.check_build_allowed("toy-projects/GameOfLife", allow)
        with pytest.raises(safety.SafetyViolation):
            safety.check_build_allowed("apps/cancer-ca", allow)

    def test_write_deny_blocks_coding_agent_clone(self):
        with pytest.raises(safety.SafetyViolation):
            safety.check_path("apps/coding-agent", write=True)


class TestConfig:
    def test_yaml_subset_flat_and_lists(self):
        data = parse_yaml_subset(
            """
            # comment
            parallel: 5
            backend: echo
            auto_approve: false
            commit_per_finding: true
            exclude:
              - apps/orchestrator
            build_allowlist: [toy-projects/GameOfLife, apps/kotcumber]
            """
        )
        assert data["parallel"] == 5
        assert data["backend"] == "echo"
        assert data["commit_per_finding"] is True
        assert data["exclude"] == ["apps/orchestrator"]
        assert data["build_allowlist"] == [
            "toy-projects/GameOfLife",
            "apps/kotcumber",
        ]

    def test_yaml_list_of_mappings(self):
        data = parse_yaml_subset(
            """
            projects:
              - path: toy-projects/rule30
                rating: 7
              - path: apps/cancer-ca
            """
        )
        assert data["projects"][0] == {"path": "toy-projects/rule30", "rating": 7}
        assert data["projects"][1] == {"path": "apps/cancer-ca"}

    def test_config_mapping_overrides_defaults(self):
        cfg = config_from_mapping({"parallel": 6, "backend": "claude"})
        assert isinstance(cfg, SwarmConfig)
        assert cfg.parallel == 6
        assert cfg.backend == "claude"
        assert cfg.interval_min == 20

    def test_unknown_keys_rejected(self):
        with pytest.raises(ValueError):
            config_from_mapping({"nope": 1})

    def test_defaults_are_safe(self):
        cfg = SwarmConfig()
        assert cfg.auto_approve is False
        assert cfg.commit_per_finding is False
        assert "research/context-engines" in cfg.exclude

    def test_cli_can_opt_in_to_commit_provenance(self):
        args = build_parser().parse_args(["run", "--commit-per-finding"])
        assert _effective_config(args).commit_per_finding is True

    @pytest.mark.parametrize(
        "argv",
        [
            ["run", "--interval-min", "-1"],
            ["run", "--timeout-s", "0"],
        ],
    )
    def test_cli_runtime_overrides_revalidate_safety_limits(self, argv):
        args = build_parser().parse_args(argv)
        with pytest.raises(ValueError):
            _effective_config(args)

    @pytest.mark.parametrize("value", ["-1", "nan", "inf", "-inf"])
    def test_cli_hours_rejects_unbounded_or_negative_values(self, value):
        with pytest.raises(SystemExit) as exc_info:
            build_parser().parse_args(["run", "--hours", value])
        assert exc_info.value.code == 2

    def test_cli_hours_accepts_finite_fraction(self):
        args = build_parser().parse_args(["run", "--hours", "0.25"])
        assert args.hours == pytest.approx(0.25)

    def test_cli_zero_hours_remains_a_single_wave(self, monkeypatch, tmp_path):
        calls = []

        class FakeSwarm:
            findings = []

            def __init__(self, *args, **kwargs):
                pass

            def run_wave(self):
                calls.append("wave")
                return 0

            def run_for_hours(self, *args):
                calls.append("hours")
                raise AssertionError("zero hours must not enter the duration loop")

        monkeypatch.setattr(
            "swarm.orchestrator.load_registry",
            lambda path: [Project(path="project", name="project")],
        )
        monkeypatch.setattr("swarm.orchestrator.apply_filters", lambda *args: args[0])
        monkeypatch.setattr("swarm.orchestrator.install_signal_handlers", lambda: None)
        monkeypatch.setattr("swarm.orchestrator.reap_stale", lambda path: [])
        monkeypatch.setattr("swarm.orchestrator.Swarm", FakeSwarm)
        monkeypatch.setattr("swarm.orchestrator.RUNS_DIR", tmp_path / "runs")

        assert main(["run", "--hours", "0", "--dry-run"]) == 0
        assert calls == ["wave"]

    @pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
    def test_config_interval_rejects_non_finite_values(self, value):
        with pytest.raises(ValueError, match="finite"):
            SwarmConfig(interval_min=value)
