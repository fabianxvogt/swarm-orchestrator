# Agent wave — 2026-08-24 orchestrator safety hardening

## Summary

Added a fail-closed working-directory check at the `dispatch()` boundary. A
denied `config.workdir` now raises before notebook dispatch logging or backend
invocation, including when `dispatch()` is called directly with a custom
configuration.

## Changed paths

- `swarm/runner.py` — added `safety.check_path(config.workdir, write=mission.writable)` before dispatch.
- `tests/test_runner.py` — appended a regression test proving the backend is not
  called for a denied working directory; existing working-tree tests were kept.
- `docs/agent-wave-2026-08-24-orchestrator.md` — this evidence record.

Unrelated pre-existing edits in the orchestrator worktree were preserved.

## Evidence

- **EMPIRICAL, before:** with `workdir="/tmp/.env"` and a fake backend,
  `dispatch()` returned `(True, None)` and the backend was called with
  `['/tmp/.env']`.
- **EMPIRICAL, after:** the same probe raised `SafetyViolation` with a denied
  `.env` path message; the backend call count was `0`.
- **EMPIRICAL:**
  `PYTHONPATH=. .venv/bin/pytest -q -p no:cacheprovider tests/test_runner.py tests/test_safety.py tests/test_findings.py`
  passed: **24 passed in 0.04s**.
- **EMPIRICAL:** `git diff --check` passed.

## Limitations

This validates the configured child-process working directory at dispatch time;
it does not broaden finding-schema validation or test a multi-process backend.
The focused pytest run does not claim that the full repository suite is clean.

## Classification

**INCREMENTAL.** The change closes one concrete unchecked path at the existing
safety boundary; it is not a novelty or breakthrough claim.

## Next falsifiable test

Run `Swarm.run_wave()` with a symlinked `config.workdir` whose resolved target
matches the deny list, and assert that all submitted dispatches fail before any
backend call or notebook `dispatch` event. This tests the guard under parallel
submission rather than only through direct `dispatch()`.
