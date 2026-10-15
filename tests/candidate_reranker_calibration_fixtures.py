"""공통 CAL/FROZEN 합성 fixture. import 시 학습/I/O를 실행하지 않는다.

공개 API: build_calibration_fixture(tmp_path) -> dict.
반환 키 계약:
 training_manifest, calibration_manifest, policy, source_payloads, evidence_payloads,
 model, model_manifest, model_manifest_path, model_manifest_sha256, scorer, scorer_summary,
 common_kwargs, cal_rows, expected_calibration_example_ids, cal_kwargs, calibration_events,
 frozen_args (행별 build_frozen_event_score kwargs 목록), frozen_vectors (example_id -> vector),
 frozen_base_shadows (example_id -> typed base), frozen_assignments (example_id -> typed assignment).
TRAIN/DEV/CALIBRATION/FROZEN_HOLDOUT 각각 CANDIDATE 1행 + NIL 1행, 총 8행이다.
한 NIL 모델을 실제 로컬 합성 TRAIN 2행에서 base/head 각각 2epoch 학습한다.
네트워크·실제 source-backed 데이터·CAL optimizer는 사용하지 않는다.
"""
from copy import deepcopy
import hashlib
import json

from src.llm_batch.grounding import candidate_reranker_event_bridge as bridge
from src.llm_batch.grounding import candidate_reranker_nil_learned as nil
from src.llm_batch.grounding import candidate_reranker_shadow as adapter
from src.llm_batch.grounding import reranker_training_split as split
from src.llm_batch.grounding.candidate_generation import (
    build_candidate_generation_proof, build_candidate_producer_plan, build_candidate_producer_receipt,
)
from src.llm_batch.grounding.candidate_set_calibration_shadow import (
    CalibrationEvaluationPolicy, CalibrationSplitAssignment, CalibrationSplitManifest,
)
from src.llm_batch.grounding.candidate_set_shadow import build_uncalibrated_selective_shadow
from src.llm_batch.promotion_gate import EvidenceRecord, GroundingState, RetrievalState, can_publish_title


def raw(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def sha(value):
    return hashlib.sha256(value).hexdigest()


def complete_proof(titles):
    """고정 합성 producer 선언만 만든다. 검색·fetch 실행은 없다."""
    plans, receipts = [], []
    for producer, key, value in (("search", "query", "synthetic calibration query"),
                                  ("fetch", "url", "https://example.invalid/calibration")):
        plan = build_candidate_producer_plan([{key: value, "purpose": "synthetic"}],
            producer=producer, enumeration_finished=True)
        receipts.append(build_candidate_producer_receipt(
            [{"title": title, "url": f"https://example.invalid/{i}"} for i, title in enumerate(titles)],
            {"attempted_count": 1, "raw_count": len(titles), "enumeration_finished": True},
            producer=producer, operation_input=value, purpose="synthetic", plan_fingerprint=plan.plan_fingerprint))
        plans.append(plan)
    return build_candidate_generation_proof(plans, receipts, local_snapshots=["UNKNOWN"])


def graph_record(args):
    """제품 private projection을 쓰지 않은 독립 source binding fixture."""
    row = next(r for r in args["training_manifest"]["rows"]
               if r["assignment"]["example_id"] == args["example"]["example_id"])
    ex, base = args["example"], args["base_shadow"]
    view, receipt = ex["frozen_view"], args["raw_receipt"]
    mapping = {r["corpus_candidate_id"]: r["candidate_ids"][0] for r in row["r2_id_bridges"]}
    return {"schema_version": "candidate_reranker_event_source_binding_v1", "stage": "PRE_SELECTION",
        "authority": "DECLARED_SOURCE_GRAPH_BINDING_NOT_INDEPENDENTLY_VERIFIED",
        "example_id": ex["example_id"], "post_id": row["assignment"]["post_id"],
        "binding": {**row["binding"], "publication_scope_id": args["publication_scope_id"]},
        "source_spans_sha256": bridge.canonical_sha256(row["source_spans"]),
        "capture_sha256": ex["capture_sha256"], "query_sha256": bridge.canonical_sha256(view["source_view"]),
        "frozen_view_sha256": bridge.canonical_sha256(view), "raw_receipt_sha256": receipt["receipt_sha256"],
        "scorer_summary_sha256": bridge.canonical_sha256(args["scorer_summary"]),
        "training_split_manifest_sha256": args["training_manifest"]["manifest_sha256"],
        "calibration_split_manifest_sha256": args["calibration_manifest"].manifest_sha256,
        "base_shadow_fingerprint": base.shadow_fingerprint,
        "publication_input_fingerprint": base.input_fingerprint,
        "candidate_set_fingerprint": base.candidate_set.candidate_set_fingerprint,
        "observation_fingerprint": base.candidate_set.observation_fingerprint,
        "raw_generation_sha256": view["generation_sha256"],
        "generation_proof_fingerprint": args["generation_proof"].metadata_fingerprint,
        "retrieval_state_fingerprint": bridge.canonical_sha256(args["retrieval_state"].to_dict()),
        "candidate_id_mapping": [{"raw_candidate_id": c["candidate_id"], "candidate_option_id":
            mapping[c["candidate_id"]] if view["candidate_namespace"] == "CORPUS_CANDIDATE" else c["candidate_id"]}
            for c in view["candidates"]],
        "r2_id_bridges_sha256": bridge.canonical_sha256(row["r2_id_bridges"])}


def bind_graph(args):
    encoded = raw(graph_record(args))
    args["source_binding_sha256"] = sha(encoded)
    args["evidence_payloads"][sha(encoded)] = encoded


def _policy():
    return CalibrationEvaluationPolicy.create(fixed_bin_edges=(0.0, 0.5, 1.0),
        selector_max_error_probability=0.4, nil_min_probability=0.6, alpha=0.05,
        min_dev_rows=2, min_dev_per_truth_class=1, min_calibration_rows=2,
        min_calibration_per_truth_class=1, min_frozen_rows=2, min_per_truth_class=1,
        min_occupied_bin_rows=1, target_coverage=0.5, max_selective_risk_upper_bound=1.0,
        baseline_noninferiority_margin=1.0, min_candidate_recall_lower_bound=0.0,
        min_nil_prediction_count=1, min_nil_precision_lower_bound=0.0, min_nil_recall_lower_bound=0.0,
        paired_delta_ci_bounds={"top_label_accuracy": -1.0, "brier": 2.0, "log_loss": 100.0,
            "ece": 1.0, "selective_risk": 1.0, "aurc": 1.0},
        policy_scope="SYNTHETIC_CONTRACT_ONLY", policy_origin="PRE_REGISTERED_DEV_CALIBRATION")


def build_calibration_fixture(tmp_path) -> dict:
    """호출 시에만 합성 학습/새 model manifest 배타 생성을 한다. CAL 학습은 없다.

    policy의 내부 MappingProxyType 때문에 bundle 전체 deepcopy는 피한다.
    common_kwargs/cal_rows는 deepcopy 가능하며 정책은 to_dict()로 내보낸다.
    """
    sources, rows, source_payloads, evidence, examples, bases, proofs = [], [], {}, {}, {}, {}, {}
    for i, (partition, truth_kind) in enumerate((p, t) for p in split.SPLITS for t in ("CANDIDATE", "NIL")):
        sid, post = f"calibration-source-{i}", str(9000 + i)
        titles = [f"교정합성대상작품{i}", f"교정합성비교작품{i}"]
        text = f"대상은 {titles[0]}입니다. 예전 {titles[1]}과 비교합니다."
        encoded = text.encode("utf-8")
        source_payloads[sid] = encoded
        sources.append({"source_id": sid, "payload_sha256": sha(encoded), "source_group_id": f"cal-group-{i}",
            "lineage_root_id": f"cal-lineage-{i}", "rights_status": "SYNTHETIC_FIXTURE"})
        annotation = raw({"schema_version": "synthetic_calibration_annotation", "author": "synthetic author",
            "partition": partition, "truth_kind": truth_kind, "identity": titles[0] if truth_kind == "CANDIDATE" else None,
            "roles": ["PRIMARY", "COMPARISON"]})
        label_sha = sha(annotation)
        evidence[label_sha] = annotation
        original = {"source_id": sid, "raw_path": "/content", "utf8_byte_span_start": 0,
            "utf8_byte_span_end": len(encoded), "text": text, "span_sha256": sha(encoded)}
        state = GroundingState(post_id=post, candidate_title=titles[0])
        records = [EvidenceRecord(kind="candidate_preservation", candidate_title=t, supports_publish=True) for t in titles]
        base = build_uncalibrated_selective_shadow(state, records, can_publish_title(state, records), generation_status="COMPLETE")
        actual_ids = {c.titles[0]: c.candidate_id for c in base.candidate_set.candidates}
        exposures, mentions, bridges, candidates, text_bindings = [], [], [], [], []
        for j, title in enumerate(titles):
            cid, corpus, role = actual_ids[title], f"cal-corpus-{i}-{j}", "PRIMARY" if j == 0 else "COMPARISON"
            start = encoded.index(title.encode("utf-8"))
            span = {**original, "utf8_byte_span_start": start, "utf8_byte_span_end": start + len(title.encode("utf-8")),
                "text": title, "span_sha256": sha(title.encode("utf-8"))}
            exposures.append({"candidate_id": cid, "corpus_candidate_id": corpus,
                "polarity": "POSITIVE" if j == 0 and truth_kind == "CANDIDATE" else "NEGATIVE",
                "work_id": f"cal-work-{i}-{j}", "edition_id": f"cal-edition-{i}-{j}", "media_type": "WEB_NOVEL",
                "alias_family_ids": [f"cal-alias-{i}-{j}"], "source_ids": [sid]})
            bridges.append({"corpus_candidate_id": corpus, "status": "UNIQUE", "candidate_ids": [cid], "provenance_sha256": label_sha})
            mentions.append({"candidate_id": cid, "source_span": span, "roles": [role],
                "provenance": {"grade": "SYNTHETIC_FIXTURE", "artifact_sha256": label_sha,
                    "reviewer": "synthetic author", "scope": "MENTION_ROLE"}})
            char_start = text.index(title)
            candidates.append({"candidate_id": corpus, "titles": [title], "urls": [], "aliases": [],
                "option_kind": "WORK_CANDIDATE", "event_eligible": True, "identity_conflict": False, "negative_evidence": [],
                "role_observations": [{"role": role, "raw_path": "/content", "start": char_start,
                    "end": char_start + len(title), "text_sha256": span["span_sha256"]}]})
            text_bindings.append({"candidate_id": corpus, "titles": [deepcopy(span)], "aliases": []})
        assignment = {"example_id": f"cal-example-{i}", "post_id": post, "split_group_id": f"cal-split-{i}",
            "content_fingerprint": split.canonical_sha256([original]),
            "source_group_fingerprint": split.canonical_sha256([f"cal-group-{i}"]), "split": partition,
            "truth_kind": truth_kind, "truth_label": actual_ids[titles[0]] if truth_kind == "CANDIDATE" else "__NIL__",
            "label_provenance_sha256": label_sha, "candidate_set_fingerprint": base.candidate_set.candidate_set_fingerprint,
            "gold_work_fingerprint": split.canonical_sha256(exposures[0]["work_id"]) if truth_kind == "CANDIDATE" else None,
            "binding_status": "UNIQUE" if truth_kind == "CANDIDATE" else "NOT_APPLICABLE",
            "matched_candidate_ids": [actual_ids[titles[0]]] if truth_kind == "CANDIDATE" else []}
        row = {"assignment": assignment, "binding": {"run_id": "synthetic-calibration-run",
            "attempt_id": f"cal-attempt-{i}", "input_index": i + 1}, "source_ids": [sid], "source_spans": [original],
            "exposures": exposures, "r2_id_bridges": bridges, "role_mentions": mentions,
            "label_provenance": {"grade": "SYNTHETIC_FIXTURE", "artifact_sha256": label_sha,
                "reviewer": "synthetic author", "scope": "WORK_IDENTITY"}}
        rows.append(row)
        # 구형 후보 순서와 반대인 corpus 순서로 명시 ID bridge의 재배열을 검증한다.
        order = sorted(range(len(candidates)), key=lambda n: exposures[n]["candidate_id"], reverse=True)
        view = {"schema_version": adapter.VIEW_SCHEMA, "stage": "PRE_SELECTION", "post_id": post,
            "source_view": {"schema_version": adapter.SOURCE_SCHEMA, "post_id": post,
                "fragments": [{"raw_path": "/content", "kind": "BODY", "text": text}]},
            "candidate_namespace": "CORPUS_CANDIDATE", "generation_sha256": sha(f"synthetic-r2-{i}".encode()),
            "candidate_set_fingerprint": None, "generation_status": "COMPLETE", "candidates": [candidates[n] for n in order]}
        example = {"example_id": assignment["example_id"], "frozen_view": view,
            "candidate_text_bindings": [text_bindings[n] for n in order], "capture_sha256": None}
        capture = {"schema_version": "reranker_preselection_capture_v1", "stage": "PRE_SELECTION",
            "feature_authority": "SOURCE_OBSERVATION_NOT_GOLD", "example_id": example["example_id"], "post_id": post,
            "binding": row["binding"], "source_spans_sha256": bridge.canonical_sha256(row["source_spans"]),
            "candidate_set_fingerprint": assignment["candidate_set_fingerprint"],
            "frozen_view_sha256": bridge.canonical_sha256(view),
            "candidate_text_bindings_sha256": bridge.canonical_sha256(example["candidate_text_bindings"])}
        capture_raw = raw(capture)
        example["capture_sha256"] = sha(capture_raw)
        evidence[sha(capture_raw)] = capture_raw
        examples[example["example_id"]], bases[example["example_id"]] = example, base
        proofs[example["example_id"]] = complete_proof(titles)
    manifest = split.seal_manifest({"schema_version": split.SCHEMA_VERSION, "data_kind": "SYNTHETIC_FIXTURE",
        "split_policy_version": split.POLICY_VERSION, "sources": sources, "rows": rows})
    train_examples = [examples[r["assignment"]["example_id"]] for r in rows if r["assignment"]["split"] == "TRAIN"]
    trained = nil.train_model(manifest, source_payloads=source_payloads, evidence_payloads=evidence, examples=train_examples,
        config={"base": {"epochs": 2}, "nil_head": {"epochs": 2}})
    model = trained["model"]
    envelope = {"schema_version": adapter.NIL_MANIFEST_SCHEMA, "scorer_id": "synthetic-calibration-bridge",
        "backend": nil.BACKEND, "data_kind": "SYNTHETIC_FIXTURE", "feature_schema": nil.FEATURE_SCHEMA, "model": model}
    model_raw = raw(envelope)
    path = tmp_path / "synthetic_calibration_model_manifest.json"
    with path.open("xb") as stream:
        stream.write(model_raw)
    scorer = adapter.load_scorer(path, expected_sha256=sha(model_raw))
    summary = scorer.summary()
    calibration = CalibrationSplitManifest.create(assignments=[CalibrationSplitAssignment(**a)
        for a in split.calibration_assignments(manifest)], source_label_ledger_sha256=sha(b"synthetic-calibration-label-ledger"),
        assignment_seed_sha256=sha(b"synthetic-calibration-assignment-seed"))
    common = {"scorer_summary": summary, "expected_scorer_summary_sha256": bridge.canonical_sha256(summary),
        "training_manifest": manifest, "expected_training_manifest_sha256": manifest["manifest_sha256"],
        "calibration_manifest": calibration, "expected_calibration_manifest_sha256": calibration.manifest_sha256,
        "source_payloads": source_payloads, "evidence_payloads": evidence}
    cal_rows, frozen_args = [], []
    for row in rows:
        assignment = row["assignment"]
        if assignment["split"] not in {"CALIBRATION", "FROZEN_HOLDOUT"}:
            continue
        eid = assignment["example_id"]
        item = {"example": examples[eid], "raw_receipt": scorer.score(examples[eid]["frozen_view"]),
            "base_shadow": bases[eid], "generation_proof": proofs[eid], "retrieval_state": RetrievalState(),
            "publication_scope_id": "synthetic-calibration-scope"}
        args = {**common, **item}
        bind_graph(args)
        item["source_binding_sha256"] = args["source_binding_sha256"]
        if assignment["split"] == "CALIBRATION":
            cal_rows.append(item)
        else:
            frozen_args.append(args)
    expected_ids = [r["assignment"]["example_id"] for r in rows if r["assignment"]["split"] == "CALIBRATION"]
    cal_kwargs = {**common, "rows": cal_rows, "expected_example_ids": expected_ids}
    events = bridge.build_calibration_fit_events(**cal_kwargs)
    vectors = {a["example"]["example_id"]: bridge.build_frozen_event_score(**a) for a in frozen_args}
    return {"training_manifest": manifest, "calibration_manifest": calibration, "policy": _policy(),
        "source_payloads": source_payloads, "evidence_payloads": evidence, "model": model,
        "model_manifest": envelope, "model_manifest_path": path, "model_manifest_sha256": sha(model_raw),
        "scorer": scorer, "scorer_summary": summary, "common_kwargs": common, "cal_rows": cal_rows,
        "expected_calibration_example_ids": expected_ids, "cal_kwargs": cal_kwargs, "calibration_events": events,
        "frozen_args": frozen_args, "frozen_vectors": vectors,
        "frozen_base_shadows": {eid: bases[eid] for eid in vectors},
        "frozen_assignments": {a.example_id: a for a in calibration.assignments if a.split == "FROZEN_HOLDOUT"}}
