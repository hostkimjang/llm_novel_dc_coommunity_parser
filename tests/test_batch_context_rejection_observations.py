"""확정 거절의 통계와 실제 별칭 등록 자격을 분리하는 기능 대조."""

from copy import deepcopy

import pytest

from llm_batch.domain.batch_context import BatchContextMemory
from alias_learning_test_inputs import qualified_learning_input


def _input(alias="월항기", title="달빛 항로의 기록"):
    return {
        "identity": {
            "is_relevant": True,
            "novel_identity": {"official_title": title, "confidence": "High"},
            "slang_insight": {
                "detected_term": alias, "canonical_work_alias": alias,
                "decoded_term": title, "alias_scope": "pure_work_alias",
            },
        }
    }, [{"original": alias, "best_match": {"title": title}}]


def _assert_no_registration(memory):
    # register_abbreviation를 교체하지 않고 실제 확정/대기 저장소를 확인한다.
    assert memory.resolved_abbreviations == {}
    assert memory.pending_abbreviations == {}
    assert memory.resolved_authors == {}
    assert memory.resolved_characters == {}


@pytest.mark.parametrize("flag,alias,expected", [
    ("official_detail_title_preferred_over_surface_form", "제벨가 차녀의 2회차 결그룹", "abbreviation_image_surface_skipped"),
    ("search_supported_title_preferred_over_surface_form", "제벨가 차녀의 2회차 결그룹", "abbreviation_image_surface_skipped"),
    ("image_surface_title_unverified_without_official_evidence", "제벨가 차녀의 2회차 결그룹", "abbreviation_image_surface_skipped"),
    (None, "제벨가 차녀의 2회차 결그룹", "abbreviation_title_variant_surface_skipped"),
    (None, "재벌가 차녀의 2회차", "abbreviation_title_variant_surface_skipped"),
])
def test_raw_unqualified_rejections_record_specific_reason_without_registration(flag, alias, expected):
    result, terms = _input(alias, "재벌가 차녀의 2회차 걸그룹")
    if flag:
        result["identity"]["consistency_flags"] = [flag]
    before = deepcopy((result, terms))
    memory = BatchContextMemory(enabled=True)
    memory.learn_from_result(result, decoded_terms=terms)
    _assert_no_registration(memory)
    assert memory.stats.get(expected, 0) == 1
    other = ("abbreviation_title_variant_surface_skipped" if expected == "abbreviation_image_surface_skipped"
             else "abbreviation_image_surface_skipped")
    assert memory.stats.get(other, 0) == 0
    assert memory.stats.get("abbreviation_learning_evidence_rejected", 0) == 0
    assert (result, terms) == before


def test_short_unqualified_alias_still_requires_source_proof():
    result, terms = _input()
    before = deepcopy((result, terms))
    memory = BatchContextMemory(enabled=True)
    memory.learn_from_result(result, decoded_terms=terms)
    _assert_no_registration(memory)
    assert memory.stats.get("abbreviation_learning_evidence_rejected", 0) == 1
    assert memory.stats.get("abbreviation_image_surface_skipped", 0) == 0
    assert memory.stats.get("abbreviation_title_variant_surface_skipped", 0) == 0
    assert (result, terms) == before


@pytest.mark.parametrize("source_changed", [False, True])
def test_real_producer_proof_is_required_and_revalidated(source_changed):
    raw, _ = _input()
    result, terms = qualified_learning_input(raw, [])
    assert len(terms) == 1
    assert terms[0]["learning_evidence"]
    if source_changed:
        result["title"] += " 변경된 원문"
    before = deepcopy((result, terms))
    memory = BatchContextMemory(enabled=True)
    memory.learn_from_result(result, decoded_terms=terms)
    if source_changed:
        _assert_no_registration(memory)
        assert memory.stats.get("abbreviation_learning_evidence_rejected", 0) == 1
    else:
        assert memory.get_abbreviation("월항기") == "달빛 항로의 기록"
        assert len(memory.resolved_abbreviations) == 1
        assert memory.pending_abbreviations == {}
        assert memory.stats.get("abbreviation_learning_evidence_rejected", 0) == 0
    assert memory.stats.get("abbreviation_image_surface_skipped", 0) == 0
    assert memory.stats.get("abbreviation_title_variant_surface_skipped", 0) == 0
    assert (result, terms) == before


def test_valid_proof_does_not_override_realigned_surface_rejection():
    raw, _ = _input()
    result, terms = qualified_learning_input(raw, [])
    result["identity"]["consistency_flags"] = ["search_supported_title_preferred_over_surface_form"]
    before = deepcopy((result, terms))
    memory = BatchContextMemory(enabled=True)
    memory.learn_from_result(result, decoded_terms=terms)
    _assert_no_registration(memory)
    assert memory.stats.get("abbreviation_image_surface_skipped", 0) == 1
    assert memory.stats.get("abbreviation_learning_evidence_rejected", 0) == 0
    assert (result, terms) == before


def test_exact_title_observation_keeps_priority_and_deduplication():
    result, terms = _input("달빛 항로의 기록", "달빛 항로의 기록")
    result["identity"]["consistency_flags"] = ["search_supported_title_preferred_over_surface_form"]
    before = deepcopy((result, terms))
    memory = BatchContextMemory(enabled=True)
    memory.learn_from_result(result, decoded_terms=terms)
    _assert_no_registration(memory)
    assert memory.stats.get("abbreviation_exact_title_skipped", 0) == 1
    assert memory.stats.get("abbreviation_image_surface_skipped", 0) == 0
    assert memory.stats.get("abbreviation_learning_evidence_rejected", 0) == 0
    assert (result, terms) == before


@pytest.mark.parametrize("denial", ["low", "resolution_denied", "alias_denied"])
def test_outer_learning_denials_remain_before_rejection_observations(denial):
    result, terms = _input("제벨가 차녀의 2회차 결그룹", "재벌가 차녀의 2회차 걸그룹")
    identity = result["identity"]
    identity["consistency_flags"] = ["search_supported_title_preferred_over_surface_form"]
    if denial == "low":
        identity["novel_identity"]["confidence"] = "Low"
    elif denial == "resolution_denied":
        identity["title_resolution_allowed"] = False
    else:
        identity["slang_insight"]["decode_verified"] = False
    before = deepcopy((result, terms))
    memory = BatchContextMemory(enabled=True)
    memory.learn_from_result(result, decoded_terms=terms)
    _assert_no_registration(memory)
    for key in ("abbreviation_image_surface_skipped", "abbreviation_title_variant_surface_skipped",
                "abbreviation_learning_evidence_rejected"):
        assert memory.stats.get(key, 0) == 0
    assert (result, terms) == before
