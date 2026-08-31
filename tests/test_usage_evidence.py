from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import replace

import pytest

from swarm.backends import TokenUsage
from swarm.usage_evidence import (
    Extension,
    InvocationNode,
    Provenance,
    RawEvidence,
    Relation,
    TokenQuantity,
    UsageEvidenceEnvelope,
    UsageEvidenceError,
    UsageRecord,
    project_exact_token_usage,
)


SEMANTICS = "https://example.invalid/token-semantics/v1"
HASH = hashlib.sha256(b"fixture").hexdigest()


def _provenance(
    source: str,
    cli_version: str,
    source_schema_version: str,
) -> Provenance:
    return Provenance(
        source=source,
        cli_version=cli_version,
        binary_sha256=HASH,
        source_schema_uri="https://example.invalid/source-schema",
        source_schema_version=source_schema_version,
        source_schema_sha256=HASH,
        parser_name="swarm.offline_fixture_parser",
        parser_version="1",
        parser_sha256=HASH,
        command_shape_sha256=HASH,
    )


def _observed(
    value: int,
    raw_id: str,
    *,
    authority: str = "client_normalized",
    basis: str = "consumed",
) -> TokenQuantity:
    return TokenQuantity.observed(
        value=value,
        authority=authority,
        basis=basis,
        semantics_uri=SEMANTICS,
        evidence_refs=(raw_id,),
    )


def _derived(value: int, raw_id: str, *operands: str) -> TokenQuantity:
    return TokenQuantity.derived(
        value=value,
        basis="consumed",
        semantics_uri=SEMANTICS,
        evidence_refs=(raw_id,),
        operands=operands,
    )


def _unknown(reason: str, raw_id: str) -> TokenQuantity:
    return TokenQuantity.unknown(
        reason=reason,
        semantics_uri=SEMANTICS,
        evidence_refs=(raw_id,),
    )


def _opencode_fixture() -> UsageEvidenceEnvelope:
    raw_bytes = (
        b'{"type":"step_finish","timestamp":1,"sessionID":"ses_x","part":'
        b'{"type":"step-finish","reason":"stop","cost":0,"tokens":{"input":10,'
        b'"output":5,"reasoning":2,"cache":{"read":3,"write":1}}}}'
    )
    raw = RawEvidence.from_bytes(
        "opencode-step-finish-0",
        raw_bytes,
        "application/x-ndjson; charset=utf-8",
        0,
        True,
    )
    nodes = (
        InvocationNode(
            node_id="opencode-invocation",
            parent_node_id=None,
            node_kind="cli_invocation",
            attribution="unknown",
            coverage="unknown",
            known_exclusions=("unobserved_helper_or_summary_calls",),
            child_node_ids=("opencode-step-0",),
            terminal_observed=False,
            outcome="unknown",
        ),
        InvocationNode(
            node_id="opencode-step-0",
            parent_node_id="opencode-invocation",
            node_kind="model_call",
            attribution="per_step",
            coverage="unknown",
            known_exclusions=(),
            child_node_ids=(),
            terminal_observed=False,
            outcome="unknown",
        ),
    )
    record = UsageRecord(
        record_id="opencode-usage-0",
        scope_node_id="opencode-step-0",
        prompt_non_cached=_observed(10, raw.raw_id),
        prompt_cache_read=_observed(3, raw.raw_id),
        prompt_cache_write=_observed(1, raw.raw_id),
        prompt_inclusive=_derived(
            14,
            raw.raw_id,
            "prompt.non_cached",
            "prompt.cache_read",
            "prompt.cache_write",
        ),
        completion_visible=_observed(5, raw.raw_id),
        completion_reasoning=_observed(2, raw.raw_id),
        completion_inclusive=_derived(
            7,
            raw.raw_id,
            "completion.visible",
            "completion.reasoning",
        ),
        total_inclusive=_unknown("source total field absent", raw.raw_id),
        relations=(
            Relation(
                "prompt.inclusive",
                ("prompt.non_cached", "prompt.cache_read", "prompt.cache_write"),
                "disjoint_sum",
                "versioned_adapter",
            ),
            Relation(
                "completion.inclusive",
                ("completion.visible", "completion.reasoning"),
                "disjoint_sum",
                "versioned_adapter",
            ),
            Relation(
                "total.inclusive",
                ("prompt.inclusive", "completion.inclusive"),
                "unknown",
                "versioned_adapter",
            ),
        ),
    )
    return UsageEvidenceEnvelope(
        envelope_id="opencode-offline-fixture",
        invocation_id="opencode-invocation",
        provenance=_provenance("opencode", "1.18.21", "v1.18.21"),
        nodes=nodes,
        records=(record,),
        raw_evidence=(raw,),
        extensions=(
            Extension.from_value(
                "ai.opencode.step_finish.v1_18_21",
                {
                    "event_type": "step_finish",
                    "part_tokens": {
                        "input": 10,
                        "output": 5,
                        "reasoning": 2,
                        "cache": {"read": 3, "write": 1},
                    },
                },
            ),
        ),
    )


def _claude_fixture() -> UsageEvidenceEnvelope:
    raw_bytes = (
        b'{"type":"result","subtype":"success","usage":{"input_tokens":10,'
        b'"output_tokens":5,"cache_creation_input_tokens":3,'
        b'"cache_read_input_tokens":7},"modelUsage":{"model-x":{"inputTokens":10,'
        b'"outputTokens":5,"cacheReadInputTokens":7,"cacheCreationInputTokens":3,'
        b'"webSearchRequests":0,"costUSD":0,"contextWindow":200000,'
        b'"maxOutputTokens":64000}},"total_cost_usd":0}'
    )
    raw = RawEvidence.from_bytes(
        "claude-model-usage-0",
        raw_bytes,
        "application/json; charset=utf-8",
        0,
        True,
    )
    record = UsageRecord(
        record_id="claude-usage-0",
        scope_node_id="claude-invocation",
        prompt_non_cached=_observed(10, raw.raw_id),
        prompt_cache_read=_observed(7, raw.raw_id),
        prompt_cache_write=_observed(3, raw.raw_id),
        prompt_inclusive=_derived(
            20,
            raw.raw_id,
            "prompt.non_cached",
            "prompt.cache_read",
            "prompt.cache_write",
        ),
        completion_visible=_unknown("source exposes only inclusive model output", raw.raw_id),
        completion_reasoning=_unknown("source does not split reasoning output", raw.raw_id),
        completion_inclusive=_observed(5, raw.raw_id),
        total_inclusive=_unknown("source total field absent", raw.raw_id),
        relations=(
            Relation(
                "prompt.inclusive",
                ("prompt.non_cached", "prompt.cache_read", "prompt.cache_write"),
                "disjoint_sum",
                "versioned_adapter",
            ),
            Relation(
                "completion.inclusive",
                ("completion.visible", "completion.reasoning"),
                "includes_subset",
                "source_schema",
            ),
            Relation(
                "total.inclusive",
                ("prompt.inclusive", "completion.inclusive"),
                "unknown",
                "versioned_adapter",
            ),
        ),
    )
    return UsageEvidenceEnvelope(
        envelope_id="claude-offline-fixture",
        invocation_id="claude-invocation",
        provenance=_provenance("claude-code", "2.1.112", "docs-2026-08-31"),
        nodes=(
            InvocationNode(
                node_id="claude-invocation",
                parent_node_id=None,
                node_kind="cli_invocation",
                attribution="per_model_aggregate",
                coverage="partial",
                known_exclusions=("out_of_pipeline_helper_calls",),
                child_node_ids=(),
                terminal_observed=True,
                outcome="succeeded",
            ),
        ),
        records=(record,),
        raw_evidence=(raw,),
        extensions=(
            Extension.from_value(
                "com.anthropic.claude_code.model_usage.docs_2026_08_31",
                {
                    "model": "model-x",
                    "cost_usd": 0.01,
                    "source_field": "modelUsage",
                },
            ),
        ),
    )


def _exact_provider_fixture() -> UsageEvidenceEnvelope:
    raw = RawEvidence.from_bytes(
        "provider-aggregate-0",
        b'{"input_tokens":10,"output_tokens":5,"total_tokens":15}',
        "application/json; charset=utf-8",
        0,
        True,
    )
    observed = lambda value: _observed(
        value,
        raw.raw_id,
        authority="provider",
        basis="billed",
    )
    record = UsageRecord(
        record_id="provider-usage-0",
        scope_node_id="provider-invocation",
        prompt_non_cached=_unknown("source does not split non-cached input", raw.raw_id),
        prompt_cache_read=_unknown("source does not split cache-read input", raw.raw_id),
        prompt_cache_write=_unknown("source does not split cache-write input", raw.raw_id),
        prompt_inclusive=observed(10),
        completion_visible=_unknown("source does not split visible output", raw.raw_id),
        completion_reasoning=_unknown("source does not split reasoning output", raw.raw_id),
        completion_inclusive=observed(5),
        total_inclusive=observed(15),
        relations=(
            Relation(
                "prompt.inclusive",
                ("prompt.non_cached", "prompt.cache_read", "prompt.cache_write"),
                "includes_subset",
                "source_schema",
            ),
            Relation(
                "completion.inclusive",
                ("completion.visible", "completion.reasoning"),
                "includes_subset",
                "source_schema",
            ),
            Relation(
                "total.inclusive",
                ("prompt.inclusive", "completion.inclusive"),
                "disjoint_sum",
                "source_schema",
            ),
        ),
    )
    return UsageEvidenceEnvelope(
        envelope_id="provider-offline-fixture",
        invocation_id="provider-invocation",
        provenance=_provenance("provider-api", "fixture-v1", "fixture-v1"),
        nodes=(
            InvocationNode(
                node_id="provider-invocation",
                parent_node_id=None,
                node_kind="cli_invocation",
                attribution="invocation_aggregate",
                coverage="complete",
                known_exclusions=(),
                child_node_ids=(),
                terminal_observed=True,
                outcome="succeeded",
            ),
        ),
        records=(record,),
        raw_evidence=(raw,),
        extensions=(),
    )


@pytest.mark.parametrize("envelope", [_opencode_fixture(), _claude_fixture()])
def test_audited_cli_fixtures_round_trip_losslessly_but_are_inadmissible(envelope):
    encoded = envelope.to_json()
    reparsed = UsageEvidenceEnvelope.from_json(encoded)

    assert reparsed == envelope
    assert reparsed.to_json() == encoded
    assert reparsed.envelope_sha256 == envelope.envelope_sha256
    assert [item.decode() for item in reparsed.raw_evidence] == [
        item.decode() for item in envelope.raw_evidence
    ]
    assert project_exact_token_usage(reparsed) is None


def test_unknown_is_distinct_from_observed_zero():
    unknown = TokenQuantity.unknown("field absent from source")
    zero = TokenQuantity.observed(0, "provider", "billed", SEMANTICS, ("raw-0",))

    assert unknown.state == "unknown"
    assert unknown.value is None
    assert zero.state == "observed"
    assert zero.value == 0
    assert unknown.to_payload() != zero.to_payload()


def test_exact_complete_provider_aggregate_is_the_only_projection():
    envelope = _exact_provider_fixture()

    assert project_exact_token_usage(envelope) == TokenUsage(
        input_tokens=10,
        output_tokens=5,
        total_tokens=15,
        source="provider",
    )
    assert project_exact_token_usage(
        replace(
            envelope,
            nodes=(replace(envelope.nodes[0], coverage="partial"),),
        )
    ) is None
    assert project_exact_token_usage(
        replace(
            envelope,
            raw_evidence=(
                replace(envelope.raw_evidence[0], captured_complete=False),
            ),
        )
    ) is None
    incomplete_extra = RawEvidence.from_bytes(
        "unscoped-incomplete",
        b"incomplete",
        "application/octet-stream",
        1,
        False,
    )
    assert project_exact_token_usage(
        replace(envelope, raw_evidence=(*envelope.raw_evidence, incomplete_extra))
    ) is None
    assert project_exact_token_usage(
        replace(
            envelope,
            nodes=(replace(envelope.nodes[0], outcome="failed"),),
        )
    ) is None
    assert project_exact_token_usage(
        replace(
            envelope,
            provenance=replace(
                envelope.provenance,
                source_schema_sha256=None,
            ),
        )
    ) is None
    assert project_exact_token_usage(
        replace(
            envelope,
            records=(
                replace(
                    envelope.records[0],
                    relations=envelope.records[0].relations[:-1],
                ),
            ),
        )
    ) is None
    with pytest.raises(UsageEvidenceError, match="incompatible semantics"):
        replace(
            envelope.records[0],
            prompt_inclusive=replace(
                envelope.records[0].prompt_inclusive,
                semantics_uri="urn:example:incompatible-token-semantics",
            ),
        )


def test_helper_call_coverage_round_trips_without_becoming_admissible():
    envelope = _exact_provider_fixture()
    helper = InvocationNode(
        node_id="helper-0",
        parent_node_id=envelope.invocation_id,
        node_kind="helper_call",
        attribution="per_call",
        coverage="partial",
        known_exclusions=("nested_classifier_call",),
        child_node_ids=(),
        terminal_observed=True,
        outcome="succeeded",
    )
    root = replace(
        envelope.nodes[0],
        attribution="unknown",
        coverage="partial",
        known_exclusions=("helper_call_not_fully_attributed",),
        child_node_ids=(helper.node_id,),
    )
    archived = replace(envelope, nodes=(root, helper))

    reparsed = UsageEvidenceEnvelope.from_json(archived.to_json())
    assert reparsed.nodes[1].node_kind == "helper_call"
    assert reparsed.nodes[1].known_exclusions == ("nested_classifier_call",)
    assert project_exact_token_usage(reparsed) is None


def test_malformed_invocation_tree_is_rejected():
    envelope = _opencode_fixture()
    bad_child = replace(envelope.nodes[1], parent_node_id="missing-parent")

    with pytest.raises(UsageEvidenceError, match="parent/child"):
        replace(envelope, nodes=(envelope.nodes[0], bad_child))


def test_bad_additive_relation_is_rejected():
    envelope = _opencode_fixture()
    record = envelope.records[0]
    wrong_prompt_total = _derived(
        15,
        envelope.raw_evidence[0].raw_id,
        "prompt.non_cached",
        "prompt.cache_read",
        "prompt.cache_write",
    )

    with pytest.raises(UsageEvidenceError, match="value mismatch"):
        replace(record, prompt_inclusive=wrong_prompt_total)
    with pytest.raises(UsageEvidenceError, match="matching disjoint_sum"):
        replace(record, relations=record.relations[1:])


def test_derived_quantity_cycles_are_rejected():
    envelope = _opencode_fixture()
    record = envelope.records[0]
    raw_id = envelope.raw_evidence[0].raw_id
    zero_observed = _observed(0, raw_id)
    prompt = TokenQuantity.derived(
        0,
        "consumed",
        SEMANTICS,
        (raw_id,),
        ("completion.inclusive", "prompt.non_cached"),
    )
    completion = TokenQuantity.derived(
        0,
        "consumed",
        SEMANTICS,
        (raw_id,),
        ("prompt.inclusive", "completion.visible"),
    )
    relations = (
        Relation(
            "prompt.inclusive",
            ("completion.inclusive", "prompt.non_cached"),
            "disjoint_sum",
            "versioned_adapter",
        ),
        Relation(
            "completion.inclusive",
            ("prompt.inclusive", "completion.visible"),
            "disjoint_sum",
            "versioned_adapter",
        ),
        record.relations[2],
    )
    with pytest.raises(UsageEvidenceError, match="cycle"):
        replace(
            record,
            prompt_non_cached=zero_observed,
            prompt_inclusive=prompt,
            completion_visible=zero_observed,
            completion_inclusive=completion,
            relations=relations,
        )


def test_raw_hash_mismatch_is_rejected_before_envelope_integrity():
    payload = json.loads(_opencode_fixture().to_json())
    payload["raw_evidence"][0]["sha256"] = "0" * 64

    with pytest.raises(UsageEvidenceError, match="raw evidence hash mismatch"):
        UsageEvidenceEnvelope.from_payload(payload)


def test_envelope_tampering_is_detected():
    payload = json.loads(_opencode_fixture().to_json())
    payload["envelope_id"] = "tampered"

    with pytest.raises(UsageEvidenceError, match="envelope hash mismatch"):
        UsageEvidenceEnvelope.from_payload(payload)


@pytest.mark.parametrize("mutation", ["missing", "extra"])
def test_missing_and_extra_keys_are_rejected(mutation):
    payload = json.loads(_opencode_fixture().to_json())
    if mutation == "missing":
        del payload["provenance"]["binary_sha256"]
    else:
        payload["provenance"]["unexpected"] = True

    with pytest.raises(UsageEvidenceError, match="missing or unexpected fields"):
        UsageEvidenceEnvelope.from_payload(payload)


def test_extension_namespace_collision_is_rejected():
    envelope = _opencode_fixture()

    with pytest.raises(UsageEvidenceError, match="namespace collision"):
        replace(envelope, extensions=(envelope.extensions[0], envelope.extensions[0]))


def test_binary_raw_evidence_is_lossless():
    data = b"\x00\xff\xf0\x9f\x99\x82\n"
    evidence = RawEvidence.from_bytes(
        "binary-0", data, "application/octet-stream", 0, True
    )

    assert evidence.decode() == data
    assert evidence.byte_length == len(data)
    assert evidence.sha256 == hashlib.sha256(data).hexdigest()


@pytest.mark.parametrize(
    "constructor",
    [
        lambda: TokenQuantity.observed(True, "provider", "billed", SEMANTICS, ("raw",)),
        lambda: InvocationNode(
            "root", None, "cli_invocation", "unknown", "unknown", (), (), 1, "unknown"
        ),
        lambda: RawEvidence.from_bytes(
            "raw", bytearray(b"not-exact-bytes"), "application/octet-stream", 0, True
        ),
    ],
)
def test_security_fields_reject_non_exact_builtin_types(constructor):
    with pytest.raises(UsageEvidenceError):
        constructor()


def test_duplicate_json_keys_are_rejected():
    encoded = _opencode_fixture().to_json()
    duplicate = encoded.replace(
        '"schema":"usage-evidence/v1"',
        '"schema":"usage-evidence/v1","schema":"usage-evidence/v1"',
        1,
    )

    with pytest.raises(UsageEvidenceError, match="envelope JSON is invalid"):
        UsageEvidenceEnvelope.from_json(duplicate)

def test_non_scalar_unicode_and_non_exact_schema_are_rejected():
    with pytest.raises(UsageEvidenceError, match="Unicode surrogate"):
        Extension.from_value("com.example.extension", {"value": "\ud800"})

    class StringSubclass(str):
        pass

    payload = _opencode_fixture().to_payload()
    payload["schema"] = StringSubclass("usage-evidence/v1")
    with pytest.raises(UsageEvidenceError, match="schema"):
        UsageEvidenceEnvelope.from_payload(payload)


def test_non_string_extension_namespace_is_rejected_cleanly():
    payload = _opencode_fixture().to_payload()
    payload["extensions"] = {1: {}}
    with pytest.raises(UsageEvidenceError, match="namespace"):
        UsageEvidenceEnvelope.from_payload(payload)


def test_fixture_projection_rejects_complete_but_non_provider_totals():
    envelope = _exact_provider_fixture()
    record = envelope.records[0]
    fixture_total = TokenQuantity.observed(
        15,
        "fixture",
        "unknown",
        SEMANTICS,
        (envelope.raw_evidence[0].raw_id,),
    )

    with pytest.raises(UsageEvidenceError, match="incompatible bases"):
        replace(record, total_inclusive=fixture_total)


def test_payload_copy_mutation_does_not_alias_extension_value():
    envelope = _opencode_fixture()
    payload = envelope.to_payload()
    copied = copy.deepcopy(payload)
    copied["extensions"]["ai.opencode.step_finish.v1_18_21"]["event_type"] = "other"

    assert envelope.extensions[0].value()["event_type"] == "step_finish"
