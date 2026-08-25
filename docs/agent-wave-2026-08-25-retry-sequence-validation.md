# Agent wave — 2026-08-25 retry sequence validation

## Summary

Closed a remaining JSON-valid status contradiction: malformed `retry` events
were excluded from the retry counter but their event type still participated in
result/retry ordering. A notebook could therefore report `retries=0` and one
malformed record while accepting two valid results as a complete bounded retry
sequence.

Status now uses the validated retry records for both retry counting and
sequence ordering. The malformed event remains visible through
`malformed_records`, and the two-result sequence is reported as a contract
violation because no valid retry bridges it.

## Reproduced sequence

```text
dispatch → result → finding:null → retry:["not", "a", "retry"]
         → result → finding
```

The JSONL record is valid JSON, but its retry payload violates the runner
contract and cannot stand in for the recorded bounded retry.

## Evidence and limits

- **EMPIRICAL:** the fixture reports zero retries, one malformed record, one
  finding, and one contract violation.
- **EMPIRICAL:** valid attempt-2 retry records retain their existing count and
  ordering behavior.
- **EMPIRICAL:** this is a status-only check; dispatch, retry scheduling,
  parsing, and provider behavior are unchanged.

## Classification

**INCREMENTAL / EMPIRICAL.** A minimal observability-only contract fix with
focused local regression evidence.
