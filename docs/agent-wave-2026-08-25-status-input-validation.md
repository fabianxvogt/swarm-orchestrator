# Agent wave — 2026-08-25 status input validation

## Summary

Strengthened the bounded `swarm status` contract at the public API boundary.
The CLI already parses `--limit` as an integer, but direct callers of
`summarize_runs` could pass a float, string, `None`, or boolean. Status now
rejects those values with `ValueError("limit must be an integer")` before
checking the runs directory; non-positive integers retain the existing
`ValueError("limit must be positive")` contract.

## Changed paths

- `swarm/status.py` — runtime validation for the direct `limit` API input.
- `tests/test_status.py` — regression coverage for non-integer and boolean
  limits.
- `README.md` / `ROADMAP.md` — public contract and evidence update.

## Evidence

- **EMPIRICAL:** the focused status suite passed: **14 passed**.
- **EMPIRICAL:** the full suite passed: **92 passed**.
- **EMPIRICAL:** invalid direct API limits fail with a stable `ValueError`
  instead of incidental slicing errors or boolean acceptance.
- **EMPIRICAL:** numeric collision ordering and malformed JSONL handling remain
  covered by the same status suite.
- **EMPIRICAL:** no provider, run notebook, secret, or portfolio path is
  required by the regression.

## Limitations

This validates the type and lower bound of the requested scan size; it does not
add a new maximum beyond the caller's explicit positive limit or change the
name-based ordering of run directories.

## Classification

**INCREMENTAL.** This is a small defensive API validation improvement with no
change to dispatch, publication, notebook writes, or provider behavior.
