# Agent wave — 2026-08-25 retry payload validation

## Summary

Closed two status-reporting input gaps: a JSON-valid `retry` event whose payload
was not an object, or whose required fields were absent or wrongly typed, was
previously counted as a retry. Status now reports that record as malformed and
excludes it from retry totals. Runtime retry payloads contain a non-empty string
`reason` and a positive integer `attempt`.

## Changed paths

- `swarm/status.py` — validate retry event payload shape.
- `tests/test_status.py` — regressions for non-object and invalid-field retry
  payloads.
- `README.md` / `ROADMAP.md` / `docs/README.md` — contract evidence and
  navigation.

## Evidence

- **EMPIRICAL:** a malformed retry payload increments `malformed_records` and
  does not inflate `retries`.
- **EMPIRICAL:** retry mappings with missing, empty, or wrongly typed `reason`
  and `attempt` fields increment `malformed_records` and do not inflate
  `retries`.
- **EMPIRICAL:** the focused status tests and complete pytest suite pass.
- **EMPIRICAL:** no provider, long workflow, run notebook, dependency, or
  generated artifact is required.

## Boundary and classification

This validates the retry event envelope and the two fields emitted by the
runner. It does not change retry scheduling or provider behavior.

**INCREMENTAL.** Narrow defensive status validation with local regression
evidence; no dispatch, publication, or provider behavior changed.
