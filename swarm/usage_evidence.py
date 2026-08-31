from __future__ import annotations

import base64
import binascii
import hashlib
import json
import math
import re
from dataclasses import dataclass
from typing import Any

from .backends import TokenUsage


SCHEMA_VERSION = "usage-evidence/v1"
_HASH_RE = re.compile(r"^[0-9a-f]{64}$")
_NAMESPACE_RE = re.compile(r"^[a-z0-9]+(?:[._-][a-z0-9]+)*\.[a-z0-9]+(?:[._-][a-z0-9]+)*$")
_QUANTITY_PATHS = {
    "prompt.non_cached",
    "prompt.cache_read",
    "prompt.cache_write",
    "prompt.inclusive",
    "completion.visible",
    "completion.reasoning",
    "completion.inclusive",
    "total.inclusive",
}


class UsageEvidenceError(ValueError):
    """Raised when token evidence is malformed, ambiguous, or tampered with."""


def _strict_keys(payload: object, expected: set[str], label: str) -> dict[str, Any]:
    if type(payload) is not dict:
        raise UsageEvidenceError(f"{label} must be an object")
    if set(payload) != expected:
        raise UsageEvidenceError(f"{label} has missing or unexpected fields")
    return payload


def _validate_unicode_scalars(value: str, label: str) -> None:
    if any(0xD800 <= ord(character) <= 0xDFFF for character in value):
        raise UsageEvidenceError(f"{label} contains a lone Unicode surrogate")


def _nonempty_str(value: object, label: str) -> str:
    if type(value) is not str or not value.strip():
        raise UsageEvidenceError(f"{label} must be a non-empty string")
    _validate_unicode_scalars(value, label)
    return value


def _enum_str(value: object, allowed: set[str], label: str) -> str:
    if type(value) is not str or value not in allowed:
        raise UsageEvidenceError(f"{label} is invalid")
    return value

def _optional_str(value: object, label: str) -> str | None:
    if value is None:
        return None
    return _nonempty_str(value, label)


def _nonnegative_int(value: object, label: str) -> int:
    if type(value) is not int or value < 0:
        raise UsageEvidenceError(f"{label} must be a non-negative built-in integer")
    return value


def _exact_bool(value: object, label: str) -> bool:
    if type(value) is not bool:
        raise UsageEvidenceError(f"{label} must be a built-in boolean")
    return value


def _string_tuple(value: object, label: str) -> tuple[str, ...]:
    if type(value) is not list:
        raise UsageEvidenceError(f"{label} must be an array")
    items = tuple(_nonempty_str(item, f"{label} item") for item in value)
    if len(set(items)) != len(items):
        raise UsageEvidenceError(f"{label} must not contain duplicates")
    return items


def _validate_hash(value: object, label: str) -> str:
    text = _nonempty_str(value, label)
    if not _HASH_RE.fullmatch(text):
        raise UsageEvidenceError(f"{label} must be a lowercase SHA-256")
    return text


def _validate_json_value(value: object, label: str = "extension") -> None:
    if value is None or type(value) in {bool, int}:
        return
    if type(value) is str:
        _validate_unicode_scalars(value, label)
        return
    if type(value) is float:
        if not math.isfinite(value):
            raise UsageEvidenceError(f"{label} contains a non-finite number")
        return
    if type(value) is list:
        for item in value:
            _validate_json_value(item, label)
        return
    if type(value) is dict:
        for key, item in value.items():
            if type(key) is not str:
                raise UsageEvidenceError(f"{label} contains a non-string key")
            _validate_unicode_scalars(key, label)
            _validate_json_value(item, label)
        return
    raise UsageEvidenceError(f"{label} contains a non-JSON value")


def _canonical_json(payload: object) -> str:
    _validate_json_value(payload, "payload")
    return json.dumps(
        payload,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _reject_duplicate_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise UsageEvidenceError(f"duplicate JSON key: {key}")
        result[key] = value
    return result
@dataclass(frozen=True)
class TokenQuantity:
    state: str
    value: int | None
    authority: str | None
    basis: str | None
    semantics_uri: str | None
    evidence_refs: tuple[str, ...]
    expression: str | None
    operands: tuple[str, ...]
    reason: str | None

    def __post_init__(self) -> None:
        _enum_str(self.state, {"observed", "derived", "unknown"}, "quantity state")
        if type(self.evidence_refs) is not tuple:
            raise UsageEvidenceError("evidence_refs must be a tuple")
        for ref in self.evidence_refs:
            _nonempty_str(ref, "evidence ref")
        if len(set(self.evidence_refs)) != len(self.evidence_refs):
            raise UsageEvidenceError("evidence_refs must not contain duplicates")
        if type(self.operands) is not tuple:
            raise UsageEvidenceError("operands must be a tuple")
        for operand in self.operands:
            if type(operand) is not str or operand not in _QUANTITY_PATHS:
                raise UsageEvidenceError("quantity operand is invalid")
        if len(set(self.operands)) != len(self.operands):
            raise UsageEvidenceError("operands must not contain duplicates")

        if self.state == "observed":
            _nonnegative_int(self.value, "observed value")
            _enum_str(
                self.authority,
                {"provider", "client_normalized", "fixture"},
                "observed authority",
            )
            _enum_str(
                self.basis,
                {"billed", "consumed", "unknown"},
                "observed basis",
            )
            _nonempty_str(self.semantics_uri, "observed semantics_uri")
            if not self.evidence_refs:
                raise UsageEvidenceError("observed quantity needs evidence")
            if self.expression is not None or self.operands or self.reason is not None:
                raise UsageEvidenceError("observed quantity has derived/unknown fields")
            return

        if self.state == "derived":
            _nonnegative_int(self.value, "derived value")
            if self.authority is not None:
                raise UsageEvidenceError("derived quantity cannot claim authority")
            _enum_str(
                self.basis,
                {"billed", "consumed", "unknown"},
                "derived basis",
            )
            _nonempty_str(self.semantics_uri, "derived semantics_uri")
            if not self.evidence_refs:
                raise UsageEvidenceError("derived quantity needs evidence")
            if self.expression != "sum" or not self.operands:
                raise UsageEvidenceError("derived quantity needs sum operands")
            if self.reason is not None:
                raise UsageEvidenceError("derived quantity cannot have unknown reason")
            return

        if any(
            value is not None
            for value in (self.value, self.authority, self.basis, self.expression)
        ) or self.operands:
            raise UsageEvidenceError("unknown quantity cannot contain a value or derivation")
        _nonempty_str(self.reason, "unknown reason")
        _optional_str(self.semantics_uri, "unknown semantics_uri")

    @classmethod
    def observed(
        cls,
        value: int,
        authority: str,
        basis: str,
        semantics_uri: str,
        evidence_refs: tuple[str, ...],
    ) -> TokenQuantity:
        return cls(
            "observed",
            value,
            authority,
            basis,
            semantics_uri,
            evidence_refs,
            None,
            (),
            None,
        )

    @classmethod
    def derived(
        cls,
        value: int,
        basis: str,
        semantics_uri: str,
        evidence_refs: tuple[str, ...],
        operands: tuple[str, ...],
    ) -> TokenQuantity:
        return cls(
            "derived",
            value,
            None,
            basis,
            semantics_uri,
            evidence_refs,
            "sum",
            operands,
            None,
        )

    @classmethod
    def unknown(
        cls,
        reason: str,
        semantics_uri: str | None = None,
        evidence_refs: tuple[str, ...] = (),
    ) -> TokenQuantity:
        return cls(
            "unknown",
            None,
            None,
            None,
            semantics_uri,
            evidence_refs,
            None,
            (),
            reason,
        )

    def to_payload(self) -> dict[str, object]:
        return {
            "state": self.state,
            "value": self.value,
            "authority": self.authority,
            "basis": self.basis,
            "semantics_uri": self.semantics_uri,
            "evidence_refs": list(self.evidence_refs),
            "expression": self.expression,
            "operands": list(self.operands),
            "reason": self.reason,
        }

    @classmethod
    def from_payload(cls, payload: object) -> TokenQuantity:
        data = _strict_keys(
            payload,
            {
                "state",
                "value",
                "authority",
                "basis",
                "semantics_uri",
                "evidence_refs",
                "expression",
                "operands",
                "reason",
            },
            "token quantity",
        )
        return cls(
            state=data["state"],
            value=data["value"],
            authority=data["authority"],
            basis=data["basis"],
            semantics_uri=data["semantics_uri"],
            evidence_refs=_string_tuple(data["evidence_refs"], "evidence_refs"),
            expression=data["expression"],
            operands=_string_tuple(data["operands"], "operands"),
            reason=data["reason"],
        )


@dataclass(frozen=True)
class Relation:
    parent: str
    children: tuple[str, ...]
    kind: str
    authority: str

    def __post_init__(self) -> None:
        if type(self.parent) is not str or self.parent not in _QUANTITY_PATHS:
            raise UsageEvidenceError("relation parent is invalid")
        if type(self.children) is not tuple or not self.children:
            raise UsageEvidenceError("relation children must be a non-empty tuple")
        for child in self.children:
            if type(child) is not str or child not in _QUANTITY_PATHS:
                raise UsageEvidenceError("relation child is invalid")
        if len(set(self.children)) != len(self.children) or self.parent in self.children:
            raise UsageEvidenceError("relation paths must be distinct")
        _enum_str(
            self.kind,
            {"disjoint_sum", "includes_subset", "unknown"},
            "relation kind",
        )
        if self.kind == "disjoint_sum" and len(self.children) < 2:
            raise UsageEvidenceError("disjoint_sum needs at least two children")
        _enum_str(
            self.authority,
            {"source_schema", "versioned_adapter", "otel_projection"},
            "relation authority",
        )

    def to_payload(self) -> dict[str, object]:
        return {
            "parent": self.parent,
            "children": list(self.children),
            "kind": self.kind,
            "authority": self.authority,
        }

    @classmethod
    def from_payload(cls, payload: object) -> Relation:
        data = _strict_keys(
            payload,
            {"parent", "children", "kind", "authority"},
            "relation",
        )
        return cls(
            parent=data["parent"],
            children=_string_tuple(data["children"], "relation children"),
            kind=data["kind"],
            authority=data["authority"],
        )


@dataclass(frozen=True)
class UsageRecord:
    record_id: str
    scope_node_id: str
    prompt_non_cached: TokenQuantity
    prompt_cache_read: TokenQuantity
    prompt_cache_write: TokenQuantity
    prompt_inclusive: TokenQuantity
    completion_visible: TokenQuantity
    completion_reasoning: TokenQuantity
    completion_inclusive: TokenQuantity
    total_inclusive: TokenQuantity
    relations: tuple[Relation, ...]

    def __post_init__(self) -> None:
        _nonempty_str(self.record_id, "record_id")
        _nonempty_str(self.scope_node_id, "scope_node_id")
        for quantity in self.quantities().values():
            if type(quantity) is not TokenQuantity:
                raise UsageEvidenceError("record quantities must be exact TokenQuantity objects")
        if type(self.relations) is not tuple:
            raise UsageEvidenceError("relations must be a tuple")
        seen: set[tuple[str, tuple[str, ...], str]] = set()
        quantities = self.quantities()
        for relation in self.relations:
            if type(relation) is not Relation:
                raise UsageEvidenceError("relations must contain exact Relation objects")
            identity = (relation.parent, relation.children, relation.kind)
            if identity in seen:
                raise UsageEvidenceError("duplicate relation")
            seen.add(identity)
            parent = quantities[relation.parent]
            children = [quantities[path] for path in relation.children]
            if relation.kind == "disjoint_sum":
                if parent.state == "derived":
                    if set(parent.operands) != set(relation.children):
                        raise UsageEvidenceError("disjoint_sum operands do not match relation")
                elif parent.state != "observed":
                    raise UsageEvidenceError("disjoint_sum parent must be known")
                if any(child.state == "unknown" for child in children):
                    raise UsageEvidenceError("disjoint_sum children must be known")
                if parent.value != sum(child.value for child in children):
                    raise UsageEvidenceError("disjoint_sum value mismatch")
                related = [parent, *children]
                bases = {quantity.basis for quantity in related}
                if len(bases) != 1 or "unknown" in bases:
                    raise UsageEvidenceError("disjoint_sum quantities have incompatible bases")
                if len({quantity.semantics_uri for quantity in related}) != 1:
                    raise UsageEvidenceError(
                        "disjoint_sum quantities have incompatible semantics"
                    )
            elif relation.kind == "includes_subset" and parent.state != "unknown":
                known = [parent, *(child for child in children if child.state != "unknown")]
                bases = {quantity.basis for quantity in known}
                if len(bases) != 1 or "unknown" in bases:
                    raise UsageEvidenceError("subset quantities have incompatible bases")
                if len({quantity.semantics_uri for quantity in known}) != 1:
                    raise UsageEvidenceError("subset quantities have incompatible semantics")
                for child in children:
                    if child.state != "unknown" and child.value > parent.value:
                        raise UsageEvidenceError("subset exceeds its parent")
        for path, quantity in quantities.items():
            if quantity.state != "derived":
                continue
            matches = [
                relation
                for relation in self.relations
                if relation.kind == "disjoint_sum"
                and relation.parent == path
                and set(relation.children) == set(quantity.operands)
            ]
            if len(matches) != 1:
                raise UsageEvidenceError("derived sum needs one matching disjoint_sum relation")

        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(path: str) -> None:
            if path in visiting:
                raise UsageEvidenceError("derived quantity operands contain a cycle")
            if path in visited or quantities[path].state != "derived":
                return
            visiting.add(path)
            for operand in quantities[path].operands:
                visit(operand)
            visiting.remove(path)
            visited.add(path)

        for path in quantities:
            visit(path)

    def quantities(self) -> dict[str, TokenQuantity]:
        return {
            "prompt.non_cached": self.prompt_non_cached,
            "prompt.cache_read": self.prompt_cache_read,
            "prompt.cache_write": self.prompt_cache_write,
            "prompt.inclusive": self.prompt_inclusive,
            "completion.visible": self.completion_visible,
            "completion.reasoning": self.completion_reasoning,
            "completion.inclusive": self.completion_inclusive,
            "total.inclusive": self.total_inclusive,
        }

    def to_payload(self) -> dict[str, object]:
        return {
            "record_id": self.record_id,
            "scope_node_id": self.scope_node_id,
            "prompt": {
                "non_cached": self.prompt_non_cached.to_payload(),
                "cache_read": self.prompt_cache_read.to_payload(),
                "cache_write": self.prompt_cache_write.to_payload(),
                "inclusive": self.prompt_inclusive.to_payload(),
            },
            "completion": {
                "visible": self.completion_visible.to_payload(),
                "reasoning": self.completion_reasoning.to_payload(),
                "inclusive": self.completion_inclusive.to_payload(),
            },
            "total": {"inclusive": self.total_inclusive.to_payload()},
            "relations": [relation.to_payload() for relation in self.relations],
        }

    @classmethod
    def from_payload(cls, payload: object) -> UsageRecord:
        data = _strict_keys(
            payload,
            {"record_id", "scope_node_id", "prompt", "completion", "total", "relations"},
            "usage record",
        )
        prompt = _strict_keys(
            data["prompt"],
            {"non_cached", "cache_read", "cache_write", "inclusive"},
            "prompt quantities",
        )
        completion = _strict_keys(
            data["completion"],
            {"visible", "reasoning", "inclusive"},
            "completion quantities",
        )
        total = _strict_keys(data["total"], {"inclusive"}, "total quantities")
        if type(data["relations"]) is not list:
            raise UsageEvidenceError("relations must be an array")
        return cls(
            record_id=data["record_id"],
            scope_node_id=data["scope_node_id"],
            prompt_non_cached=TokenQuantity.from_payload(prompt["non_cached"]),
            prompt_cache_read=TokenQuantity.from_payload(prompt["cache_read"]),
            prompt_cache_write=TokenQuantity.from_payload(prompt["cache_write"]),
            prompt_inclusive=TokenQuantity.from_payload(prompt["inclusive"]),
            completion_visible=TokenQuantity.from_payload(completion["visible"]),
            completion_reasoning=TokenQuantity.from_payload(completion["reasoning"]),
            completion_inclusive=TokenQuantity.from_payload(completion["inclusive"]),
            total_inclusive=TokenQuantity.from_payload(total["inclusive"]),
            relations=tuple(Relation.from_payload(item) for item in data["relations"]),
        )


@dataclass(frozen=True)
class InvocationNode:
    node_id: str
    parent_node_id: str | None
    node_kind: str
    attribution: str
    coverage: str
    known_exclusions: tuple[str, ...]
    child_node_ids: tuple[str, ...]
    terminal_observed: bool
    outcome: str

    def __post_init__(self) -> None:
        _nonempty_str(self.node_id, "node_id")
        _optional_str(self.parent_node_id, "parent_node_id")
        _enum_str(
            self.node_kind,
            {"cli_invocation", "model_call", "model_aggregate", "helper_call"},
            "node_kind",
        )
        _enum_str(
            self.attribution,
            {
                "per_call",
                "per_step",
                "per_model_aggregate",
                "invocation_aggregate",
                "unknown",
            },
            "attribution",
        )
        _enum_str(self.coverage, {"complete", "partial", "unknown"}, "coverage")
        if type(self.known_exclusions) is not tuple:
            raise UsageEvidenceError("known_exclusions must be a tuple")
        for exclusion in self.known_exclusions:
            _nonempty_str(exclusion, "known exclusion")
        if len(set(self.known_exclusions)) != len(self.known_exclusions):
            raise UsageEvidenceError("known_exclusions must not contain duplicates")
        if type(self.child_node_ids) is not tuple:
            raise UsageEvidenceError("child_node_ids must be a tuple")
        for child_id in self.child_node_ids:
            _nonempty_str(child_id, "child node id")
        if len(set(self.child_node_ids)) != len(self.child_node_ids):
            raise UsageEvidenceError("child_node_ids must not contain duplicates")
        _exact_bool(self.terminal_observed, "terminal_observed")
        _enum_str(
            self.outcome,
            {"succeeded", "failed", "cancelled", "timed_out", "unknown"},
            "outcome",
        )
        if self.coverage == "complete" and (
            self.known_exclusions or not self.terminal_observed
        ):
            raise UsageEvidenceError("complete coverage cannot have exclusions or an open terminal")

    def to_payload(self) -> dict[str, object]:
        return {
            "node_id": self.node_id,
            "parent_node_id": self.parent_node_id,
            "node_kind": self.node_kind,
            "attribution": self.attribution,
            "coverage": self.coverage,
            "known_exclusions": list(self.known_exclusions),
            "child_node_ids": list(self.child_node_ids),
            "terminal_observed": self.terminal_observed,
            "outcome": self.outcome,
        }

    @classmethod
    def from_payload(cls, payload: object) -> InvocationNode:
        data = _strict_keys(
            payload,
            {
                "node_id",
                "parent_node_id",
                "node_kind",
                "attribution",
                "coverage",
                "known_exclusions",
                "child_node_ids",
                "terminal_observed",
                "outcome",
            },
            "invocation node",
        )
        return cls(
            node_id=data["node_id"],
            parent_node_id=data["parent_node_id"],
            node_kind=data["node_kind"],
            attribution=data["attribution"],
            coverage=data["coverage"],
            known_exclusions=_string_tuple(data["known_exclusions"], "known_exclusions"),
            child_node_ids=_string_tuple(data["child_node_ids"], "child_node_ids"),
            terminal_observed=data["terminal_observed"],
            outcome=data["outcome"],
        )


@dataclass(frozen=True)
class Provenance:
    source: str
    cli_version: str
    binary_sha256: str
    source_schema_uri: str
    source_schema_version: str
    source_schema_sha256: str | None
    parser_name: str
    parser_version: str
    parser_sha256: str
    command_shape_sha256: str

    def __post_init__(self) -> None:
        for name in (
            "source",
            "cli_version",
            "source_schema_uri",
            "source_schema_version",
            "parser_name",
            "parser_version",
        ):
            _nonempty_str(getattr(self, name), name)
        for name in ("binary_sha256", "parser_sha256", "command_shape_sha256"):
            _validate_hash(getattr(self, name), name)
        if self.source_schema_sha256 is not None:
            _validate_hash(self.source_schema_sha256, "source_schema_sha256")

    def to_payload(self) -> dict[str, object]:
        return {
            "source": self.source,
            "cli_version": self.cli_version,
            "binary_sha256": self.binary_sha256,
            "source_schema_uri": self.source_schema_uri,
            "source_schema_version": self.source_schema_version,
            "source_schema_sha256": self.source_schema_sha256,
            "parser_name": self.parser_name,
            "parser_version": self.parser_version,
            "parser_sha256": self.parser_sha256,
            "command_shape_sha256": self.command_shape_sha256,
        }

    @classmethod
    def from_payload(cls, payload: object) -> Provenance:
        data = _strict_keys(
            payload,
            {
                "source",
                "cli_version",
                "binary_sha256",
                "source_schema_uri",
                "source_schema_version",
                "source_schema_sha256",
                "parser_name",
                "parser_version",
                "parser_sha256",
                "command_shape_sha256",
            },
            "provenance",
        )
        return cls(**data)


@dataclass(frozen=True)
class RawEvidence:
    raw_id: str
    media_type: str
    encoding: str
    bytes_base64: str
    byte_length: int
    sha256: str
    stream_ordinal: int
    captured_complete: bool

    def __post_init__(self) -> None:
        _nonempty_str(self.raw_id, "raw_id")
        _nonempty_str(self.media_type, "media_type")
        _enum_str(self.encoding, {"base64"}, "raw encoding")
        if type(self.bytes_base64) is not str:
            raise UsageEvidenceError("bytes_base64 must be a built-in string")
        _nonnegative_int(self.byte_length, "byte_length")
        _validate_hash(self.sha256, "raw sha256")
        _nonnegative_int(self.stream_ordinal, "stream_ordinal")
        _exact_bool(self.captured_complete, "captured_complete")
        try:
            decoded = base64.b64decode(self.bytes_base64, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise UsageEvidenceError("raw evidence is not valid base64") from exc
        if base64.b64encode(decoded).decode("ascii") != self.bytes_base64:
            raise UsageEvidenceError("raw evidence base64 is not canonical")
        if len(decoded) != self.byte_length:
            raise UsageEvidenceError("raw evidence length mismatch")
        if hashlib.sha256(decoded).hexdigest() != self.sha256:
            raise UsageEvidenceError("raw evidence hash mismatch")

    @classmethod
    def from_bytes(
        cls,
        raw_id: str,
        data: bytes,
        media_type: str,
        stream_ordinal: int,
        captured_complete: bool,
    ) -> RawEvidence:
        if type(data) is not bytes:
            raise UsageEvidenceError("raw evidence data must be built-in bytes")
        return cls(
            raw_id=raw_id,
            media_type=media_type,
            encoding="base64",
            bytes_base64=base64.b64encode(data).decode("ascii"),
            byte_length=len(data),
            sha256=hashlib.sha256(data).hexdigest(),
            stream_ordinal=stream_ordinal,
            captured_complete=captured_complete,
        )

    def decode(self) -> bytes:
        return base64.b64decode(self.bytes_base64, validate=True)

    def to_payload(self) -> dict[str, object]:
        return {
            "raw_id": self.raw_id,
            "media_type": self.media_type,
            "encoding": self.encoding,
            "bytes_base64": self.bytes_base64,
            "byte_length": self.byte_length,
            "sha256": self.sha256,
            "stream_ordinal": self.stream_ordinal,
            "captured_complete": self.captured_complete,
        }

    @classmethod
    def from_payload(cls, payload: object) -> RawEvidence:
        data = _strict_keys(
            payload,
            {
                "raw_id",
                "media_type",
                "encoding",
                "bytes_base64",
                "byte_length",
                "sha256",
                "stream_ordinal",
                "captured_complete",
            },
            "raw evidence",
        )
        return cls(**data)


@dataclass(frozen=True)
class Extension:
    namespace: str
    canonical_json: str

    def __post_init__(self) -> None:
        if type(self.namespace) is not str or not _NAMESPACE_RE.fullmatch(self.namespace):
            raise UsageEvidenceError("extension namespace is invalid")
        _nonempty_str(self.canonical_json, "extension canonical_json")
        try:
            value = json.loads(self.canonical_json, object_pairs_hook=_reject_duplicate_pairs)
        except (json.JSONDecodeError, UsageEvidenceError) as exc:
            raise UsageEvidenceError("extension JSON is invalid") from exc
        if _canonical_json(value) != self.canonical_json:
            raise UsageEvidenceError("extension JSON is not canonical")

    @classmethod
    def from_value(cls, namespace: str, value: object) -> Extension:
        _validate_json_value(value)
        return cls(namespace, _canonical_json(value))

    def value(self) -> object:
        return json.loads(self.canonical_json, object_pairs_hook=_reject_duplicate_pairs)


@dataclass(frozen=True)
class UsageEvidenceEnvelope:
    envelope_id: str
    invocation_id: str
    provenance: Provenance
    nodes: tuple[InvocationNode, ...]
    records: tuple[UsageRecord, ...]
    raw_evidence: tuple[RawEvidence, ...]
    extensions: tuple[Extension, ...]

    def __post_init__(self) -> None:
        _nonempty_str(self.envelope_id, "envelope_id")
        _nonempty_str(self.invocation_id, "invocation_id")
        if type(self.provenance) is not Provenance:
            raise UsageEvidenceError("provenance must be exact Provenance")
        for name in ("nodes", "records", "raw_evidence", "extensions"):
            if type(getattr(self, name)) is not tuple:
                raise UsageEvidenceError(f"{name} must be a tuple")
        self._validate_tree()

        node_ids = {node.node_id for node in self.nodes}
        record_ids: set[str] = set()
        raw_ids: set[str] = set()
        ordinals: set[int] = set()
        for raw in self.raw_evidence:
            if type(raw) is not RawEvidence:
                raise UsageEvidenceError("raw_evidence must contain exact RawEvidence")
            if raw.raw_id in raw_ids or raw.stream_ordinal in ordinals:
                raise UsageEvidenceError("raw evidence id/ordinal collision")
            raw_ids.add(raw.raw_id)
            ordinals.add(raw.stream_ordinal)
        for record in self.records:
            if type(record) is not UsageRecord:
                raise UsageEvidenceError("records must contain exact UsageRecord")
            if record.record_id in record_ids:
                raise UsageEvidenceError("record id collision")
            if record.scope_node_id not in node_ids:
                raise UsageEvidenceError("record references an unknown scope node")
            record_ids.add(record.record_id)
            for quantity in record.quantities().values():
                if any(ref not in raw_ids for ref in quantity.evidence_refs):
                    raise UsageEvidenceError("quantity references unknown raw evidence")
        namespaces: set[str] = set()
        for extension in self.extensions:
            if type(extension) is not Extension:
                raise UsageEvidenceError("extensions must contain exact Extension")
            if extension.namespace in namespaces:
                raise UsageEvidenceError("extension namespace collision")
            namespaces.add(extension.namespace)

    def _validate_tree(self) -> None:
        if not self.nodes:
            raise UsageEvidenceError("invocation tree must not be empty")
        by_id: dict[str, InvocationNode] = {}
        roots: list[InvocationNode] = []
        for node in self.nodes:
            if type(node) is not InvocationNode:
                raise UsageEvidenceError("nodes must contain exact InvocationNode")
            if node.node_id in by_id:
                raise UsageEvidenceError("node id collision")
            by_id[node.node_id] = node
            if node.parent_node_id is None:
                roots.append(node)
        if len(roots) != 1 or roots[0].node_id != self.invocation_id:
            raise UsageEvidenceError("tree needs one matching invocation root")
        if roots[0].node_kind != "cli_invocation":
            raise UsageEvidenceError("tree root must be a cli_invocation")
        for node in self.nodes:
            if node.parent_node_id is not None:
                parent = by_id.get(node.parent_node_id)
                if parent is None or node.node_id not in parent.child_node_ids:
                    raise UsageEvidenceError("tree parent/child link is inconsistent")
            for child_id in node.child_node_ids:
                child = by_id.get(child_id)
                if child is None or child.parent_node_id != node.node_id:
                    raise UsageEvidenceError("tree parent/child link is inconsistent")
        visited: set[str] = set()
        active: set[str] = set()

        def visit(node_id: str) -> None:
            if node_id in active:
                raise UsageEvidenceError("invocation tree contains a cycle")
            if node_id in visited:
                return
            active.add(node_id)
            for child_id in by_id[node_id].child_node_ids:
                visit(child_id)
            active.remove(node_id)
            visited.add(node_id)

        visit(self.invocation_id)
        if visited != set(by_id):
            raise UsageEvidenceError("invocation tree contains unreachable nodes")

    def body_payload(self) -> dict[str, object]:
        return {
            "schema": SCHEMA_VERSION,
            "envelope_id": self.envelope_id,
            "invocation_id": self.invocation_id,
            "provenance": self.provenance.to_payload(),
            "nodes": [node.to_payload() for node in self.nodes],
            "records": [record.to_payload() for record in self.records],
            "raw_evidence": [raw.to_payload() for raw in self.raw_evidence],
            "extensions": {
                extension.namespace: extension.value()
                for extension in sorted(self.extensions, key=lambda item: item.namespace)
            },
        }

    @property
    def envelope_sha256(self) -> str:
        return hashlib.sha256(_canonical_json(self.body_payload()).encode("utf-8")).hexdigest()

    def to_payload(self) -> dict[str, object]:
        payload = self.body_payload()
        payload["integrity"] = {"envelope_sha256": self.envelope_sha256}
        return payload

    def to_json(self) -> str:
        return _canonical_json(self.to_payload())

    @classmethod
    def from_json(cls, text: str) -> UsageEvidenceEnvelope:
        if type(text) is not str:
            raise UsageEvidenceError("envelope JSON must be a built-in string")
        try:
            payload = json.loads(text, object_pairs_hook=_reject_duplicate_pairs)
        except (json.JSONDecodeError, UsageEvidenceError) as exc:
            raise UsageEvidenceError("envelope JSON is invalid") from exc
        return cls.from_payload(payload)

    @classmethod
    def from_payload(cls, payload: object) -> UsageEvidenceEnvelope:
        data = _strict_keys(
            payload,
            {
                "schema",
                "envelope_id",
                "invocation_id",
                "provenance",
                "nodes",
                "records",
                "raw_evidence",
                "extensions",
                "integrity",
            },
            "usage evidence envelope",
        )
        _enum_str(data["schema"], {SCHEMA_VERSION}, "schema")
        for name in ("nodes", "records", "raw_evidence"):
            if type(data[name]) is not list:
                raise UsageEvidenceError(f"{name} must be an array")
        extension_payload = data["extensions"]
        if type(extension_payload) is not dict:
            raise UsageEvidenceError("extensions must be an object")
        for namespace in extension_payload:
            if type(namespace) is not str or not _NAMESPACE_RE.fullmatch(namespace):
                raise UsageEvidenceError("extension namespace is invalid")
        extensions = tuple(
            Extension.from_value(namespace, value)
            for namespace, value in sorted(extension_payload.items())
        )
        envelope = cls(
            envelope_id=data["envelope_id"],
            invocation_id=data["invocation_id"],
            provenance=Provenance.from_payload(data["provenance"]),
            nodes=tuple(InvocationNode.from_payload(item) for item in data["nodes"]),
            records=tuple(UsageRecord.from_payload(item) for item in data["records"]),
            raw_evidence=tuple(RawEvidence.from_payload(item) for item in data["raw_evidence"]),
            extensions=extensions,
        )
        integrity = _strict_keys(data["integrity"], {"envelope_sha256"}, "integrity")
        expected = _validate_hash(integrity["envelope_sha256"], "envelope_sha256")
        if envelope.envelope_sha256 != expected:
            raise UsageEvidenceError("envelope hash mismatch")
        return envelope


def project_exact_token_usage(envelope: UsageEvidenceEnvelope) -> TokenUsage | None:
    """Project only a complete provider-authority invocation aggregate."""
    if type(envelope) is not UsageEvidenceEnvelope:
        return None
    nodes = {node.node_id: node for node in envelope.nodes}
    root = nodes.get(envelope.invocation_id)
    if (
        root is None
        or root.outcome != "succeeded"
        or envelope.provenance.source_schema_sha256 is None
        or any(
            node.coverage != "complete"
            or not node.terminal_observed
            or bool(node.known_exclusions)
            for node in envelope.nodes
        )
    ):
        return None
    candidates = [
        record
        for record in envelope.records
        if record.scope_node_id == root.node_id
        and root.attribution == "invocation_aggregate"
    ]
    if len(candidates) != 1:
        return None
    record = candidates[0]
    required = (
        record.prompt_inclusive,
        record.completion_inclusive,
        record.total_inclusive,
    )
    if any(
        quantity.state != "observed" or quantity.authority != "provider"
        for quantity in required
    ):
        return None
    bases = {quantity.basis for quantity in required}
    if len(bases) != 1 or "unknown" in bases:
        return None
    semantics_uris = {quantity.semantics_uri for quantity in required}
    if len(semantics_uris) != 1:
        return None
    total_relations = [
        relation
        for relation in record.relations
        if relation.parent == "total.inclusive"
        and set(relation.children)
        == {"prompt.inclusive", "completion.inclusive"}
        and relation.kind == "disjoint_sum"
        and relation.authority in {"source_schema", "versioned_adapter"}
    ]
    if len(total_relations) != 1:
        return None
    if any(not raw.captured_complete for raw in envelope.raw_evidence):
        return None
    if record.total_inclusive.value != (
        record.prompt_inclusive.value + record.completion_inclusive.value
    ):
        return None
    return TokenUsage(
        input_tokens=record.prompt_inclusive.value,
        output_tokens=record.completion_inclusive.value,
        total_tokens=record.total_inclusive.value,
        source="provider",
    )
