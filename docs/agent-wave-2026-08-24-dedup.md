# Agent wave — 2026-08-24 finding publication deduplication

## Summary

Added the next roadmap increment at the publication boundary. Findings now
receive a deterministic 0–5 quality rating and are normalized to a fingerprint
before publication. When agents emit the same normalized finding, the
highest-rated copy is retained; unique findings continue to publish as before.

## Changed paths

- `swarm/findings.py` — added `rate_finding()`, `finding_fingerprint()`, and
  `prepare_findings()`.
- `swarm/orchestrator.py` — applies `prepare_findings()` before writing to
  `INBOX.md` or `CONNECTIONS.md`.
- `tests/test_findings.py` — covers rating-based duplicate selection and
  direction-independent connection fingerprints.
- `tests/test_runner.py` — proves publication writes one copy of a duplicate.
- `ROADMAP.md` — moved the completed item to Done.

No run directories, run logs, secrets, or generated artifacts were touched.

## Deterministic behavior

- Identity uses finding type, title, claim, and normalized project names.
- Case and repeated whitespace are ignored; connection project order is ignored.
- Punctuation and wording remain significant, so this is not fuzzy semantic
  clustering.
- The score rewards populated title/claim, a recognized claim label
  (`FORMAL`, `EMPIRICAL`, `REPORTED`, or `SPECULATIVE`), an experiment, and the
  expected number of projects.
- The score chooses between duplicates only. There is no minimum score gate, so
  a unique parsed finding retains the existing publication behavior.
- First-seen order is retained, with a later higher-rated duplicate replacing
  the earlier copy in that position.

## Evidence

- **EMPIRICAL:** before this change, `_publish()` iterated over every parsed
  finding and called an appender for each one.
- **EMPIRICAL:** the new regression probe submits two case/whitespace-equivalent
  findings and observes exactly one appender call, for the copy containing an
  experiment.
- **EMPIRICAL:** reversed project order produces one connection fingerprint.
- **EMPIRICAL:** `PYTHONPATH=. .venv/bin/pytest -q -p no:cacheprovider`
  passed: **48 passed in 0.05s**.
- **EMPIRICAL:** `git diff --check` passed.

## Safety boundary and limitations

The guard runs only after successful child results have already been parsed
into `Finding` objects and immediately before the existing publication
appenders. It does not dispatch agents, grant permissions, resolve project
paths, read run artifacts, or broaden the existing deny-list boundary. It also
does not prevent semantically similar findings with different wording, nor
duplicates across separate process invocations whose prior publication files
are not loaded. Per-project concurrency protection remains the next roadmap
item.

## Classification

**INCREMENTAL.** This is a small, deterministic reduction of same-run swarm
echo at the existing publication boundary. It has regression evidence but no
novelty or breakthrough claim.

## Next falsifiable test

Run two separate waves with equivalent findings and a persisted temporary
publication destination, then verify whether cross-run deduplication is needed
without reading or modifying `runs/` artifacts.
