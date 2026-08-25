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
- [`agent-wave-2026-08-25-notebook-paths.md`](agent-wave-2026-08-25-notebook-paths.md)
  — containment of direct notebook agent paths
- [`agent-wave-2026-08-25-status-contracts.md`](agent-wave-2026-08-25-status-contracts.md)
  — bounded validation of runtime notebook event sequences
- [`agent-wave-2026-08-25-dispatch-payload-validation.md`](agent-wave-2026-08-25-dispatch-payload-validation.md)
  — object validation for runtime dispatch event payloads
- [`agent-wave-2026-08-25-dispatch-project-validation.md`](agent-wave-2026-08-25-dispatch-project-validation.md)
  — rejects padded runtime dispatch project identifiers before project accounting
- [`agent-wave-2026-08-25-dispatch-project-identity.md`](agent-wave-2026-08-25-dispatch-project-identity.md)
  — compares valid path-like project identifiers by lexical identity for
  same-wave duplicate accounting
- [`agent-wave-2026-08-25-retry-payload-validation.md`](agent-wave-2026-08-25-retry-payload-validation.md)
  — object and required-field validation for retry event payloads
- [`agent-wave-2026-08-25-finding-payload-validation.md`](agent-wave-2026-08-25-finding-payload-validation.md)
  — required/present-optional-field validation and sequencing for runtime
  finding payloads
- [`agent-wave-2026-08-25-finding-order-validation.md`](agent-wave-2026-08-25-finding-order-validation.md)
  — rejects finding events that do not immediately follow a result
- [`agent-wave-2026-08-25-retry-after-finding.md`](agent-wave-2026-08-25-retry-after-finding.md)
  — flags retries after an already parsed first finding
- [`agent-wave-2026-08-25-attempt-coherence.md`](agent-wave-2026-08-25-attempt-coherence.md)
  — validates bounded retry/result/finding attempt numbering
- [`agent-wave-2026-08-25-retry-sequence-validation.md`](agent-wave-2026-08-25-retry-sequence-validation.md)
  — keeps malformed retry records out of sequence validation
- `swarm/` — implementation
- `tests/` — verification

Record swarm runs and durable findings in the root `ideas/` files or a focused project document. Do not store logs or generated run artifacts here.
