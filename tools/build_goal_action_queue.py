from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return payload


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_no, raw_line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        payload = json.loads(line)
        if not isinstance(payload, dict):
            raise ValueError(f"Expected JSON object at {path}:{line_no}")
        rows.append(payload)
    return rows


def _item(
    *,
    action_id: str,
    priority: str,
    title: str,
    status: str,
    evidence: Any,
    next_step: str,
    owner_mode: str,
    requires_completed_source: bool = False,
    executable_now: bool = True,
    requires_browser_visual: bool = False,
    approval_blocker: bool = False,
    related_gate: str = "",
) -> dict[str, Any]:
    return {
        "action_id": action_id,
        "priority": priority,
        "title": title,
        "status": status,
        "owner_mode": owner_mode,
        "executable_now": executable_now,
        "requires_completed_source": requires_completed_source,
        "requires_browser_visual": requires_browser_visual,
        "approval_blocker": approval_blocker,
        "related_gate": related_gate,
        "evidence": evidence,
        "next_step": next_step,
    }


def _safe_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _semantic_coverage_evidence(semantic_coverage_audit: dict[str, Any] | None) -> dict[str, Any]:
    if not semantic_coverage_audit:
        return {}
    issues = semantic_coverage_audit.get("issues") or []
    return {
        "gate": semantic_coverage_audit.get("gate"),
        "semantic_approval": (semantic_coverage_audit.get("semantic_approval") or {}).get("status"),
        "coverage": semantic_coverage_audit.get("coverage") or {},
        "issue_counts": {
            str(item.get("code")): item.get("count")
            for item in issues
            if item.get("code")
        },
    }


def _process_snapshot_evidence(process_snapshot_audit: dict[str, Any] | None) -> dict[str, Any]:
    if not process_snapshot_audit:
        return {}
    snapshot = process_snapshot_audit.get("process_snapshot") or {}
    gate = process_snapshot_audit.get("gate") or {}
    return {
        "runtime_contract": gate.get("runtime_contract"),
        "snapshot_available": snapshot.get("available"),
        "snapshot_source": snapshot.get("source"),
        "patterns": snapshot.get("patterns"),
        "matching_process_count": snapshot.get("matching_process_count"),
        "stale_process_candidate_count": snapshot.get("stale_process_candidate_count"),
        "error": snapshot.get("error"),
    }


def _hardcoded_alias_evidence(hardcoded_alias_audit: dict[str, Any] | None) -> dict[str, Any]:
    if not hardcoded_alias_audit:
        return {}
    gate = hardcoded_alias_audit.get("gate") or {}
    blockers = hardcoded_alias_audit.get("positive_hardcoded_alias_blockers") or []
    return {
        "semantic_approval": gate.get("semantic_approval"),
        "registry_count": hardcoded_alias_audit.get("registry_count"),
        "risk_class_counts": hardcoded_alias_audit.get("risk_class_counts") or {},
        "gate_status_counts": hardcoded_alias_audit.get("gate_status_counts") or {},
        "positive_hardcoded_alias_blocker_count": gate.get("positive_hardcoded_alias_blocker_count"),
        "quarantine_only_count": gate.get("quarantine_only_count"),
        "top_positive_blockers": [
            {
                "registry_name": item.get("registry_name"),
                "file": item.get("file"),
                "line": item.get("line"),
                "gate_status": item.get("gate_status"),
                "usage_kind_counts": item.get("usage_kind_counts") or {},
            }
            for item in blockers[:8]
        ],
    }


def _hardcoded_alias_packet_evidence(
    hardcoded_alias_packet_review: dict[str, Any] | None,
) -> dict[str, Any]:
    if not hardcoded_alias_packet_review:
        return {}
    summary = hardcoded_alias_packet_review.get("summary") or {}
    return {
        "gate": summary.get("gate"),
        "semantic_approval": summary.get("semantic_approval"),
        "packet_coverage": summary.get("packet_coverage"),
        "scanned_files": summary.get("scanned_files"),
        "scanned_records": summary.get("scanned_records"),
        "matched_packets": summary.get("matched_packets"),
        "unique_registry_match_count": summary.get("unique_registry_match_count"),
        "unique_post_context_registry_match_count": summary.get(
            "unique_post_context_registry_match_count"
        ),
        "unique_decision_context_only_registry_match_count": summary.get(
            "unique_decision_context_only_registry_match_count"
        ),
        "unique_context_only_registry_match_count": summary.get(
            "unique_context_only_registry_match_count"
        ),
        "registry_match_counts": summary.get("registry_match_counts") or {},
        "post_context_registry_match_counts": summary.get("post_context_registry_match_counts") or {},
        "decision_context_only_registry_match_counts": (
            summary.get("decision_context_only_registry_match_counts") or {}
        ),
        "context_only_registry_match_counts": summary.get("context_only_registry_match_counts") or {},
        "marker_hit_counts": summary.get("marker_hit_counts") or {},
    }


def _hardcoded_alias_packet_label_evidence(
    hardcoded_alias_packet_labels: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    if not hardcoded_alias_packet_labels:
        return {}
    label_counts: dict[str, int] = {}
    semantic_counts: dict[str, int] = {}
    action_counts: dict[str, int] = {}
    risk_counts: dict[str, int] = {}
    for item in hardcoded_alias_packet_labels:
        label = str(item.get("review_label") or "UNKNOWN")
        semantic = str(item.get("semantic_decision_quality") or "UNKNOWN")
        label_counts[label] = label_counts.get(label, 0) + 1
        semantic_counts[semantic] = semantic_counts.get(semantic, 0) + 1
        actions = item.get("action") or []
        if isinstance(actions, str):
            actions = [actions]
        for action in actions:
            action_key = str(action)
            action_counts[action_key] = action_counts.get(action_key, 0) + 1
        for risk in item.get("risk_tags") or []:
            risk_key = str(risk)
            risk_counts[risk_key] = risk_counts.get(risk_key, 0) + 1
    reject_count = label_counts.get("REJECT", 0)
    hold_count = label_counts.get("HOLD", 0)
    gate = "REVIEW" if reject_count or hold_count else "GO"
    return {
        "gate": gate,
        "semantic_approval": "not_granted_by_packet_label_review",
        "reviewed_packets": len(hardcoded_alias_packet_labels),
        "label_counts": dict(sorted(label_counts.items())),
        "semantic_decision_quality_counts": dict(sorted(semantic_counts.items())),
        "action_counts": dict(sorted(action_counts.items())),
        "risk_tag_counts": dict(sorted(risk_counts.items())),
        "reject_count": reject_count,
        "hold_count": hold_count,
        "sample_rejects": [
            {
                "review_id": item.get("review_id"),
                "source_packet_id": item.get("source_packet_id"),
                "post_id": item.get("post_id"),
                "resolved_title": item.get("resolved_title"),
                "rationale_ko": item.get("rationale_ko"),
            }
            for item in hardcoded_alias_packet_labels
            if item.get("review_label") == "REJECT"
        ][:5],
    }


def _packet_review_closed_by_labels(
    hardcoded_alias_packet: dict[str, Any],
    hardcoded_alias_packet_labels_evidence: dict[str, Any],
) -> bool:
    if not hardcoded_alias_packet or not hardcoded_alias_packet_labels_evidence:
        return False
    if hardcoded_alias_packet_labels_evidence.get("gate") != "GO":
        return False
    if _safe_int(hardcoded_alias_packet_labels_evidence.get("reject_count")):
        return False
    if _safe_int(hardcoded_alias_packet_labels_evidence.get("hold_count")):
        return False
    matched_packets = _safe_int(
        hardcoded_alias_packet.get("unique_post_context_registry_match_count")
    )
    if matched_packets <= 0:
        matched_packets = _safe_int(hardcoded_alias_packet.get("matched_packets"))
    reviewed_packets = _safe_int(hardcoded_alias_packet_labels_evidence.get("reviewed_packets"))
    if matched_packets <= 0:
        return False
    return reviewed_packets >= matched_packets


def build_action_queue(
    state_map: dict[str, Any],
    *,
    semantic_coverage_audit: dict[str, Any] | None = None,
    process_snapshot_audit: dict[str, Any] | None = None,
    hardcoded_alias_audit: dict[str, Any] | None = None,
    hardcoded_alias_packet_review: dict[str, Any] | None = None,
    hardcoded_alias_packet_labels: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    gates = state_map.get("gates") or {}
    original = state_map.get("original_run") or {}
    source_policy = state_map.get("source_review_policy") or {}
    random_baseline = source_policy.get("random_baseline") or {}
    runtime = state_map.get("small_run_runtime_audit") or {}
    hygiene = state_map.get("reason_hygiene_scan") or {}
    blockers = state_map.get("critical_blockers") or []
    semantic_coverage = _semantic_coverage_evidence(semantic_coverage_audit)
    process_snapshot = _process_snapshot_evidence(process_snapshot_audit)
    hardcoded_alias = _hardcoded_alias_evidence(hardcoded_alias_audit)
    hardcoded_alias_packet = _hardcoded_alias_packet_evidence(hardcoded_alias_packet_review)
    hardcoded_alias_packet_labels_evidence = _hardcoded_alias_packet_label_evidence(
        hardcoded_alias_packet_labels
    )
    hardcoded_alias_packet_closed_by_labels = _packet_review_closed_by_labels(
        hardcoded_alias_packet,
        hardcoded_alias_packet_labels_evidence,
    )

    items: list[dict[str, Any]] = []
    partial_signals = original.get("partial_signals") or []
    if partial_signals:
        items.append(
            _item(
                action_id="obtain_completed_vlm_ocr_source",
                priority="P0",
                title="완료된 VLM/OCR-on source 확보",
                status="blocked_until_new_run_or_completed_artifact",
                owner_mode="RUN_REVIEW_MODE",
                executable_now=False,
                requires_completed_source=True,
                approval_blocker=True,
                related_gate="original_source_approval",
                evidence={
                    "counts": {
                        "input_post_count": original.get("input_post_count"),
                        "completed_count": original.get("completed_count"),
                        "flushed_count": original.get("flushed_count"),
                        "pending_count": original.get("pending_count"),
                        "failed_count": original.get("failed_count"),
                        "result_rows": original.get("result_rows"),
                    },
                    "partial_signals": partial_signals,
                },
                next_step=(
                    "현재 원본은 approval source가 아니므로 completed VLM/OCR-on result/manifest/checkpoint를 "
                    "확보한 뒤 같은 preflight를 다시 실행한다."
                ),
            )
        )

    if random_baseline.get("feasible") is False:
        items.append(
            _item(
                action_id="rerun_large_scale_preflight_on_completed_source",
                priority="P0",
                title="완료 source에서 fail-on-locked preflight 재실행",
                status="blocked_by_partial_source",
                owner_mode="RUN_REVIEW_MODE",
                executable_now=False,
                requires_completed_source=True,
                approval_blocker=True,
                related_gate="semantic_approval",
                evidence=random_baseline,
                next_step=(
                    "available rows가 random baseline 목표보다 작으므로 completed source 확보 후 "
                    "`preflight_qualitative_large_scale_review.py --fail-on-locked`를 다시 실행한다."
                ),
            )
        )
        items.append(
            _item(
                action_id="expanded_random_baseline_1000",
                priority="P0",
                title="무작위 기준선 1000건 이상 확대",
                status="blocked_by_partial_source",
                owner_mode="QUALITATIVE_SEMANTIC_REVIEW_LOOP",
                executable_now=False,
                requires_completed_source=True,
                approval_blocker=True,
                related_gate="semantic_approval",
                evidence={
                    "requested_sample_size": random_baseline.get("requested_sample_size"),
                    "available_rows": random_baseline.get("available_rows"),
                    "shortfall": random_baseline.get("shortfall"),
                },
                next_step=(
                    "completed source에서 row index/time/window/state 층화 random control 1000건 이상을 만들고 "
                    "high-risk oversample과 분리 보고한다."
                ),
            )
        )

    items.append(
        _item(
            action_id="p0_p1_high_risk_expansion",
            priority="P0",
            title="P0/P1 고위험 bucket 확대 리뷰",
            status="blocked_by_partial_source",
            owner_mode="QUALITATIVE_SEMANTIC_REVIEW_LOOP",
            executable_now=False,
            requires_completed_source=True,
            approval_blocker=True,
            related_gate="semantic_approval",
            evidence={
                "required_buckets": [
                    "weak_evidence_but_strong_resolution",
                    "generic_parenthetical_bridge",
                    "search_degraded_or_timeout",
                    "reason_decision_contradiction",
                    "slang_db_noise_or_alias_pollution",
                    "VLM_OCR_involved",
                    "worker_or_shard_degraded_window",
                ]
            },
            next_step=(
                "completed source에서 P0/P1 bucket별 최소 200건 또는 bucket 전수를 뽑아 "
                "ACCEPT/HOLD/REPROCESS/REJECT/INFO_MISSING으로 라벨링한다."
            ),
        )
    )

    if semantic_coverage:
        coverage = semantic_coverage.get("coverage") or {}
        issue_counts = semantic_coverage.get("issue_counts") or {}
        if semantic_coverage.get("gate") == "REVIEW-LOCKED":
            items.append(
                _item(
                    action_id="modern_semantic_coverage_source_required",
                    priority="P0",
                    title="modern semantic/VLM/comment coverage source 확보",
                    status="blocked_by_partial_or_legacy_source",
                    owner_mode="RUN_REVIEW_MODE",
                    executable_now=False,
                    requires_completed_source=True,
                    requires_browser_visual=bool(coverage.get("browser_visual_missing")),
                    approval_blocker=True,
                    related_gate="semantic_approval",
                    evidence={
                        "coverage_gate": semantic_coverage.get("gate"),
                        "semantic_approval": semantic_coverage.get("semantic_approval"),
                        "total_rows": coverage.get("total_rows"),
                        "image_evidence_catalog_missing": coverage.get("image_evidence_catalog_missing"),
                        "image_context_without_vlm_catalog": coverage.get("image_context_without_vlm_catalog"),
                        "browser_visual_missing": coverage.get("browser_visual_missing"),
                        "comment_metadata_missing": coverage.get("comment_metadata_missing"),
                        "comment_dialogue_context_missing": coverage.get("comment_dialogue_context_missing"),
                        "comment_context_resolution_without_attribution": coverage.get(
                            "comment_context_resolution_without_attribution"
                        ),
                        "comment_author_match_unverified_used_for_resolution": coverage.get(
                            "comment_author_match_unverified_used_for_resolution"
                        ),
                        "search_only_resolved_title": coverage.get("search_only_resolved_title"),
                        "search_only_resolved_title_review_only": coverage.get(
                            "search_only_resolved_title_review_only"
                        ),
                        "blocked_intent_resolved_title": coverage.get("blocked_intent_resolved_title"),
                        "blocked_intent_resolved_title_review_only": coverage.get(
                            "blocked_intent_resolved_title_review_only"
                        ),
                        "final_semantic_reread_missing": coverage.get("final_semantic_reread_missing"),
                        "final_semantic_reread_required": coverage.get("final_semantic_reread_required"),
                        "final_semantic_reread_required_missing": coverage.get("final_semantic_reread_required_missing"),
                        "issue_counts": issue_counts,
                    },
                    next_step=(
                        "completed source는 image_evidence_catalog, browser visual/loading evidence, "
                        "comment_metadata, comment_dialogue_context_lines, 댓글 맥락 attribution을 포함해야 한다. "
                        "search_only/차단 intent resolved title은 별도 bucket으로 남겨야 한다. "
                        "semantic-risk resolved row는 final_semantic_reread 공개 흔적도 포함해야 하며, "
                        "`build_semantic_coverage_audit.py`로 다시 확인한다."
                    ),
                )
            )
        items.append(
            _item(
                action_id="semantic_coverage_audit_required_for_new_source",
                priority="P1",
                title="새 source마다 semantic coverage audit 실행",
                status="ready",
                owner_mode="RUN_REVIEW_MODE",
                executable_now=True,
                requires_completed_source=False,
                approval_blocker=False,
                related_gate="semantic_approval",
                evidence=semantic_coverage,
                next_step=(
                    "새 completed/canary source가 생길 때마다 `build_semantic_coverage_audit.py`를 실행해 "
                    "image/comment/search-only/blocked-intent/final reread coverage를 approval 전 분리 보고한다."
                ),
            )
        )

    items.append(
        _item(
            action_id="small_run_runtime_audit_required",
            priority="P1",
            title="소규모 targeted rerun 후 runtime 감사 고정",
            status="ready",
            owner_mode="RUN_REVIEW_MODE",
            executable_now=True,
            approval_blocker=False,
            related_gate="small_run_runtime_contract",
            evidence={
                "runtime_contract": runtime.get("runtime_contract"),
                "requested_parallel": runtime.get("requested_parallel"),
                "effective_parallel": runtime.get("effective_parallel"),
                "log_evidence_present": runtime.get("log_evidence_present"),
                "semantic_approval": runtime.get("semantic_approval"),
            },
            next_step=(
                "새 소규모 canary가 생기면 `audit_goal_test_run_contract.py`를 실행해 "
                "parallel 36 max/effective 축소, no Docker lifecycle, VLM/OCR ready를 확인한다."
            ),
        )
    )

    if process_snapshot:
        stale_count = process_snapshot.get("stale_process_candidate_count")
        available = process_snapshot.get("snapshot_available")
        if available is True and stale_count == 0:
            status = "ready_clean_snapshot"
            next_step = (
                "현재 외부 process snapshot 기준 stale expert_main/llm_batch/warp_shards/vllm/uvicorn 후보가 0건이다. "
                "다음 run 전에도 같은 snapshot audit를 남긴다."
            )
        elif available is True:
            status = "review_process_candidates"
            next_step = "matching process가 있으므로 다음 run 전 PID/command_line을 확인하고 필요한 경우 정리한다."
        else:
            status = "ready_requires_external_snapshot"
            next_step = (
                "sandbox/CIM 권한 문제로 direct snapshot이 실패하면 외부에서 process JSON을 캡처해 "
                "`--process-snapshot-json`으로 audit에 주입한다."
            )
        items.append(
            _item(
                action_id="process_snapshot_required_for_goal_reruns",
                priority="P1",
                title="goal/test rerun 전 process snapshot 확인",
                status=status,
                owner_mode="RUN_REVIEW_MODE",
                executable_now=True,
                requires_completed_source=False,
                approval_blocker=False,
                related_gate="small_run_runtime_contract",
                evidence=process_snapshot,
                next_step=next_step,
            )
        )

    if hardcoded_alias:
        alias_gate = hardcoded_alias.get("semantic_approval")
        is_blocker = alias_gate in {"REVIEW", "REVIEW-LOCKED"}
        items.append(
            _item(
                action_id="hardcoded_alias_risk_review_required",
                priority="P1",
                title="hardcoded alias/abbreviation positive 경로 리뷰",
                status="ready_review_locked" if alias_gate == "REVIEW-LOCKED" else "ready_review",
                owner_mode="MIXED_MODE",
                executable_now=True,
                requires_completed_source=False,
                approval_blocker=is_blocker,
                related_gate="semantic_approval",
                evidence=hardcoded_alias,
                next_step=(
                    "hardcoded positive alias/abbreviation registry와 final title rescue/High 승격/guard 예외 경로를 "
                    "`audit_hardcoded_alias_risk.py` 산출물 기준으로 검토한다. quarantine-only registry는 approval blocker로 "
                    "세지 않고, positive registry는 evidence-supported bootstrap인지 별도 표본/코드 근거로 확인한다."
                ),
            )
        )

    if hardcoded_alias_packet:
        packet_gate = hardcoded_alias_packet.get("gate")
        coverage = hardcoded_alias_packet.get("packet_coverage")
        is_blocker = packet_gate in {"REVIEW", "INFO_MISSING"} and not hardcoded_alias_packet_closed_by_labels
        if hardcoded_alias_packet_closed_by_labels:
            status = "closed_by_packet_labels"
            next_step = (
                "v407 packet review의 matched packet은 후속 label review에서 모두 ACCEPT로 닫혔다. "
                "이 항목은 더 이상 approval blocker가 아니며, positive registry 전체 경로는 별도 action에서 계속 검토한다."
            )
        else:
            status = "ready_packet_review" if coverage == "FOUND" else "ready_targeted_canary_required"
            next_step = (
                "v407 packet review에서 실제 packet alias hit가 확인됐으므로, 각 packet을 원문/evidence/reason 기준으로 "
                "ACCEPT/HOLD/REPROCESS/REJECT 라벨링하고 registry provenance가 누락된 경우 source_registry 필드를 보강한다."
                if coverage == "FOUND"
                else (
                    "hardcoded alias registry가 실제 packet에 노출된 근거가 부족하므로 registry별 targeted canary를 만들고 "
                    "source_registry/provenance 필드가 남는지 확인한다."
                )
            )
        packet_evidence = dict(hardcoded_alias_packet)
        packet_evidence["closed_by_packet_labels"] = hardcoded_alias_packet_closed_by_labels
        if hardcoded_alias_packet_closed_by_labels:
            packet_evidence["effective_gate"] = "GO"
            packet_evidence["closure_source"] = "hardcoded_alias_packet_labels"
        items.append(
            _item(
                action_id="hardcoded_alias_packet_review_required",
                priority="P1",
                title="hardcoded alias 실제 packet/provenance 리뷰",
                status=status,
                owner_mode="QUALITATIVE_SEMANTIC_REVIEW_LOOP",
                executable_now=True,
                requires_completed_source=False,
                approval_blocker=is_blocker,
                related_gate="semantic_approval",
                evidence=packet_evidence,
                next_step=next_step,
            )
        )

    if hardcoded_alias_packet_labels_evidence:
        label_gate = hardcoded_alias_packet_labels_evidence.get("gate")
        reject_count = hardcoded_alias_packet_labels_evidence.get("reject_count")
        hold_count = hardcoded_alias_packet_labels_evidence.get("hold_count")
        label_followup_closed = label_gate == "GO"
        items.append(
            _item(
                action_id="hardcoded_alias_packet_label_followup",
                priority="P1",
                title="hardcoded alias packet 라벨 후속 조치",
                status="closed_by_packet_labels" if label_followup_closed else "ready_review",
                owner_mode="QUALITATIVE_SEMANTIC_REVIEW_LOOP",
                executable_now=not label_followup_closed,
                requires_completed_source=False,
                approval_blocker=label_gate == "REVIEW",
                related_gate="semantic_approval",
                evidence=hardcoded_alias_packet_labels_evidence,
                next_step=(
                    "후속 label review가 모두 ACCEPT/no_action으로 닫혔다. "
                    "이 packet label followup은 더 이상 실행 항목이 아니며, positive registry 전체 경로는 별도 action에서 계속 검토한다."
                    if label_followup_closed
                    else (
                        f"label review에서 HOLD {hold_count}건, REJECT {reject_count}건이 나왔다. "
                        "REJECT packet은 re_judge/re_search로 재확인하고, HOLD packet은 source_registry/provenance 보강 "
                        "전까지 approval ACCEPT로 올리지 않는다."
                    )
                ),
            )
        )

    items.append(
        _item(
            action_id="reason_hygiene_before_using_canary",
            priority="P1",
            title="canary를 증거로 쓰기 전 reason hygiene 스캔",
            status="ready",
            owner_mode="RUN_REVIEW_MODE",
            executable_now=True,
            approval_blocker=False,
            related_gate="latest_reason_hygiene",
            evidence={
                "gate": hygiene.get("gate"),
                "files_scanned": hygiene.get("files_scanned"),
                "hit_files": hygiene.get("hit_files"),
                "hit_type_counts": hygiene.get("hit_type_counts"),
            },
            next_step=(
                "latest canary/result set을 approval 보조 증거로 말하기 전 `scan_reason_hygiene.py --fail-on-hit`를 "
                "실행해 stale template, colon payload, deterministic reread drift를 막는다."
            ),
        )
    )

    coverage_for_visual_gate = {}
    if semantic_coverage:
        coverage_for_visual_gate = semantic_coverage.get("coverage") or {}
    visual_gate_blocker_signal_count = sum(
        _safe_int(coverage_for_visual_gate.get(key))
        for key in (
            "browser_visual_missing",
            "image_evidence_catalog_missing",
            "image_context_without_vlm_catalog",
        )
    )
    visual_gate_blocker = visual_gate_blocker_signal_count > 0

    items.append(
        _item(
            action_id="vlm_ocr_browser_visual_gate",
            priority="P0" if visual_gate_blocker else "P1",
            title="VLM/OCR 이미지 row 브라우저 시각 gate",
            status=(
                "blocked_by_missing_or_weak_visual_evidence"
                if visual_gate_blocker
                else "ready_when_image_rows_exist"
            ),
            owner_mode="MIXED_MODE",
            executable_now=True,
            requires_browser_visual=True,
            approval_blocker=visual_gate_blocker,
            related_gate="semantic_approval",
            evidence={
                "current_small_run_image_post_count": runtime.get("image_post_count"),
                "current_small_run_vlm_ocr_ready": runtime.get("vlm_ocr_semantic_review_ready"),
                "source_browser_visual_missing": coverage_for_visual_gate.get("browser_visual_missing"),
                "source_image_evidence_catalog_missing": coverage_for_visual_gate.get(
                    "image_evidence_catalog_missing"
                ),
                "source_image_context_without_vlm_catalog": coverage_for_visual_gate.get(
                    "image_context_without_vlm_catalog"
                ),
                "visual_gate_blocker_signal_count": visual_gate_blocker_signal_count,
                "visual_gate_missing_count": visual_gate_blocker_signal_count,
                "visual_gate_missing_count_note": (
                    "legacy compatibility field; this is a sum of blocker signals, not unique post count"
                ),
            },
            next_step=(
                "이미지/VLM/OCR row는 in-app Browser 또는 동등 시각 증거로 본문 이미지 loaded/placeholder/"
                "incomplete/broken 상태와 screenshot/observation을 packet에 붙인다. "
                "이미지 row의 VLM/OCR catalog나 browser loading 증거가 Missing/Weak이면 semantic approval blocker로 둔다."
            ),
        )
    )

    items.append(
        _item(
            action_id="preserve_original_as_regression_seed_only",
            priority="P1",
            title="원본 partial source는 regression seed로만 사용",
            status="ready",
            owner_mode="RUN_REVIEW_MODE",
            executable_now=True,
            approval_blocker=False,
            related_gate="original_source_approval",
            evidence={
                "original_source_approval": gates.get("original_source_approval"),
                "source_dataset_kind": source_policy.get("source_dataset_kind"),
                "source_integrity_classification": source_policy.get("source_integrity_classification"),
            },
            next_step=(
                "원본 71 result rows와 checkpoint 80 completed rows는 known-bad/targeted triage 후보로만 쓰고, "
                "10만 품질 기준선 통계에는 섞지 않는다."
            ),
        )
    )

    ready_count = sum(1 for item in items if item["executable_now"])
    blocked_count = sum(1 for item in items if not item["executable_now"])
    approval_blockers = [item["action_id"] for item in items if item["approval_blocker"]]
    return {
        "queue_type": "goal_action_queue",
        "generated_at": datetime.now().replace(microsecond=0).isoformat(),
        "source_state_map": state_map.get("map_type"),
        "goal_result_path": state_map.get("goal_result_path"),
        "gates": gates,
        "blockers_from_state_map": blockers,
        "summary": {
            "total_actions": len(items),
            "ready_now": ready_count,
            "blocked_until_completed_source": blocked_count,
            "approval_blockers": approval_blockers,
            "semantic_approval": gates.get("semantic_approval"),
            "semantic_coverage_gate": semantic_coverage.get("gate") if semantic_coverage else None,
            "process_snapshot_available": process_snapshot.get("snapshot_available") if process_snapshot else None,
            "process_snapshot_stale_candidate_count": (
                process_snapshot.get("stale_process_candidate_count") if process_snapshot else None
            ),
            "hardcoded_alias_gate": hardcoded_alias.get("semantic_approval") if hardcoded_alias else None,
            "hardcoded_alias_positive_blocker_count": (
                hardcoded_alias.get("positive_hardcoded_alias_blocker_count") if hardcoded_alias else None
            ),
            "hardcoded_alias_packet_gate": (
                hardcoded_alias_packet.get("gate") if hardcoded_alias_packet else None
            ),
            "hardcoded_alias_packet_effective_gate": (
                "GO"
                if hardcoded_alias_packet_closed_by_labels
                else (hardcoded_alias_packet.get("gate") if hardcoded_alias_packet else None)
            ),
            "hardcoded_alias_packet_closed_by_labels": (
                hardcoded_alias_packet_closed_by_labels if hardcoded_alias_packet else None
            ),
            "hardcoded_alias_packet_coverage": (
                hardcoded_alias_packet.get("packet_coverage") if hardcoded_alias_packet else None
            ),
            "hardcoded_alias_packet_matched": (
                hardcoded_alias_packet.get("matched_packets") if hardcoded_alias_packet else None
            ),
            "hardcoded_alias_packet_unique_post_context_matches": (
                hardcoded_alias_packet.get("unique_post_context_registry_match_count")
                if hardcoded_alias_packet
                else None
            ),
            "hardcoded_alias_packet_label_gate": (
                hardcoded_alias_packet_labels_evidence.get("gate")
                if hardcoded_alias_packet_labels_evidence
                else None
            ),
            "hardcoded_alias_packet_label_counts": (
                hardcoded_alias_packet_labels_evidence.get("label_counts")
                if hardcoded_alias_packet_labels_evidence
                else None
            ),
        },
        "actions": items,
    }


def write_markdown(queue: dict[str, Any], path: Path) -> None:
    summary = queue["summary"]
    gates = queue.get("gates") or {}
    lines = [
        "# Goal 실행 큐",
        "",
        "## 요약",
        "",
        f"- total_actions: `{summary['total_actions']}`",
        f"- ready_now: `{summary['ready_now']}`",
        f"- blocked_until_completed_source: `{summary['blocked_until_completed_source']}`",
        f"- semantic_approval: `{summary.get('semantic_approval')}`",
        f"- semantic_coverage_gate: `{summary.get('semantic_coverage_gate')}`",
        f"- process_snapshot_available: `{summary.get('process_snapshot_available')}`",
        f"- process_snapshot_stale_candidate_count: `{summary.get('process_snapshot_stale_candidate_count')}`",
        f"- hardcoded_alias_gate: `{summary.get('hardcoded_alias_gate')}`",
        f"- hardcoded_alias_positive_blocker_count: `{summary.get('hardcoded_alias_positive_blocker_count')}`",
        f"- hardcoded_alias_packet_gate: `{summary.get('hardcoded_alias_packet_gate')}`",
        f"- hardcoded_alias_packet_effective_gate: `{summary.get('hardcoded_alias_packet_effective_gate')}`",
        f"- hardcoded_alias_packet_closed_by_labels: `{summary.get('hardcoded_alias_packet_closed_by_labels')}`",
        f"- hardcoded_alias_packet_coverage: `{summary.get('hardcoded_alias_packet_coverage')}`",
        f"- hardcoded_alias_packet_matched: `{summary.get('hardcoded_alias_packet_matched')}`",
        (
            "- hardcoded_alias_packet_unique_post_context_matches: "
            f"`{summary.get('hardcoded_alias_packet_unique_post_context_matches')}`"
        ),
        f"- hardcoded_alias_packet_label_gate: `{summary.get('hardcoded_alias_packet_label_gate')}`",
        f"- hardcoded_alias_packet_label_counts: `{summary.get('hardcoded_alias_packet_label_counts')}`",
        f"- original_source_approval: `{gates.get('original_source_approval')}`",
        f"- small_run_runtime_contract: `{gates.get('small_run_runtime_contract')}`",
        f"- latest_reason_hygiene: `{gates.get('latest_reason_hygiene')}`",
        "",
        "## 승인 차단 항목",
        "",
    ]
    for action_id in summary.get("approval_blockers") or []:
        lines.append(f"- `{action_id}`")
    lines.extend(["", "## 실행 항목", ""])
    for item in queue["actions"]:
        lines.extend(
            [
                f"### {item['priority']} {item['action_id']}",
                "",
                f"- 제목: {item['title']}",
                f"- 상태: `{item['status']}`",
                f"- 담당 모드: `{item['owner_mode']}`",
                f"- 지금 실행 가능: `{item['executable_now']}`",
                f"- 완료 source 필요: `{item['requires_completed_source']}`",
                f"- 브라우저 시각 확인 필요: `{item['requires_browser_visual']}`",
                f"- 승인 차단 여부: `{item['approval_blocker']}`",
                f"- 관련 gate: `{item['related_gate']}`",
                f"- 다음 단계: {item['next_step']}",
                "",
            ]
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a Korean action queue from a goal current-state map.")
    parser.add_argument("--state-map", required=True, type=Path, help="v393 goal current-state map JSON.")
    parser.add_argument("--semantic-coverage-audit", type=Path, default=None)
    parser.add_argument("--process-snapshot-audit", type=Path, default=None)
    parser.add_argument("--hardcoded-alias-audit", type=Path, default=None)
    parser.add_argument("--hardcoded-alias-packet-review", type=Path, default=None)
    parser.add_argument("--hardcoded-alias-packet-labels", type=Path, default=None)
    parser.add_argument("--output-json", type=Path, default=None)
    parser.add_argument("--output-md", type=Path, default=None)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    queue = build_action_queue(
        load_json(args.state_map),
        semantic_coverage_audit=(
            load_json(args.semantic_coverage_audit) if args.semantic_coverage_audit else None
        ),
        process_snapshot_audit=(
            load_json(args.process_snapshot_audit) if args.process_snapshot_audit else None
        ),
        hardcoded_alias_audit=(
            load_json(args.hardcoded_alias_audit) if args.hardcoded_alias_audit else None
        ),
        hardcoded_alias_packet_review=(
            load_json(args.hardcoded_alias_packet_review)
            if args.hardcoded_alias_packet_review
            else None
        ),
        hardcoded_alias_packet_labels=(
            load_jsonl(args.hardcoded_alias_packet_labels)
            if args.hardcoded_alias_packet_labels
            else None
        ),
    )
    payload = json.dumps(queue, ensure_ascii=False, indent=2)
    if args.output_json:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(payload + "\n", encoding="utf-8")
    if args.output_md:
        write_markdown(queue, args.output_md)
    print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
