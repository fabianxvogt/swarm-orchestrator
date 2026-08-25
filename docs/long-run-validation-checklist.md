# Long-run validation checklist

## Purpose

The roadmap's remaining validation item is one real 2–4 hour provider-backed
session followed by a notebook-quality review. This checklist makes the safe
local preflight reproducible and defines the evidence needed before moving that
item out of `Now`. It does not run a provider or claim long-run evidence.

## Local preflight — safe in this repository

Run these from the orchestrator directory:

```bash
PYTHONPATH=. .venv/bin/pytest -q -p no:cacheprovider tests/test_validation_gate.py
PYTHONPATH=. .venv/bin/pytest -q -p no:cacheprovider
git diff --check
```

Expected results:

- The validation-gate test passes using only the `echo` backend and temporary
  directories. It should report five dispatches, five bounded retries, zero
  failures, zero malformed records, and five agent notebooks.
- The full local suite passes.
- `git diff --check` reports no whitespace errors.

This preflight does not create provider runs, portfolio notebooks, or
publication changes. Do not substitute a normal `swarm run` command for it:
the CLI writes run notebooks and may dispatch a real backend.

## Owner-run session — not performed by this lane

After the local preflight, the owner may run the roadmap command with an
approved provider and the normal safety defaults:

```bash
swarm run --hours 2 --parallel 8 --interval-min 20
```

Before starting, confirm that the selected backend, model, project inventory,
and output location are intentional; credentials must remain in the provider's
normal local authentication mechanism and never in config, briefs, or
notebooks. Keep `--auto` and `--commit-per-finding` off unless separately
approved.

Stop the session for an unexpected path/safety warning, a provider
authentication or repeated timeout failure, malformed notebook growth, or an
unexpected write outside the explicitly intended scope. Preserve the run
directory for review; do not copy notebooks into other projects.

## Notebook acceptance review

Use the read-only status report first:

```bash
swarm status --runs-dir /path/to/runs --limit 1 --json
```

Record the run directory, backend/model, start and end times, configured
parallelism, interval, and observed wave count. Then verify:

- `schema_version` is recognized and `malformed_records` is zero.
- `contract_violations` is zero; this confirms each runtime dispatch has a
  result/finding record, retries stay bounded and do not follow failed results,
  and no primary project is dispatched twice in one wave. Dry-run notebooks are
  intentionally exempt because they do not call a backend; safety-blocked
  notebooks are exempt because they stop before dispatch.
- Every wave has no more than eight dispatches and no duplicate primary
  project; fewer dispatches are explainable only by safety or project filters.
- Each dispatch has a result; a successful result without a finding has at
  most one retry. Failed or timed-out results are not retried.
- Finding, failure, retry, and approximate output-token counts in the status
  report agree with a spot-check of the JSONL notebooks.
- Findings are readable and evidence-labeled, with useful experiments or
  next tests; repeated, empty, or provider-error outputs are noted rather than
  treated as swarm discoveries.
- The run produced no unapproved project edits, secrets, or publication
  changes. Review `git status` in any touched allowlisted project before
  considering the session complete.

The long-run roadmap item is complete only when this review is recorded with
the run evidence and its limitations. The local preflight alone remains
`EMPIRICAL local validation`, not evidence of provider stability or swarm
quality.
