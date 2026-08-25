# Agent wave — 2026-08-25 bounded duration guards

## Summary

Closed non-finite duration bypasses at both the CLI/config and direct API
boundaries. `--hours` and `Swarm.run_for_hours(hours, interval_min)` now accept
only finite, non-negative durations. The CLI still maps `hours=0` to exactly
one wave.

## Changed paths

- `swarm/orchestrator.py` — validates CLI `--hours` values during argument parsing.
- `swarm/runner.py` — validates both direct `run_for_hours` duration arguments
  before computing a deadline or dispatching a wave.
- `swarm/config.py` — validates finite, non-negative configured intervals.
- `tests/test_safety.py` / `tests/test_runner.py` — cover CLI, config, and direct
  API duration inputs, including zero-hour single-wave routing.
- `README.md` / `ROADMAP.md` — records the operator-facing safety boundary.
- This document — evidence record.

No run directories, notebooks, secrets, or portfolio files were touched.

## Evidence

- **EMPIRICAL, before:** `--hours` used `type=float`, so values such as `inf`
  and `nan` parsed successfully; `interval_min` only checked `< 0`, which did
  not reject NaN or infinity.
- **EMPIRICAL, after:** parser probes reject `-1`, `nan`, `inf`, and `-inf`
  with argparse status 2; config and direct API probes reject negative, NaN,
  and infinite durations with a `ValueError` before dispatch.
- **EMPIRICAL:** `PYTHONPATH=. .venv/bin/pytest -q -p no:cacheprovider
  tests/test_safety.py tests/test_runner.py` passed: **47 passed**.
- **EMPIRICAL:** the full suite passed: **87 passed**.
- **EMPIRICAL:** `git diff --check` passed.

## Safety boundary and limitations

The guard does not change the allowed hour range, provider timeout policy,
project allowlist, backend behavior, or `Swarm.run_for_hours` loop cadence.
`timeout_s` remains an integer and positive under the existing config guard.

## Classification

**INCREMENTAL.** This is a small fail-closed input validation fix with
deterministic regression evidence. It makes no claim about long-run provider
behavior or swarm quality.

## Next falsifiable test

Run the CLI with a finite fractional interval in a temporary echo-backed wave
and verify it remains accepted without creating any non-temporary artifacts.
