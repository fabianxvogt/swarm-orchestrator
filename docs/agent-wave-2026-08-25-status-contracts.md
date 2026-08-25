# Agent wave — 2026-08-25 notebook contract reporting

## Summary

Extended the read-only status report with `contract_violations` counters at
wave, run, and aggregate levels. The counters flag incomplete runtime notebook
sequences and retry protocol breaks: a dispatch without a result, a result
without its finding record, unbounded retries, or a retry after a failed
result. Dry-run notebooks are intentionally exempt because they do not invoke a
backend; safety-blocked notebooks are exempt because they stop before dispatch.

## Evidence

- **EMPIRICAL:** a complete dispatch/result/finding sequence reports zero
  contract violations.
- **EMPIRICAL:** synthetic incomplete and failed-retry notebooks report two
  violations without invoking a backend or writing outside a temporary
  directory.
- **EMPIRICAL:** the local echo validation gate reports zero contract
  violations.

## Boundary

This validates notebook structure and runner-level sequencing only. It does
not assess provider quality, finding usefulness, exact token usage, or
long-run stability. The owner-run checklist still requires a spot-check of
actual JSONL content and a separate provider-backed session.

## Classification

**INCREMENTAL.** This is a narrow local observability and evidence-validation
improvement with no provider, publication, or notebook mutation.
