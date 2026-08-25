# Agent wave — 2026-08-25 result payload validation

## Summary

Closed a status-reporting input gap: JSON-valid runtime `result` events now
require the stable fields written by the runner (`returncode` as an integer,
`timed_out` as a boolean, and non-negative `stdout_chars` as an integer).
Malformed result payloads are reported as malformed records, do not contribute
to failure or output-character totals, and cannot satisfy the required runtime
result sequence. A follow-up audit also closes a sequencing gap where a
malformed result after an otherwise complete bounded retry could be paired with
a finding and accepted as an additional result.

## Changed paths

- `swarm/status.py` — validate runtime result field types and bounds before
  counting failures or output characters, and require validated result events
  for retry ordering, attempt checks, and result/finding sequencing.
- `tests/test_status.py` — regression coverage for string, non-boolean, and
  negative result fields, including an invalid result after a complete retry.
- `ROADMAP.md` — records the bounded contract and evidence.

## Evidence

- **EMPIRICAL:** each malformed result fixture increments
  `malformed_records`, contributes zero failures and output characters, and
  reports one contract violation when it is the only result before a finding.
- **EMPIRICAL:** an otherwise complete retry sequence followed by a malformed
  result and valid finding reports one contract violation; the malformed result
  remains excluded from result and failure totals.
- **EMPIRICAL:** valid result/finding sequencing and existing result accounting
  remain unchanged.
- **EMPIRICAL:** no provider, notebook, dependency, or workflow behavior is
  changed; this is read-only status validation.

## Limitations

This validates the runner's stable result summary fields only. It does not
infer provider quality, reconstruct missing events, or validate optional
provider metadata.

## Classification

**INCREMENTAL / EMPIRICAL.** A narrow defensive status-contract fix with local
regression evidence.
