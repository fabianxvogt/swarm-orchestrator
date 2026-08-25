# Agent wave — 2026-08-25 dispatch project validation

## Summary

Closed a status-accounting edge in runtime `dispatch` records. A JSON-valid
`project` value with surrounding whitespace was previously accepted as a
different project string, so a padded duplicate could evade the same-wave
duplicate-project check and inflate the dispatch total. Status now requires the
serialized project identifier to be non-empty and already trimmed.

## Evidence

- **EMPIRICAL:** a normal dispatch plus a padded duplicate now reports one valid
  dispatch and one malformed record; the padded record cannot enter duplicate
  primary-project accounting.
- **EMPIRICAL:** the complete focused and full test suites pass, as do
  compilation and whitespace checks.
- **EMPIRICAL:** this is status-only validation; dispatch scheduling, notebook
  writing, provider execution, and dry-run payloads are unchanged.

## Boundary and classification

Only surrounding whitespace on the runtime `project` field is rejected. Existing
non-empty trimmed project paths remain compatible, and optional dispatch metadata
continues to use its existing contract.

**INCREMENTAL / EMPIRICAL.** Narrow defensive status validation with a
reproducible project-accounting regression; no provider or workflow behavior
changed.
