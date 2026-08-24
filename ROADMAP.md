# ROADMAP

## Now

- **Goal checkpoint (2026-08-22):** A held breakthrough candidate proposes typed, fail-closed capability gating for swarm actions; next is a temporary-directory enforcement probe, not production integration. See the portfolio review at `Development/docs/reviews/BREAKTHROUGH-fail-closed-swarm-gating.md`.

- Long-run validation: one real 2–4 hour session (`swarm run --hours 2
  --parallel 8 --interval-min 20`) and a review of notebook quality.
- Tune the FINDING block: agents occasionally omit it; add retry-on-missing.

## Next

- Per-agent concurrency limits per project (don't send two agents into one repo).
- `swarm status` command summarizing runs/, findings per wave, cost estimate.
- Optional git commit-per-finding provenance for BUILD missions (opt-in).

## Later

- Web dashboard over the JSONL notebooks.
- Cross-run memory: feed prior findings back as context to new missions.
- Measure the swarm-emergence hypothesis directly (connections/hour vs solo baseline)
  and write up results — see ideas/INBOX.md "Swarm-emergence lab".

## Done

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
