# Agent wave — 2026-08-31 token evidence envelope

## Classification

**INCREMENTAL / EMPIRICAL.** This is an offline archival and projection contract. It is not a provider adapter, admission integration, or collective-performance result.

## Change

- `swarm/usage_evidence.py` adds the strict `usage-evidence/v1` envelope.
- Raw built-in bytes are retained as canonical base64 with exact byte length and
  SHA-256; source, CLI version, executable, source-schema, parser, and redacted
  command-shape provenance are explicit. Partial archives may mark a schema
  digest unknown; exact projection cannot.
- A validated invocation tree records call kind, attribution, terminal state,
  success/failure outcome, complete/partial/unknown coverage, helper calls, and
  known exclusions.
- Every usage record distinguishes observed, derived, and unknown quantities.
  `disjoint_sum`, `includes_subset`, and `unknown` relations prevent accidental
  addition of overlapping counters. Derived sums require one matching relation,
  compatible known basis and semantics, exact arithmetic, and an acyclic
  dependency graph.
- Namespaced JSON extensions preserve source-specific structure. Strict key
  sets, exact built-in security fields, duplicate rejection, Unicode-scalar
  validation, canonical JSON, an envelope self-hash, and raw hashes reject
  malformed records, accidental corruption, and stale digests. These unsigned
  hashes do not authenticate evidence against an adversary able to rewrite it.
- `project_exact_token_usage()` returns no receipt unless exactly one root
  invocation aggregate succeeded, is terminal, fully covered, exclusion-free,
  backed by a pinned source schema and only complete raw captures, and has
  consistent observed provider-authority inclusive input/output/total under one
  known basis, one semantics URI, and a trusted additive relation. Unknown
  component splits remain distinct from observed zero and do not block an exact
  inclusive aggregate.
- `tests/test_usage_evidence.py` freezes documentation-derived OpenCode 1.18.21
  and Claude Code/Agent SDK shapes. Both round-trip raw bytes and normalized
  evidence but remain inadmissible. Adversarial cases cover malformed trees,
  outcomes, incomplete captures, unknown versus zero, unsupported/cyclic
  derivations, raw and envelope digest mismatches, semantics/basis conflicts,
  missing/extra keys, extension collisions, Unicode surrogates, non-exact
  built-ins, helper coverage, and fixture non-admission.

The frozen shapes follow OpenCode's version-tagged
[`StepFinishPart`](https://github.com/anomalyco/opencode/blob/v1.18.21/packages/schema/src/v1/session.ts)
and [`Session.getUsage`](https://github.com/anomalyco/opencode/blob/v1.18.21/packages/opencode/src/session/session.ts),
and Anthropic's current [`SDKResultMessage`](https://code.claude.com/docs/en/agent-sdk/typescript#sdkresultmessage)
and [`ModelUsage`](https://code.claude.com/docs/en/agent-sdk/typescript#modelusage)
documentation. They are offline documentation fixtures, not claims about a live invocation.

## Focused validation

The exact provider fixture round-tripped its canonical envelope and projected
only the provider-authority inclusive aggregate; its absent cache/reasoning
splits remained unknown rather than fabricated zeroes:

```text
provider envelope_sha256=ecfe1219d182e39fb8e2211dce8e9ff7ac3b849e3db885fb30868dc732b28c7a
provider canonical_json_bytes=3950 raw_bytes=55 projection=10/5/15
```

Both documentation-derived CLI fixtures round-tripped their exact raw bytes and
remained inadmissible:

```text
opencode envelope_sha256=4868a63a86551cc6b3ea0140bc5f5fc36838c7ff3a7a92ddd7dc70b01be81e91 canonical_json_bytes=4573 raw_bytes=187 projection=None
claude envelope_sha256=dac3fe9bd15a5843b6a724d57ee44235f12e3b4a341d5c2164a5851cd39c5695 canonical_json_bytes=4529 raw_bytes=358 projection=None
```

Parent verification after review fixes:

```text
PYTHONPATH=. .venv/bin/pytest -q -p no:cacheprovider tests/test_usage_evidence.py tests/test_backends.py
47 passed

PYTHONPATH=. .venv/bin/pytest -q -p no:cacheprovider
184 passed
```

No provider command, model call, authentication, or network access was used.

## Boundary

The module is deliberately not imported by the runner or Gate-1 helpers.
OpenCode's step-normalized counts and Claude's documentation-level aggregate
remain evidence only: neither establishes complete invocation-tree coverage or
an exact provider-authority total. Production notebook and status schemas are
unchanged.
