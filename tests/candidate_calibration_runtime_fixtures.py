"""실제 로컬 R2→MENTIONED→NIL scorer 흐름의 명시 FROZEN 재관측 합성 자료.

build_runtime_calibration_fixture(tmp_path)는 호출 시에만 16문서/8행과 학습 모델,
CAL artifact/runtime bundle을 새 경로에 만든다. 외부 모델/네트워크는 없다.
반환: settings, bundle_path/bundle_sha256/bundle, corpus_path/corpus_sha256,
retrieval_observer, scorer/model/scorer_summary, runtime_rows(8행),
frozen_runtime_rows(2행), training_manifest/calibration_manifest/policy/artifact,
frozen_args, source_payloads/evidence_payloads. runtime_rows의 각 행에는 post,
frozen_view, retrieval_receipt, reranker_receipt, capture, dataset_example_id,
dataset_post_id가 있다. 기존 CAL fixture의 PRIMARY/COMPARISON을 복사하지 않는다.
"""
from copy import deepcopy

from src.llm_batch.domain.models import PostInput
from src.llm_batch.grounding import candidate_retrieval_shadow as retrieval
from src.llm_batch.grounding import candidate_reranker_shadow as adapter
from src.llm_batch.grounding import candidate_reranker_nil_learned as nil
from src.llm_batch.grounding import candidate_reranker_calibration as calibration_fit
from src.llm_batch.grounding import candidate_reranker_event_bridge as bridge
from src.llm_batch.grounding import reranker_training_split as split
from src.llm_batch.grounding.candidate_reranker_roles import observe_preselection_roles
from src.llm_batch.grounding.candidate_set_calibration_shadow import CalibrationSplitAssignment, CalibrationSplitManifest
from src.llm_batch.grounding.candidate_set_shadow import build_uncalibrated_selective_shadow
from src.llm_batch.promotion_gate import EvidenceRecord, GroundingState, RetrievalState, can_publish_title
from src.llm_batch.runtime.candidate_reranker import _source_view, observe_candidate_reranker
from tests.candidate_reranker_calibration_fixtures import raw, sha, _policy, complete_proof, bind_graph


def _write(path, content):
    with path.open("xb") as stream:
        stream.write(content)
    return {"path": path.name, "sha256": sha(content), "bytes": len(content)}


def _stored_row(args, runtime_post_id, dataset_post_id):
    result = {key: deepcopy(args[key]) for key in ("example", "raw_receipt", "base_shadow", "generation_proof",
        "retrieval_state", "publication_scope_id", "source_binding_sha256")}
    result.update(runtime_post_id=runtime_post_id, dataset_post_id=dataset_post_id)
    for key, method in (("base_shadow", "to_dict"), ("generation_proof", "to_ledger_dict"), ("retrieval_state", "to_dict")):
        result[key] = getattr(result[key], method)()
    return result


def build_runtime_calibration_fixture(tmp_path):
    from src.llm_batch.grounding.candidate_reranker_capture import build_capture
    entries = []
    for i in range(8):
        for j, suffix in enumerate(("alpha", "beta")):
            title = f"rtwork{i:02d}{suffix}"
            source_raw = title.encode("utf-8")
            source_path = tmp_path / f"corpus_source_{i}_{j}.txt"
            _write(source_path, source_raw)
            entries.append({"corpus_candidate_id": f"runtime-corpus-{i}-{j}", "work_id": f"runtime-work-{i}-{j}",
                "edition_id": f"runtime-edition-{i}-{j}", "media_type": "WEB_NOVEL", "title": title, "aliases": [],
                "text": title, "content_sha256": retrieval.candidate_content_sha256(title, [], title),
                "sources": [{"source_ref": source_path.name, "source_sha256": sha(source_raw),
                    "lineage_id": f"runtime-corpus-lineage-{i}-{j}", "observed_at": "2026-10-10T00:00:00+09:00",
                    "rights": {"status": "SYNTHETIC_FIXTURE", "basis": "시험 작성자가 새로 만든 합성 제목"}}]})
    corpus = {"schema_version": retrieval.CORPUS_SCHEMA, "corpus_id": "runtime-calibration-synthetic",
        "data_kind": "SYNTHETIC_FIXTURE", "entries": entries}
    corpus_path = tmp_path / "corpus.json"
    corpus_ref = _write(corpus_path, raw(corpus))
    r2 = retrieval.load_corpus(corpus_path, expected_sha256=corpus_ref["sha256"], top_k=20)
    sources, rows, payloads, evidence, examples, bases, proofs, observations = [], [], {}, {}, {}, {}, {}, []
    for i, (partition, truth_kind) in enumerate((p, t) for p in split.SPLITS for t in ("CANDIDATE", "NIL")):
        titles = [f"rtwork{i:02d}alpha", f"rtwork{i:02d}beta"]
        text, sid, eid = " ".join(titles), f"runtime-source-{i}", f"runtime-example-{i:02d}"
        dataset_post = f"dataset-post-{i}"
        post = PostInput(post_id=12000 + i, title=text, content_blocks=[], comments=[])
        original_source = _source_view(post)
        r2_receipt = r2.observe(original_source)
        assert r2_receipt["status"] == "OK" and len(r2_receipt["ranked_candidates"]) == 2
        assert r2_receipt["counts"]["positive_candidates"] == 2 and r2_receipt["counts"]["omitted_ranked_candidates"] == 0
        runtime_view, role_metadata = observe_preselection_roles(adapter.build_frozen_view(original_source, r2_receipt))
        assert role_metadata["status"] == "OBSERVED"
        assert all(c["role_observations"] and all(r["role"] == "MENTIONED" for r in c["role_observations"]) for c in runtime_view["candidates"])
        view = deepcopy(runtime_view)
        view["post_id"] = view["source_view"]["post_id"] = dataset_post
        encoded = text.encode("utf-8")
        payloads[sid] = encoded
        sources.append({"source_id": sid, "payload_sha256": sha(encoded), "source_group_id": f"runtime-source-group-{i}",
            "lineage_root_id": f"runtime-source-lineage-{i}", "rights_status": "SYNTHETIC_FIXTURE"})
        annotation = raw({"schema_version": "synthetic_runtime_calibration_annotation", "example_id": eid,
            "partition": partition, "truth_kind": truth_kind, "identity": titles[0] if truth_kind == "CANDIDATE" else None,
            "roles": ["MENTIONED", "MENTIONED"], "reviewer": "synthetic author"})
        label_sha = sha(annotation); evidence[label_sha] = annotation
        original = {"source_id": sid, "raw_path": "/title", "utf8_byte_span_start": 0, "utf8_byte_span_end": len(encoded),
            "text": text, "span_sha256": sha(encoded)}
        state = GroundingState(post_id=dataset_post, candidate_title=titles[0])
        records = [EvidenceRecord(kind="candidate_preservation", candidate_title=t, supports_publish=True) for t in titles]
        base = build_uncalibrated_selective_shadow(state, records, can_publish_title(state, records), generation_status="COMPLETE")
        actual_ids = {c.titles[0]: c.candidate_id for c in base.candidate_set.candidates}
        exposures, id_bridges, mentions, binding_by_corpus = [], [], [], {}
        for j, title in enumerate(titles):
            cid, corpus_id = actual_ids[title], f"runtime-corpus-{i}-{j}"
            start = encoded.index(title.encode("utf-8"))
            span = {**original, "utf8_byte_span_start": start, "utf8_byte_span_end": start + len(title.encode("utf-8")),
                "text": title, "span_sha256": sha(title.encode("utf-8"))}
            exposures.append({"candidate_id": cid, "corpus_candidate_id": corpus_id,
                "polarity": "POSITIVE" if j == 0 and truth_kind == "CANDIDATE" else "NEGATIVE",
                "work_id": f"runtime-work-{i}-{j}", "edition_id": f"runtime-edition-{i}-{j}", "media_type": "WEB_NOVEL",
                "alias_family_ids": [f"runtime-alias-{i}-{j}"], "source_ids": [sid]})
            id_bridges.append({"corpus_candidate_id": corpus_id, "status": "UNIQUE", "candidate_ids": [cid], "provenance_sha256": label_sha})
            mentions.append({"candidate_id": cid, "source_span": span, "roles": ["MENTIONED"],
                "provenance": {"grade": "SYNTHETIC_FIXTURE", "artifact_sha256": label_sha, "reviewer": "synthetic author", "scope": "MENTION_ROLE"}})
            binding_by_corpus[corpus_id] = {"candidate_id": corpus_id, "titles": [deepcopy(span)], "aliases": []}
        assignment = {"example_id": eid, "post_id": dataset_post, "split_group_id": f"runtime-split-{i}",
            "content_fingerprint": split.canonical_sha256([original]),
            "source_group_fingerprint": split.canonical_sha256([f"runtime-source-group-{i}"]), "split": partition,
            "truth_kind": truth_kind, "truth_label": actual_ids[titles[0]] if truth_kind == "CANDIDATE" else "__NIL__",
            "label_provenance_sha256": label_sha, "candidate_set_fingerprint": base.candidate_set.candidate_set_fingerprint,
            "gold_work_fingerprint": split.canonical_sha256(exposures[0]["work_id"]) if truth_kind == "CANDIDATE" else None,
            "binding_status": "UNIQUE" if truth_kind == "CANDIDATE" else "NOT_APPLICABLE",
            "matched_candidate_ids": [actual_ids[titles[0]]] if truth_kind == "CANDIDATE" else []}
        row = {"assignment": assignment, "binding": {"run_id": "runtime-calibration-dataset-run", "attempt_id": f"runtime-dataset-attempt-{i}", "input_index": i + 1},
            "source_ids": [sid], "source_spans": [original], "exposures": exposures, "r2_id_bridges": id_bridges, "role_mentions": mentions,
            "label_provenance": {"grade": "SYNTHETIC_FIXTURE", "artifact_sha256": label_sha, "reviewer": "synthetic author", "scope": "WORK_IDENTITY"}}
        rows.append(row)
        example = {"example_id": eid, "frozen_view": view,
            "candidate_text_bindings": [binding_by_corpus[c["candidate_id"]] for c in view["candidates"]], "capture_sha256": None}
        capture = {"schema_version": "reranker_preselection_capture_v1", "stage": "PRE_SELECTION", "feature_authority": "SOURCE_OBSERVATION_NOT_GOLD",
            "example_id": eid, "post_id": dataset_post, "binding": row["binding"], "source_spans_sha256": bridge.canonical_sha256([original]),
            "candidate_set_fingerprint": assignment["candidate_set_fingerprint"], "frozen_view_sha256": bridge.canonical_sha256(view),
            "candidate_text_bindings_sha256": bridge.canonical_sha256(example["candidate_text_bindings"])}
        capture_raw = raw(capture); example["capture_sha256"] = sha(capture_raw); evidence[sha(capture_raw)] = capture_raw
        examples[eid], bases[eid], proofs[eid] = example, base, complete_proof(titles)
        observations.append({"post": post, "frozen_view": runtime_view, "retrieval_receipt": r2_receipt,
            "dataset_example_id": eid, "dataset_post_id": dataset_post})
    manifest = split.seal_manifest({"schema_version": split.SCHEMA_VERSION, "data_kind": "SYNTHETIC_FIXTURE",
        "split_policy_version": split.POLICY_VERSION, "sources": sources, "rows": rows})
    trained = nil.train_model(manifest, source_payloads=payloads, evidence_payloads=evidence,
        examples=[examples[r["assignment"]["example_id"]] for r in rows if r["assignment"]["split"] == "TRAIN"],
        config={"base": {"epochs": 2}, "nil_head": {"epochs": 2}})
    model = trained["model"]
    envelope = {"schema_version": adapter.NIL_MANIFEST_SCHEMA, "scorer_id": "runtime-calibration-actual-r2-synthetic",
        "backend": nil.BACKEND, "data_kind": "SYNTHETIC_FIXTURE", "feature_schema": nil.FEATURE_SCHEMA, "model": model}
    model_path = tmp_path / "model_manifest.json"; model_ref = _write(model_path, raw(envelope))
    scorer = adapter.load_scorer(model_path, expected_sha256=model_ref["sha256"]); summary = scorer.summary()
    calibration = CalibrationSplitManifest.create(assignments=[CalibrationSplitAssignment(**a) for a in split.calibration_assignments(manifest)],
        source_label_ledger_sha256=sha(b"runtime-synthetic-label-ledger"), assignment_seed_sha256=sha(b"runtime-synthetic-assignment-seed"))
    common = {"scorer_summary": summary, "expected_scorer_summary_sha256": bridge.canonical_sha256(summary),
        "training_manifest": manifest, "expected_training_manifest_sha256": manifest["manifest_sha256"],
        "calibration_manifest": calibration, "expected_calibration_manifest_sha256": calibration.manifest_sha256,
        "source_payloads": payloads, "evidence_payloads": evidence}
    cal_rows, frozen_args, frozen_rows = [], [], []
    for row, observed in zip(rows, observations):
        eid = row["assignment"]["example_id"]
        observed["reranker_receipt"] = observe_candidate_reranker(scorer, observed["post"], observed["retrieval_receipt"], r2)
        observed["capture"] = build_capture(observed["frozen_view"], observed["reranker_receipt"], observed["retrieval_receipt"], summary)
        if row["assignment"]["split"] not in {"CALIBRATION", "FROZEN_HOLDOUT"}:
            continue
        item = {"example": examples[eid], "raw_receipt": scorer.score(examples[eid]["frozen_view"]), "base_shadow": bases[eid],
            "generation_proof": proofs[eid], "retrieval_state": RetrievalState(), "publication_scope_id": "runtime-calibration-dataset-scope"}
        args = {**common, **item}; bind_graph(args); item["source_binding_sha256"] = args["source_binding_sha256"]
        if row["assignment"]["split"] == "CALIBRATION":
            cal_rows.append(item)
        else:
            frozen_args.append(args)
            frozen_rows.append(_stored_row(args, observed["post"].post_id, observed["dataset_post_id"]))
    events = bridge.build_calibration_fit_events(cal_rows, [r["example"]["example_id"] for r in cal_rows], **common)
    policy = _policy()
    artifact = calibration_fit.fit_temperature(events, split_manifest=calibration, policy=policy)["artifact"]
    folder = tmp_path / "runtime_bundle"; folder.mkdir(exist_ok=False)
    artifact_ref = _write(folder / "artifact.json", raw(artifact.to_dict()))
    maps = {}
    for category, values in (("source_files", payloads), ("evidence_files", evidence)):
        maps[category] = {key: _write(folder / f"{category}_{i}.bin", value) for i, (key, value) in enumerate(values.items())}
    bundle = {"schema_version": "candidate_calibration_runtime_bundle_v1", "artifact": artifact_ref,
        "training_manifest": manifest, "expected_training_manifest_sha256": manifest["manifest_sha256"],
        "calibration_manifest": calibration.to_dict(), "expected_calibration_manifest_sha256": calibration.manifest_sha256,
        "policy": policy.to_dict(), "expected_scorer_summary_sha256": bridge.canonical_sha256(summary),
        **maps, "frozen_rows": frozen_rows}
    bundle_path = folder / "bundle.json"; bundle_ref = _write(bundle_path, raw(bundle))
    settings = {"mode": "SHADOW", "bundle_path": str(bundle_path), "bundle_sha256": bundle_ref["sha256"],
        "sources": {"mode": "CLI", "bundle_path": "CLI", "bundle_sha256": "CLI"}}
    return {"settings": settings, "bundle_path": bundle_path, "bundle_sha256": bundle_ref["sha256"], "bundle": bundle,
        "corpus_path": corpus_path, "corpus_sha256": corpus_ref["sha256"], "retrieval_observer": r2,
        "scorer": scorer, "model": model, "scorer_summary": summary, "runtime_rows": observations,
        "frozen_runtime_rows": observations[-2:], "training_manifest": manifest, "calibration_manifest": calibration,
        "policy": policy, "artifact": artifact, "frozen_args": frozen_args, "source_payloads": payloads, "evidence_payloads": evidence}
