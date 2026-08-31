from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from swarm.backends import (
    BackendResult,
    TokenAccountingError,
    TokenUsage,
    build_command,
    require_fixture_token_usage,
    require_pilot_token_usage,
    run_agent,
)

class IntSubclass(int):
    pass


class TokenUsageSubclass(TokenUsage):
    pass


class TestBackends:
    def test_opencode_command_shape(self):
        cmd = build_command("opencode", "hello", None, auto=False)
        assert cmd[:3] == ["/opt/homebrew/bin/opencode", "run", "hello"]
        assert "--auto" not in cmd

    def test_auto_flag_only_when_enabled(self):
        cmd = build_command("opencode", "hello", None, auto=True)
        assert "--auto" in cmd

    def test_claude_command_shape(self):
        cmd = build_command("claude", "hi", "opus", False)
        assert cmd == ["claude", "-p", "hi", "--model", "opus"]

    def test_echo_backend_runs(self):
        result = run_agent("echo", "brief text", cwd=".", timeout_s=30)
        assert result.ok
        assert "brief text" in result.stdout

    def test_echo_backend_records_deterministic_unicode_usage(self):
        brief = "café 🙂"

        result = run_agent("echo", brief, cwd=".", timeout_s=30)

        assert result.usage == TokenUsage(
            input_tokens=len(brief.encode("utf-8")),
            output_tokens=len(result.stdout.encode("utf-8")),
            total_tokens=len(brief.encode("utf-8"))
            + len(result.stdout.encode("utf-8")),
            source="echo-fixture",
        )
        with pytest.raises(FrozenInstanceError):
            result.usage.total_tokens = 0

    @pytest.mark.parametrize(
        "payload",
        [
            {
                "input_tokens": True,
                "output_tokens": 2,
                "total_tokens": 3,
                "source": "echo-fixture",
                "complete": True,
            },
            {
                "input_tokens": IntSubclass(1),
                "output_tokens": 2,
                "total_tokens": 3,
                "source": "echo-fixture",
                "complete": True,
            },
            {
                "input_tokens": -1,
                "output_tokens": 2,
                "total_tokens": 1,
                "source": "echo-fixture",
                "complete": True,
            },
            {
                "input_tokens": 1,
                "output_tokens": 2,
                "total_tokens": 4,
                "source": "echo-fixture",
                "complete": True,
            },
            {
                "input_tokens": 1,
                "output_tokens": 2,
                "total_tokens": 3,
                "source": "estimate",
                "complete": True,
            },
            {
                "input_tokens": 1,
                "output_tokens": 2,
                "total_tokens": 3,
                "source": [],
                "complete": True,
            },
            {
                "input_tokens": 1,
                "output_tokens": 2,
                "total_tokens": 3,
                "source": "echo-fixture",
                "complete": False,
            },
            {
                "input_tokens": 1,
                "output_tokens": 2,
                "total_tokens": 3,
                "source": "echo-fixture",
            },
        ],
    )
    def test_token_usage_rejects_malformed_receipts(self, payload):
        with pytest.raises(ValueError):
            TokenUsage.from_payload(payload)

    def test_pilot_admission_requires_successful_exact_provider_usage(self):
        unknown = BackendResult(0, "provider output", False)
        with pytest.raises(TokenAccountingError, match="unavailable"):
            require_pilot_token_usage(unknown, max_total_tokens=10)

        usage = TokenUsage(3, 4, 7, "provider")
        result = BackendResult(0, "provider output", False, usage)
        assert require_pilot_token_usage(result, max_total_tokens=7) == usage
        with pytest.raises(TokenAccountingError, match="exceeded"):
            require_pilot_token_usage(result, max_total_tokens=6)

    def test_echo_usage_is_fixture_only_and_cannot_admit_a_pilot(self):
        result = run_agent("echo", "fixture", cwd=".", timeout_s=30)

        with pytest.raises(TokenAccountingError, match="cannot satisfy"):
            require_pilot_token_usage(result, max_total_tokens=100)
        assert (
            require_fixture_token_usage(result, max_total_tokens=100)
            == result.usage
        )

    @pytest.mark.parametrize(
        "result",
        [
            BackendResult(1, "", False, TokenUsage(1, 1, 2, "provider")),
            BackendResult(0, "", True, TokenUsage(1, 1, 2, "provider")),
        ],
    )
    def test_admission_rejects_failed_or_timed_out_results(self, result):
        with pytest.raises(TokenAccountingError, match="not successful"):
            require_pilot_token_usage(result, max_total_tokens=2)

    @pytest.mark.parametrize(
        "usage",
        [
            object(),
            TokenUsageSubclass(1, 1, 2, "provider"),
        ],
    )
    def test_admission_rejects_arbitrary_or_subclassed_usage(self, usage):
        result = BackendResult(0, "", False, usage)
        with pytest.raises(TokenAccountingError, match="invalid type"):
            require_pilot_token_usage(result, max_total_tokens=2)

    def test_admission_revalidates_forged_usage_fields(self):
        usage = TokenUsage(1, 1, 2, "provider")
        object.__setattr__(usage, "total_tokens", -1)

        with pytest.raises(TokenAccountingError, match="invalid"):
            require_pilot_token_usage(
                BackendResult(0, "", False, usage),
                max_total_tokens=2,
            )

    @pytest.mark.parametrize("budget", [True, -1, 1.5, IntSubclass(1)])
    def test_pilot_admission_rejects_invalid_budgets(self, budget):
        result = BackendResult(0, "", False, TokenUsage(0, 0, 0, "provider"))
        with pytest.raises(ValueError):
            require_pilot_token_usage(result, max_total_tokens=budget)

    def test_unknown_backend_rejected(self):
        with pytest.raises(ValueError):
            build_command("magic", "x", None, False)
