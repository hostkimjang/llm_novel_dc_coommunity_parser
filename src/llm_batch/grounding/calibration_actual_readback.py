"""Bounded, independent readback primitives for P3 FROZEN_ACTUAL evidence.

This module deliberately has no pipeline/provider dependencies.  It snapshots
small, explicitly scoped JSON/JSONL artifacts and fails closed on any ambiguity.
"""
from __future__ import annotations

import hashlib
import json
import math
import random
import statistics
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

SCHEMA_VERSION = "calibration-actual-readback-v2"
PROBABILITY_SCALE = 1_000_000


def canonical_bytes(value: Any) -> bytes:
    _validate_json(value)
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")

def _validate_json(value: Any) -> None:
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("non-finite JSON value")
    if isinstance(value, Mapping):
        keys = [k for k in value]
        if any(not isinstance(k, str) for k in keys) or len(keys) != len(set(keys)):
            raise ValueError("JSON mapping keys must be unique strings")
        for k, v in value.items():
            _validate_json(k); _validate_json(v)
    elif isinstance(value, (list, tuple)):
        for item in value: _validate_json(item)


def _reject_duplicate_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise ValueError(f"duplicate JSON key: {key}")
        value[key] = item
    return value


def _loads_strict(text: str) -> Any:
    return json.loads(text, object_pairs_hook=_reject_duplicate_pairs)


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()

def _sha(value: Any, name: str) -> str:
    if not isinstance(value, str) or len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
        raise ValueError(f"{name} must be lowercase sha256")
    return value


def hash_sequence(values: Iterable[str]) -> str:
    return sha256_bytes(canonical_bytes(list(values)))


def hash_set(values: Iterable[str]) -> str:
    return hash_sequence(sorted(set(values)))


def _stat(path: Path) -> tuple[int, int, int]:
    s = path.stat()
    return (int(s.st_size), int(s.st_mtime_ns), int(getattr(s, "st_ino", 0)))


def _read_stable(path: Path) -> tuple[bytes, tuple[int, int, int]]:
    before = _stat(path)
    first = path.read_bytes()
    middle = _stat(path)
    second = path.read_bytes()
    after = _stat(path)
    if before != middle or middle != after or first != second:
        raise ValueError(f"artifact changed during read: {path}")
    return first, after


@dataclass(frozen=True)
class ArtifactRef:
    logical_name: str
    relative_path: str
    bytes: int
    sha256: str
    canonical_payload_sha256: str
    row_count: int | None

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


def _artifact_path(root: str | Path, relative_path: str) -> tuple[Path, Path]:
    base = Path(root).resolve()
    path = (base / relative_path).resolve()
    if path != base and base not in path.parents:
        raise ValueError("artifact path escapes supplied root")
    if not path.is_file():
        raise ValueError(f"artifact is not a regular file: {relative_path}")
    return base, path


def _parse_jsonl_rows(raw: bytes) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for lineno, line in enumerate(raw.splitlines(), 1):
        if not line.strip():
            raise ValueError(f"blank JSONL line: {lineno}")
        try:
            row = _loads_strict(line.decode("utf-8-sig" if lineno == 1 else "utf-8"))
        except Exception as exc:
            raise ValueError(f"invalid JSONL at line {lineno}: {exc}") from exc
        if not isinstance(row, dict):
            raise ValueError(f"JSONL row must be an object: {lineno}")
        _validate_json(row)
        rows.append(row)
    return rows


def snapshot_jsonl_rows(
    root: str | Path,
    logical_name: str,
    relative_path: str,
) -> tuple[ArtifactRef, list[dict[str, Any]]]:
    """Read one JSONL artifact stably and return the ref and exact parsed rows."""

    base, path = _artifact_path(root, relative_path)
    raw, _ = _read_stable(path)
    rows = _parse_jsonl_rows(raw)
    ref = ArtifactRef(
        logical_name,
        path.relative_to(base).as_posix(),
        len(raw),
        sha256_bytes(raw),
        sha256_bytes(b"\n".join(canonical_bytes(row) for row in rows)),
        len(rows),
    )
    return ref, rows


def snapshot_json_object(
    root: str | Path,
    logical_name: str,
    relative_path: str,
) -> tuple[ArtifactRef, dict[str, Any]]:
    """Read one JSON object stably with duplicate-key/non-finite rejection."""

    base, path = _artifact_path(root, relative_path)
    raw, _ = _read_stable(path)
    try:
        value = _loads_strict(raw.decode("utf-8-sig"))
    except Exception as exc:
        raise ValueError(f"invalid JSON artifact: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError("JSON artifact must be an object")
    _validate_json(value)
    ref = ArtifactRef(
        logical_name,
        path.relative_to(base).as_posix(),
        len(raw),
        sha256_bytes(raw),
        sha256_bytes(canonical_bytes(value)),
        None,
    )
    return ref, value


def snapshot_artifact(root: str | Path, logical_name: str, relative_path: str, *, jsonl: bool = False) -> ArtifactRef:
    if jsonl:
        return snapshot_jsonl_rows(root, logical_name, relative_path)[0]
    base, path = _artifact_path(root, relative_path)
    raw, _ = _read_stable(path)
    row_count: int | None = None
    canonical_hash: str
    try:
        value = _loads_strict(raw.decode("utf-8-sig"))
    except Exception as exc:
        raise ValueError(f"invalid JSON artifact: {exc}") from exc
    canonical_hash = sha256_bytes(canonical_bytes(value))
    if isinstance(value, list):
        row_count = len(value)
    return ArtifactRef(logical_name, path.relative_to(base).as_posix(), len(raw), sha256_bytes(raw), canonical_hash, row_count)


def validate_artifact_snapshots(root: str | Path, manifest: Mapping[str, Any]) -> dict[str, ArtifactRef]:
    """Re-read every declared artifact and compare current bytes to the manifest."""
    validate_readback_manifest(manifest)
    refs: dict[str, ArtifactRef] = {}
    for name, stored in manifest["artifacts"].items():
        suffix = Path(stored["relative_path"]).suffix.lower()
        if suffix not in {".json", ".jsonl"}:
            raise ValueError(f"ambiguous artifact format: {stored['relative_path']}")
        current = snapshot_artifact(root, name, stored["relative_path"], jsonl=suffix == ".jsonl")
        if current.to_dict() != dict(stored):
            raise ValueError(f"artifact snapshot mismatch: {name}")
        refs[name] = current
    return refs


def read_bound_jsonl_rows(root: str | Path, manifest: Mapping[str, Any], logical_name: str) -> list[dict[str, Any]]:
    validate_artifact_snapshots(root, manifest)
    stored = manifest["artifacts"].get(logical_name)
    if not isinstance(stored, Mapping) or Path(stored["relative_path"]).suffix.lower() != ".jsonl":
        raise ValueError(f"{logical_name} must be a bound JSONL artifact")
    current, rows = snapshot_jsonl_rows(root, logical_name, stored["relative_path"])
    if current.to_dict() != dict(stored):
        raise ValueError(f"artifact snapshot mismatch after validation: {logical_name}")
    return rows


def _ids(rows: Sequence[Mapping[str, Any]]) -> tuple[list[str], list[str]]:
    try:
        examples = [row["example_id"] for row in rows]
        posts = [row["post_id"] for row in rows]
    except KeyError as exc:
        raise ValueError(f"missing identity field: {exc}") from exc
    examples = [x.strip() if isinstance(x, str) else x for x in examples]; posts = [x.strip() if isinstance(x, str) else x for x in posts]
    if any(isinstance(x, (bool, type(None))) or not isinstance(x, str) or not x for x in examples + posts) or len(set(examples)) != len(examples) or len(set(posts)) != len(posts):
        raise ValueError("duplicate or empty identity")
    return examples, posts


def expected_universe_readback(
    expected_rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Bind the pre-registered expected universe independently of producer output."""

    if not expected_rows:
        raise ValueError("expected universe must not be empty")
    examples, posts = _ids(expected_rows)
    records = [
        {
            "example_id": row["example_id"],
            "post_id": row["post_id"],
            "row_payload_sha256": sha256_bytes(canonical_bytes(dict(row))),
        }
        for row in expected_rows
    ]
    return {
        "row_count": len(records),
        "ordered_example_id_sha256": hash_sequence(examples),
        "ordered_post_id_sha256": hash_sequence(posts),
        "set_example_id_sha256": hash_set(examples),
        "set_post_id_sha256": hash_set(posts),
        "per_row": records,
        "payload_sha256": sha256_bytes(canonical_bytes(records)),
    }


def _coverage(expected: Sequence[Mapping[str, Any]], observed: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    ee, ep = _ids(expected)
    oe, op = _ids(observed)
    if ee != oe or ep != op:
        raise ValueError("producer coverage order/set mismatch")
    bad = {"UNKNOWN", "TRUNCATED"}
    statuses = [str(r.get("generation_status", "")) for r in observed]
    if any(s != "COMPLETE" for s in statuses):
        raise ValueError("producer coverage contains non-COMPLETE row")
    per_row = []
    for row in observed:
        for key in ("candidate_set_fingerprint", "generation_proof_fingerprint", "source_digest_sha256"):
            _sha(row.get(key), key)
        per_row.append({k: row[k] for k in ("example_id", "post_id", "candidate_set_fingerprint", "generation_proof_fingerprint", "source_digest_sha256")})
    return {"expected_ids_sha256": hash_sequence(ee), "row_count": len(observed), "complete_count": len(observed), "unknown_count": 0, "truncated_count": 0, "missing_count": 0, "extra_count": 0, "duplicate_count": 0, "per_row": per_row, "coverage_sha256": sha256_bytes(canonical_bytes(per_row))}


def producer_coverage_receipt(expected_rows: Sequence[Mapping[str, Any]], observed_rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    return _coverage(expected_rows, observed_rows)


def prediction_payload_readback(expected_rows: Sequence[Mapping[str, Any]], prediction_rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    ee, ep = _ids(expected_rows)
    pe, pp = _ids(prediction_rows)
    if (ee, ep) != (pe, pp):
        raise ValueError("prediction payload order/set mismatch")
    records = []
    for row in prediction_rows:
        probs = row.get("probabilities")
        if not isinstance(probs, Mapping) or not probs or any(isinstance(v, bool) or not isinstance(v, int) or v < 0 for v in probs.values()) or sum(probs.values()) != PROBABILITY_SCALE:
            raise ValueError("prediction probability mass is not exactly 1,000,000")
        for key in ("shadow_fingerprint", "score_vector_sha256", "candidate_set_fingerprint", "generation_proof_fingerprint", "source_digest_sha256"):
            _sha(row.get(key), key)
        records.append({"example_id": row["example_id"], "post_id": row["post_id"], "payload_sha256": sha256_bytes(canonical_bytes(row)), "shadow_fingerprint": row["shadow_fingerprint"], "score_vector_sha256": row["score_vector_sha256"], "candidate_set_fingerprint": row["candidate_set_fingerprint"], "generation_proof_fingerprint": row["generation_proof_fingerprint"], "source_digest_sha256": row["source_digest_sha256"]})
    return {"row_count": len(records), "ordered_example_id_sha256": hash_sequence(ee), "ordered_post_id_sha256": hash_sequence(ep), "set_example_id_sha256": hash_set(ee), "set_post_id_sha256": hash_set(ep), "per_row": records, "payload_sha256": sha256_bytes(canonical_bytes(records))}


def _finite(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("metric must be numeric")
    value = float(value)
    if not math.isfinite(value):
        raise ValueError("non-finite metric")
    return value


def cluster_bootstrap(rows: Sequence[Mapping[str, Any]], *, seed: int, replicates: int = 2000, alpha: float = 0.05, baseline_rows: Sequence[Mapping[str, Any]] | None = None, min_group_count: int = 2, ece_bin_edges: Sequence[float] = (0.0, 0.5, 1.0), top_label_accuracy_denominator: str = "ALL_FROZEN_ROWS") -> dict[str, Any]:
    if isinstance(seed, bool) or not isinstance(seed, int) or isinstance(replicates, bool) or not isinstance(replicates, int) or isinstance(min_group_count, bool) or not isinstance(min_group_count, int) or not isinstance(alpha, (int, float)) or isinstance(alpha, bool) or not math.isfinite(float(alpha)):
        raise ValueError("seed/replicates/min_group_count/alpha types invalid")
    edges = tuple(ece_bin_edges)
    if len(edges) < 2 or any(isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(float(x)) for x in edges) or any(float(a) >= float(b) for a, b in zip(edges, edges[1:])) or float(edges[0]) != 0.0 or float(edges[-1]) != 1.0:
        raise ValueError("ece_bin_edges must be strictly increasing finite numeric edges")
    if top_label_accuracy_denominator not in {"ALL_FROZEN_ROWS", "NON_ABSTAIN_ROWS"}:
        raise ValueError("unsupported top_label_accuracy_denominator")
    if not rows or min_group_count <= 0:
        return {"estimable": False, "reason": "EMPTY_ROWS_OR_INVALID_GROUP_LIMIT", "intervals": {}}
    def validate_metric_rows(values: Sequence[Mapping[str, Any]], label: str) -> None:
        ids = [r.get("example_id") for r in values]
        if (
            not values
            or any(not isinstance(x, str) or not x.strip() or x != x.strip() for x in ids)
            or len(set(ids)) != len(ids)
        ):
            raise ValueError(f"duplicate or invalid {label} example_id")
        for row in values:
            group = row.get("group")
            if (
                not isinstance(group, str)
                or not group.strip()
                or group != group.strip()
                or not isinstance(row.get("correct"), bool)
                or not isinstance(row.get("abstain"), bool)
            ):
                raise ValueError(f"invalid required {label} row shape")
            confidence = _finite(row.get("confidence"))
            risk_score = _finite(row.get("risk_score"))
            brier = _finite(row.get("brier"))
            log_loss = _finite(row.get("log_loss"))
            if not (0.0 <= confidence <= 1.0 and 0.0 <= risk_score <= 1.0):
                raise ValueError(f"{label} probability-like metric out of bounds")
            if brier < 0.0 or log_loss < 0.0:
                raise ValueError(f"{label} loss metric out of bounds")

    validate_metric_rows(rows, "actual")
    groups: dict[str, list[Mapping[str, Any]]] = {}
    for row in rows:
        group = str(row.get("group", ""))
        if not group:
            raise ValueError("missing bootstrap group")
        groups.setdefault(group, []).append(row)
    if len(groups) < min_group_count or replicates < 100 or not 0 < alpha < 1:
        return {"estimable": False, "reason": "INSUFFICIENT_GROUPS_OR_REPLICATES", "intervals": {}}
    if baseline_rows is not None:
        validate_metric_rows(baseline_rows, "baseline")
        by_id = {str(r.get("example_id")): r for r in baseline_rows}
        if len(by_id) != len(baseline_rows) or set(by_id) != {str(r.get("example_id")) for r in rows} or any(str(b.get("group")) != str(r.get("group")) for r in rows for b in [by_id.get(str(r.get("example_id")), {})]):
            return {"estimable": False, "reason": "BASELINE_ROW_MISMATCH", "intervals": {}}
        if sum(not bool(r["abstain"]) for r in baseline_rows) != sum(not bool(r["abstain"]) for r in rows):
            return {"estimable": False, "reason": "BASELINE_COVERAGE_MISMATCH", "intervals": {}}
    rng = random.Random(seed)
    keys = sorted(groups)
    samples: dict[str, list[float]] = {k: [] for k in ("top_label_accuracy", "brier", "log_loss", "ece", "selective_risk", "aurc")}
    delta_values: dict[str, list[float]] = {k: [] for k in ("top_label_accuracy", "brier", "log_loss", "ece", "selective_risk", "aurc")}
    def calc(sample: list[Mapping[str, Any]]) -> dict[str, float]:
        n = len(sample)
        if any(not isinstance(r.get("correct"), bool) or not isinstance(r.get("abstain", False), bool) for r in sample): raise ValueError("correct/abstain must be bool")
        if any(not isinstance(r.get("example_id"), str) or not r.get("example_id") or not isinstance(r.get("group"), str) or not r.get("group") for r in sample): raise ValueError("invalid row identity")
        if any(_finite(r["confidence"]) < 0 or _finite(r["confidence"]) > 1 or _finite(r["risk_score"]) < 0 or _finite(r["risk_score"]) > 1 or _finite(r["brier"]) < 0 or _finite(r["log_loss"]) < 0 for r in sample): raise ValueError("metric out of bounds")
        accuracy_rows = (
            sample
            if top_label_accuracy_denominator == "ALL_FROZEN_ROWS"
            else [r for r in sample if not bool(r["abstain"])]
        )
        acc = (
            sum(bool(r["correct"]) for r in accuracy_rows) / len(accuracy_rows)
            if accuracy_rows
            else float("nan")
        )
        brier = sum(_finite(r["brier"]) for r in sample) / n
        loss = sum(_finite(r["log_loss"]) for r in sample) / n
        bins = tuple(float(x) for x in ece_bin_edges); ece = 0.0
        for left, right in zip(bins, bins[1:]):
            members = [r for r in sample if left <= _finite(r["confidence"]) < right or (_finite(r["confidence"]) == 1 and right == 1)]
            if members: ece += len(members) / n * abs(sum(_finite(r["confidence"]) for r in members) / len(members) - sum(bool(r["correct"]) for r in members) / len(members))
        covered = [r for r in sample if not bool(r.get("abstain", False))]
        risk = sum(not bool(r["correct"]) for r in covered) / len(covered) if covered else float("nan")
        ranked = sorted(sample, key=lambda r: (_finite(r.get("risk_score", 0.0)), str(r.get("example_id"))))
        errors = 0; curve = []
        for i, r in enumerate(ranked, 1):
            errors += int(not bool(r["correct"])); curve.append(errors / i)
        return {"top_label_accuracy": acc, "brier": brier, "log_loss": loss, "ece": ece, "selective_risk": risk, "aurc": sum(curve) / n}
    for _ in range(replicates):
        sample = [row for key in rng.choices(keys, k=len(keys)) for row in groups[key]]
        values = calc(sample)
        for key, value in values.items():
            if math.isfinite(value): samples[key].append(value)
        if baseline_rows is not None:
            bmap = {str(r["example_id"]): r for r in baseline_rows}
            before = calc([bmap[str(r["example_id"])] for r in sample])
            for key in delta_values:
                if math.isfinite(values[key]) and math.isfinite(before[key]): delta_values[key].append(values[key] - before[key])
    qlo, qhi = alpha / 2, 1 - alpha / 2
    def interval(values: list[float], point_value: float) -> dict[str, Any]:
        if len(values) < replicates or not values:
            return {"value": None, "bootstrap_mean": None, "lower": None, "upper": None, "estimable": False}
        values.sort(); return {"value": point_value, "bootstrap_mean": statistics.fmean(values), "lower": values[int(qlo * (len(values)-1))], "upper": values[int(qhi * (len(values)-1))], "estimable": True}
    point = calc(list(rows))
    intervals = {k: interval(v, point[k]) for k, v in samples.items()}
    all_estimable = all(item["estimable"] for item in intervals.values()) and math.isfinite(point["selective_risk"])
    result = {"estimable": all_estimable, "seed": seed, "replicates": replicates, "group_count": len(groups), "alpha": alpha, "ece_bin_edges": list(edges), "top_label_accuracy_denominator": top_label_accuracy_denominator, "point_estimate": point, "interval_method": "CLUSTER_BOOTSTRAP_PERCENTILE", "intervals": intervals}
    if baseline_rows is not None:
        baseline_point = calc(list(baseline_rows))
        paired_point = {key: point[key] - baseline_point[key] for key in delta_values}
        result["baseline_point_estimate"] = baseline_point
        result["paired_point_estimate"] = paired_point
        result["paired_deltas"] = {key: interval(values, paired_point[key]) for key, values in delta_values.items()}
        result["estimable"] = result["estimable"] and all(item["estimable"] for item in result["paired_deltas"].values())
    return result


def build_readback_manifest(
    *,
    run_spec_sha256: str,
    artifacts: Mapping[str, ArtifactRef],
    expected_universe: Mapping[str, Any],
    producer_coverage: Mapping[str, Any],
    prediction: Mapping[str, Any],
    baseline_prediction: Mapping[str, Any],
    source_digest_sha256: str,
    metric_protocol_sha256: str,
    bootstrap_seed: int,
    bootstrap_replicates: int,
) -> dict[str, Any]:
    _sha(run_spec_sha256, "run_spec_sha256")
    _sha(source_digest_sha256, "source_digest_sha256")
    _sha(metric_protocol_sha256, "metric_protocol_sha256")
    if isinstance(bootstrap_seed, bool) or not isinstance(bootstrap_seed, int) or bootstrap_seed < 0:
        raise ValueError("bootstrap_seed must be a non-negative integer")
    if (
        isinstance(bootstrap_replicates, bool)
        or not isinstance(bootstrap_replicates, int)
        or bootstrap_replicates <= 0
    ):
        raise ValueError("bootstrap_replicates must be a positive integer")
    required_artifacts = {
        "expected_universe",
        "producer",
        "prediction",
        "baseline_prediction",
    }
    if required_artifacts - set(artifacts):
        raise ValueError("actual readback required artifacts are missing")
    if not expected_universe or not producer_coverage or not prediction or not baseline_prediction:
        raise ValueError("actual readback requires universe, coverage and paired predictions")
    if len({ref.relative_path for ref in artifacts.values()}) != len(artifacts):
        raise ValueError("duplicate artifact path")
    for name, ref in artifacts.items():
        if (
            ref.logical_name != name
            or not ref.logical_name
            or ref.relative_path.startswith("/")
            or ref.bytes < 0
            or (ref.row_count is not None and ref.row_count < 0)
        ):
            raise ValueError("invalid artifact ref")
        _sha(ref.sha256, "artifact sha256")
        _sha(ref.canonical_payload_sha256, "artifact canonical sha256")
    evaluation_plan = {
        "metric_protocol_sha256": metric_protocol_sha256,
        "bootstrap_seed": bootstrap_seed,
        "bootstrap_replicates": bootstrap_replicates,
        "expected_universe_payload_sha256": expected_universe.get("payload_sha256"),
    }
    payload = {
        "schema_version": SCHEMA_VERSION,
        "run_spec_sha256": run_spec_sha256,
        "artifacts": {key: value.to_dict() for key, value in sorted(artifacts.items())},
        "expected_universe": dict(expected_universe),
        "producer_coverage": dict(producer_coverage),
        "prediction": dict(prediction),
        "baseline_prediction": dict(baseline_prediction),
        "source_digest_sha256": source_digest_sha256,
        "metric_protocol_sha256": metric_protocol_sha256,
        "bootstrap_seed": bootstrap_seed,
        "bootstrap_replicates": bootstrap_replicates,
        "evaluation_plan_sha256": sha256_bytes(canonical_bytes(evaluation_plan)),
    }
    payload["manifest_sha256"] = sha256_bytes(canonical_bytes(payload))
    validate_readback_manifest(payload)
    return payload


def _validate_universe_receipt(receipt: Mapping[str, Any]) -> tuple[list[str], list[str]]:
    keys = {
        "row_count",
        "ordered_example_id_sha256",
        "ordered_post_id_sha256",
        "set_example_id_sha256",
        "set_post_id_sha256",
        "per_row",
        "payload_sha256",
    }
    if not isinstance(receipt, Mapping) or set(receipt) != keys or not isinstance(receipt.get("per_row"), list):
        raise ValueError("invalid expected universe receipt")
    count = receipt.get("row_count")
    if isinstance(count, bool) or not isinstance(count, int) or count <= 0 or count != len(receipt["per_row"]):
        raise ValueError("invalid expected universe row count")
    for key in (
        "ordered_example_id_sha256",
        "ordered_post_id_sha256",
        "set_example_id_sha256",
        "set_post_id_sha256",
        "payload_sha256",
    ):
        _sha(receipt.get(key), key)
    row_keys = {"example_id", "post_id", "row_payload_sha256"}
    examples: list[str] = []
    posts: list[str] = []
    for row in receipt["per_row"]:
        if not isinstance(row, Mapping) or set(row) != row_keys:
            raise ValueError("invalid expected universe row")
        example_id, post_id = row.get("example_id"), row.get("post_id")
        if any(not isinstance(value, str) or not value or value != value.strip() for value in (example_id, post_id)):
            raise ValueError("invalid expected universe identity")
        _sha(row.get("row_payload_sha256"), "expected universe row payload sha256")
        examples.append(example_id)
        posts.append(post_id)
    if len(set(examples)) != len(examples) or len(set(posts)) != len(posts):
        raise ValueError("duplicate expected universe identity")
    if receipt["payload_sha256"] != sha256_bytes(canonical_bytes(receipt["per_row"])):
        raise ValueError("expected universe payload hash mismatch")
    if (
        receipt["ordered_example_id_sha256"] != hash_sequence(examples)
        or receipt["ordered_post_id_sha256"] != hash_sequence(posts)
        or receipt["set_example_id_sha256"] != hash_set(examples)
        or receipt["set_post_id_sha256"] != hash_set(posts)
    ):
        raise ValueError("expected universe identity hash mismatch")
    return examples, posts


def _validate_prediction_receipt(
    name: str,
    receipt: Mapping[str, Any],
    *,
    expected_examples: Sequence[str],
    expected_posts: Sequence[str],
    producer_rows: Sequence[Mapping[str, Any]],
) -> None:
    keys = {
        "row_count",
        "ordered_example_id_sha256",
        "ordered_post_id_sha256",
        "set_example_id_sha256",
        "set_post_id_sha256",
        "per_row",
        "payload_sha256",
    }
    if not isinstance(receipt, Mapping) or set(receipt) != keys or not isinstance(receipt.get("per_row"), list):
        raise ValueError(f"invalid {name} receipt")
    count = receipt.get("row_count")
    if isinstance(count, bool) or not isinstance(count, int) or count != len(receipt["per_row"]):
        raise ValueError(f"invalid {name} row count")
    if count != len(expected_examples) or count != len(producer_rows):
        raise ValueError(f"{name} row coverage mismatch")
    for key in (
        "ordered_example_id_sha256",
        "ordered_post_id_sha256",
        "set_example_id_sha256",
        "set_post_id_sha256",
        "payload_sha256",
    ):
        _sha(receipt.get(key), f"{name} {key}")
    cov_keys = {
        "example_id",
        "post_id",
        "candidate_set_fingerprint",
        "generation_proof_fingerprint",
        "source_digest_sha256",
    }
    row_keys = cov_keys | {"payload_sha256", "shadow_fingerprint", "score_vector_sha256"}
    for index, (row, producer_row) in enumerate(zip(receipt["per_row"], producer_rows)):
        if not isinstance(row, Mapping) or set(row) != row_keys:
            raise ValueError(f"invalid {name} per-row shape")
        if row.get("example_id") != expected_examples[index] or row.get("post_id") != expected_posts[index]:
            raise ValueError(f"{name} expected universe mismatch")
        for key in (
            "payload_sha256",
            "shadow_fingerprint",
            "score_vector_sha256",
            "candidate_set_fingerprint",
            "generation_proof_fingerprint",
            "source_digest_sha256",
        ):
            _sha(row.get(key), f"{name} {key}")
        for key in cov_keys:
            if row.get(key) != producer_row.get(key):
                raise ValueError(f"producer/{name} binding mismatch: {key}")
    if receipt["payload_sha256"] != sha256_bytes(canonical_bytes(receipt["per_row"])):
        raise ValueError(f"{name} payload hash mismatch")
    if (
        receipt["ordered_example_id_sha256"] != hash_sequence(expected_examples)
        or receipt["ordered_post_id_sha256"] != hash_sequence(expected_posts)
        or receipt["set_example_id_sha256"] != hash_set(expected_examples)
        or receipt["set_post_id_sha256"] != hash_set(expected_posts)
    ):
        raise ValueError(f"{name} identity hash mismatch")


def validate_readback_manifest(manifest: Mapping[str, Any]) -> None:
    required = {
        "schema_version",
        "run_spec_sha256",
        "artifacts",
        "expected_universe",
        "producer_coverage",
        "prediction",
        "baseline_prediction",
        "source_digest_sha256",
        "metric_protocol_sha256",
        "bootstrap_seed",
        "bootstrap_replicates",
        "evaluation_plan_sha256",
        "manifest_sha256",
    }
    if not isinstance(manifest, Mapping) or set(manifest) != required or manifest.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("invalid manifest keys")
    stored = manifest.get("manifest_sha256")
    if _sha(stored, "manifest_sha256") != sha256_bytes(
        canonical_bytes({key: value for key, value in manifest.items() if key != "manifest_sha256"})
    ):
        raise ValueError("manifest hash mismatch")
    _sha(manifest.get("run_spec_sha256"), "run_spec_sha256")
    _sha(manifest.get("source_digest_sha256"), "source_digest_sha256")
    _sha(manifest.get("metric_protocol_sha256"), "metric_protocol_sha256")
    seed = manifest.get("bootstrap_seed")
    replicates = manifest.get("bootstrap_replicates")
    if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
        raise ValueError("invalid bootstrap_seed")
    if isinstance(replicates, bool) or not isinstance(replicates, int) or replicates <= 0:
        raise ValueError("invalid bootstrap_replicates")
    _sha(manifest.get("evaluation_plan_sha256"), "evaluation_plan_sha256")
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, Mapping):
        raise ValueError("manifest artifacts missing")
    required_artifacts = {"expected_universe", "producer", "prediction", "baseline_prediction"}
    if required_artifacts - set(artifacts):
        raise ValueError("manifest required artifacts missing")
    paths: set[str] = set()
    for name, ref in artifacts.items():
        if (
            not isinstance(ref, Mapping)
            or set(ref) != {"logical_name", "relative_path", "bytes", "sha256", "canonical_payload_sha256", "row_count"}
            or ref.get("logical_name") != name
        ):
            raise ValueError("invalid artifact shape")
        relative_path = ref.get("relative_path")
        if (
            not isinstance(relative_path, str)
            or not relative_path
            or relative_path.startswith(("/", "\\"))
            or ".." in Path(relative_path).parts
            or relative_path in paths
        ):
            raise ValueError("invalid artifact path")
        if (
            isinstance(ref.get("bytes"), bool)
            or not isinstance(ref.get("bytes"), int)
            or ref["bytes"] < 0
            or (
                ref.get("row_count") is not None
                and (
                    isinstance(ref["row_count"], bool)
                    or not isinstance(ref["row_count"], int)
                    or ref["row_count"] < 0
                )
            )
        ):
            raise ValueError("invalid artifact numeric shape")
        paths.add(relative_path)
        _sha(ref.get("sha256"), "artifact sha256")
        _sha(ref.get("canonical_payload_sha256"), "artifact canonical sha256")

    expected_examples, expected_posts = _validate_universe_receipt(manifest["expected_universe"])
    evaluation_plan = {
        "metric_protocol_sha256": manifest["metric_protocol_sha256"],
        "bootstrap_seed": seed,
        "bootstrap_replicates": replicates,
        "expected_universe_payload_sha256": manifest["expected_universe"]["payload_sha256"],
    }
    if manifest["evaluation_plan_sha256"] != sha256_bytes(canonical_bytes(evaluation_plan)):
        raise ValueError("evaluation plan hash mismatch")
    coverage = manifest["producer_coverage"]
    coverage_keys = {
        "expected_ids_sha256",
        "row_count",
        "complete_count",
        "unknown_count",
        "truncated_count",
        "missing_count",
        "extra_count",
        "duplicate_count",
        "per_row",
        "coverage_sha256",
    }
    if not isinstance(coverage, Mapping) or set(coverage) != coverage_keys or not isinstance(coverage.get("per_row"), list):
        raise ValueError("invalid producer coverage receipt")
    _sha(coverage.get("expected_ids_sha256"), "expected_ids_sha256")
    _sha(coverage.get("coverage_sha256"), "coverage_sha256")
    for key in (
        "row_count",
        "complete_count",
        "unknown_count",
        "truncated_count",
        "missing_count",
        "extra_count",
        "duplicate_count",
    ):
        value = coverage.get(key)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError("invalid producer coverage count")
    if (
        coverage["row_count"] != len(expected_examples)
        or coverage["row_count"] != len(coverage["per_row"])
        or coverage["complete_count"] != coverage["row_count"]
        or any(coverage[key] != 0 for key in ("unknown_count", "truncated_count", "missing_count", "extra_count", "duplicate_count"))
    ):
        raise ValueError("producer coverage is not frozen-actual complete")
    if coverage["expected_ids_sha256"] != hash_sequence(expected_examples):
        raise ValueError("producer expected universe hash mismatch")
    if coverage["coverage_sha256"] != sha256_bytes(canonical_bytes(coverage["per_row"])):
        raise ValueError("producer coverage hash mismatch")
    coverage_row_keys = {
        "example_id",
        "post_id",
        "candidate_set_fingerprint",
        "generation_proof_fingerprint",
        "source_digest_sha256",
    }
    for index, row in enumerate(coverage["per_row"]):
        if not isinstance(row, Mapping) or set(row) != coverage_row_keys:
            raise ValueError("invalid producer coverage row")
        if row.get("example_id") != expected_examples[index] or row.get("post_id") != expected_posts[index]:
            raise ValueError("producer coverage expected universe mismatch")
        for key in ("candidate_set_fingerprint", "generation_proof_fingerprint", "source_digest_sha256"):
            _sha(row.get(key), key)
        if row.get("source_digest_sha256") != manifest["source_digest_sha256"]:
            raise ValueError("top-level source digest is not bound to producer rows")
    _validate_prediction_receipt(
        "prediction",
        manifest["prediction"],
        expected_examples=expected_examples,
        expected_posts=expected_posts,
        producer_rows=coverage["per_row"],
    )
    _validate_prediction_receipt(
        "baseline_prediction",
        manifest["baseline_prediction"],
        expected_examples=expected_examples,
        expected_posts=expected_posts,
        producer_rows=coverage["per_row"],
    )
    expected_count = len(expected_examples)
    for name in required_artifacts:
        if artifacts[name].get("row_count") != expected_count:
            raise ValueError(f"artifact row count mismatch: {name}")


def validate_actual_readback_artifacts(
    root: str | Path,
    manifest: Mapping[str, Any],
) -> dict[str, list[dict[str, Any]]]:
    """Re-read all required JSONL bytes and recompute every semantic receipt."""

    validate_readback_manifest(manifest)
    validate_artifact_snapshots(root, manifest)
    rows: dict[str, list[dict[str, Any]]] = {}
    for name in ("expected_universe", "producer", "prediction", "baseline_prediction"):
        stored = manifest["artifacts"][name]
        current_ref, current_rows = snapshot_jsonl_rows(root, name, stored["relative_path"])
        if current_ref.to_dict() != dict(stored):
            raise ValueError(f"artifact snapshot mismatch: {name}")
        rows[name] = current_rows
    expected_receipt = expected_universe_readback(rows["expected_universe"])
    coverage_receipt = producer_coverage_receipt(rows["expected_universe"], rows["producer"])
    prediction_receipt = prediction_payload_readback(rows["expected_universe"], rows["prediction"])
    baseline_receipt = prediction_payload_readback(rows["expected_universe"], rows["baseline_prediction"])
    if expected_receipt != manifest["expected_universe"]:
        raise ValueError("expected universe semantic receipt mismatch")
    if coverage_receipt != manifest["producer_coverage"]:
        raise ValueError("producer semantic receipt mismatch")
    if prediction_receipt != manifest["prediction"]:
        raise ValueError("prediction semantic receipt mismatch")
    if baseline_receipt != manifest["baseline_prediction"]:
        raise ValueError("baseline prediction semantic receipt mismatch")
    validate_artifact_snapshots(root, manifest)
    return rows
