# Agent wave — 2026-08-25 dispatch project identity

## Summary

Closed a reproducible status-accounting gap for valid path-like runtime
`dispatch` identifiers. The wave duplicate check previously compared project
strings literally, so `validation/project-1` and `./validation/project-1`
could be emitted by two runtime dispatches and be treated as distinct even
though both resolve to the same relative target under the configured workdir.

Status now uses lexical POSIX path identity for the duplicate check. It does
not rewrite or reject either valid payload, and both dispatches remain counted;
the alias is reported as a same-wave contract violation.

## Evidence

- **EMPIRICAL:** before the fix, a synthetic runtime notebook containing the
  two valid identifiers reported `dispatches=2`, `malformed_records=0`, and
  `contract_violations=0`.
- **EMPIRICAL:** the same identifiers constructed as two `Project` values
  produced two wave jobs while `Path(workdir) / project` resolved to the same
  target, establishing that the accounting input is reachable from runtime
  configuration rather than being a malformed-record-only case.
- **EMPIRICAL:** after the fix, the regression reports two valid dispatches,
  zero malformed records, and one duplicate-project contract violation.

## Boundary and classification

The identity key collapses lexical path aliases such as `./project`, repeated
separators, `project/`, and `a/../project`. The serialized project string and
dispatch total remain unchanged. Symlink resolution, case folding, `~`
expansion, and workdir-relative absolute-path equivalence are intentionally not
performed because status notebooks do not carry enough context for those
transformations and they could change valid existing identifiers.

**INCREMENTAL / EMPIRICAL.** Narrow status-only duplicate accounting with a
reproducible runtime path-alias regression; dispatch scheduling, provider
execution, and payload contracts are unchanged.
