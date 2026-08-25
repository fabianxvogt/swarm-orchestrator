# ROADMAP

## Now

- **Goal checkpoint (2026-08-22):** A held breakthrough candidate proposes typed, fail-closed capability gating for swarm actions; next is a temporary-directory enforcement probe, not production integration. See the portfolio review at `Development/docs/reviews/BREAKTHROUGH-fail-closed-swarm-gating.md`.

- Long-run validation: one real 2–4 hour session (`swarm run --hours 2
  --parallel 8 --interval-min 20`) and a review of notebook quality.
- The safe local preflight and owner-run acceptance criteria are recorded in
  [`docs/long-run-validation-checklist.md`](docs/long-run-validation-checklist.md).

## Next

- No additional implementation gap is scheduled; long-run validation remains in
  Now.

## Later

- Web dashboard over the JSONL notebooks.
- Cross-run memory: feed prior findings back as context to new missions.
- Measure the swarm-emergence hypothesis directly (connections/hour vs solo baseline)
  and write up results — see ideas/INBOX.md "Swarm-emergence lab".

## Done

- 2026-08-25: read-only status now reports runtime notebook contract
  violations for incomplete dispatch/result/finding sequences and retries after
  failed results; dry-run notebooks remain exempt. [EMPIRICAL observability
  regression]

- 2026-08-25: notebook path handling now rejects path-like agent identifiers,
  preventing direct notebook reads or writes from escaping the run directory;
  regression coverage preserves normal generated labels. [EMPIRICAL safety
  regression]

- 2026-08-25: the status CLI/API now reject non-integer (including boolean)
  limits with a stable validation error before scanning run directories.
  [EMPIRICAL observability regression]

- 2026-08-25: status ordering now treats numeric same-second run-directory
  collision suffixes numerically, so bounded reports do not omit a newer
  `...-10` run in favor of `...-2`. [EMPIRICAL observability regression]

- 2026-08-25: added a bounded long-run validation checklist separating the
  temporary-directory `echo` preflight from the owner-only provider session;
  it defines notebook integrity, retry, safety, and evidence checks without
  running a provider or multi-hour job. [EMPIRICAL local validation / process]

- 2026-08-25: direct `Swarm.run_for_hours` callers now receive finite,
  non-negative guards for hours and inter-wave interval; CLI zero-hour routing
  remains a single wave. [EMPIRICAL safety regression]

- 2026-08-25: CLI `--hours` and config `interval_min` now reject negative or
  non-finite duration values before project resolution or dispatch; regression
  coverage protects the bounded-run invariant. [EMPIRICAL safety regression]

- 2026-08-25: CLI runtime overrides are revalidated after application, so invalid
  interval and timeout values fail closed before project resolution or backend
  dispatch. [EMPIRICAL safety regression]

- 2026-08-25: added a deterministic temporary-directory CLI validation gate
  using only the local `echo` backend; it verifies one five-agent wave writes
  five clean notebooks, bounds malformed-finding retries, and reports no
  failures without touching portfolio notebooks or providers. [EMPIRICAL local
  validation]

- 2026-08-25: dispatch now validates mission text before any backend call, closing
  a direct/mutated-brief bypass of the documented deny-list; deterministic
  no-backend regression coverage added. [EMPIRICAL safety regression]
- 2026-08-25: added a deterministic wave-level symlink probe proving that a
  deny-listed resolved working directory blocks two scheduled local missions
  before backend calls or notebook dispatch events. [EMPIRICAL safety regression]
- 2026-08-25: added opt-in local git commit provenance for successful BUILD
  findings. It is disabled by default, requires a clean target worktree, stages
  only post-dispatch safe paths, clears staging when a commit fails, and never
  pushes. [EMPIRICAL safety regression]

- 2026-08-25: successful backend responses without a parseable FINDING block
  receive one bounded retry with an explicit machine-readable reminder; failed
  and timed-out responses remain single-attempt. [EMPIRICAL runner regression]

- 2026-08-25: added bounded read-only `swarm status`, summarizing the newest
  run notebooks by wave with dispatch, finding, failure, malformed-record, and
  approximate output-token counts. Exact cost remains unavailable because
  notebooks do not record provider pricing. [EMPIRICAL observability]
- 2026-08-25: added opt-in `swarm status --json` with schema version, run and
  wave counters, aggregate totals, and explicit unavailable-cost metadata;
  default text output is unchanged. Status also exposes bounded retry counts
  from existing notebook events. [EMPIRICAL observability]

- 2026-08-25: wave assembly caps dispatches at one primary mission per unique
  project, so parallel size cannot create duplicate project targets; deterministic
  runner coverage added. [EMPIRICAL concurrency regression]

- 2026-08-24: findings are normalized and deduplicated before publication;
  duplicate copies retain the highest deterministic quality rating. [EMPIRICAL
  publication regression]
- 2026-08-22: canonicalized paths before deny matching and added a symlink-target regression probe; full pytest remains unavailable in the environment.

- 2026-08-22: failed and timed-out child findings are now excluded from publication; focused writer-agent suite reports 38 passing tests. [EMPIRICAL safety regression]

- Core orchestrator: parallel dispatch, mission rotation, timeouts, graceful shutdown,
  stale-process reaping.
- Safety layer: Sokra\*/.env/key deny-list enforced on paths and task text;
  BUILD allowlist; read-only-by-default missions; `--auto` off by default.
- Registry from PROJECT_INVENTORY.md Tier A with YAML/JSON override.
- Lab notebook (JSONL per agent) + finding parser + INBOX/CONNECTIONS appenders.
- Pluggable backends: opencode, claude, echo.
- CLI with `--dry-run`, `--once`, hours-long loop mode; test suite (36 tests).
