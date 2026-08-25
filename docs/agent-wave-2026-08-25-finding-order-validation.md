# Agent wave — 2026-08-25 finding order validation

## Summary

Closed a sequencing gap in the read-only status report: every valid runtime
`finding` event must immediately follow a `result` event. Before this check,
the sequence `dispatch → result → finding → finding` reported zero contract
violations and counted both findings, even though the runner emits one finding
per result and only inserts a retry before a second result.

The validator now reports one contract violation for that duplicate/orphan
finding shape while preserving the existing payload count and malformed-record
accounting.

## Changed paths

- `swarm/status.py` — flag finding events without an immediately preceding
  result.
- `tests/test_status.py` — regression coverage for a duplicate finding after a
  completed result/finding pair.
- `ROADMAP.md` and `docs/README.md` — record and link the evidence.

## Evidence

- **EMPIRICAL:** the duplicate-finding fixture reports two valid finding
  payloads, zero malformed records, and one contract violation; it is no longer
  accepted as a complete sequence.
- **EMPIRICAL:** existing direct and one-bounded-retry runner sequences remain
  valid because each finding still immediately follows its corresponding
  result.
- **EMPIRICAL:** this is read-only notebook validation; provider dispatch,
  retry behavior, and finding parsing are unchanged.

## Boundary

This check establishes the runner's local event order only. It does not assess
provider quality, finding usefulness, provenance-event contents, or long-run
stability.

## Classification

**INCREMENTAL / EMPIRICAL.** A minimal defensive status-contract fix with
focused regression evidence.
