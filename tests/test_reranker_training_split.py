"""합성 split/원문/판정 근거만 사용한다. 학습과 실제 정확도를 평가하지 않는다."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from llm_batch.grounding import reranker_training_split as split


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def fixture():
    sources, rows, payloads, evidence = [], [], {}, {}
    for i, partition in enumerate(split.SPLITS):
        sid = "source-" + str(i)
        text = "주작품" + str(i) + " 그리고 비교작" + str(i)
        raw = text.encode("utf-8")
        payloads[sid] = raw
        sources.append({"source_id": sid, "payload_sha256": sha(raw), "source_group_id": "source-group-" + str(i),
                        "lineage_root_id": "lineage-" + str(i), "rights_status": "SYNTHETIC_FIXTURE"})
        annotation = json.dumps({"fixture": i, "identity": "synthetic work", "roles": ["PRIMARY", "COMPARISON"]}, sort_keys=True).encode()
        annotation_sha = sha(annotation)
        evidence[annotation_sha] = annotation
        original = {"source_id": sid, "raw_path": "/content", "utf8_byte_span_start": 0, "utf8_byte_span_end": len(raw), "text": text, "span_sha256": sha(raw)}
        exposures, mentions, bridges = [], [], []
        for j in range(2):
            cid = f"candidate-{i}-{j}"
            corpus = f"corpus-{i}-{j}"
            exposures.append({"candidate_id": cid, "corpus_candidate_id": corpus, "polarity": "POSITIVE" if j == 0 else "NEGATIVE",
                              "work_id": f"work-{i}-{j}", "edition_id": f"edition-{i}-{j}", "media_type": "WEB_NOVEL",
                              "alias_family_ids": [f"alias-family-{i}-{j}"], "source_ids": [sid]})
            bridges.append({"corpus_candidate_id": corpus, "status": "UNIQUE", "candidate_ids": [cid], "provenance_sha256": annotation_sha})
            token = ("주작품" if j == 0 else "비교작") + str(i)
            start = raw.index(token.encode())
            mention_span = {**original, "utf8_byte_span_start": start, "utf8_byte_span_end": start + len(token.encode()), "text": token, "span_sha256": sha(token.encode())}
            mentions.append({"candidate_id": cid, "source_span": mention_span, "roles": ["PRIMARY"] if j == 0 else ["COMPARISON", "MENTIONED"],
                             "provenance": {"grade": "SYNTHETIC_FIXTURE", "artifact_sha256": annotation_sha, "reviewer": "synthetic author", "scope": "MENTION_ROLE"}})
        assignment = {"example_id": "example-" + str(i), "post_id": str(100 + i), "split_group_id": "split-group-" + str(i),
                      "content_fingerprint": split.canonical_sha256([original]), "source_group_fingerprint": split.canonical_sha256(["source-group-" + str(i)]),
                      "split": partition, "truth_kind": "CANDIDATE", "truth_label": exposures[0]["candidate_id"],
                      "label_provenance_sha256": annotation_sha, "candidate_set_fingerprint": split.canonical_sha256(exposures),
                      "gold_work_fingerprint": split.canonical_sha256(exposures[0]["work_id"]), "binding_status": "UNIQUE", "matched_candidate_ids": [exposures[0]["candidate_id"]]}
        rows.append({"assignment": assignment, "binding": {"run_id": "synthetic-run", "attempt_id": "attempt-" + str(i), "input_index": i + 1},
                     "source_ids": [sid], "source_spans": [original], "exposures": exposures, "r2_id_bridges": bridges, "role_mentions": mentions,
                     "label_provenance": {"grade": "SYNTHETIC_FIXTURE", "artifact_sha256": annotation_sha, "reviewer": "synthetic author", "scope": "WORK_IDENTITY"}})
    return split.seal_manifest({"schema_version": split.SCHEMA_VERSION, "data_kind": "SYNTHETIC_FIXTURE", "split_policy_version": split.POLICY_VERSION, "sources": sources, "rows": rows}), payloads, evidence


def validate(bundle, *, reseal=True, **kwargs):
    manifest, payloads, evidence = bundle
    return split.validate_training_split(split.seal_manifest(manifest) if reseal else manifest,
                                         source_payloads=payloads, evidence_payloads=evidence, **kwargs)


def codes(report):
    return {issue["code"] for issue in report["issues"]}


def calibration(manifest):
    from llm_batch.grounding.candidate_set_calibration_shadow import CalibrationSplitAssignment, CalibrationSplitManifest
    assignments = [CalibrationSplitAssignment(**item) for item in split.calibration_assignments(manifest)]
    return CalibrationSplitManifest.create(assignments=assignments, source_label_ledger_sha256="a" * 64, assignment_seed_sha256="b" * 64).to_dict()


def test_valid_pure_input_unchanged_roles_and_denominators():
    bundle = fixture()
    before = deepcopy(bundle)
    with patch.object(Path, "open", side_effect=AssertionError("pure validator must not read files")):
        report = validate(bundle)
    assert report["status"] == "VALID"
    assert report["calibration_bridge_status"] == "NOT_PROVIDED"
    assert report["ready_for_calibration_bridge"] is False
    assert report["counts"]["total_rows"] == report["counts"]["unique_posts"] == 4
    for value in report["counts"]["by_split"].values():
        assert value["rows"] == value["positive"] == value["negative"] == 1
        assert value["candidates"] == 2
    assert report["publication_authority"] is report["model_training_executed"] is report["actual_performance_evaluated"] is False
    assert bundle == before
    again = validate(bundle)
    assert again == report
    digest = report.pop("report_sha256")
    assert split.canonical_sha256(report) == digest


def test_explicit_bridge_uses_legacy_schema_without_train():
    bundle = fixture()
    old = calibration(bundle[0])
    assert {item["split"] for item in old["assignments"]} == {"DEV", "CALIBRATION", "FROZEN_HOLDOUT"}
    result = validate(bundle, calibration_manifest=old, expected_calibration_sha256=old["manifest_sha256"])
    assert result["status"] == "VALID" and result["ready_for_calibration_bridge"] is True
    assert result["calibration_manifest_sha256"] == old["manifest_sha256"]
    assert result["manifest_sha256"] == bundle[0]["manifest_sha256"]
    projection = split.calibration_assignments(bundle[0])
    projection[0]["truth_kind"] = "NIL"
    assert bundle[0]["rows"][1]["assignment"]["truth_kind"] == "CANDIDATE"


def test_bridge_rejects_wrong_sha_assignment_or_legacy_train():
    bundle = fixture()
    old = calibration(bundle[0])
    wrong_sha = validate(bundle, calibration_manifest=old, expected_calibration_sha256="c" * 64)
    assert "CALIBRATION_MANIFEST_SHA_MISMATCH" in codes(wrong_sha)
    old["assignments"][0]["post_id"] = "foreign-post"
    from llm_batch.grounding.candidate_set_calibration_shadow import CalibrationSplitAssignment, CalibrationSplitManifest
    changed = CalibrationSplitManifest.create(assignments=[CalibrationSplitAssignment(**item) for item in old["assignments"]], source_label_ledger_sha256="a" * 64, assignment_seed_sha256="b" * 64).to_dict()
    assert "CALIBRATION_ASSIGNMENT_MISMATCH" in codes(validate(bundle, calibration_manifest=changed, expected_calibration_sha256=changed["manifest_sha256"]))
    changed["assignments"][0]["split"] = "TRAIN"
    assert validate(bundle, calibration_manifest=changed, expected_calibration_sha256=changed["manifest_sha256"])["status"] == "INVALID"
    assert validate(bundle, calibration_manifest=calibration(bundle[0]))["status"] == "INVALID"


@pytest.mark.parametrize("dimension", ["work_id", "edition_media", "alias_family_id", "corpus_candidate_id", "candidate_id", "post_id", "split_group_id", "candidate_set_fingerprint", "gold_work_fingerprint"])
def test_cross_split_negative_exposure_and_assignment_leaks(dimension):
    bundle = fixture()
    left, right = bundle[0]["rows"][:2]
    a, b = left["exposures"][1], right["exposures"][1]
    if dimension in {"work_id", "corpus_candidate_id", "candidate_id"}:
        b[dimension] = a[dimension]
        if dimension == "candidate_id":
            for key in ("work_id", "edition_id", "media_type"):
                b[key] = a[key]
    elif dimension == "edition_media":
        b["edition_id"] = a["edition_id"]
    elif dimension == "alias_family_id":
        b["alias_family_ids"] = a["alias_family_ids"][:]
    else:
        right["assignment"][dimension] = left["assignment"][dimension]
    result = validate(bundle)
    assert result["status"] == "INVALID"
    assert any(issue["code"] == "CROSS_SPLIT_EXPOSURE" and issue["dimension"] == dimension for issue in result["issues"])


@pytest.mark.parametrize("dimension", ["source_group_id", "lineage_root_id", "payload_sha256", "source_id"])
def test_source_and_mirror_content_leaks(dimension):
    bundle = fixture()
    sources = bundle[0]["sources"]
    if dimension in {"source_group_id", "lineage_root_id"}:
        sources[1][dimension] = sources[0][dimension]
        if dimension == "source_group_id":
            bundle[0]["rows"][1]["assignment"]["source_group_fingerprint"] = split.canonical_sha256([sources[0][dimension]])
    elif dimension == "payload_sha256":
        sources[1][dimension] = sources[0][dimension]
        bundle[1][sources[1]["source_id"]] = bundle[1][sources[0]["source_id"]]
    else:
        bundle[0]["rows"][1]["source_ids"].append(sources[0]["source_id"])
    result = validate(bundle)
    assert any(issue["code"] == "CROSS_SPLIT_EXPOSURE" and issue["dimension"] == dimension for issue in result["issues"])


@pytest.mark.parametrize("field", ["work_id", "edition_id", "media_type", "alias_family_ids"])
def test_unknown_exposure_identity_is_not_ready(field):
    bundle = fixture()
    bundle[0]["rows"][0]["exposures"][1][field] = None
    result = validate(bundle)
    assert result["status"] == "NOT_READY"
    assert not any(issue["severity"] == "ERROR" for issue in result["issues"])


def test_missing_sources_and_evidence_have_no_fabricated_hashes():
    bundle = fixture()
    del bundle[1]["source-0"]
    bundle[2].clear()
    result = validate(bundle)
    assert result["status"] == "NOT_READY"
    assert {"SOURCE_BYTES_MISSING", "EVIDENCE_BYTES_MISSING"} <= codes(result)


@pytest.mark.parametrize("corrupt", ["source", "evidence", "span", "span_hash", "manifest"])
def test_known_byte_hash_or_span_mismatch_invalid(corrupt):
    bundle = fixture()
    if corrupt == "source":
        bundle[1]["source-0"] += b"tampered"
    elif corrupt == "evidence":
        key = next(iter(bundle[2]))
        bundle[2][key] += b"tampered"
    elif corrupt == "span":
        bundle[0]["rows"][0]["source_spans"][0]["utf8_byte_span_start"] = 1
    elif corrupt == "span_hash":
        bundle[0]["rows"][0]["role_mentions"][0]["source_span"]["span_sha256"] = "0" * 64
    else:
        bundle[0]["manifest_sha256"] = "0" * 64
    assert validate(bundle, reseal=corrupt != "manifest")["status"] == "INVALID"


def test_unknown_group_fingerprint_not_invented():
    bundle = fixture()
    bundle[0]["sources"][0]["lineage_root_id"] = None
    bundle[0]["sources"][0]["source_group_id"] = None
    bundle[0]["rows"][0]["assignment"]["source_group_fingerprint"] = None
    assert validate(bundle)["status"] == "NOT_READY"
    bundle[0]["rows"][0]["assignment"]["source_group_fingerprint"] = "a" * 64
    assert "UNKNOWN_SOURCE_GROUP_HASH_INVENTED" in codes(validate(bundle))


def test_work_miss_and_unjudged_are_not_nil():
    bundle = fixture()
    work = bundle[0]["rows"][0]["assignment"]
    work.update(binding_status="MISSING", matched_candidate_ids=[], truth_label=None)
    unknown = bundle[0]["rows"][1]["assignment"]
    unknown.update(truth_kind="UNJUDGED", binding_status="NOT_APPLICABLE", matched_candidate_ids=[], truth_label=None)
    result = validate(bundle)
    assert result["status"] == "NOT_READY"
    assert {"CANDIDATE_BINDING_MISSING", "TRUTH_UNJUDGED"} <= codes(result)
    assert work["truth_kind"] == "CANDIDATE" and unknown["truth_kind"] == "UNJUDGED"
    unknown["truth_label"] = "__NIL__"
    assert "UNJUDGED_BINDING_INVALID" in codes(validate(bundle))


def test_legitimate_nil_is_distinct_from_positive_or_candidate_miss():
    bundle = fixture()
    row = bundle[0]["rows"][0]
    row["assignment"].update(truth_kind="NIL", truth_label="__NIL__", binding_status="NOT_APPLICABLE", matched_candidate_ids=[], gold_work_fingerprint=None)
    row["exposures"][0]["polarity"] = "NEGATIVE"
    assert validate(bundle)["status"] == "VALID"
    row["exposures"][0]["polarity"] = "POSITIVE"
    assert "NIL_POSITIVE_CONFLICT" in codes(validate(bundle))


def test_r2_missing_ambiguous_and_unrelated_ids_remain_explicit():
    bundle = fixture()
    row = bundle[0]["rows"][0]
    row["r2_id_bridges"][0].update(status="MISSING", candidate_ids=[])
    assert validate(bundle)["status"] == "NOT_READY"
    row["exposures"][1]["corpus_candidate_id"] = row["exposures"][0]["corpus_candidate_id"]
    row["r2_id_bridges"] = [{**row["r2_id_bridges"][0], "status": "AMBIGUOUS", "candidate_ids": [item["candidate_id"] for item in row["exposures"]]}]
    assert validate(bundle)["status"] == "NOT_READY"
    row["r2_id_bridges"][0]["candidate_ids"][1] = "outside-candidate"
    assert "R2_BRIDGE_CANDIDATE_NOT_EXPOSED" in codes(validate(bundle))


def repeated_train_row(bundle):
    """Same supplied source, separate observation coordinates in TRAIN."""
    row = deepcopy(bundle[0]["rows"][0])
    row["assignment"]["example_id"] = "repeated-train-" + str(len(bundle[0]["rows"]))
    row["binding"]["input_index"] = 1000 + len(bundle[0]["rows"])
    bundle[0]["rows"].append(row)
    return row


def rename_exposed_candidate(row, index, new_id):
    exposure = row["exposures"][index]
    old_id = exposure["candidate_id"]
    exposure["candidate_id"] = new_id
    for bridge in row["r2_id_bridges"]:
        bridge["candidate_ids"] = [new_id if cid == old_id else cid for cid in bridge["candidate_ids"]]
    for mention in row["role_mentions"]:
        if mention["candidate_id"] == old_id:
            mention["candidate_id"] = new_id
    assignment = row["assignment"]
    if assignment["truth_label"] == old_id:
        assignment["truth_label"] = new_id
    assignment["matched_candidate_ids"] = [new_id if cid == old_id else cid for cid in assignment["matched_candidate_ids"]]
    assignment["candidate_set_fingerprint"] = split.canonical_sha256(row["exposures"])


@pytest.mark.parametrize("index", [0, 1])
@pytest.mark.parametrize("dimension", ["candidate_id", "work_id", "edition_id", "media_type"])
def test_same_split_unique_corpus_bridge_known_conflicts(index, dimension):
    bundle = fixture()
    first = bundle[0]["rows"][0]
    row = repeated_train_row(bundle)
    rename_exposed_candidate(row, index, "candidate-conflict")
    if dimension != "candidate_id":
        row["exposures"][index][dimension] = "known-conflict"
    row["assignment"]["candidate_set_fingerprint"] = split.canonical_sha256(row["exposures"])
    original = deepcopy(bundle)
    report = validate(bundle)
    assert report["status"] == "INVALID"
    issue = next(item for item in report["issues"] if item["code"] == "R2_UNIQUE_BRIDGE_CONFLICT" and item["dimension"] == dimension)
    assert issue["corpus_candidate_id"] == first["exposures"][index]["corpus_candidate_id"]
    assert issue["first_example"] == first["assignment"]["example_id"]
    assert issue["second_example"] == row["assignment"]["example_id"]
    assert issue["first_split"] == issue["second_split"] == "TRAIN"
    assert issue["first_value"] != issue["second_value"]
    assert bundle == original


def test_repeated_unique_corpus_mapping_is_valid_and_absent_ids_are_not_grouped():
    bundle = fixture()
    repeated_train_row(bundle)
    assert validate(bundle)["status"] == "VALID"
    for row in bundle[0]["rows"]:
        row["r2_id_bridges"] = []
        for exposure in row["exposures"]:
            exposure["corpus_candidate_id"] = None
    assert validate(bundle)["status"] == "VALID"


@pytest.mark.parametrize("dimension", ["work_id", "edition_id", "media_type"])
@pytest.mark.parametrize("unknown_first", [False, True])
def test_unique_corpus_unknown_identity_remains_not_ready(dimension, unknown_first):
    bundle = fixture()
    row = repeated_train_row(bundle)
    unknown = bundle[0]["rows"][0] if unknown_first else row
    unknown["exposures"][1][dimension] = None
    report = validate(bundle)
    assert report["status"] == "NOT_READY"
    assert not any(item["severity"] == "ERROR" for item in report["issues"])
    assert unknown["exposures"][1][dimension] is None


@pytest.mark.parametrize("status", ["MISSING", "AMBIGUOUS"])
def test_unresolved_corpus_proposal_is_not_promoted_to_unique_conflict(status):
    bundle = fixture()
    row = repeated_train_row(bundle)
    rename_exposed_candidate(row, 0, "unresolved-proposal")
    row["exposures"][0]["work_id"] = "unresolved-work"
    bridge = row["r2_id_bridges"][0]
    bridge.update(status=status, candidate_ids=[])
    if status == "AMBIGUOUS":
        row["exposures"][1]["corpus_candidate_id"] = bridge["corpus_candidate_id"]
        bridge["candidate_ids"] = [item["candidate_id"] for item in row["exposures"]]
        row["r2_id_bridges"].pop()
    report = validate(bundle)
    assert report["status"] == "NOT_READY"
    assert "R2_BRIDGE_" + status in codes(report)
    assert "R2_UNIQUE_BRIDGE_CONFLICT" not in codes(report)
    assert bridge["status"] == status


def test_multiple_role_mentions_preserved_and_unknown_not_guessed():
    bundle = fixture()
    row = bundle[0]["rows"][0]
    additional = deepcopy(row["role_mentions"][1])
    additional["candidate_id"] = row["exposures"][0]["candidate_id"]
    additional["roles"] = ["PREVIOUS", "MENTIONED"]
    row["role_mentions"].append(additional)
    original = deepcopy(row["role_mentions"])
    assert validate(bundle)["status"] == "VALID"
    assert row["role_mentions"] == original
    additional["roles"] = ["UNKNOWN"]
    assert validate(bundle)["status"] == "NOT_READY"
    additional["roles"] = ["UNKNOWN", "PRIMARY"]
    assert "ROLE_INVALID" in codes(validate(bundle))


@pytest.mark.parametrize("kind", ["example", "coordinate", "role", "bridge", "candidate"])
def test_duplicate_coordinates_and_records_rejected(kind):
    bundle = fixture()
    a, b = bundle[0]["rows"][:2]
    if kind == "example":
        b["assignment"]["example_id"] = a["assignment"]["example_id"]
    elif kind == "coordinate":
        b["binding"] = deepcopy(a["binding"])
    elif kind == "role":
        a["role_mentions"].append(deepcopy(a["role_mentions"][0]))
    elif kind == "bridge":
        a["r2_id_bridges"].append(deepcopy(a["r2_id_bridges"][0]))
    else:
        a["exposures"].append(deepcopy(a["exposures"][0]))
    assert validate(bundle)["status"] == "INVALID"


def test_source_backed_never_silently_promotes_synthetic_or_model_reference():
    bundle = fixture()
    bundle[0]["data_kind"] = "SOURCE_BACKED"
    assert "SYNTHETIC_PROVENANCE_MIXED" in codes(validate(bundle))
    for source in bundle[0]["sources"]:
        source["rights_status"] = "REUSE_PERMITTED"
    for row in bundle[0]["rows"]:
        row["label_provenance"]["grade"] = "MODEL_REFERENCE"
        for mention in row["role_mentions"]:
            mention["provenance"]["grade"] = "MODEL_REFERENCE"
    result = validate(bundle)
    assert result["status"] == "VALID"
    assert result["counts"]["provenance_grade_observations"] == {"MODEL_REFERENCE": 12}
    assert result["actual_performance_evaluated"] is False


def test_missing_split_and_unknown_rights_not_ready_revoked_invalid():
    bundle = fixture()
    bundle[0]["rows"].pop()
    bundle[0]["sources"][0]["rights_status"] = "UNKNOWN"
    result = validate(bundle)
    assert result["status"] == "NOT_READY"
    assert {"SPLIT_EMPTY", "RIGHTS_UNKNOWN"} <= codes(result)
    bundle[0]["sources"][0]["rights_status"] = "REVOKED"
    assert "RIGHTS_REVOKED" in codes(validate(bundle))


def test_hard_limits_and_boolean_input_index():
    bundle = fixture()
    bundle[0]["rows"][0]["binding"]["input_index"] = True
    assert "INPUT_INDEX_INVALID" in codes(validate(bundle))
    bundle = fixture()
    bundle[0]["rows"] *= 251
    assert "LIST_OR_LIMIT_INVALID" in codes(validate(bundle))
    bundle = fixture()
    bundle[1]["extra"] = b"a" * (split.MAX_BYTES + 1)
    assert "PAYLOAD_BYTES_LIMIT_OR_TYPE" in codes(validate(bundle))


def test_bad_shape_is_reported_not_mutated_or_raised():
    for manifest in (None, [], {"schema_version": "unknown"}):
        result = split.validate_training_split(manifest, source_payloads={}, evidence_payloads={})
        assert result["status"] == "INVALID"
