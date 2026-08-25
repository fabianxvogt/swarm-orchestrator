# swarm

An agent-swarm orchestrator that runs 5–10 parallel AI coding-agent subagents
continuously for hours across a development portfolio — generating new ideas,
discovering cross-project connections, and logging everything to an append-only
JSONL lab notebook.

Built as part of a portfolio of research projects (`docs/PROJECT_INVENTORY.md`).
The swarm is itself the experiment: does a parallel agent swarm surface more
cross-project connections than sequential single-agent sessions?

## Why interesting

- **Continuous synthesis**: missions rotate through EXPLORE → CONNECT → IDEATE →
  DOCUMENT → BUILD across every Tier-A project, so the swarm keeps producing
  structured findings instead of one-shot answers.
- **Safety-first by construction**: a hardcoded deny-list (Sokra\* paths,
  `.env` files, service-account keys) is enforced on every mission brief and
  working directory before dispatch. Missions are read-only by default; write
  missions are restricted to an explicit allowlist.
- **Auditable**: every dispatch, raw result, retry, and parsed finding lands in
  `runs/<timestamp>/<agent>.jsonl`. Curated findings flow into
  `ideas/INBOX.md` and `ideas/CONNECTIONS.md` using their existing templates.

## Requirements

- Python ≥ 3.9, stdlib only
- A backend CLI on PATH:
  - [opencode](https://opencode.ai) — used via `opencode run "<brief>"`
  - or Claude Code — via `claude -p "<brief>"`
  - or `echo` for dry testing without any model

## Quickstart

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e .

# print mission briefs without spawning anything
swarm run --parallel 5 --dry-run

# single validation wave with the echo backend (no model needed)
swarm run --parallel 5 --backend echo --once

# inspect the newest run notebooks without dispatching agents
swarm status

# consume the same bounded report from scripts
swarm status --json

# real run: one wave of 8 parallel opencode subagents
swarm run --parallel 8 --once

# hours-long mode: re-dispatch fresh missions for 6 hours, 20 min between waves
swarm run --hours 6 --parallel 8 --interval-min 20
```

Config overrides via YAML:

```yaml
# swarm.yaml
backend: opencode        # opencode | claude | echo
parallel: 8
interval_min: 20
timeout_s: 900           # per-agent timeout
auto_approve: false      # true lets DOCUMENT/BUILD agents auto-approve permissions
commit_per_finding: false # true makes successful BUILD findings local commits
workdir: /Users/fabian/Development
projects:                # override registry (Tier A of PROJECT_INVENTORY.md)
  - path: toy-projects/rule30
exclude:
  - research/context-engines
build_allowlist:         # only these projects may receive BUILD missions
  - toy-projects/GameOfLife
```

```bash
swarm run --hours 4 --config swarm.yaml
```

## Mission types

| Type | Behavior | Writes? |
| --- | --- | --- |
| EXPLORE | Deep-dive one project; status snapshot + next unsolved question | no |
| CONNECT | Find evidence-backed links between two projects | no |
| IDEATE | One falsifiable experiment aimed at an unsolved problem | no |
| DOCUMENT | Fix factual drift in README/ROADMAP | allowlisted only |
| BUILD | Small verifiable increment (< ~100 lines) | allowlisted only |

Subagents end their reply with a machine-readable `===FINDING===` block which
the orchestrator parses and files into `ideas/INBOX.md` (ideas) or
`ideas/CONNECTIONS.md` (connections).

## Safety model

1. **Deny-list regexes** (`swarm/safety.py`) run against every project path,
   partner path, and working directory before dispatch: Sokra\* (any case),
   `.env` files, service-account keys, `context-engines/context-ai`.
2. **Read-only default**: only DOCUMENT/BUILD missions authorize writes, and
   BUILD additionally requires the target to be in `build_allowlist`.
   Denials raise before any process spawns.
3. **No secrets**: `.env` and key paths are denied outright; the deny-list also
   blocks them from appearing in task text.
4. **Process hygiene**: per-agent timeout, stale-process reaping from previous
   runs' pid records, SIGINT/SIGTERM graceful shutdown.
5. `--auto` (permission auto-approval) is off by default and only ever passed
   for write missions.
6. A successful backend response with an absent or malformed FINDING block gets
   one bounded retry; failed and timed-out responses are not retried.
7. `swarm status --json` emits a versioned, read-only summary for scripts;
   retry counts are included, while exact provider cost remains unavailable
   until notebooks record pricing data. The CLI and `summarize_runs` API require
   a positive integer `limit`; malformed limits fail closed before notebook
   inspection.
8. `commit_per_finding` is opt-in and applies only to successful BUILD missions;
   it requires a clean target worktree, commits only agent changes, restores the
   index if the commit fails, and never pushes.
9. Run durations are finite and non-negative: CLI `--hours`, config
   `interval_min`, and direct `Swarm.run_for_hours` callers reject unbounded
   values before dispatch. CLI `--hours 0` remains one wave.

## Status

Experimental / early. Verified end-to-end with bounded local echo validation
and single-wave opencode spawns; multi-hour mode is implemented but not yet
long-run tested. See ROADMAP.md and
[`docs/long-run-validation-checklist.md`](docs/long-run-validation-checklist.md).

## License

MIT — see LICENSE.
