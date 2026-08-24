# Agent wave — 2026-08-25 retry observability

## Summary

Extended the existing read-only `swarm status` summary to count `retry`
events already recorded by the runner. Retry counts are reported per wave,
per run, and in aggregate JSON/text totals. Dispatch counts remain job counts,
so a retry is visible without being mistaken for a second dispatch.

## Why this is justified

The runner now performs one bounded retry for a successful response without a
parseable FINDING block, but the status command previously omitted those
events. Operators could see a dispatch and its eventual finding/failure, but
not the extra attempt that affected runtime and backend usage.

## Evidence

- **EMPIRICAL:** a notebook containing one dispatch and one retry reports
  `dispatches=1` and `retries=1` at wave, run, and aggregate levels.
- **EMPIRICAL:** existing status JSON remains schema version `1`; the new field
  is additive and the text formatter remains read-only.
- **EMPIRICAL:** no notebook files are written or changed by summarization.

## Classification

**INCREMENTAL.** This is an observability/test-hardening patch over existing
append-only retry events. It makes no claim about provider cost, provenance,
or finding quality.
