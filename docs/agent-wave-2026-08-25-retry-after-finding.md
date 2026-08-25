# Agent wave — 2026-08-25 retry after finding

## Summary

Closed one remaining runtime-sequence gap after result/finding ordering
validation. The runner emits a retry only when the first successful backend
response has no parseable finding, and therefore logs `finding: null` before
the retry. A JSON-valid sequence containing a non-null parsed finding followed
by a retry was previously accepted as complete.

Status now reports that contradiction as one contract violation. This is a
read-only notebook check; provider dispatch, parsing, and retry behavior are
unchanged.

## Reproduced sequence

```text
dispatch → result(attempt=1) → finding(valid) → retry(attempt=2)
         → result(attempt=2) → finding(valid)
```

The payloads can all be valid JSON and satisfy the existing field validators,
but the first non-null finding contradicts the runner condition that triggers
the retry.

## Evidence and limits

- **EMPIRICAL:** the regression fixture reports two findings, one retry, zero
  malformed records, and one contract violation.
- **EMPIRICAL:** the existing valid retry sequence with `finding: null` remains
  accepted.
- **EMPIRICAL:** the focused status tests and full suite pass after the change.
- **LIMIT:** this check verifies the runner's current notebook protocol; it
  does not prove provider output quality or infer intent from finding content.

## Classification

**INCREMENTAL / EMPIRICAL.** A minimal observability-only contract check with
local regression evidence.
