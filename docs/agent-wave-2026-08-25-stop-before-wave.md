# Agent wave — 2026-08-25 stop before wave

## Summary

Audited the STOP boundary after the duration and empty-wave fixes. A shutdown
request was honored by `run_for_hours()` before its loop, but a direct
`Swarm.run_wave()` call did not check the same process-wide stop event before
assembling a new wave. This was observable in dry-run mode, where a stopped
call still printed a mission brief and wrote a `dispatch_dry_run` notebook
event.

`run_wave()` now returns without assembling jobs when STOP is already set. It
also clears the previous wave-state marker so a caller cannot mistake the
skipped call for a wave that had jobs. A wave that has already started retains
the existing behavior of completing its current futures before the duration
loop observes STOP.

## Changed paths

- `swarm/runner.py` — check STOP at the public new-wave boundary.
- `tests/test_runner.py` — cover dry-run and backend modes before dispatch.
- `README.md`, `ROADMAP.md`, and this evidence record — document the boundary.

No provider was called and no run notebook or portfolio project was created.

## Evidence

- **EMPIRICAL, before:** with `runner.STOP` set, a one-project dry-run
  `Swarm.run_wave()` returned `0` but advanced `mission_index` from `0` to
  `1`, printed one `[dry-run]` line, logged one `dispatch_dry_run` event, and
  marked `_last_wave_had_jobs` true.
- **EMPIRICAL, after:** the focused regression covers both dry-run and normal
  modes and observes no mission-index advance, dispatch, stdout, notebook
  event, or positive wave-state marker after STOP.
- **EMPIRICAL:** the full pytest suite, compilation, and `git diff --check`
  are required completion checks for this change.

## Boundary and classification

This is a process-shutdown boundary only. It does not cancel an already
running backend, change the mission scan, alter duration validation, or
reinterpret empty-wave results.

**INCREMENTAL / EMPIRICAL.** The issue is a reproduced pre-wave side-effect
regression; it makes no provider-stability or long-run quality claim.
