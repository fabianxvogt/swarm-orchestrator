# Agent wave — 2026-08-25 notebook path handling

## Summary

Closed a direct notebook API path-containment gap. `Notebook.path_for()` now
accepts only non-empty, single-component agent filenames. This preserves the
runner’s generated labels while preventing `log()` and `entries(agent)` from
following `../`, absolute, or Windows-style separator paths outside the run
directory.

## Changed paths

- `swarm/notebook.py` — validates agent labels before constructing notebook
  paths.
- `tests/test_findings.py` — regression coverage for traversal, absolute, and
  alternate-separator labels.
- `README.md` / `ROADMAP.md` — records the notebook path boundary.

## Evidence

- **EMPIRICAL:** normal `agent-1` JSONL round-tripping remains covered.
- **EMPIRICAL:** path-like labels fail with the stable
  `ValueError("agent must be a simple filename")` before any notebook file is
  created.
- **EMPIRICAL:** the regression does not invoke a provider or touch portfolio
  notebooks.

## Limitations

This guards agent-derived filenames. The caller still controls the notebook
run directory itself; higher-level run-directory safety remains the
orchestrator’s responsibility.

## Classification

**INCREMENTAL.** This is a narrow deterministic path-containment fix with no
change to status aggregation, dispatch, publication, or provider behavior.
