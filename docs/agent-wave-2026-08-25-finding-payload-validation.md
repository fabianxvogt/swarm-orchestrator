# Agent wave — 2026-08-25 finding payload validation

## Summary

Closed a status-reporting gap after the dispatch, retry, and result checks:
non-null runtime `finding` events now require the non-empty string `title` and
`claim` fields already required by `parse_finding`. `finding: null` remains the
runner's valid record for a response without a parsed finding.

An invalid finding after a result is reported both as a malformed record and as
a contract-sequencing violation. This prevents a JSON-valid object such as
`{"title": 7, "claim": "EMPIRICAL: malformed title"}` from inflating finding
totals or satisfying the result/finding ordering check.

## Changed paths

- `swarm/status.py` — validate non-null finding fields and use that validation
  when checking result/finding sequencing.
- `tests/test_status.py` — regression coverage for the malformed title case,
  malformed finding sequencing, and valid finding payloads.
- `ROADMAP.md` / `docs/README.md` — evidence and navigation.

## Evidence and limits

- **EMPIRICAL:** the malformed title fixture contributes zero findings, one
  malformed record, and one contract violation.
- **EMPIRICAL:** valid `null` and title/claim finding records preserve existing
  retry and result accounting.
- **EMPIRICAL:** this is read-only notebook validation; provider dispatch,
  retry behavior, and finding parsing are unchanged.

Optional finding metadata remains outside this narrow check.

## Classification

**INCREMENTAL / EMPIRICAL.** A minimal defensive status-contract fix with local
regression evidence.
