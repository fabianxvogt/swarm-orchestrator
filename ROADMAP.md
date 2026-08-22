# ROADMAP

## Now

- Long-run validation: one real 2–4 hour session (`swarm run --hours 2
  --parallel 8 --interval-min 20`) and a review of notebook quality.
- Tune the FINDING block: agents occasionally omit it; add retry-on-missing.

## Next

- Finding dedup + rating before publishing to INBOX/CONNECTIONS (avoid swarm echo).
- Per-agent concurrency limits per project (don't send two agents into one repo).
- `swarm status` command summarizing runs/, findings per wave, cost estimate.
- Optional git commit-per-finding provenance for BUILD missions (opt-in).

## Later

- Web dashboard over the JSONL notebooks.
- Cross-run memory: feed prior findings back as context to new missions.
- Measure the swarm-emergence hypothesis directly (connections/hour vs solo baseline)
  and write up results — see ideas/INBOX.md "Swarm-emergence lab".

## Done

- Core orchestrator: parallel dispatch, mission rotation, timeouts, graceful shutdown,
  stale-process reaping.
- Safety layer: Sokra\*/.env/key deny-list enforced on paths and task text;
  BUILD allowlist; read-only-by-default missions; `--auto` off by default.
- Registry from PROJECT_INVENTORY.md Tier A with YAML/JSON override.
- Lab notebook (JSONL per agent) + finding parser + INBOX/CONNECTIONS appenders.
- Pluggable backends: opencode, claude, echo.
- CLI with `--dry-run`, `--once`, hours-long loop mode; test suite (36 tests).
