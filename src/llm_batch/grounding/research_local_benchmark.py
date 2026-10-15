from __future__ import annotations

"""연구 전용 로컬 grounding 벤치마크.

이 모듈은 production/publication/Slang DB 경로와 연결되지 않는다. 입력은 권리
메타데이터가 있는 fixture만 허용하고, 모든 terminal 상태를 metric 분모에 남긴다.
"""

import hashlib
import json
import math
import re
import time
import urllib.error
import urllib.request
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence
from urllib.parse import urlparse


SCHEMA_VERSION = "research-local-grounding-benchmark-v1"
DIAGNOSTIC_SCHEMA_VERSION = "candidate-selection-diagnostics-v1"
NIL = "__NIL__"
ABSTAIN = "__ABSTAIN__"
TERMINAL_STATUSES = frozenset({"RESOLVED", "NIL", "ABSTAIN", "UNAVAILABLE", "ERROR"})
RIGHTS_KINDS = frozenset({"USER_PROVIDED", "SELF_CREATED", "LICENSED", "SYNTHETIC"})
CASE_TYPES = frozenset({"WORK", "CANDIDATE_MISS", "COMPARISON_SELECTION", "ACTUAL_NIL", "AMBIGUOUS"})
EXPECTED_ACTIONS = frozenset({"RESOLVED", "NIL", "ABSTAIN"})
RETRIEVAL_TOP_K = 5
TOKEN_RE = re.compile(r"[0-9a-zA-Z가-힣]+")
PROMPT_TEMPLATE = """연구용 후보 선택 작업이다. 아래 query와 후보만 사용한다.
정답이 후보에 없으면 __NIL__, 모호하면 __ABSTAIN__, 아니면 candidate_id 하나만 답한다.
query: {query}
candidates:
{candidates}
answer:"""


class ResearchBenchmarkError(ValueError):
    pass


@dataclass(frozen=True)
class Prediction:
    query_id: str
    arm: str
    predicted_label: str | None
    terminal_status: str
    latency_ms: float
    scores: tuple[tuple[str, float], ...] = ()
    reason: str = ""
    candidate_ids: tuple[str, ...] = ()
    selection_candidate_ids: tuple[str, ...] = ()
    selection_attempted: bool = True

    def to_dict(
        self,
        *,
        gold_label: str,
        case_type: str | None = None,
        expected_action: str | None = None,
        partition: str | None = None,
    ) -> dict[str, Any]:
        normalized_case_type = case_type or _default_case_type(gold_label)
        normalized_expected_action = expected_action or _default_expected_action(normalized_case_type, gold_label)
        retrieval_ids = list(self.candidate_ids)
        selection_ids = list(self.selection_candidate_ids)
        correct = self.terminal_status in {"RESOLVED", "NIL"} and self.predicted_label == gold_label
        return {
            "query_id": self.query_id,
            "arm": self.arm,
            "partition": partition or "default",
            "case_type": normalized_case_type,
            "expected_action": normalized_expected_action,
            "gold_label": gold_label,
            "predicted_label": self.predicted_label,
            "terminal_status": self.terminal_status,
            "correct": correct,
            "action_correct": _action_correct(
                predicted_label=self.predicted_label,
                terminal_status=self.terminal_status,
                gold_label=gold_label,
                expected_action=normalized_expected_action,
            ),
            "latency_ms": round(self.latency_ms, 4),
            "scores": [{"candidate_id": key, "score": round(value, 8)} for key, value in self.scores],
            "candidate_ids": retrieval_ids,
            "selection_candidate_ids": selection_ids,
            "gold_in_retrieval_top_k": gold_label in retrieval_ids if retrieval_ids else None,
            "gold_in_selection_candidates": gold_label in selection_ids if selection_ids else None,
            "gold_in_candidate_set": gold_label in selection_ids if selection_ids else None,
            "selection_attempted": self.selection_attempted,
            "failure_stage": _failure_stage(
                predicted_label=self.predicted_label,
                terminal_status=self.terminal_status,
                gold_label=gold_label,
                expected_action=normalized_expected_action,
                selection_candidate_ids=selection_ids,
                selection_attempted=self.selection_attempted,
            ),
            "reason": self.reason,
        }


def _default_case_type(gold_label: str) -> str:
    return "ACTUAL_NIL" if gold_label == NIL else "WORK"


def _default_expected_action(case_type: str, gold_label: str) -> str:
    if case_type == "ACTUAL_NIL" or gold_label == NIL:
        return "NIL"
    if case_type == "AMBIGUOUS":
        return "ABSTAIN"
    return "RESOLVED"


def _row_case_type(row: Mapping[str, Any]) -> str:
    gold_label = str(row.get("gold_label") or "")
    return str(row.get("case_type") or _default_case_type(gold_label))


def _row_expected_action(row: Mapping[str, Any]) -> str:
    case_type = _row_case_type(row)
    gold_label = str(row.get("gold_label") or "")
    return str(row.get("expected_action") or _default_expected_action(case_type, gold_label))


def _row_partition(row: Mapping[str, Any]) -> str:
    return str(row.get("partition") or "default")


def _action_correct(
    *,
    predicted_label: str | None,
    terminal_status: str,
    gold_label: str,
    expected_action: str,
) -> bool:
    if terminal_status in {"UNAVAILABLE", "ERROR"}:
        return False
    if expected_action == "ABSTAIN":
        return terminal_status == "ABSTAIN" and predicted_label == ABSTAIN
    if expected_action == "NIL":
        return terminal_status == "NIL" and predicted_label == NIL
    return terminal_status == "RESOLVED" and predicted_label == gold_label


def _failure_stage(
    *,
    predicted_label: str | None,
    terminal_status: str,
    gold_label: str,
    expected_action: str,
    selection_candidate_ids: Sequence[str],
    selection_attempted: bool,
) -> str:
    if terminal_status in {"UNAVAILABLE", "ERROR"}:
        return terminal_status
    if gold_label == NIL:
        return "CORRECT_NIL" if predicted_label == NIL and terminal_status == "NIL" else "NIL_MISCLASSIFICATION"
    if not selection_attempted:
        return "SELECTION_NOT_ATTEMPTED"
    if selection_candidate_ids and gold_label not in selection_candidate_ids:
        return "CANDIDATE_RECALL_MISS"
    if expected_action == "ABSTAIN":
        return "CORRECT_ABSTAIN" if predicted_label == ABSTAIN and terminal_status == "ABSTAIN" else "AMBIGUOUS_NON_ABSTAIN"
    if predicted_label == gold_label and terminal_status == "RESOLVED":
        return "CORRECT_WORK"
    if predicted_label == NIL:
        return "SELECTION_FAILURE_FALSE_NIL"
    if predicted_label == ABSTAIN:
        return "SELECTION_FAILURE_ABSTAIN"
    return "SELECTION_FAILURE_WRONG_CANDIDATE"


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_value(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def effective_parallel(requested_parallel: int, input_count: int) -> int:
    if requested_parallel <= 0 or input_count <= 0:
        raise ResearchBenchmarkError("requested_parallel and input_count must be positive")
    return min(requested_parallel, input_count)


def build_parallel_contract(requested_parallel: int, input_count: int) -> dict[str, Any]:
    return {
        "requested_parallel": requested_parallel,
        "effective_parallel": effective_parallel(requested_parallel, input_count),
        "parallel_count": effective_parallel(requested_parallel, input_count),
        "parallel_policy": "effective_parallel=min(requested_parallel,benchmark_input_count)",
    }


def ensure_research_output_dir(output_dir: Path, research_root: Path) -> Path:
    resolved_output = output_dir.resolve()
    resolved_root = research_root.resolve()
    if resolved_output == resolved_root or resolved_root not in resolved_output.parents:
        raise ResearchBenchmarkError(f"output must be a child of research namespace: {resolved_root}")
    if resolved_output.exists():
        raise ResearchBenchmarkError(f"refusing to overwrite existing output directory: {resolved_output}")
    return resolved_output


def _tokens(text: str) -> list[str]:
    return [token.lower() for token in TOKEN_RE.findall(text)]


def _candidate_text(candidate: Mapping[str, Any]) -> str:
    aliases = candidate.get("aliases") or []
    return " ".join(
        [str(candidate.get("title") or ""), *(str(value) for value in aliases), str(candidate.get("text") or "")]
    )


def load_and_validate_fixture(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, raw in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), start=1):
        if not raw.strip():
            continue
        try:
            row = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ResearchBenchmarkError(f"fixture line {line_number}: invalid JSON") from exc
        if not isinstance(row, dict):
            raise ResearchBenchmarkError(f"fixture line {line_number}: row must be an object")
        rows.append(row)
    if not rows:
        raise ResearchBenchmarkError("fixture is empty")

    ids: set[str] = set()
    blind_rechecks = 0
    for row in rows:
        query_id = str(row.get("query_id") or "").strip()
        if not query_id or query_id in ids:
            raise ResearchBenchmarkError("query_id must be non-empty and unique")
        ids.add(query_id)
        if row.get("namespace") not in {"synthetic", "research"}:
            raise ResearchBenchmarkError(f"{query_id}: namespace must be synthetic or research")
        rights = row.get("rights")
        if not isinstance(rights, dict) or rights.get("kind") not in RIGHTS_KINDS:
            raise ResearchBenchmarkError(f"{query_id}: rights.kind is not research-safe")
        for key in ("source", "retention"):
            if not str(rights.get(key) or "").strip():
                raise ResearchBenchmarkError(f"{query_id}: rights.{key} is required")
        candidates = row.get("candidates")
        if not isinstance(candidates, list) or not candidates:
            raise ResearchBenchmarkError(f"{query_id}: candidates are required")
        candidate_ids = [str(item.get("candidate_id") or "") for item in candidates if isinstance(item, dict)]
        if len(candidate_ids) != len(candidates) or any(not value for value in candidate_ids) or len(set(candidate_ids)) != len(candidate_ids):
            raise ResearchBenchmarkError(f"{query_id}: candidate_id values must be unique")
        gold = str(row.get("gold_label") or "")
        if gold != NIL and gold not in candidate_ids:
            raise ResearchBenchmarkError(f"{query_id}: gold_label is outside candidate set")
        case_type = _row_case_type(row)
        expected_action = _row_expected_action(row)
        if case_type not in CASE_TYPES:
            raise ResearchBenchmarkError(f"{query_id}: unsupported case_type")
        if expected_action not in EXPECTED_ACTIONS:
            raise ResearchBenchmarkError(f"{query_id}: unsupported expected_action")
        if case_type == "ACTUAL_NIL" and gold != NIL:
            raise ResearchBenchmarkError(f"{query_id}: ACTUAL_NIL requires NIL gold")
        if case_type != "ACTUAL_NIL" and gold == NIL:
            raise ResearchBenchmarkError(f"{query_id}: non-NIL case_type requires work gold")
        if case_type == "AMBIGUOUS" and expected_action != "ABSTAIN":
            raise ResearchBenchmarkError(f"{query_id}: AMBIGUOUS requires ABSTAIN expected_action")
        if gold == NIL and expected_action != "NIL":
            raise ResearchBenchmarkError(f"{query_id}: NIL gold requires NIL expected_action")
        if gold != NIL and case_type != "AMBIGUOUS" and expected_action != "RESOLVED":
            raise ResearchBenchmarkError(f"{query_id}: work case requires RESOLVED expected_action")
        if case_type == "AMBIGUOUS" and expected_action == "NIL":
            raise ResearchBenchmarkError(f"{query_id}: AMBIGUOUS cannot expect NIL")
        partition = row.get("partition")
        if partition is not None and not str(partition).strip():
            raise ResearchBenchmarkError(f"{query_id}: partition must be non-empty")
        curator = row.get("gold_lite")
        if not isinstance(curator, dict) or not str(curator.get("curator_id") or "").strip():
            raise ResearchBenchmarkError(f"{query_id}: single-curator gold-lite metadata is required")
        recheck = row.get("blind_recheck")
        if recheck is not None:
            blind_rechecks += 1
            if not isinstance(recheck, dict) or recheck.get("label") != gold or not str(recheck.get("reviewer_id") or "").strip():
                raise ResearchBenchmarkError(f"{query_id}: blind recheck must agree with gold-lite")
    if blind_rechecks == 0 or blind_rechecks > max(1, math.ceil(len(rows) * 0.25)):
        raise ResearchBenchmarkError("blind recheck count must be between 1 and ceil(rows*0.25)")
    return rows


def build_fixture_corpus(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Fixture 전체의 후보를 합쳐 query와 분리된 공통 연구 corpus를 만든다."""

    merged: dict[str, dict[str, Any]] = {}
    for row in rows:
        for candidate in row["candidates"]:
            candidate_id = str(candidate["candidate_id"])
            current = merged.setdefault(
                candidate_id,
                {"candidate_id": candidate_id, "title": str(candidate.get("title") or ""), "aliases": set(), "texts": set()},
            )
            if current["title"] != str(candidate.get("title") or ""):
                raise ResearchBenchmarkError(f"candidate title conflict: {candidate_id}")
            current["aliases"].update(str(value) for value in candidate.get("aliases") or [])
            if str(candidate.get("text") or "").strip():
                current["texts"].add(str(candidate["text"]))
    return [
        {
            "candidate_id": candidate_id,
            "title": value["title"],
            "aliases": sorted(value["aliases"]),
            "text": " ".join(sorted(value["texts"])),
        }
        for candidate_id, value in sorted(merged.items())
    ]


def _baseline_scores(row: Mapping[str, Any], *, corpus: Sequence[Mapping[str, Any]] | None = None) -> list[tuple[str, float]]:
    query = str(row["query"]).lower()
    query_tokens = set(_tokens(query))
    scores: list[tuple[str, float]] = []
    for candidate in corpus or row["candidates"]:
        title = str(candidate.get("title") or "").lower()
        aliases = [str(value).lower() for value in candidate.get("aliases") or []]
        candidate_tokens = set(_tokens(_candidate_text(candidate)))
        exact = 4.0 if title and title in query else 0.0
        alias = 3.0 if any(value and value in query for value in aliases) else 0.0
        overlap = len(query_tokens & candidate_tokens) / max(1, len(query_tokens))
        scores.append((str(candidate["candidate_id"]), exact + alias + overlap))
    return sorted(scores, key=lambda item: (-item[1], item[0]))


def _bm25_scores(row: Mapping[str, Any], *, corpus: Sequence[Mapping[str, Any]] | None = None) -> list[tuple[str, float]]:
    query_tokens = _tokens(str(row["query"]))
    candidates = list(corpus or row["candidates"])
    documents = [_tokens(_candidate_text(candidate)) for candidate in candidates]
    average_length = sum(len(document) for document in documents) / max(1, len(documents))
    frequencies = Counter(token for token in set(query_tokens) for document in documents if token in set(document))
    scores: list[tuple[str, float]] = []
    for candidate, document in zip(candidates, documents):
        counts = Counter(document)
        score = 0.0
        for token in query_tokens:
            document_frequency = frequencies[token]
            inverse = math.log(1.0 + (len(documents) - document_frequency + 0.5) / (document_frequency + 0.5))
            frequency = counts[token]
            denominator = frequency + 1.5 * (1.0 - 0.75 + 0.75 * len(document) / max(1.0, average_length))
            score += inverse * (frequency * 2.5 / denominator if denominator else 0.0)
        scores.append((str(candidate["candidate_id"]), score))
    return sorted(scores, key=lambda item: (-item[1], item[0]))


def _retrieval_candidate_ids(
    row: Mapping[str, Any],
    *,
    corpus: Sequence[Mapping[str, Any]] | None = None,
) -> tuple[str, ...]:
    return tuple(candidate_id for candidate_id, _score in _bm25_scores(row, corpus=corpus)[:RETRIEVAL_TOP_K])


def _timed_prediction(
    query_id: str,
    arm: str,
    callback: Callable[[], Prediction],
    *,
    candidate_ids: Sequence[str] = (),
    selection_candidate_ids: Sequence[str] = (),
) -> Prediction:
    started = time.perf_counter()
    try:
        result = callback()
        return Prediction(
            query_id=result.query_id,
            arm=result.arm,
            predicted_label=result.predicted_label,
            terminal_status=result.terminal_status,
            latency_ms=(time.perf_counter() - started) * 1000.0,
            scores=result.scores,
            reason=result.reason,
            candidate_ids=result.candidate_ids,
            selection_candidate_ids=result.selection_candidate_ids,
            selection_attempted=result.selection_attempted,
        )
    except Exception as exc:  # errors remain explicit denominator members
        return Prediction(
            query_id,
            arm,
            None,
            "ERROR",
            (time.perf_counter() - started) * 1000.0,
            reason=f"{type(exc).__name__}: {exc}",
            candidate_ids=tuple(candidate_ids),
            selection_candidate_ids=tuple(selection_candidate_ids),
            selection_attempted=False,
        )


def predict_baseline(row: Mapping[str, Any], *, corpus: Sequence[Mapping[str, Any]] | None = None) -> Prediction:
    scores = _baseline_scores(row, corpus=corpus)
    top = scores[0]
    label = top[0] if top[1] > 0.0 else NIL
    status = "RESOLVED" if label != NIL else "NIL"
    return Prediction(
        str(row["query_id"]),
        "lexical_baseline",
        label,
        status,
        0.0,
        tuple(scores),
        candidate_ids=_retrieval_candidate_ids(row, corpus=corpus),
        selection_candidate_ids=tuple(candidate_id for candidate_id, _score in scores),
    )


def predict_bm25(row: Mapping[str, Any], *, corpus: Sequence[Mapping[str, Any]] | None = None) -> Prediction:
    scores = _bm25_scores(row, corpus=corpus)
    return Prediction(
        str(row["query_id"]),
        "bm25_fixture_corpus_retriever",
        scores[0][0],
        "RESOLVED",
        0.0,
        tuple(scores),
        candidate_ids=_retrieval_candidate_ids(row, corpus=corpus),
        selection_candidate_ids=tuple(candidate_id for candidate_id, _score in scores),
    )


def predict_reranker_nil(
    row: Mapping[str, Any],
    *,
    corpus: Sequence[Mapping[str, Any]] | None = None,
    nil_threshold: float = 0.35,
    abstain_margin: float = 0.08,
) -> Prediction:
    bm25 = _bm25_scores(row, corpus=corpus)
    baseline = dict(_baseline_scores(row, corpus=corpus))
    combined = sorted(((candidate_id, score + 0.55 * baseline[candidate_id]) for candidate_id, score in bm25), key=lambda item: (-item[1], item[0]))
    top_score = combined[0][1]
    second_score = combined[1][1] if len(combined) > 1 else 0.0
    retrieval_candidate_ids = _retrieval_candidate_ids(row, corpus=corpus)
    selection_candidate_ids = tuple(candidate_id for candidate_id, _score in combined)
    if top_score < nil_threshold:
        return Prediction(
            str(row["query_id"]),
            "bm25_reranker_nil",
            NIL,
            "NIL",
            0.0,
            tuple(combined),
            "below_nil_threshold",
            retrieval_candidate_ids,
            selection_candidate_ids,
        )
    if top_score - second_score < abstain_margin:
        return Prediction(
            str(row["query_id"]),
            "bm25_reranker_nil",
            ABSTAIN,
            "ABSTAIN",
            0.0,
            tuple(combined),
            "below_abstain_margin",
            retrieval_candidate_ids,
            selection_candidate_ids,
        )
    return Prediction(
        str(row["query_id"]),
        "bm25_reranker_nil",
        combined[0][0],
        "RESOLVED",
        0.0,
        tuple(combined),
        candidate_ids=retrieval_candidate_ids,
        selection_candidate_ids=selection_candidate_ids,
    )


def validate_local_endpoint(endpoint: str, *, allow_configured_remote: bool = False) -> str:
    parsed = urlparse(endpoint)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ResearchBenchmarkError("local LLM endpoint must be HTTP(S)")
    if parsed.hostname not in {"127.0.0.1", "localhost", "::1"} and not allow_configured_remote:
        raise ResearchBenchmarkError(
            "local LLM endpoint must be loopback HTTP(S) unless the configured vLLM endpoint opt-in is explicit"
        )
    return endpoint.rstrip("/")


def _local_llm_prediction(
    row: Mapping[str, Any],
    *,
    endpoint: str,
    model_id: str,
    timeout_sec: float,
    seed: int,
    retrieval_candidate_ids: Sequence[str] = (),
    allow_configured_remote: bool = False,
) -> Prediction:
    endpoint = validate_local_endpoint(endpoint, allow_configured_remote=allow_configured_remote)
    retrieval_ids = tuple(retrieval_candidate_ids) or _retrieval_candidate_ids(row)
    selection_ids = tuple(str(candidate["candidate_id"]) for candidate in row["candidates"])
    candidates = "\n".join(
        f"- {candidate['candidate_id']}: {candidate.get('title', '')} | {', '.join(candidate.get('aliases') or [])} | {candidate.get('text', '')}"
        for candidate in row["candidates"]
    )
    prompt = PROMPT_TEMPLATE.format(query=row["query"], candidates=candidates)
    body = json.dumps(
        {
            "model": model_id,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0,
            "seed": seed,
            "max_tokens": 24,
            # expert_main의 vLLM 계약과 동일하게 reasoning을 끈다. Gemma vLLM은
            # 이 플래그가 없으면 content 대신 reasoning만 채울 수 있다.
            "enable_thinking": False,
            "chat_template_kwargs": {"enable_thinking": False},
        },
        ensure_ascii=False,
    ).encode("utf-8")
    request = urllib.request.Request(f"{endpoint}/v1/chat/completions", data=body, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout_sec) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return Prediction(
            str(row["query_id"]),
            "local_llm",
            None,
            "UNAVAILABLE",
            0.0,
            reason=f"UNAVAILABLE_LOCAL_LLM_RUNTIME:{type(exc).__name__}",
            candidate_ids=retrieval_ids,
            selection_candidate_ids=selection_ids,
            selection_attempted=False,
        )
    answer = str(payload["choices"][0]["message"]["content"]).strip().split()[0]
    allowed = set(selection_ids) | {NIL, ABSTAIN}
    if answer not in allowed:
        return Prediction(
            str(row["query_id"]),
            "local_llm",
            ABSTAIN,
            "ABSTAIN",
            0.0,
            reason="output_outside_candidate_contract",
            candidate_ids=retrieval_ids,
            selection_candidate_ids=selection_ids,
        )
    status = "NIL" if answer == NIL else "ABSTAIN" if answer == ABSTAIN else "RESOLVED"
    return Prediction(
        str(row["query_id"]),
        "local_llm",
        answer,
        status,
        0.0,
        candidate_ids=retrieval_ids,
        selection_candidate_ids=selection_ids,
    )


def run_rows(
    rows: Sequence[Mapping[str, Any]],
    *,
    requested_parallel: int = 16,
    local_llm_endpoint: str | None = None,
    local_llm_model: str | None = None,
    timeout_sec: float = 30.0,
    seed: int = 20260905,
    progress: Callable[[int, int], None] | None = None,
    allow_configured_remote: bool = False,
) -> list[dict[str, Any]]:
    if requested_parallel <= 0:
        raise ResearchBenchmarkError("requested_parallel must be positive")
    worker_count = effective_parallel(requested_parallel, len(rows))
    corpus = build_fixture_corpus(rows)
    corpus_by_id = {str(candidate["candidate_id"]): candidate for candidate in corpus}
    corpus_candidate_ids = tuple(str(candidate["candidate_id"]) for candidate in corpus)
    jobs: list[
        tuple[Mapping[str, Any], str, Callable[[], Prediction], tuple[str, ...], tuple[str, ...]]
    ] = []
    row_by_id: dict[str, Mapping[str, Any]] = {}
    for row in rows:
        query_id = str(row["query_id"])
        if query_id in row_by_id:
            raise ResearchBenchmarkError("query_id must be unique within run_rows")
        row_by_id[query_id] = row
        retrieval_candidate_ids = _retrieval_candidate_ids(row, corpus=corpus)
        local_row = dict(row)
        local_row["candidates"] = [corpus_by_id[candidate_id] for candidate_id in retrieval_candidate_ids]
        jobs.extend(
            [
                (
                    row,
                    "lexical_baseline",
                    lambda row=row: predict_baseline(row, corpus=corpus),
                    retrieval_candidate_ids,
                    corpus_candidate_ids,
                ),
                (
                    row,
                    "bm25_fixture_corpus_retriever",
                    lambda row=row: predict_bm25(row, corpus=corpus),
                    retrieval_candidate_ids,
                    corpus_candidate_ids,
                ),
                (
                    row,
                    "bm25_reranker_nil",
                    lambda row=row: predict_reranker_nil(row, corpus=corpus),
                    retrieval_candidate_ids,
                    corpus_candidate_ids,
                ),
            ]
        )
        if local_llm_endpoint and local_llm_model:
            jobs.append(
                (
                    row,
                    "local_llm",
                    lambda row=local_row, retrieval_candidate_ids=retrieval_candidate_ids: _local_llm_prediction(
                        row,
                        endpoint=local_llm_endpoint,
                        model_id=local_llm_model,
                        timeout_sec=timeout_sec,
                        seed=seed,
                        retrieval_candidate_ids=retrieval_candidate_ids,
                        allow_configured_remote=allow_configured_remote,
                    ),
                    retrieval_candidate_ids,
                    retrieval_candidate_ids,
                )
            )
        else:
            jobs.append(
                (
                    row,
                    "local_llm",
                    lambda row=row, retrieval_candidate_ids=retrieval_candidate_ids: Prediction(
                        str(row["query_id"]),
                        "local_llm",
                        None,
                        "UNAVAILABLE",
                        0.0,
                        reason="UNAVAILABLE_MODEL_WEIGHTS",
                        candidate_ids=retrieval_candidate_ids,
                        selection_candidate_ids=retrieval_candidate_ids,
                        selection_attempted=False,
                    ),
                    retrieval_candidate_ids,
                    retrieval_candidate_ids,
                )
            )
    output: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        futures = {
            executor.submit(
                _timed_prediction,
                str(row["query_id"]),
                arm,
                callback,
                candidate_ids=retrieval_candidate_ids,
                selection_candidate_ids=selection_candidate_ids,
            ): (row, arm)
            for row, arm, callback, retrieval_candidate_ids, selection_candidate_ids in jobs
        }
        for completed, future in enumerate(as_completed(futures), start=1):
            prediction = future.result()
            if prediction.terminal_status not in TERMINAL_STATUSES:
                raise ResearchBenchmarkError("unknown terminal status")
            source_row = row_by_id[prediction.query_id]
            output.append(
                prediction.to_dict(
                    gold_label=str(source_row["gold_label"]),
                    case_type=_row_case_type(source_row),
                    expected_action=_row_expected_action(source_row),
                    partition=_row_partition(source_row),
                )
            )
            if progress:
                progress(completed, len(jobs))
    return sorted(output, key=lambda item: (item["arm"], item["query_id"]))


def _candidate_recall_metrics(values: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    work_truth = [item for item in values if str(item.get("gold_label") or "") != NIL]
    rankable = [
        item
        for item in work_truth
        if isinstance(item.get("candidate_ids"), list) and bool(item.get("candidate_ids"))
    ]
    metrics: dict[str, Any] = {
        "scope": "COMMON_BM25_TOP_K",
        "truth_scope": "WORK_ONLY",
        "observed_denominator": len(rankable),
        "work_truth_denominator": len(work_truth),
    }
    for limit in (1, 3, RETRIEVAL_TOP_K):
        hits = sum(
            str(item.get("gold_label") or "") in (item.get("candidate_ids") or [])[:limit]
            for item in rankable
        )
        metrics[f"recall_at_{limit}"] = {
            "value": hits / len(rankable) if rankable else None,
            "numerator": hits,
            "denominator": len(rankable),
            "status": "DIAGNOSTIC_ONLY" if rankable else "NOT_ESTIMABLE",
        }
    return metrics


def _conditional_selection_metric(values: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    conditioned = [
        item
        for item in values
        if str(item.get("gold_label") or "") != NIL
        and str(item.get("expected_action") or "RESOLVED") == "RESOLVED"
        and item.get("gold_in_selection_candidates") is True
    ]
    observed = [item for item in conditioned if item.get("terminal_status") not in {"UNAVAILABLE", "ERROR"}]
    correct = sum(
        item.get("terminal_status") == "RESOLVED"
        and item.get("predicted_label") == item.get("gold_label")
        for item in observed
    )
    return {
        "scope": "WORK_WITH_GOLD_IN_SELECTION_CANDIDATES",
        "value": correct / len(observed) if observed else None,
        "numerator": correct,
        "denominator": len(conditioned),
        "observed_denominator": len(observed),
        "operational_worst_case": {
            "value": correct / len(conditioned) if conditioned else None,
            "numerator": correct,
            "denominator": len(conditioned),
            "status": "ACCOUNTING_ONLY_WORST_CASE" if conditioned else "NOT_ESTIMABLE",
        },
        "status": "DIAGNOSTIC_ONLY" if observed else "NOT_ESTIMABLE_MODEL_UNAVAILABLE",
    }


def summarize(rows: Sequence[Mapping[str, Any]], *, include_partitions: bool = True) -> dict[str, Any]:
    by_arm: dict[str, list[Mapping[str, Any]]] = {}
    for row in rows:
        by_arm.setdefault(str(row["arm"]), []).append(row)
    metrics: dict[str, Any] = {}
    for arm, values in sorted(by_arm.items()):
        denominator = len(values)
        correct = sum(item.get("correct") is True for item in values)
        status_counts = Counter(str(item.get("terminal_status")) for item in values)
        latencies = sorted(
            float(item.get("latency_ms") or 0.0)
            for item in values
            if item.get("terminal_status") != "UNAVAILABLE"
        )
        evaluable = [item for item in values if item.get("terminal_status") in {"RESOLVED", "NIL"}]
        evaluable_correct = sum(item.get("correct") is True for item in evaluable)
        work_truth = [item for item in values if item.get("gold_label") != NIL]
        nil_truth = [item for item in values if item.get("gold_label") == NIL]
        predicted_nil = [item for item in values if item.get("predicted_label") == NIL]
        true_nil = sum(item.get("gold_label") == NIL and item.get("predicted_label") == NIL for item in values)
        rankable_work = [item for item in work_truth if item.get("scores")]
        reciprocal_ranks: list[float] = []
        for item in rankable_work:
            ranking = [score.get("candidate_id") for score in item.get("scores") or []]
            if item.get("gold_label") in ranking:
                reciprocal_ranks.append(1.0 / (ranking.index(item["gold_label"]) + 1))
            else:
                reciprocal_ranks.append(0.0)

        def percentile(fraction: float) -> float:
            if not latencies:
                return 0.0
            index = min(len(latencies) - 1, math.ceil(fraction * len(latencies)) - 1)
            return latencies[index]

        quality_estimable = bool(evaluable)
        metrics[arm] = {
            "denominator": denominator,
            "correct": correct,
            "accuracy": correct / denominator if quality_estimable else None,
            "accuracy_status": "ESTIMATED_RESEARCH_FIXTURE" if quality_estimable else "NOT_ESTIMABLE_MODEL_UNAVAILABLE",
            "operational_accuracy": {
                "value": correct / denominator if denominator else None,
                "numerator": correct,
                "denominator": denominator,
                "status": "ACCOUNTING_ONLY_WORST_CASE" if not quality_estimable else "ESTIMATED_RESEARCH_FIXTURE",
            },
            "evaluable_only_accuracy": {
                "value": evaluable_correct / len(evaluable) if evaluable else None,
                "numerator": evaluable_correct,
                "denominator": len(evaluable),
                "status": "DIAGNOSTIC_ONLY" if evaluable else "NOT_ESTIMABLE",
            },
            "terminal_status_counts": {status: status_counts.get(status, 0) for status in sorted(TERMINAL_STATUSES)},
            "coverage": {
                "value": len(evaluable) / denominator if denominator else None,
                "numerator": len(evaluable),
                "denominator": denominator,
                "status": "ESTIMATED_RESEARCH_FIXTURE" if denominator else "NOT_ESTIMABLE",
            },
            "case_type_counts": dict(
                sorted(
                    Counter(
                        str(item.get("case_type") or _default_case_type(str(item.get("gold_label") or "")))
                        for item in values
                    ).items()
                )
            ),
            "expected_action_counts": dict(
                sorted(
                    Counter(
                        str(
                            item.get("expected_action")
                            or _default_expected_action(
                                str(item.get("case_type") or _default_case_type(str(item.get("gold_label") or ""))),
                                str(item.get("gold_label") or ""),
                            )
                        )
                        for item in values
                    ).items()
                )
            ),
            "failure_stage_counts": dict(
                sorted(Counter(str(item.get("failure_stage") or "UNCLASSIFIED_LEGACY") for item in values).items())
            ),
            "candidate_recall": _candidate_recall_metrics(values),
            "conditional_selection": _conditional_selection_metric(values),
            "closed_candidate_ranking": {
                "scope": "FIXTURE_CORPUS_RETRIEVAL_NOT_EXTERNAL_OPEN_CORPUS",
                "hit_at_1": {
                    "value": sum(item.get("predicted_label") == item.get("gold_label") for item in rankable_work) / len(rankable_work) if rankable_work else None,
                    "numerator": sum(item.get("predicted_label") == item.get("gold_label") for item in rankable_work),
                    "denominator": len(rankable_work),
                    "status": "DIAGNOSTIC_ONLY" if rankable_work else "NOT_ESTIMABLE",
                },
                "mrr": {
                    "value": sum(reciprocal_ranks) / len(reciprocal_ranks) if reciprocal_ranks else None,
                    "denominator": len(reciprocal_ranks),
                    "status": "DIAGNOSTIC_ONLY" if reciprocal_ranks else "NOT_ESTIMABLE",
                },
                "hit_at_3": {
                    "value": sum(
                        item.get("gold_label") in [score.get("candidate_id") for score in (item.get("scores") or [])[:3]]
                        for item in rankable_work
                    ) / len(rankable_work) if rankable_work else None,
                    "numerator": sum(
                        item.get("gold_label") in [score.get("candidate_id") for score in (item.get("scores") or [])[:3]]
                        for item in rankable_work
                    ),
                    "denominator": len(rankable_work),
                    "status": "DIAGNOSTIC_ONLY" if rankable_work else "NOT_ESTIMABLE",
                },
            },
            "nil_precision": {
                "value": true_nil / len(predicted_nil) if predicted_nil else None,
                "numerator": true_nil,
                "denominator": len(predicted_nil),
                "status": "DIAGNOSTIC_ONLY" if quality_estimable else "NOT_ESTIMABLE_MODEL_UNAVAILABLE",
            },
            "nil_recall": {
                "value": true_nil / len(nil_truth) if nil_truth and quality_estimable else None,
                "numerator": true_nil,
                "denominator": len(nil_truth) if quality_estimable else 0,
                "operational_worst_case_denominator": len(nil_truth),
                "status": "DIAGNOSTIC_ONLY" if quality_estimable else "NOT_ESTIMABLE_MODEL_UNAVAILABLE",
            },
            "latency": {
                "mean_ms": sum(latencies) / len(latencies) if latencies else None,
                "p50_ms": percentile(0.50) if latencies else None,
                "p95_ms": percentile(0.95) if latencies else None,
                "observed_denominator": len(latencies),
                "status": "OBSERVED" if latencies else "NOT_ESTIMABLE",
            },
        }
    baseline = metrics.get("lexical_baseline", {}).get("accuracy")
    comparisons: dict[str, Any] = {}
    for arm, values in metrics.items():
        if arm == "lexical_baseline":
            continue
        evaluable_denominator = values["evaluable_only_accuracy"]["denominator"]
        if evaluable_denominator == 0 or baseline is None:
            comparisons[arm] = {"accuracy_delta_vs_lexical_baseline": None, "status": "NOT_ESTIMABLE"}
        else:
            comparisons[arm] = {
                "accuracy_delta_vs_lexical_baseline": values["accuracy"] - baseline,
                "status": "ESTIMATED_RESEARCH_FIXTURE",
            }
    result: dict[str, Any] = {
        "diagnostic_schema_version": DIAGNOSTIC_SCHEMA_VERSION,
        "arms": metrics,
        "comparisons": comparisons,
        "case_type_counts": dict(
            sorted(
                Counter(
                    str(item.get("case_type") or _default_case_type(str(item.get("gold_label") or "")))
                    for item in rows
                ).items()
            )
        ),
        "expected_action_counts": dict(
            sorted(
                Counter(
                    str(
                        item.get("expected_action")
                        or _default_expected_action(
                            str(item.get("case_type") or _default_case_type(str(item.get("gold_label") or ""))),
                            str(item.get("gold_label") or ""),
                        )
                    )
                    for item in rows
                ).items()
            )
        ),
        "failure_stage_counts": dict(
            sorted(Counter(str(item.get("failure_stage") or "UNCLASSIFIED_LEGACY") for item in rows).items())
        ),
        "denominator_policy": "ERROR/UNAVAILABLE/ABSTAIN/NIL을 포함한 모든 입력 행",
    }
    if include_partitions:
        by_partition: dict[str, list[Mapping[str, Any]]] = {}
        for row in rows:
            by_partition.setdefault(str(row.get("partition") or "default"), []).append(row)
        result["partitions"] = {
            partition: summarize(values, include_partitions=False)
            for partition, values in sorted(by_partition.items())
        }
    return result


def validate_terminal_manifest(manifest_path: Path, *, research_root: Path) -> dict[str, Any]:
    """독립 read-only terminal validator used by tests and review tooling."""

    manifest_path = manifest_path.resolve()
    root = research_root.resolve()
    if root not in manifest_path.parents:
        raise ResearchBenchmarkError("terminal manifest is outside research namespace")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict) or manifest.get("schema_version") != SCHEMA_VERSION:
        raise ResearchBenchmarkError("terminal manifest schema mismatch")
    stored_hash = manifest.get("manifest_sha256")
    payload = {key: value for key, value in manifest.items() if key != "manifest_sha256"}
    if not isinstance(stored_hash, str) or stored_hash != sha256_value(payload):
        raise ResearchBenchmarkError("terminal manifest self hash mismatch")
    required_boundary = {
        "claim_level": "RESEARCH_EVIDENCE_ONLY",
        "publication_mode": "OFFLINE_SHADOW",
        "p0_authority_claimed": False,
        "production_authority_claimed": False,
        "full_scan_approval": False,
        "central_slang_db_write": False,
    }
    if any(manifest.get(key) != expected for key, expected in required_boundary.items()):
        raise ResearchBenchmarkError("research authority boundary mismatch")
    benchmark_count = int(manifest.get("benchmark_input_count") or 0)
    requested = int(manifest.get("requested_parallel") or 0)
    partition_counts = manifest.get("benchmark_input_counts_by_partition")
    if partition_counts is not None:
        if (
            not isinstance(partition_counts, dict)
            or any(not isinstance(value, int) or value < 0 for value in partition_counts.values())
            or sum(partition_counts.values()) != benchmark_count
        ):
            raise ResearchBenchmarkError("partition input count mismatch")
        manifest_partition = manifest.get("partition")
        if manifest_partition is not None and partition_counts.get(str(manifest_partition)) != benchmark_count:
            raise ResearchBenchmarkError("manifest partition count mismatch")
    if manifest.get("effective_parallel") != effective_parallel(requested, benchmark_count):
        raise ResearchBenchmarkError("effective parallel mismatch")
    if manifest.get("parallel_policy") != "effective_parallel=min(requested_parallel,benchmark_input_count)":
        raise ResearchBenchmarkError("parallel policy mismatch")
    dashboard = manifest.get("dashboard")
    if not isinstance(dashboard, dict) or dashboard.get("enabled") is not True or dashboard.get("status") != "CONNECTED":
        raise ResearchBenchmarkError("dashboard boundary mismatch")
    for phase in ("preflight", "postflight"):
        receipt = dashboard.get(f"{phase}_receipt")
        if not isinstance(receipt, dict) or receipt.get("ok") is not True or receipt.get("standalone") is not True:
            raise ResearchBenchmarkError(f"dashboard {phase} receipt mismatch")
        if dashboard.get(f"{phase}_response_sha256") != sha256_value(receipt):
            raise ResearchBenchmarkError(f"dashboard {phase} receipt hash mismatch")
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, dict):
        raise ResearchBenchmarkError("artifact inventory missing")
    loaded: dict[str, Any] = {}
    for name in ("input", "predictions", "metrics", "report_ko"):
        ref = artifacts.get(name)
        if not isinstance(ref, dict):
            raise ResearchBenchmarkError(f"artifact ref missing: {name}")
        path = Path(str(ref.get("path") or "")).resolve()
        if name != "input" and root not in path.parents:
            raise ResearchBenchmarkError(f"generated artifact outside research namespace: {name}")
        if not path.is_file() or ref.get("bytes") != path.stat().st_size or ref.get("sha256") != sha256_file(path):
            raise ResearchBenchmarkError(f"artifact integrity mismatch: {name}")
        if name == "input":
            loaded["input_path"] = path
        elif name in {"predictions", "metrics"}:
            loaded[name] = json.loads(path.read_text(encoding="utf-8"))
    predictions = loaded["predictions"]
    metrics = loaded["metrics"]
    if not isinstance(metrics, dict):
        raise ResearchBenchmarkError("metrics artifact must be an object")
    if (
        not isinstance(predictions, list)
        or any(not isinstance(item, dict) for item in predictions)
        or manifest.get("completed_count") != len(predictions)
        or manifest.get("job_count") != len(predictions)
    ):
        raise ResearchBenchmarkError("terminal prediction count mismatch")
    statuses = Counter(str(item.get("terminal_status")) for item in predictions if isinstance(item, dict))
    expected_statuses = {status: statuses.get(status, 0) for status in ("RESOLVED", "NIL", "ABSTAIN", "UNAVAILABLE", "ERROR")}
    if manifest.get("terminal_status_counts") != expected_statuses or sum(expected_statuses.values()) != len(predictions):
        raise ResearchBenchmarkError("terminal status conservation mismatch")
    input_rows = load_and_validate_fixture(loaded["input_path"])
    if len(input_rows) != benchmark_count:
        raise ResearchBenchmarkError("input fixture count mismatch")
    input_by_id = {str(row["query_id"]): row for row in input_rows}
    configured_arms = (
        manifest.get("config", {}).get("arms")
        if isinstance(manifest.get("config"), dict)
        else None
    )
    arm_names = (
        [str(arm) for arm in configured_arms]
        if isinstance(configured_arms, list) and configured_arms
        else sorted(str(arm) for arm in metrics.get("arms", {}))
    )
    expected_pairs = {(arm, query_id) for arm in arm_names for query_id in input_by_id}
    actual_pairs = {(str(item.get("arm")), str(item.get("query_id"))) for item in predictions}
    if len(actual_pairs) != len(predictions) or actual_pairs != expected_pairs:
        raise ResearchBenchmarkError("prediction arm/query coverage mismatch")
    for item in predictions:
        query_id = str(item.get("query_id") or "")
        source = input_by_id.get(query_id)
        if source is None or str(item.get("gold_label") or "") != str(source["gold_label"]):
            raise ResearchBenchmarkError("prediction gold binding mismatch")
        expected_case_type = _row_case_type(source)
        expected_action = _row_expected_action(source)
        if "case_type" in item and item.get("case_type") != expected_case_type:
            raise ResearchBenchmarkError("prediction case_type mismatch")
        if "expected_action" in item and item.get("expected_action") != expected_action:
            raise ResearchBenchmarkError("prediction expected_action mismatch")
        selection_ids = item.get("selection_candidate_ids")
        retrieval_ids = item.get("candidate_ids")
        if selection_ids is not None and (
            not isinstance(selection_ids, list)
            or any(not isinstance(value, str) for value in selection_ids)
        ):
            raise ResearchBenchmarkError("selection candidate trace is invalid")
        if retrieval_ids is not None and (
            not isinstance(retrieval_ids, list)
            or any(not isinstance(value, str) for value in retrieval_ids)
        ):
            raise ResearchBenchmarkError("retrieval candidate trace is invalid")
        if isinstance(selection_ids, list):
            expected_selection_hit = str(source["gold_label"]) in selection_ids if selection_ids else None
            for key in ("gold_in_selection_candidates", "gold_in_candidate_set"):
                if key in item and item.get(key) != expected_selection_hit:
                    raise ResearchBenchmarkError(f"prediction {key} mismatch")
        if isinstance(retrieval_ids, list) and "gold_in_retrieval_top_k" in item:
            expected_retrieval_hit = str(source["gold_label"]) in retrieval_ids if retrieval_ids else None
            if item.get("gold_in_retrieval_top_k") != expected_retrieval_hit:
                raise ResearchBenchmarkError("prediction retrieval hit mismatch")
        if "correct" in item:
            expected_correct = (
                str(item.get("terminal_status")) in {"RESOLVED", "NIL"}
                and item.get("predicted_label") == source["gold_label"]
            )
            if item.get("correct") is not expected_correct:
                raise ResearchBenchmarkError("prediction correctness mismatch")
        if "action_correct" in item:
            expected_action_correct = _action_correct(
                predicted_label=item.get("predicted_label"),
                terminal_status=str(item.get("terminal_status")),
                gold_label=str(source["gold_label"]),
                expected_action=expected_action,
            )
            if item.get("action_correct") is not expected_action_correct:
                raise ResearchBenchmarkError("prediction action correctness mismatch")
        if "failure_stage" in item:
            if item.get("selection_attempted") is not None and not isinstance(item.get("selection_attempted"), bool):
                raise ResearchBenchmarkError("prediction selection_attempted must be boolean")
            expected_failure_stage = _failure_stage(
                predicted_label=item.get("predicted_label"),
                terminal_status=str(item.get("terminal_status")),
                gold_label=str(source["gold_label"]),
                expected_action=expected_action,
                selection_candidate_ids=selection_ids or [],
                selection_attempted=bool(item.get("selection_attempted", True)),
            )
            if item.get("failure_stage") != expected_failure_stage:
                raise ResearchBenchmarkError("prediction failure stage mismatch")
    if manifest.get("metrics_sha256") != sha256_value(metrics):
        raise ResearchBenchmarkError("metrics semantic hash mismatch")
    semantic = [{key: value for key, value in item.items() if key != "latency_ms"} for item in predictions]
    if manifest.get("semantic_output_sha256") != sha256_value(semantic):
        raise ResearchBenchmarkError("prediction semantic hash mismatch")
    for arm, values in metrics.get("arms", {}).items():
        if values.get("denominator") != benchmark_count:
            raise ResearchBenchmarkError(f"arm denominator mismatch: {arm}")
        if sum(values.get("terminal_status_counts", {}).values()) != benchmark_count:
            raise ResearchBenchmarkError(f"arm status conservation mismatch: {arm}")
    return manifest


def prompt_sha256() -> str:
    return hashlib.sha256(PROMPT_TEMPLATE.encode("utf-8")).hexdigest()
