# Agent wave — 2026-08-25 retry payload validation

## Summary

Closed a status-reporting input gap: a JSON-valid `retry` event whose payload
was not an object was previously counted as a retry. Status now reports that
record as malformed and excludes it from retry totals. Runtime retry payloads
remain mappings containing the retry reason and attempt number.

## Changed paths

- `swarm/status.py` — validate retry event payload shape.
- `tests/test_status.py` — regression for a non-object retry payload.
- `README.md` / `ROADMAP.md` / `docs/README.md` — contract evidence and
  navigation.

## Evidence

- **EMPIRICAL:** a malformed retry payload increments `malformed_records` and
  does not inflate `retries`.
- **EMPIRICAL:** the focused status tests and complete pytest suite pass.
- **EMPIRICAL:** no provider, long workflow, run notebook, dependency, or
  generated artifact is required.

## Boundary and classification

This validates the retry event envelope only. It does not add field-level
validation for the retry mapping and does not change retry scheduling or
provider behavior.

**INCREMENTAL.** Narrow defensive status validation with local regression
evidence; no dispatch, publication, or provider behavior changed.
