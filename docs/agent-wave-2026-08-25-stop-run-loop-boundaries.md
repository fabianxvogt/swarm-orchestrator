# Agent wave — 2026-08-25 STOP run-loop boundaries

## Summary

Audited `Swarm.run_for_hours()` across three boundaries: a completed wave that
sets STOP, an inter-wave wait interrupted by STOP, and a stop arriving while a
subsequent wave is still being assembled. The ordinary loop checks already
handled the first two cases. A narrow race remained after `run_wave()`'s public
guard: if STOP arrived inside `wave()`, the old implementation still entered
the dry-run loop or submitted normal-mode dispatch callables.

`_run_wave()` now rechecks STOP immediately after bounded assembly. A canceled
scan returns `(0, False)`, restores the mission index consumed by that scan,
and does not create an executor, backend call, stdout line, or notebook event.

## Changed paths

- `swarm/runner.py` — post-assembly STOP guard and mission-index rollback for a
  canceled scan.
- `tests/test_runner.py` — deterministic coverage for the assembly race,
  completed-wave return accounting, and interval-wait shutdown.
- `README.md`, `ROADMAP.md`, and this evidence record — document the boundary
  and its limits.

No provider, portfolio project, secret, or persistent run notebook was used.

## Evidence

- **EMPIRICAL, before:** a controlled `wave()` hook set STOP after the public
  `run_wave()` guard returned but before `_run_wave()` consumed its jobs. In
  dry-run mode, the call returned `0` but printed one `[dry-run]` line, logged a
  `dispatch_dry_run` event, and set `_last_wave_had_jobs` to `True`. In
  normal mode, the executor still invoked the dispatch callable, which then
  had to notice STOP itself.
- **EMPIRICAL, after:** the parametrized assembly regression covers both modes
  and observes no dispatch callable, stdout, notebook event, or positive
  `_last_wave_had_jobs`; the consumed mission index is restored.
- **EMPIRICAL:** a completed wave that collected one finding and then set STOP
  returns `1` exactly once; no second wave or interval wait is entered.
- **EMPIRICAL:** a STOP raised by the interval wait records exactly one wait,
  returns the completed wave's count unchanged, and starts no subsequent wave.
- **EMPIRICAL:** focused runner coverage passes: **34 passed**. Full pytest,
  compilation, and `git diff --check` are required completion checks.

## Boundary and classification

This is a local shutdown race fix. It does not cancel a backend that has
already started, change provider timeouts, alter mission rotation for a
completed wave, or claim multi-hour provider stability.

**INCREMENTAL / EMPIRICAL.** The defect was reproduced at the pre-dispatch
assembly boundary and the return/interval invariants are pinned by tests.

