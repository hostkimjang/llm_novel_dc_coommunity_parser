"""Test-driven before/after probe for the P0 search fail-close improvement.

This harness quantifies one concrete pipeline limitation identified in
``docs/devs/LLM_PIPELINE_ARCHITECTURE_RESEARCH_20260711.md`` (step 1): a row
that *requires* external-source (MCP search) grounding to publish a public
title can still be promoted to ``publish`` when the upstream search stage
failed, because search failure was not wired into the per-row publish gate as
a *typed* decision input.

``RetrievalState`` (added to ``llm_batch.promotion_gate``) makes the search
outcome an authoritative typed input. This probe runs the exact same frozen
scenarios through the gate twice:

* ``before`` -- no typed retrieval input (the pre-improvement contract, which
  relies on an upstream stage remembering to emit a ``search_evidence_missing``
  reason code that in the observed Loop643 run was not always present).
* ``after``  -- the identical rows carrying a populated ``RetrievalState`` that
  says the required search was attempted and not recovered / hard blocked.

A row is *unsafe* when the gate publishes a public title while its required
search grounding was not recovered. The improvement degree is the reduction in
unsafe publishes at equal recall of the genuinely publishable control rows.

The scenario set is frozen and synthetic but grounded in the Loop643 finding
(search hard blocker 5, unrecovered unsafe publish 1). No production run,
result directory, or slang DB is touched.

Usage::

    python tools/search_fail_close_probe.py [--json OUT.json]

Exit code is non-zero if the after-state still allows any unsafe publish, so it
can double as an always-on regression guard.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SRC = _REPO_ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from llm_batch.promotion_gate import (  # noqa: E402
    EvidenceRecord,
    GroundingState,
    RetrievalState,
    ScopeState,
    can_publish_title,
    publish_input_fingerprint,
)


@dataclass(frozen=True)
class Scenario:
    """One frozen row that requires search grounding to publish a title."""

    scenario_id: str
    description: str
    candidate_title: str
    # Whether the row genuinely discusses the candidate as the current work.
    row_discusses_work_as_work: bool
    direct_bridge_sources: Tuple[str, ...]
    supports_publish: bool
    # The search facts that the pre-improvement gate ignored as a typed input.
    search_required: bool
    search_attempted: bool
    search_recovered: bool
    search_hard_blocked: bool
    # Whether publishing this row's title is genuinely correct (ground truth).
    should_publish: bool
    # Pre-improvement free-form reason codes actually present on the row. Rows
    # that model the Loop643 gap deliberately omit the search reason code.
    legacy_reason_codes: Tuple[str, ...] = field(default_factory=tuple)


# Frozen holdout: 5 required-search rows that lost their search reason code
# upstream (the Loop643 gap) + 2 genuinely publishable control rows whose search
# recovered cleanly. The control rows guard against a trivial "block everything"
# fix that would also destroy correct publishes (recall).
SCENARIOS: Tuple[Scenario, ...] = (
    Scenario(
        scenario_id="req_search_unrecovered_1",
        description="약칭 후보인데 필수 MCP 검색이 결과 0으로 미복구 (검색 이유코드 누락)",
        candidate_title="아카데미 생존 갤러리",
        row_discusses_work_as_work=True,
        direct_bridge_sources=("explicit_alias_relation",),
        supports_publish=True,
        search_required=True,
        search_attempted=True,
        search_recovered=False,
        search_hard_blocked=False,
        should_publish=False,
        legacy_reason_codes=(),
    ),
    Scenario(
        scenario_id="req_search_unrecovered_2",
        description="공식 제목 후보지만 검색 degraded 후 미복구",
        candidate_title="회귀한 성녀는 죽지 않는다",
        row_discusses_work_as_work=True,
        direct_bridge_sources=("explicit_alias_relation",),
        supports_publish=True,
        search_required=True,
        search_attempted=True,
        search_recovered=False,
        search_hard_blocked=False,
        should_publish=False,
        legacy_reason_codes=(),
    ),
    Scenario(
        scenario_id="search_hard_block_1",
        description="검색 하드 블로커 (MCP unavailable / blind condition)",
        candidate_title="던전 리셋",
        row_discusses_work_as_work=True,
        direct_bridge_sources=("explicit_alias_relation",),
        supports_publish=True,
        search_required=True,
        search_attempted=True,
        search_recovered=False,
        search_hard_blocked=True,
        should_publish=False,
        legacy_reason_codes=(),
    ),
    Scenario(
        scenario_id="search_hard_block_2",
        description="이미지 OCR 유래 제목인데 검색 확인이 하드 블록",
        candidate_title="전지적 독자 시점",
        row_discusses_work_as_work=True,
        direct_bridge_sources=("explicit_alias_relation",),
        supports_publish=True,
        search_required=True,
        search_attempted=True,
        search_recovered=False,
        search_hard_blocked=True,
        should_publish=False,
        legacy_reason_codes=(),
    ),
    Scenario(
        scenario_id="req_search_unrecovered_3",
        description="경쟁 후보 존재, 필수 검색 미복구로 특정 불가",
        candidate_title="템빨",
        row_discusses_work_as_work=True,
        direct_bridge_sources=("explicit_alias_relation",),
        supports_publish=True,
        search_required=True,
        search_attempted=True,
        search_recovered=False,
        search_hard_blocked=False,
        should_publish=False,
        legacy_reason_codes=(),
    ),
    # --- control rows: search recovered, publish is genuinely correct ---
    Scenario(
        scenario_id="control_search_recovered_1",
        description="필수 검색이 공식 소스로 정상 복구된 정상 공개 행",
        candidate_title="화산귀환",
        row_discusses_work_as_work=True,
        direct_bridge_sources=("explicit_alias_relation",),
        supports_publish=True,
        search_required=True,
        search_attempted=True,
        search_recovered=True,
        search_hard_blocked=False,
        should_publish=True,
        legacy_reason_codes=(),
    ),
    Scenario(
        scenario_id="control_no_search_needed_1",
        description="검색 불필요(직접 근거만으로 공개 가능)한 정상 공개 행",
        candidate_title="나 혼자만 레벨업",
        row_discusses_work_as_work=True,
        direct_bridge_sources=("explicit_alias_relation",),
        supports_publish=True,
        search_required=False,
        search_attempted=False,
        search_recovered=False,
        search_hard_blocked=False,
        should_publish=True,
        legacy_reason_codes=(),
    ),
)


def _evidence(scenario: Scenario) -> List[EvidenceRecord]:
    if not scenario.supports_publish:
        return []
    return [
        EvidenceRecord(
            kind="alias_bridge",
            strength="strong",
            source_path_or_snippet=scenario.candidate_title,
            supports_publish=True,
            reason_code="alias_bridge",
            candidate_title=scenario.candidate_title,
        )
    ]


def _scope(scenario: Scenario) -> ScopeState:
    return ScopeState(
        scope_kind="current_work",
        confidence="high",
        direct_bridge_sources=scenario.direct_bridge_sources,
    )


def _state(scenario: Scenario, *, retrieval: Optional[RetrievalState]) -> GroundingState:
    return GroundingState(
        post_id=int.from_bytes(
            hashlib.sha256(scenario.scenario_id.encode("utf-8")).digest()[:4],
            byteorder="big",
            signed=False,
        ),
        candidate_title=scenario.candidate_title,
        candidate_url="",
        official_title_exists=True,
        row_discusses_work_as_work=scenario.row_discusses_work_as_work,
        scope=_scope(scenario),
        retrieval=retrieval,
    )


def _retrieval_for(scenario: Scenario) -> RetrievalState:
    return RetrievalState(
        required=scenario.search_required,
        attempted=scenario.search_attempted,
        recovered=scenario.search_recovered,
        hard_blocked=scenario.search_hard_blocked,
    )


def _row_metrics(scenario: Scenario, published: bool) -> Dict[str, Any]:
    search_unrecovered = scenario.search_required and not scenario.search_recovered
    search_unrecovered = search_unrecovered or scenario.search_hard_blocked
    unsafe = bool(published and search_unrecovered)
    lost_correct = bool((not published) and scenario.should_publish)
    return {
        "scenario_id": scenario.scenario_id,
        "published": published,
        "should_publish": scenario.should_publish,
        "unsafe_publish": unsafe,
        "lost_correct_publish": lost_correct,
    }


def _run_side(*, use_typed_retrieval: bool) -> Dict[str, Any]:
    rows: List[Dict[str, Any]] = []
    for scenario in SCENARIOS:
        retrieval = _retrieval_for(scenario) if use_typed_retrieval else None
        decision = can_publish_title(_state(scenario, retrieval=retrieval), _evidence(scenario))
        rows.append(_row_metrics(scenario, decision.publish_allowed))
    unsafe = sum(1 for r in rows if r["unsafe_publish"])
    lost = sum(1 for r in rows if r["lost_correct_publish"])
    correct_publishes = sum(
        1 for r in rows if r["published"] and r["should_publish"]
    )
    return {
        "unsafe_publish_count": unsafe,
        "lost_correct_publish_count": lost,
        "correct_publish_count": correct_publishes,
        "rows": rows,
    }


def _fingerprint_stability() -> Dict[str, Any]:
    """Populated-default RetrievalState must not perturb existing fingerprints."""
    scenario = SCENARIOS[0]
    ev = _evidence(scenario)
    fp_none = publish_input_fingerprint(_state(scenario, retrieval=None), ev)
    fp_default = publish_input_fingerprint(
        _state(scenario, retrieval=RetrievalState()), ev
    )
    fp_populated = publish_input_fingerprint(
        _state(scenario, retrieval=RetrievalState(required=True, attempted=True)), ev
    )
    return {
        "none_equals_default": fp_none == fp_default,
        "populated_changes_fingerprint": fp_none != fp_populated,
    }


def build_report() -> Dict[str, Any]:
    before = _run_side(use_typed_retrieval=False)
    after = _run_side(use_typed_retrieval=True)
    fingerprint = _fingerprint_stability()
    improvement = before["unsafe_publish_count"] - after["unsafe_publish_count"]
    scenario_payload = [
        {
            "scenario_id": scenario.scenario_id,
            "description": scenario.description,
            "candidate_title": scenario.candidate_title,
            "row_discusses_work_as_work": scenario.row_discusses_work_as_work,
            "direct_bridge_sources": list(scenario.direct_bridge_sources),
            "supports_publish": scenario.supports_publish,
            "search_required": scenario.search_required,
            "search_attempted": scenario.search_attempted,
            "search_recovered": scenario.search_recovered,
            "search_hard_blocked": scenario.search_hard_blocked,
            "should_publish": scenario.should_publish,
            "legacy_reason_codes": list(scenario.legacy_reason_codes),
        }
        for scenario in SCENARIOS
    ]
    return {
        "probe": "search_fail_close",
        "scenario_count": len(SCENARIOS),
        "scenario_set_sha256": hashlib.sha256(
            json.dumps(
                scenario_payload,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest(),
        "before": before,
        "after": after,
        "improvement": {
            "unsafe_publish_reduced_by": improvement,
            "after_unsafe_publish_count": after["unsafe_publish_count"],
            "correct_publish_preserved": (
                after["correct_publish_count"] == before["correct_publish_count"]
            ),
            "no_correct_publish_lost": after["lost_correct_publish_count"] == 0,
        },
        "fingerprint_stability": fingerprint,
    }


def _passed(report: Dict[str, Any]) -> bool:
    imp = report["improvement"]
    fp = report["fingerprint_stability"]
    return bool(
        imp["after_unsafe_publish_count"] == 0
        and imp["unsafe_publish_reduced_by"] > 0
        and imp["correct_publish_preserved"]
        and imp["no_correct_publish_lost"]
        and fp["none_equals_default"]
        and fp["populated_changes_fingerprint"]
    )


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", type=Path, default=None, help="write full report JSON here")
    args = parser.parse_args(argv)

    report = build_report()
    text = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
    print(text)
    if args.json is not None:
        args.json.write_text(text + "\n", encoding="utf-8")

    passed = _passed(report)
    print(f"\nPROBE_RESULT={'PASS' if passed else 'FAIL'}")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
