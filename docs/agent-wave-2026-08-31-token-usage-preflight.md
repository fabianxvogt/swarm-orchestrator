# Agent wave — 2026-08-31 exact token-usage preflight boundary

## Classification

**INCREMENTAL / PREFLIGHT.** This is a dependency-free accounting contract. It is not a collective-performance result and does not enable a model-backed pilot.

## Change

- `swarm/backends.py` adds immutable `TokenUsage` receipts with exact built-in
  integer/string validation, explicit complete/source fields, exact
  input-plus-output totals, strict serialized parsing, and
  `TokenAccountingError`.
- `BackendResult.usage` is optional so unavailable provider accounting is
  represented by `None`, never an invented zero.
- `require_pilot_token_usage()` admits only successful results carrying
  revalidated exact `provider` receipts within budget.
- `require_fixture_token_usage()` separately admits deterministic UTF-8-byte
  `echo-fixture` units to local preflights; fixture units cannot admit a pilot.
- `tests/test_backends.py` covers Unicode receipt determinism, immutability,
  Boolean/negative/inconsistent/incomplete/unknown/missing receipts, exact-int
  budgets, list sources, failed/timed-out results, arbitrary/subclassed/forged
  usage, source separation, and over-budget rejection.
- `README.md`, `ROADMAP.md`, and the documentation index record the boundary.

## Compatibility and limit

Production backend construction, retry behavior, parallelism, notebook events,
and status schemas are unchanged. Existing
`BackendResult(returncode, stdout, timed_out)` callers remain valid because
usage defaults to `None`. The legacy status token estimate remains available
for operations but cannot satisfy provider-only pilot admission.

The provider adapters do not yet supply authoritative receipts. A provider
result therefore fails the pilot admission boundary. No provider tokenizer,
credential, model call, solo scheduler, isolation layer, communication channel,
retry-policy change, or condition-blinding behavior is introduced here.

## Focused validation

The dependency-free smoke command imported the repaired contract, ran Unicode
through `echo`, admitted its exact receipt only through the fixture boundary,
rejected it at the provider-only pilot boundary, and rejected a missing
provider receipt. Its valid fixture receipt was:

```text
{'input_tokens': 10, 'output_tokens': 31, 'total_tokens': 41, 'source': 'echo-fixture', 'complete': True}
```

The owner validation command is:

```text
PYTHONPATH=. python3 -m pytest -q -p no:cacheprovider tests/test_backends.py
```

This lane intentionally did not run tests, linters, formatters, provider
commands, or project-wide validation; validation is reserved for the
integration owner.
