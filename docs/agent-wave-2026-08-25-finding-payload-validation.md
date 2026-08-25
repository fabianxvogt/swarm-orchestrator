# Agent wave — 2026-08-25 finding payload validation

## Summary

Closed a status-reporting gap after the dispatch, retry, and result checks:
non-null runtime `finding` events now require the non-empty string `title` and
`claim` fields already required by `parse_finding`. Present optional fields now
also retain the parser's output shape: `type` is a string, `projects` is a list
of strings, `experiment` is a string or `null`, and `attempt` is a positive
integer. `finding: null` remains the runner's valid record for a response
without a parsed finding; older notebooks that omit optional fields remain
compatible.

An invalid finding after a result is reported both as a malformed record and as
a contract-sequencing violation. This prevents a JSON-valid object such as
`{"title": 7, "claim": "EMPIRICAL: malformed title"}` from inflating finding
totals or satisfying the result/finding ordering check. The same protection now
covers a malformed optional payload on the second finding of a bounded retry.

## Changed paths

- `swarm/status.py` — validate non-null finding fields and present optional
  metadata, then use that validation when checking result/finding sequencing.
- `tests/test_status.py` — regression coverage for malformed required and
  optional finding fields, malformed finding sequencing, and valid payloads.
- `ROADMAP.md` / `docs/README.md` — evidence and navigation.

## Evidence and limits

- **EMPIRICAL:** the malformed title fixture contributes zero findings, one
  malformed record, and one contract violation.
- **EMPIRICAL:** a retry whose second finding has a string `projects` field
  contributes zero findings, one malformed record, and one contract violation;
  before this check, its required fields made it appear to complete the retry.
- **EMPIRICAL:** valid `null` and title/claim finding records preserve existing
  retry and result accounting.
- **EMPIRICAL:** this is read-only notebook validation; provider dispatch,
  retry behavior, and finding parsing are unchanged.

Optional finding metadata may still be omitted for compatibility, but present
fields are checked for the parser's serialized types. Their content quality is
not assessed.

## Classification

**INCREMENTAL / EMPIRICAL.** A minimal defensive status-contract fix with local
regression evidence.
