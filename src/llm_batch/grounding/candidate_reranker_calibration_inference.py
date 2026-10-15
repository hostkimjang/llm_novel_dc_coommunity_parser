"""새 입력의 고정 R2 사건 점수에 CAL 온도를 적용한다. 평가 split은 배정하지 않는다.

이 순수 소비자는 capture와 모델/CAL 지문의 구조적 결속을 검산한다. 실제
고정 모델의 수치 재생과 현재 실행/저장 결속은 runtime 소비자가 담당한다.
확률은 고정 corpus의 반환 후보와 NIL에 한정되며 실제 정확도 보증이 아니다.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import re

from .candidate_reranker_capture import canonical_bytes, canonical_sha256
from .candidate_reranker_inference_graph import validate_inference_graph
from .candidate_reranker_event_bridge import _model, _scores
from .candidate_reranker_calibration import _manifest, _policy
from .candidate_set_calibration_shadow import (
    CalibrationArtifact, CalibrationFitReceipt, PROBABILITY_SCALE, _probability_masses,
)
from .candidate_set_shadow import (
    NIL_LABEL, SHADOW_ACTION_ABSTAIN, SHADOW_ACTION_ASSERT_NIL, SHADOW_ACTION_RESOLVE,
)

SCHEMA = "candidate_inference_temperature_receipt_v1"
POLICY_SCHEMA = "candidate_inference_temperature_policy_v1"
SCOPE = "GENERAL_INPUT_SHADOW"
MAX_BYTES = 16 * 1024 * 1024
_CODE = re.compile(r"[A-Z0-9_]{1,96}\Z")


class InferenceCalibrationError(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def _require(condition, code):
    if not condition:
        raise InferenceCalibrationError(code)


def _copy(value):
    raw = canonical_bytes(value)
    _require(len(raw) <= MAX_BYTES, "INFERENCE_CALIBRATION_BYTE_LIMIT")
    return json.loads(raw)


def _seal(value):
    return {**value, "receipt_sha256": canonical_sha256(value)}


def _receipt(summary, *, graph=None, status="NOT_AVAILABLE", reasons=()):
    graph = graph or {}
    return {"schema_version": SCHEMA, "mode": "SHADOW", "scope": SCOPE,
        "status": status, "reason_codes": list(reasons), "post_id": graph.get("post_id"),
        **{k: summary[k] for k in ("calibration_artifact_sha256", "calibration_manifest_sha256",
            "training_split_manifest_sha256", "scorer_summary_sha256", "model_sha256",
            "base_model_sha256", "scorer_sha256", "data_kind", "temperature", "policy_sha256")},
        "graph_sha256": graph.get("graph_sha256"), "capture_sha256": graph.get("capture_sha256"),
        "raw_receipt_sha256": graph.get("raw_receipt_sha256"),
        "semantic_input_sha256": graph.get("semantic_input_sha256"),
        "corpus_sha256": graph.get("corpus_sha256"),
        "probability_scope": "BOUNDED_PINNED_R2_CORPUS",
        "score_provenance": "CAPTURE_STRUCTURAL_BINDING_RUNTIME_REPLAY_REQUIRED",
        "event_probabilities": None, "selected_label": None, "selected_error_probability": None,
        "nil_probability": None, "action": SHADOW_ACTION_ABSTAIN,
        "truth_status": "UNJUDGED_NOT_ASSIGNED", "evaluation_split": None,
        "actual_quality_evaluated": False, "publication_authority": False,
        "public_apply": False, "central_db_write": False, "action_applied": False,
        "operational_effect": "NONE_SHADOW_ONLY"}


@dataclass(frozen=True, slots=True)
class FrozenInferenceCalibration:
    _summary_json: bytes
    _scorer_summary_json: bytes

    def summary(self):
        return json.loads(self._summary_json)

    def apply(self, graph, *, capture, corpus_snapshot, source_payloads):
        """검산된 고정 온도만 사용한다. fit/optimizer/파일/네트워크 호출은 없다."""
        summary = self.summary()
        checked = None
        try:
            checked = validate_inference_graph(graph, capture=capture,
                corpus_snapshot=corpus_snapshot, source_payloads=source_payloads)
            _require(canonical_bytes(checked["scorer_summary"]) == self._scorer_summary_json,
                     "INFERENCE_SCORER_MISMATCH")
            if checked["status"] != "COMPLETE":
                return _seal(_receipt(summary, graph=checked, reasons=checked["reason_codes"]))
            proof = checked["generation_proof"]
            _require(1 <= len(checked["candidates"]) <= 20
                and proof["positive_candidates"] == proof["returned_candidates"] == len(checked["candidates"])
                and proof["omitted_ranked_candidates"] == 0, "INFERENCE_CANDIDATE_UNIVERSE_INCOMPLETE")
            scores = _scores(capture["raw_receipt"], capture["frozen_view"], checked["scorer_summary"],
                             capture.get("semantic_input"))
            labels = [c["candidate_id"] for c in checked["candidates"]] + [NIL_LABEL]
            _require(checked["labels"] == labels and checked["raw_scores"] == [scores[x] for x in labels],
                     "INFERENCE_EVENT_SPACE_MISMATCH")
            masses = _probability_masses(checked["raw_scores"], summary["temperature"])
            chosen = max(range(len(masses)), key=lambda i: (masses[i], -i))
            label, error = labels[chosen], (PROBABILITY_SCALE - masses[chosen]) / PROBABILITY_SCALE
            reasons = ["FIXED_CAL_TEMPERATURE_APPLIED", "NEW_INPUT_NOT_EVALUATION_ASSIGNMENT"]
            if error > summary["selector_max_error_probability"]:
                action = SHADOW_ACTION_ABSTAIN
                reasons.append("SELECTIVE_RISK_THRESHOLD_REQUIRES_ABSTAIN")
            elif label == NIL_LABEL and masses[chosen] / PROBABILITY_SCALE < summary["nil_min_probability"]:
                action = SHADOW_ACTION_ABSTAIN
                reasons.append("NIL_THRESHOLD_REQUIRES_ABSTAIN")
            else:
                action = SHADOW_ACTION_ASSERT_NIL if label == NIL_LABEL else SHADOW_ACTION_RESOLVE
            value = _receipt(summary, graph=checked, status="TEMPERATURE_APPLIED_BOUND_INFERENCE", reasons=reasons)
            value.update(event_probabilities=[{"label": x, "probability_mass": m,
                "probability_scale": PROBABILITY_SCALE, "probability": m / PROBABILITY_SCALE}
                for x, m in zip(labels, masses)], selected_label=label, selected_error_probability=error,
                nil_probability=masses[-1] / PROBABILITY_SCALE, action=action)
            return _seal(value)
        except Exception as exc:
            code = getattr(exc, "code", str(exc))
            if type(code) is not str or not _CODE.fullmatch(code):
                code = "INFERENCE_CALIBRATION_VALIDATION_FAILED"
            return _seal(_receipt(summary, graph=checked, reasons=[code]))


def prepare_inference_calibration(*, scorer_summary, artifact, calibration_manifest, policy):
    """실제 CAL 학습 근거를 한 번 재생 검산하고 모델·정책을 불변으로 고정한다."""
    summary = _copy(scorer_summary)
    # TRAIN의 내용을 재구성하거나 새 입력에 assignment를 발명하지 않는다.
    # 실제 고정 모델 로딩은 runtime 책임이며 여기서는 그 summary 계약을 검사한다.
    _model(summary, canonical_sha256(summary), {"manifest_sha256": summary.get("training_split_manifest_sha256"),
                                               "data_kind": summary.get("data_kind")})
    raw = _copy(artifact.to_dict() if isinstance(artifact, CalibrationArtifact) else artifact)
    _require(raw.get("schema_version") == "candidate_set_calibration_artifact_v2", "LEARNED_CALIBRATION_V2_REQUIRED")
    try:
        fitted = CalibrationArtifact(**{**raw, "fit_receipt": CalibrationFitReceipt(**raw["fit_receipt"])})
        manifest, frozen_policy = _manifest(calibration_manifest), _policy(policy)
        fitted.validate_against(manifest, frozen_policy)
    except (TypeError, ValueError, KeyError) as exc:
        raise InferenceCalibrationError("FITTED_CALIBRATION_INVALID") from exc
    binding = {"training_split_manifest_sha256": summary["training_split_manifest_sha256"],
        "calibration_manifest_sha256": manifest.manifest_sha256, "scorer_fingerprint": summary["scorer_sha256"],
        "scorer_summary_sha256": canonical_sha256(summary), "model_sha256": summary["model_sha256"],
        "base_model_sha256": summary["candidate_ranker_model_sha256"], "data_kind": summary["data_kind"]}
    _require(canonical_bytes(raw["fit_receipt"]["learning_evidence"]["binding"]) == canonical_bytes(binding),
             "ARTIFACT_MODEL_BINDING_MISMATCH")
    value = {"schema_version": POLICY_SCHEMA, "mode": "SHADOW", "scope": SCOPE, "status": "AVAILABLE",
        "reason_codes": [], "calibration_artifact_sha256": fitted.artifact_sha256,
        "calibration_manifest_sha256": manifest.manifest_sha256,
        "training_split_manifest_sha256": summary["training_split_manifest_sha256"],
        "scorer_summary_sha256": canonical_sha256(summary), "model_sha256": summary["model_sha256"],
        "base_model_sha256": summary["candidate_ranker_model_sha256"], "scorer_sha256": summary["scorer_sha256"],
        "data_kind": summary["data_kind"], "temperature": fitted.temperature,
        "selector_max_error_probability": frozen_policy.selector_max_error_probability,
        "nil_min_probability": frozen_policy.nil_min_probability,
        "evaluation_split": None, "actual_quality_evaluated": False, "publication_authority": False,
        "public_apply": False, "central_db_write": False, "action_applied": False}
    value["policy_sha256"] = canonical_sha256(value)
    return FrozenInferenceCalibration(canonical_bytes(value), canonical_bytes(summary))
