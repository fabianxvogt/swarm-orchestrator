# Agent wave — 2026-08-25 project identity boundary

## Summary

The status duplicate check already used lexical POSIX normalization, but the
live wave assembler still compared configured project strings literally. A
wave containing `validation/project-1` and `validation//project-1` therefore
scheduled two missions even though both identifiers select the same target
under the configured workdir.

The scheduler and status summary now share the same lexical identity helper.
This prevents duplicate scheduling for dot segments, repeated separators, and
trailing separators while preserving the original project string in the
mission and notebook payload.

The helper also owns the existing non-empty, trimmed identifier boundary. An
empty configured project previously became ``.`` under ``posixpath.normpath``
and was scheduled, while the same empty runtime payload was rejected by status.
Invalid configured entries are now skipped before wave assembly, so scheduler
and status agree without changing any filesystem resolution behavior.

## Evidence

- **EMPIRICAL:** before the fix, `Swarm.wave()` returned both
  `validation/project-1` and `validation//project-1`; joining either with a
  temporary workdir produced the same normalized target.
- **EMPIRICAL:** after the fix, the wave returns one job for that alias pair.
- **EMPIRICAL:** `validation/project-1` and `validation/project_1` remain two
  jobs, so normalization does not conflate distinct lexical identifiers.
- **EMPIRICAL:** status accounting continues to report valid lexical aliases
  as one same-wave contract violation without changing dispatch totals.
- **EMPIRICAL:** before the boundary fix, `Swarm.wave()` returned an empty
  project for `Project(path="", ...)`, while a notebook dispatch with
  `{"project": ""}` produced zero dispatches and one malformed record.
- **EMPIRICAL:** after the fix, the scheduler skips the empty entry and status
  retains its existing fail-closed accounting.

## Boundary and classification

The shared helper is deliberately lexical and POSIX-style. It does not
resolve symlinks, fold case, expand `~`, or collapse filesystem-dependent
absolute-path aliases. In particular, exactly two leading slashes retain the
platform-defined behavior of `posixpath.normpath`; the project contract is
relative identifiers, and broadening that boundary would risk conflating
valid targets.

**INCREMENTAL / EMPIRICAL.** This is a reproduced scheduler/status identity
boundary gap with focused regression coverage; provider execution and
filesystem canonicalization remain unchanged.
