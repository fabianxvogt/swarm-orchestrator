# Orchestrator Documentation

Entry point for the swarm implementation in this project.

- [`../README.md`](../README.md) — purpose and quickstart
- [`../ROADMAP.md`](../ROADMAP.md) — current work
- [`long-run-validation-checklist.md`](long-run-validation-checklist.md) — safe
  local preflight and owner-run evidence criteria for the remaining roadmap item
- [`agent-wave-2026-08-25-status-ordering.md`](agent-wave-2026-08-25-status-ordering.md)
  — deterministic ordering for same-second run-directory collisions
- [`agent-wave-2026-08-25-status-input-validation.md`](agent-wave-2026-08-25-status-input-validation.md)
  — positive-integer validation for the status limit CLI/API contract
- `swarm/` — implementation
- `tests/` — verification

Record swarm runs and durable findings in the root `ideas/` files or a focused project document. Do not store logs or generated run artifacts here.
