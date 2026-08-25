# Agent wave — 2026-08-25 attempt coherence

## Summary

Closed one remaining JSON-valid retry-sequence gap in the read-only status
report. The runner emits attempt 1 for the initial result/finding pair and
attempt 2 for its single bounded retry pair. Status previously accepted a
retry with `attempt: 3` and matching result/finding metadata as a complete
sequence because the envelope validators checked types and presence, but not
the bounded numbering relationship.

Status now reports one contract violation when runner-emitted attempt metadata
does not match that protocol. Result and finding attempt metadata remains
optional for compatibility with older notebooks; omitted fields are not
invented or counted as malformed.

## Reproduced sequence

```text
dispatch → result(attempt=1) → finding:null → retry(attempt=3)
         → result(attempt=3) → finding(attempt=3)
```

All event envelopes and fields are JSON-valid, but the retry path is bounded
to the runner's second attempt.

## Evidence and limits

- **EMPIRICAL:** the regression fixture reports one retry, one finding, zero
  malformed records, and one contract violation.
- **EMPIRICAL:** existing runner-shaped attempt 1/2 sequences and legacy
  records without optional result/finding attempt metadata remain accepted.
- **EMPIRICAL:** this is status-only validation; dispatch, retry scheduling,
  parsing, and provider behavior are unchanged.
- **LIMIT:** the check validates the current local notebook protocol; it does
  not infer provider quality or prove that a provider actually performed the
  stated attempt.

## Classification

**INCREMENTAL / EMPIRICAL.** A minimal observability-only contract check with
local regression evidence.
