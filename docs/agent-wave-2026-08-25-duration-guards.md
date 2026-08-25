# Agent wave — 2026-08-25 bounded duration guards

## Summary

Closed one non-finite duration bypass at the CLI/config boundary. `--hours`
now accepts only finite, non-negative numbers, and `SwarmConfig.interval_min`
rejects NaN and infinite values before project resolution or backend dispatch.

## Changed paths

- `swarm/orchestrator.py` — validates CLI `--hours` values during argument parsing.
- `swarm/config.py` — validates finite, non-negative configured intervals.
- `tests/test_safety.py` — covers negative, NaN, and infinite duration inputs.
- `README.md` / `ROADMAP.md` — records the operator-facing safety boundary.
- This document — evidence record.

No run directories, notebooks, secrets, or portfolio files were touched.

## Evidence

- **EMPIRICAL, before:** `--hours` used `type=float`, so values such as `inf`
  and `nan` parsed successfully; `interval_min` only checked `< 0`, which did
  not reject NaN or infinity.
- **EMPIRICAL, after:** parser probes reject `-1`, `nan`, `inf`, and `-inf`
  with argparse status 2; config probes reject NaN and both infinities with a
  `ValueError`.
- **EMPIRICAL:** `PYTHONPATH=. .venv/bin/pytest -q -p no:cacheprovider
  tests/test_safety.py tests/test_missions.py` passed: **41 passed**.
- **EMPIRICAL:** the full suite passed: **78 passed**.
- **EMPIRICAL:** `git diff --check` passed.

## Safety boundary and limitations

The guard applies to CLI run hours and the configured inter-wave interval. It
does not change the allowed hour range, provider timeout policy, project
allowlist, backend behavior, or direct callers that bypass the CLI and pass
invalid values to unrelated APIs. `timeout_s` remains an integer and positive
under the existing config guard.

## Classification

**INCREMENTAL.** This is a small fail-closed input validation fix with
deterministic regression evidence. It makes no claim about long-run provider
behavior or swarm quality.

## Next falsifiable test

Run the CLI with a finite fractional interval in a temporary echo-backed wave
and verify it remains accepted without creating any non-temporary artifacts.
