# Agent wave — 2026-08-25 per-project concurrency protection

## Summary

Implemented the next roadmap item at wave assembly. A wave now schedules at
most one mission for each unique primary project target, and a configured
parallel size larger than the project count produces a smaller, safe wave
instead of duplicate targets. The existing mission rotation, configuration
shape, dispatch API, backend behavior, and safety checks remain unchanged.

If safety or BUILD-allowlist filtering leaves fewer dispatchable primary
projects, the wave may contain fewer jobs than both `parallel` and the raw
project count. Duplicate candidates are skipped with a bounded scan so wave
assembly cannot loop forever. `CONNECT` partner projects remain contextual;
the concurrency key is the mission's primary `Mission.project` target.

## Changed paths

- `swarm/runner.py` — deduplicates primary project targets while assembling a
  wave and caps the requested size at unique configured project paths.
- `tests/test_runner.py` — verifies one backend call for a one-project wave and
  deterministic unique targets for a two-project wave with parallel size 8.
- `ROADMAP.md` — moves per-project concurrency protection to Done.
- This document — evidence record.

No run directories, logs, secrets, or generated artifacts were created.

## Evidence

- **EMPIRICAL:** before this change, `Swarm.wave()` called `next_mission()` once
  per configured slot, allowing repeated `Mission.project` values when slots
  exceeded project count (and in some rotation/BUILD cases even before that).
- **EMPIRICAL:** after this change, the one-project `run_wave()` regression
  invokes the backend exactly once despite `parallel=5`.
- **EMPIRICAL:** a two-project wave with `parallel=8` returns exactly the two
  primary targets in deterministic order, with no duplicate target.
- **EMPIRICAL:** `PYTHONPATH=. .venv/bin/pytest -q -p no:cacheprovider` passed:
  **49 passed in 0.11s**.
- **EMPIRICAL:** `git diff --check` passed.

## Exact safety boundary and limitations

The guard is in `Swarm.wave()`, before `run_wave()` logs dry-run dispatches or
submits anything to `ThreadPoolExecutor`. A skipped duplicate is therefore
not passed to `dispatch()`, creates no notebook dispatch event, and cannot call
`run_agent()`. The existing `dispatch()` working-directory safety check still
runs for every retained mission; this change does not weaken or replace it.

The protection is a per-wave scheduling invariant on `Mission.project`, not a
cross-wave lock, filesystem lock, or lock over the secondary `CONNECT.partner`
context. It also does not change the existing BUILD allowlist or broaden path
authorization.

## Classification

**INCREMENTAL.** This is a small, deterministic scheduler-safety fix with full
regression evidence. It makes no novelty or breakthrough claim.

## Next concrete gap

The next roadmap item is `swarm status`. A separate future safety decision is
whether `CONNECT.partner` should participate in the concurrency key; that is
intentionally outside this minimal primary-target fix.
