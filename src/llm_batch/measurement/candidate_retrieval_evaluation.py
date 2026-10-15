"""고정 R1 관측의 후보 회수·선택 평가. 파일 IO와 공개 권한은 없다.

corpus/CandidateOption/reference ID는 명시 매핑만 사용한다. 운영 회수율은
모든 lane에 같은 WORK 분모를 쓰며 실패·미완료를 성공 관측으로 바꾸지 않는다.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from copy import deepcopy
import math
import re
from typing import Any, Mapping, Sequence

from .research_evaluation_snapshot import SNAPSHOT_SCHEMA, semantic_hash


SCHEMA_VERSION = "candidate_retrieval_evaluation_v1"
MAPPING_SCHEMA = "candidate_retrieval_id_mapping_v1"
KS = (1, 5, 10, 20)
COMPLETE = frozenset({"COMPLETE", "EMPTY"})
REFERENCE_KINDS = frozenset({"MODEL_REFERENCE", "GOLD_LITE", "HUMAN_GOLD"})
SHA_RE = re.compile(r"^[0-9a-f]{64}$")
COORDINATE_FIELDS = ("run_id", "result_sha256", "input_index", "post_id", "row_attempt_id")


class RetrievalEvaluationError(ValueError):
    """평가 입력·고정 해시·명시 ID 매핑 계약 오류."""


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RetrievalEvaluationError(f"{label}: non-empty string required")
    return value


def _sha(value: Any, label: str) -> str:
    if not isinstance(value, str) or not SHA_RE.fullmatch(value):
        raise RetrievalEvaluationError(f"{label}: lowercase SHA256 required")
    return value


def _ids(value: Any, label: str) -> list[str]:
    if not isinstance(value, (list, tuple)):
        raise RetrievalEvaluationError(f"{label}: ID list required")
    return [_text(item, label) for item in value]


def _coordinate(row: Mapping[str, Any], *, allow_missing_attempt: bool = False) -> tuple:
    coordinate = row.get("coordinate")
    if not isinstance(coordinate, Mapping):
        raise RetrievalEvaluationError("coordinate required")
    index = coordinate.get("input_index")
    if type(index) is not int or index < 1:
        raise RetrievalEvaluationError("positive input_index required")
    post = coordinate.get("post_id")
    if not ((type(post) is int and post >= 0) or (isinstance(post, str) and post.strip())):
        raise RetrievalEvaluationError("post_id required")
    attempt = coordinate.get("row_attempt_id")
    if attempt is not None or not allow_missing_attempt:
        attempt = _text(attempt, "row_attempt_id")
    return (_text(row.get("dataset_id"), "dataset_id"),
            _text(coordinate.get("run_id"), "run_id"),
            _sha(coordinate.get("result_sha256"), "result_sha256"), index, str(post).strip(),
            attempt)


def _mapping(corpus: Mapping, value: Mapping, snapshot_sha: str) -> tuple[set, dict, dict]:
    corpus_sha = _sha(corpus.get("corpus_sha256"), "corpus_sha256")
    if corpus.get("data_kind") not in {"SOURCE_BACKED", "SYNTHETIC_FIXTURE"}:
        raise RetrievalEvaluationError("explicit corpus data_kind required")
    corpus_list = _ids(corpus.get("candidate_ids"), "corpus.candidate_ids")
    corpus_ids = set(corpus_list)
    if len(corpus_ids) != len(corpus_list):
        raise RetrievalEvaluationError("duplicate corpus candidate ID")
    if (value.get("schema_version") != MAPPING_SCHEMA or
            value.get("corpus_sha256") != corpus_sha or
            value.get("snapshot_semantic_sha256") != snapshot_sha):
        raise RetrievalEvaluationError("ID mapping schema/corpus/snapshot binding mismatch")
    source = value.get("source_ref")
    if not isinstance(source, Mapping):
        raise RetrievalEvaluationError("mapping source_ref required")
    _text(source.get("path"), "mapping source path")
    _sha(source.get("sha256"), "mapping source SHA")
    entries = value.get("entries")
    if not isinstance(entries, list):
        raise RetrievalEvaluationError("mapping entries required")
    options, references, seen = {}, {}, set()
    for entry in entries:
        if not isinstance(entry, Mapping):
            raise RetrievalEvaluationError("mapping entry must be an object")
        candidate = entry.get("corpus_candidate_id")
        if candidate not in corpus_ids or candidate in seen:
            raise RetrievalEvaluationError("unknown or duplicate mapped corpus ID")
        seen.add(candidate)
        for field, target in (("candidate_option_ids", options), ("reference_candidate_ids", references)):
            for external in _ids(entry.get(field), field):
                if external in target and target[external] != candidate:
                    raise RetrievalEvaluationError("ambiguous immutable ID mapping")
                target[external] = candidate
    return corpus_ids, options, references


def _rank(value: Any, space: Any, corpus_ids: set, option_map: dict) -> list[str]:
    raw = _ids(value, "ranked candidate IDs")
    if space not in {"CORPUS", "CANDIDATE_OPTION"}:
        raise RetrievalEvaluationError("explicit CORPUS/CANDIDATE_OPTION ID space required")
    mapped = []
    for candidate in raw:
        key = candidate if space == "CORPUS" else option_map.get(candidate)
        if key not in corpus_ids:
            raise RetrievalEvaluationError("unknown or unmapped candidate ID")
        if key not in mapped:
            mapped.append(key)
    return mapped


def _metric(numerator: float, denominator: int, *, unavailable: bool = False) -> dict:
    return {"numerator": numerator, "denominator": denominator,
            "value": None if unavailable or not denominator else numerator / denominator,
            "status": "NOT_ESTIMABLE" if unavailable or not denominator else "DIAGNOSTIC_ONLY"}


def observation_from_saved_shadow(snapshot_row: Mapping[str, Any], lane_name: str = "bm25") -> dict:
    """저장 receipt를 같은 R1 행에 결속해 평가 view로 바꾼다. 누락은 성공이 아니다."""
    _text(lane_name, "lane_name")
    coordinate = snapshot_row.get("coordinate") or {}
    meta = (snapshot_row.get("saved_row") or {}).get("run_meta") or {}
    receipt = meta.get("candidate_retrieval_shadow")
    result = {"dataset_id": snapshot_row.get("dataset_id"), "coordinate": deepcopy(coordinate),
              "corpus_sha256": receipt.get("corpus_sha256") if isinstance(receipt, Mapping) else None,
              "binding_status": "NOT_AVAILABLE", "reason_codes": [], "source": "SAVED_SHADOW_RECEIPT",
              "lanes": {lane_name: {"status": "NOT_AVAILABLE", "id_space": "CORPUS", "ranked_candidate_ids": []}}}
    def failure(code: str, *, invalid: bool = False) -> dict:
        result["binding_status"] = "INVALID_BINDING" if invalid else "NOT_AVAILABLE"
        result["reason_codes"].append(code)
        result["lanes"][lane_name]["status"] = result["binding_status"]
        return result
    if not isinstance(receipt, Mapping):
        return failure("RECEIPT_NOT_STORED")
    try:
        result["source_receipt_sha256"] = semantic_hash(receipt)
    except (TypeError, ValueError):
        return failure("RECEIPT_NOT_CANONICAL_JSON", invalid=True)
    if (receipt.get("schema_version") != "candidate_retrieval_shadow_v1" or receipt.get("mode") != "SHADOW" or
            receipt.get("publication_authority") is not False or receipt.get("central_db_write") is not False or
            receipt.get("public_apply", False) is not False):
        return failure("RECEIPT_SCHEMA_OR_AUTHORITY_MISMATCH", invalid=True)
    if "observation_sha256" in receipt:
        expected_digest = receipt["observation_sha256"]
        digest_payload = {key: value for key, value in receipt.items() if key not in {"latency_ms", "binding", "observation_sha256"}}
        if (not isinstance(expected_digest, str) or not SHA_RE.fullmatch(expected_digest) or
                semantic_hash(digest_payload) != expected_digest):
            return failure("OBSERVATION_SHA_MISMATCH", invalid=True)
    query_sha = receipt.get("query_sha256")
    if query_sha is not None and (not isinstance(query_sha, str) or not SHA_RE.fullmatch(query_sha)):
        return failure("QUERY_SHA_INVALID", invalid=True)
    binding = receipt.get("binding")
    binding = binding if isinstance(binding, Mapping) else {}
    attempt_receipt = meta.get("decision_call_attempt_receipt") or {}
    attempt_row = attempt_receipt.get("row") if isinstance(attempt_receipt, Mapping) else {}
    ledger = meta.get("decision_call_ledger") or {}
    ledger_row = ledger.get("row") if isinstance(ledger, Mapping) else {}
    cost_trace = meta.get("decision_cost_trace") or {}
    carriers = [coordinate, meta, attempt_receipt, attempt_row, ledger, ledger_row, cost_trace, receipt, binding]
    scopes = [carrier["publication_scope_id"] for carrier in carriers
              if isinstance(carrier, Mapping) and carrier.get("publication_scope_id") is not None]
    if any(not isinstance(scope, str) or not SHA_RE.fullmatch(scope) for scope in scopes):
        return failure("KNOWN_SCOPE_INVALID", invalid=True)
    if len(set(scopes)) > 1:
        return failure("RECEIPT_SCOPE_MISMATCH", invalid=True)
    # Missing fields never hide contradictions between other known carriers.
    for names in (("run_id", "attempt_run_id"), ("input_index",), ("post_id",), ("row_attempt_id", "attempt_id")):
        known = [carrier[name] for carrier in [coordinate, meta, attempt_row, ledger_row, binding]
                 if isinstance(carrier, Mapping) for name in names if carrier.get(name) is not None]
        if names == ("post_id",):
            known = [str(value).strip() for value in known]
        if known and (any(value != known[0] for value in known) or
                      (names == ("input_index",) and any(type(value) is not int for value in known))):
            return failure("KNOWN_ROW_COORDINATE_MISMATCH", invalid=True)
    try:
        _coordinate(snapshot_row)
    except RetrievalEvaluationError:
        return failure("ROW_COORDINATE_NOT_AVAILABLE")
    if not binding:
        return failure("RECEIPT_BINDING_NOT_AVAILABLE")
    for source, target in (("run_id", "run_id"), ("input_index", "input_index"), ("post_id", "post_id"), ("attempt_id", "row_attempt_id")):
        if binding.get(source) is None:
            return failure("RECEIPT_COORDINATE_NOT_AVAILABLE")
        left, right = binding[source], coordinate[target]
        if source == "post_id":
            left, right = str(left).strip(), str(right).strip()
        if left != right or (source == "input_index" and type(left) is not int):
            return failure("RECEIPT_COORDINATE_MISMATCH", invalid=True)
    if str(receipt.get("post_id")).strip() != str(coordinate["post_id"]).strip():
        return failure("RECEIPT_POST_MISMATCH", invalid=True)
    if scopes:
        if binding.get("publication_scope_id") is None:
            return failure("RECEIPT_SCOPE_NOT_AVAILABLE")
    else:
        result["reason_codes"].append("ROW_SCOPE_NOT_AVAILABLE")
    if result["corpus_sha256"] is None:
        return failure("CORPUS_SHA_NOT_AVAILABLE")
    if query_sha is None:
        return failure("QUERY_SHA_NOT_AVAILABLE")
    try:
        _sha(result["corpus_sha256"], "receipt corpus SHA")
        ranking, scores = [], []
        raw_candidates = receipt.get("ranked_candidates")
        if not isinstance(raw_candidates, list):
            raise RetrievalEvaluationError("ranked_candidates list required")
        for candidate in raw_candidates:
            candidate_id = _text(candidate.get("corpus_candidate_id"), "corpus candidate ID")
            score = candidate.get("score")
            if type(score) not in (int, float) or not math.isfinite(score) or score <= 0 or candidate_id in ranking:
                raise RetrievalEvaluationError("positive finite score and unique ID required")
            ranking.append(candidate_id)
            scores.append(score)
        if scores != sorted(scores, reverse=True):
            raise RetrievalEvaluationError("ranked scores are out of order")
        status = _text(receipt.get("status"), "receipt status")
        empty_statuses = {"NO_MATCH", "EMPTY_QUERY", "EMPTY_CORPUS"}
        if status in empty_statuses and ranking:
            raise RetrievalEvaluationError("empty status contains candidates")
        converted = "COMPLETE" if status == "OK" else "EMPTY" if status in empty_statuses else status
        counts = receipt.get("counts") or {}
        top_k = ((receipt.get("policy") or {}).get("config") or {}).get("top_k")
        if converted == "COMPLETE" and (counts.get("omitted_ranked_candidates", 0) or
                (type(top_k) is int and top_k < max(KS) and counts.get("positive_candidates", 0) > len(ranking))):
            converted = "INCOMPLETE"
            result["reason_codes"].append("RANK_DEPTH_OR_RECEIPT_INCOMPLETE")
        result["binding_status"] = "BOUND"
        result["source_status"] = status
        result["lanes"][lane_name] = {"status": converted, "id_space": "CORPUS", "ranked_candidate_ids": ranking}
        return result
    except (RetrievalEvaluationError, AttributeError, TypeError, ValueError):
        return failure("INVALID_RANKING_OR_CORPUS_SHA", invalid=True)


def _summarize(rows: list[dict], lane_names: tuple[str, ...], *, invalid: bool) -> dict:
    work = [row for row in rows if row["reference_status"] in {"JUDGED_WORK", "UNMAPPED_WORK"}]
    unavailable = invalid or any(row["reference_status"] == "UNMAPPED_WORK" for row in work)
    lanes = {}
    for lane in (*lane_names, "union"):
        lanes[lane] = {
            "recall": {f"at_{k}": _metric(sum(row["hits"][lane][str(k)] for row in work), len(work),
                                          unavailable=unavailable) for k in KS},
            "operational_status_counts": dict(sorted(Counter(row["lane_statuses"][lane] for row in work).items())),
        }
    conditioned = [row for row in work if row["selection"]["condition_met"]]
    observed = [row for row in conditioned if row["selection"]["complete"]]
    correct = sum(row["selection"]["correct"] for row in observed)
    reciprocal = sum(row["selection"]["reciprocal_rank"] for row in observed)
    return {
        "saved_observation_count": len(rows), "judged_work_denominator": len(work),
        "unique_post_count": len({(row["sample_namespace"], str((row["coordinate"] or {}).get("post_id"))) for row in rows}),
        "independent_sample_count": None,
        "reference_status_counts": dict(sorted(Counter(row["reference_status"] for row in rows).items())),
        "reference_kind_counts": dict(sorted(Counter(row["reference_kind"] for row in rows).items())),
        "lanes": lanes,
        "selection": {
            "scope": "BOUND_WORK_EXPECTED_RESOLVE_GOLD_IN_SELECTION_POOL",
            "gold_present_denominator": len(conditioned), "complete_observation_denominator": len(observed),
            "condition_status_counts": dict(sorted(Counter(row["selection"]["condition_status"] for row in work).items())),
            "operational_gold_present_accuracy": _metric(correct, len(conditioned), unavailable=unavailable),
            "operational_mrr": _metric(reciprocal, len(conditioned), unavailable=unavailable),
            "complete_only_gold_present_accuracy": _metric(correct, len(observed), unavailable=unavailable),
            "complete_only_mrr": _metric(reciprocal, len(observed), unavailable=unavailable),
        },
    }


def evaluate_candidate_retrieval(snapshot: Mapping[str, Any], observations: Sequence[Mapping[str, Any]], *,
                                 corpus: Mapping[str, Any], id_mapping: Mapping[str, Any],
                                 lane_names: Sequence[str]) -> dict[str, Any]:
    """R1 pure-builder snapshot과 고정 corpus의 명시 관측만 평가한다.

    lane union@K는 각 lane top-K 합집합이다. 실패/미완료 lane은 0 hit이며
    해당 행을 WORK 분모에서 제거하지 않는다. 선택 평가는 공개 허용 평가가 아니다.
    """
    if snapshot.get("schema_version") != SNAPSHOT_SCHEMA:
        raise RetrievalEvaluationError("R1 snapshot schema required")
    snapshot_sha = _sha(snapshot.get("semantic_sha256"), "snapshot semantic SHA")
    if semantic_hash({key: value for key, value in snapshot.items() if key != "semantic_sha256"}) != snapshot_sha:
        raise RetrievalEvaluationError("pure R1 snapshot semantic hash mismatch")
    lanes = tuple(_ids(lane_names, "lane_names"))
    if not lanes or len(lanes) != len(set(lanes)) or "union" in lanes:
        raise RetrievalEvaluationError("unique explicit lane names required; union is reserved")
    if not isinstance(observations, (list, tuple)) or not isinstance(snapshot.get("rows"), list):
        raise RetrievalEvaluationError("snapshot rows and observations must be lists")
    corpus_ids, option_map, reference_map = _mapping(corpus, id_mapping, snapshot_sha)
    if corpus["data_kind"] == "SYNTHETIC_FIXTURE" and any(row.get("data_kind") != "SYNTHETIC_FIXTURE" for row in snapshot["rows"]):
        raise RetrievalEvaluationError("synthetic corpus cannot evaluate saved actual observations")
    issues, by_coordinate = [], {}
    invalid = snapshot.get("binding_status") != "COMPLETE_WITH_LIMITS"
    if invalid:
        issues.append({"code": "SNAPSHOT_INVALID_BINDING"})
    for ordinal, observation in enumerate(observations, 1):
        try:
            key = _coordinate(observation, allow_missing_attempt=True)
            if key in by_coordinate:
                raise RetrievalEvaluationError("duplicate observation coordinate")
            by_coordinate[key] = observation
        except (RetrievalEvaluationError, AttributeError) as exc:
            invalid = True
            issues.append({"code": "OBSERVATION_INVALID_BINDING", "ordinal": ordinal, "detail": str(exc)})
    output_rows, seen, used = [], set(), set()
    for ordinal, source in enumerate(snapshot["rows"], 1):
        problems = []
        row_unavailable = False
        try:
            key = _coordinate(source, allow_missing_attempt=True)
            row_unavailable = key[-1] is None
            if key in seen:
                raise RetrievalEvaluationError("duplicate snapshot coordinate")
            seen.add(key)
            observation = by_coordinate.get(key, {})
            if observation:
                used.add(key)
                if observation.get("binding_status") == "INVALID_BINDING":
                    problems.append("OBSERVATION_INVALID_BINDING")
                observed_sha = observation.get("corpus_sha256")
                if ((observed_sha is not None and observed_sha != corpus["corpus_sha256"]) or
                        (observed_sha is None and observation.get("binding_status") != "NOT_AVAILABLE")):
                    problems.append("OBSERVATION_CORPUS_MISMATCH")
                if observation.get("source") == "SAVED_SHADOW_RECEIPT":
                    saved_lanes = observation.get("lanes") or {}
                    if len(saved_lanes) != 1 or observation != observation_from_saved_shadow(source, next(iter(saved_lanes))):
                        problems.append("SAVED_RECEIPT_VIEW_MISMATCH")
                row_unavailable = row_unavailable or observation.get("binding_status") == "NOT_AVAILABLE"
            if row_unavailable:
                observation = {}
        except (RetrievalEvaluationError, AttributeError) as exc:
            key, observation = None, {}
            problems.append(str(exc))
        reference = source.get("reference") or {}
        payload = reference.get("payload") or {}
        grade = reference.get("reference_kind", "UNJUDGED")
        truth = payload.get("truth_kind")
        status, gold = "UNJUDGED", None
        if reference.get("binding_status") == "INVALID_BINDING":
            status = "INVALID_BINDING"
            problems.append("REFERENCE_INVALID_BINDING")
        elif reference.get("binding_status") == "BOUND_CALLER_SUPPLIED" and grade in REFERENCE_KINDS:
            if truth == "WORK":
                gold = reference_map.get(payload.get("truth_candidate_id"))
                status = "JUDGED_WORK" if gold else "UNMAPPED_WORK"
            elif truth == "NIL":
                status = "NIL"
            else:
                status = "UNJUDGED"
        ranks, lane_statuses = {}, {}
        for lane in lanes:
            record = (observation.get("lanes") or {}).get(lane)
            if record is None:
                lane_statuses[lane], ranks[lane] = "UNAVAILABLE", []
                continue
            try:
                lane_statuses[lane] = _text(record.get("status"), "lane status")
                ranking = _rank(record.get("ranked_candidate_ids"), record.get("id_space"), corpus_ids, option_map)
                if lane_statuses[lane] == "EMPTY" and ranking:
                    raise RetrievalEvaluationError("EMPTY lane contains candidates")
                ranks[lane] = ranking if lane_statuses[lane] in COMPLETE else []
            except (RetrievalEvaluationError, AttributeError) as exc:
                ranks[lane], lane_statuses[lane] = [], "INVALID_BINDING"
                problems.append(f"{lane}: {exc}")
        lane_statuses["union"] = "COMPLETE" if all(lane_statuses[lane] in COMPLETE for lane in lanes) else "PARTIAL_OR_UNAVAILABLE"
        hits = {lane: {str(k): int(gold is not None and gold in ranks[lane][:k]) for k in KS} for lane in lanes}
        hits["union"] = {str(k): int(gold is not None and any(gold in ranks[lane][:k] for lane in lanes)) for k in KS}
        selection = {"condition_met": False, "condition_status": "SELECTION_NOT_OBSERVED", "complete": False,
                     "correct": False, "reciprocal_rank": 0.0}
        selected = observation.get("selection")
        if selected is not None:
            try:
                pool = _rank(selected.get("candidate_ids"), selected.get("id_space"), corpus_ids, option_map)
                ranking = _rank(selected.get("ranked_candidate_ids"), selected.get("id_space"), corpus_ids, option_map)
                predicted = selected.get("selected_candidate_id")
                predicted_ids = _rank([predicted], selected.get("id_space"), corpus_ids, option_map) if predicted is not None else []
                if not set(ranking + predicted_ids).issubset(pool):
                    raise RetrievalEvaluationError("selection ranking/prediction outside candidate pool")
                if selected.get("status") == "EMPTY" and (ranking or predicted_ids):
                    raise RetrievalEvaluationError("EMPTY selection contains ranking/prediction")
                complete = selected.get("status") in COMPLETE
                condition = gold is not None and gold in pool and payload.get("expected_action") in {"RESOLVED", "RESOLVE"}
                selection.update(condition_met=condition, complete=complete,
                                 condition_status="GOLD_PRESENT" if condition else "ACTION_NOT_RESOLVE" if payload.get("expected_action") not in {"RESOLVED", "RESOLVE"} else "GOLD_NOT_IN_POOL",
                                 correct=bool(complete and predicted_ids == [gold]),
                                 reciprocal_rank=1.0 / (ranking.index(gold) + 1) if complete and gold in ranking else 0.0)
            except (RetrievalEvaluationError, AttributeError) as exc:
                problems.append(f"selection: {exc}")
                selection["condition_status"] = "INVALID_BINDING"
        if problems:
            invalid = True
            issues.append({"code": "ROW_INVALID_BINDING", "ordinal": ordinal, "details": problems})
        output_rows.append({"dataset_id": source.get("dataset_id"), "coordinate": deepcopy(source.get("coordinate")),
                            "data_kind": source.get("data_kind"), "sample_namespace": source.get("sample_namespace"),
                            "reference_kind": grade, "reference_status": status, "reference_candidate_id": payload.get("truth_candidate_id"),
                            "corpus_gold_id": gold, "lane_statuses": lane_statuses, "hits": hits,
                            "selection": selection, "binding_status": "INVALID_BINDING" if problems else "NOT_AVAILABLE" if row_unavailable else "BOUND"})
    unused = set(by_coordinate) - used
    if unused:
        invalid = True
        issues.append({"code": "OBSERVATIONS_NOT_IN_SNAPSHOT", "count": len(unused)})
    by_kind, by_grade, by_dataset = defaultdict(list), defaultdict(list), defaultdict(list)
    for row in output_rows:
        by_kind[row["data_kind"]].append(row)
        by_grade[(row["data_kind"], row["reference_kind"])].append(row)
        by_dataset[row["dataset_id"]].append(row)
    core = {"schema_version": SCHEMA_VERSION,
            "status": "INVALID_BINDING" if invalid else "COMPLETE_WITH_LIMITS",
            "snapshot_semantic_sha256": snapshot_sha, "corpus_sha256": corpus["corpus_sha256"],
            "corpus_data_kind": corpus["data_kind"],
            "id_mapping_sha256": semantic_hash(id_mapping), "mapping_source_ref": deepcopy(id_mapping["source_ref"]),
            "binding_scope": "CALLER_PROVIDED_SNAPSHOT_AND_MAPPING_NO_INDEPENDENT_LABEL_AUTHORITY",
            "publication_authority": False, "formal_kpi_status": "NOT_ESTIMABLE", "model_calls": 0, "network_calls": 0,
            "union_policy": "SET_UNION_OF_EACH_LANE_TOP_K_NO_FUSED_RANKING",
            "operational_miss_policy": "MISSING_UNAVAILABLE_INCOMPLETE_LANES_ZERO_HIT_SAME_WORK_DENOMINATOR",
            "independent_sample_count": None,
            "by_data_kind": {kind: _summarize(rows, lanes, invalid=invalid) for kind, rows in sorted(by_kind.items())},
            "by_reference_kind": {f"{kind}:{grade}": _summarize(rows, lanes, invalid=invalid) for (kind, grade), rows in sorted(by_grade.items())},
            "by_dataset": {key: _summarize(rows, lanes, invalid=invalid) for key, rows in sorted(by_dataset.items())},
            "rows": output_rows, "issues": issues}
    return {**core, "semantic_sha256": semantic_hash(core)}
