# Agent wave — 2026-08-25 notebook contract reporting

## Summary

Extended the read-only status report with `contract_violations` counters at
wave, run, and aggregate levels. The counters flag incomplete runtime notebook
sequences and retry protocol breaks: a dispatch without a result, a result
without its finding record, unbounded retries, or a retry after a failed
result, or a duplicate primary project within a wave. Status also reports a
JSON-valid `finding` event whose payload is not an object or `null` as
malformed, so that payload cannot inflate the finding count. Dry-run notebooks
are intentionally exempt because they do not invoke a backend; safety-blocked
notebooks are exempt because they stop before dispatch.

## Evidence

- **EMPIRICAL:** a complete dispatch/result/finding sequence reports zero
  contract violations.
- **EMPIRICAL:** synthetic incomplete and failed-retry notebooks report two
  violations without invoking a backend or writing outside a temporary
  directory.
- **EMPIRICAL:** synthetic notebooks that dispatch the same primary project in
  one wave report one contract violation, while distinct projects remain clean.
- **EMPIRICAL:** a JSON-valid `finding` event with a list payload increments
  `malformed_records` without incrementing `findings`.
- **EMPIRICAL:** the local echo validation gate reports zero contract
  violations and five distinct primary projects.

## Boundary

This validates notebook structure and runner-level sequencing only. It does
not assess provider quality, finding usefulness, exact token usage, or
long-run stability. The owner-run checklist still requires a spot-check of
actual JSONL content and a separate provider-backed session.

## Classification

**INCREMENTAL.** This is a narrow local observability and evidence-validation
improvement with no provider, publication, or notebook mutation.
