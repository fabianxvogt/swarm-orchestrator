from __future__ import annotations

import pytest

from swarm.backends import build_command, run_agent


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

    def test_unknown_backend_rejected(self):
        with pytest.raises(ValueError):
            build_command("magic", "x", None, False)
