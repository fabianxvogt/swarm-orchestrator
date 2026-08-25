# Agent wave — 2026-08-25 dispatch payload validation

## Summary

Closed a status-reporting input gap: a JSON-valid runtime `dispatch` event
whose payload was not an object was previously counted as a dispatch. Status
now reports that record as malformed and excludes it from dispatch totals.
Dry-run dispatches remain compatible with their existing string brief payload.

## Changed paths

- `swarm/status.py` — validate runtime dispatch payload shape.
- `tests/test_status.py` — regression for a non-object dispatch payload.
- `ROADMAP.md` / `docs/README.md` — evidence and navigation.

## Evidence

- **EMPIRICAL:** a malformed runtime dispatch payload increments
  `malformed_records` and does not inflate `dispatches`.
- **EMPIRICAL:** the complete focused and full test suites pass.
- **EMPIRICAL:** no provider, workflow, run notebook, dependency, or generated
  artifact is required.

## Boundary and classification

This validates the runtime dispatch event envelope only. It does not require a
project field, because existing synthetic and safety-reporting tests use an
empty object, and it does not change the separate dry-run payload contract.

**INCREMENTAL.** Narrow defensive status validation with local regression
evidence; no dispatch or provider behavior changed.
