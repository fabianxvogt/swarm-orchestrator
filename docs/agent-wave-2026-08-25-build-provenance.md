# Agent wave — 2026-08-25 BUILD finding provenance

## Summary

Added an opt-in `commit_per_finding` setting for successful BUILD missions.
When enabled, the runner takes a clean-worktree snapshot before dispatch,
stages only the resulting safe paths, and creates one local commit named from
the finding title. No push operation is available or performed.

## Changed paths

- `swarm/config.py` — safe-by-default config field and parser support.
- `swarm/orchestrator.py` — opt-in `--commit-per-finding` flag.
- `swarm/runner.py` — clean-worktree preflight and guarded local commit.
- `tests/test_runner.py` — successful commit and dirty-worktree refusal probes.
- `tests/test_safety.py` — config default and YAML coverage.
- `README.md` / `ROADMAP.md` — operator boundary and roadmap evidence.

## Evidence

- **EMPIRICAL:** an isolated temporary git repository receives one local commit
  after a successful BUILD finding, containing the agent-created file.
- **EMPIRICAL:** a dirty target worktree blocks the backend before dispatch and
  does not create a commit.
- **EMPIRICAL:** the setting defaults to `false`; no production repository was
  committed or pushed during this change.
- **EMPIRICAL:** focused safety/runner tests pass (26), and the full suite passes
  (65); `git diff --check` passes.

## Safety boundary and limitations

The feature is opt-in, BUILD-only, and requires a pre-dispatch clean worktree
with an existing `HEAD`. It refuses renames/copies, paths denied by the normal
safety layer, HEAD changes during dispatch, and findings that produce no git
changes. A failed provenance commit is recorded in the notebook, clears any
staging created by the attempt while preserving agent worktree edits, and does
not silently retry or push.

## Classification

**INCREMENTAL.** This is bounded local provenance plumbing. It makes no claim
about long-run swarm quality, provider cost, or commit authorship beyond the
existing local git configuration.
