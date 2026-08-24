# Agent wave — 2026-08-25 bounded FINDING retry

## Summary

Implemented the next runner-hardening item from `ROADMAP.md`: when a backend
returns successfully but the output has no parseable `===FINDING===` block, the
runner makes one retry with a concise formatting reminder. Failed and timed-out
backend results are not retried. The retry is recorded in the append-only
notebook as a `retry` event; dispatch counts continue to represent jobs rather
than attempts.

## Changed paths

- `swarm/runner.py` — one bounded retry for absent or malformed findings.
- `tests/test_runner.py` — recovery, boundedness, and no-unnecessary-retry
  coverage.
- `README.md` — safety and audit behavior.
- `ROADMAP.md` — item moved to Done.

## Evidence

- **EMPIRICAL:** a successful response without a finding is retried once and a
  valid second response is collected.
- **EMPIRICAL:** a response that remains unparseable after the retry produces no
  finding and does not trigger a third backend call.
- **EMPIRICAL:** a parseable first response is not retried.
- **LIMITATION:** each retry receives the full configured backend timeout, so a
  missing finding can consume up to two per-agent timeout windows.

## Classification

**INCREMENTAL.** This is a bounded reliability improvement with focused
regression coverage. It makes no claim about model quality or finding validity
beyond the existing parser contract.
