# Agent wave — 2026-08-25 status ordering

## Summary

Corrected `swarm status` run selection for same-second directory-name
collisions. The runner names the first run `YYYYMMDD-HHMMSS` and subsequent
runs in that second `YYYYMMDD-HHMMSS-2`, `...-3`, and so on. Lexicographic
sorting places `...-10` before/after the wrong numeric neighbors, so a bounded
status scan could omit the newest collision. Status now sorts generated names
by timestamp and numeric collision suffix; non-generated directory names keep
a deterministic lexical fallback.

## Changed paths

- `swarm/status.py` — numeric run-directory sort key.
- `tests/test_status.py` — regression for `-2` versus `-10` ordering.
- `ROADMAP.md` / `docs/README.md` — evidence and navigation updates.

## Evidence

- **EMPIRICAL:** a synthetic run directory set containing the base name,
  `-2`, and `-10` is reported newest-first as `-10`, `-2`, then the base name.
- **EMPIRICAL:** the focused status suite passed: **10 passed**.
- **EMPIRICAL:** the full suite passed after the change: **88 passed**.
- **EMPIRICAL:** no provider, run notebook, secret, or portfolio path is
  required by the regression.

## Limitations

The ordering remains name-based and does not infer filesystem modification
times. It recognizes the runner's `YYYYMMDD-HHMMSS[-N]` convention; other
directory names use a lexical fallback.

## Classification

**INCREMENTAL.** This is a deterministic bounded-observability correction with
no change to dispatch, duration guards, notebook writes, or provider behavior.
