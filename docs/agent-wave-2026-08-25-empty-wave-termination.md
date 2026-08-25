# Agent wave — 2026-08-25 empty-wave termination

## Summary

Audited the scheduler boundary after lexical project validation and alias
deduplication. The wave target was bounded, but two empty-wave paths were not
handled consistently:

- A syntactically valid project denied by the safety layer caused
  `Swarm.next_mission()` to raise out of `Swarm.wave()` after its bounded scan.
- A configuration containing only lexically invalid projects returned an empty
  wave. With `interval_min=0`, `run_for_hours()` immediately started another
  empty wave and busy-spun until the time budget expired.

Wave assembly now catches its explicit no-dispatchable-mission condition and
returns the jobs already found, or an empty list. Duration runs stop after an
empty wave, while non-empty waves retain their existing interval and duration
behavior.

## Changed paths

- `swarm/runner.py` — typed the exhausted mission scan, made wave assembly
  return safely, and carried the empty/non-empty result into duration-loop
  termination.
- `tests/test_runner.py` — covers all-safety-denied projects, repeated invalid
  and duplicate mission generation, and zero-interval empty-wave termination.
- `README.md`, `ROADMAP.md`, and this evidence record — document the bounded
  scheduler contract.

No run directories, logs, secrets, provider calls, or project files were
created.

## Evidence

- **EMPIRICAL, before:** a `service-account/project` candidate made
  `Swarm.wave(5)` raise `RuntimeError("no dispatchable mission: every candidate
  was denied")` after the internal scan, despite the wave contract allowing
  fewer jobs after safety filtering.
- **EMPIRICAL, before:** an all-empty configured project list ran **19,131**
  empty waves in **0.361 seconds** under `run_for_hours(0.0001, 0.0)` in the
  local probe.
- **EMPIRICAL, after:** focused runner coverage passes, including the
  all-safety-denied wave, both repeated invalid/duplicate generation cases, and
  empty duration termination: **28 passed**.
- **EMPIRICAL, after:** the full suite passes: **129 passed**.
- **EMPIRICAL, after:** compilation and `git diff --check` pass.

## Boundary and classification

The fix does not broaden project validity, change lexical identity, resolve
filesystem aliases, or bypass safety checks. A mission scan remains bounded by
the existing rotation/project guard and wave attempt limit. If no dispatchable
mission exists, the scheduler reports no jobs through its normal zero-finding
result rather than retrying an impossible wave indefinitely.

**INCREMENTAL / EMPIRICAL.** This is a reproduced scheduler termination and
accounting-boundary fix; it makes no provider-stability or research claim.
