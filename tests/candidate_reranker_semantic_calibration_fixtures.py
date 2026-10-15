"""8행의 실제 합성 R2→의미 producer→TRAIN/NIL→CAL/FROZEN 공용 fixture.

호출 시에만 로컬 합성 base/head 각 2epoch를 실행한다. import 시 실행 없음.
기존 calibration fixture 반환 키와 semantic_inputs(example_id→artifact)를 제공한다.
원문 역할을 수동 score 입력으로 복사하지 않는다. 기본은 별칭 없는 경로이며
with_alias=True는 FROZEN 후보 행에만 실제 R3 별칭·review·family 노출을 추가한다.
"""
from copy import deepcopy
from src.llm_batch.grounding import candidate_reranker_event_bridge as bridge
from src.llm_batch.grounding import candidate_reranker_nil_learned as nil
from src.llm_batch.grounding import candidate_reranker_shadow as adapter
from src.llm_batch.grounding import candidate_reranker_semantic_input as semantic
from src.llm_batch.grounding import candidate_retrieval_shadow as retrieval
from src.llm_batch.grounding import reranker_training_split as split
from src.llm_batch.grounding.candidate_set_calibration_shadow import CalibrationSplitAssignment, CalibrationSplitManifest
from src.llm_batch.grounding.candidate_set_shadow import build_uncalibrated_selective_shadow
from src.llm_batch.promotion_gate import EvidenceRecord, GroundingState, RetrievalState, can_publish_title
from tests.candidate_reranker_calibration_fixtures import raw, sha, _policy, complete_proof, graph_record


def _bind_semantic_graph(args):
    # 독립 fixture의 기존 정확 projection에 새 소비 지문을 명시한다.
    value = graph_record(args)
    value.update(schema_version="candidate_reranker_event_source_binding_v2",
                 semantic_input_sha256=args["raw_receipt"]["semantic_input_sha256"])
    encoded = raw(value)
    args["source_binding_sha256"] = sha(encoded)
    args["evidence_payloads"][sha(encoded)] = encoded


def build_semantic_calibration_fixture(tmp_path, *, with_alias=False) -> dict:
    """호출 시에만 합성 학습/새 model manifest 배타 생성을 한다. CAL 학습은 없다.

    policy의 내부 MappingProxyType 때문에 bundle 전체 deepcopy는 피한다.
    common_kwargs/cal_rows는 deepcopy 가능하며 정책은 to_dict()로 내보낸다.
    """
    sources, rows, source_payloads, evidence, examples, bases, proofs, semantic_inputs = [], [], {}, {}, {}, {}, {}, {}
    for i, (partition, truth_kind) in enumerate((p, t) for p in split.SPLITS for t in ("CANDIDATE", "NIL")):
        sid, post = f"calibration-source-{i}", str(9000 + i)
        alias_fixture = None
        if with_alias and partition == "FROZEN_HOLDOUT" and truth_kind == "CANDIDATE":
            from tests.test_candidate_reranker_alias_evidence import build_alias_fixture
            alias_fixture = build_alias_fixture(tmp_path / "frozen-alias")
        titles = [f"교정합성대상작품{i}", f"교정합성비교작품{i}"]
        if alias_fixture is not None:
            titles = [item["title"] for item in alias_fixture["corpus"]["entries"]]
        text = f"나는 {titles[0]}를 리뷰한다. {titles[1]}은 김하늘 작가의 전작이다. {titles[1]}보다 {titles[0]}가 더 좋다."
        if alias_fixture is not None:
            text = f"나는 아생갤을 리뷰한다. {titles[0]} 안내. {titles[1]}은 김하늘 작가의 전작이다. {titles[1]}보다 {titles[0]}가 더 좋다."
        encoded = text.encode("utf-8")
        source_payloads[sid] = encoded
        sources.append({"source_id": sid, "payload_sha256": sha(encoded), "source_group_id": f"cal-group-{i}",
            "lineage_root_id": f"cal-lineage-{i}", "rights_status": "SYNTHETIC_FIXTURE"})
        annotation = raw({"schema_version": "synthetic_calibration_annotation", "author": "synthetic author",
            "partition": partition, "truth_kind": truth_kind, "identity": titles[0] if truth_kind == "CANDIDATE" else None,
            "roles": ["PRIMARY", "PREVIOUS", "COMPARISON"]})
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
            cid, corpus, role = actual_ids[title], f"cal-corpus-{i}-{j}", "PRIMARY" if j == 0 else "PREVIOUS"
            identity = {"work_id": f"cal-work-{i}-{j}", "edition_id": f"cal-edition-{i}-{j}", "media_type": "WEB_NOVEL"}
            if alias_fixture is not None:
                entry = alias_fixture["corpus"]["entries"][j]
                corpus = entry["corpus_candidate_id"]
                identity = {key: entry[key] for key in identity}
            start = encoded.index(title.encode("utf-8"))
            span = {**original, "utf8_byte_span_start": start, "utf8_byte_span_end": start + len(title.encode("utf-8")),
                "text": title, "span_sha256": sha(title.encode("utf-8"))}
            exposures.append({"candidate_id": cid, "corpus_candidate_id": corpus,
                "polarity": "POSITIVE" if j == 0 and truth_kind == "CANDIDATE" else "NEGATIVE",
                **identity,
                "alias_family_ids": [f"cal-alias-{i}-{j}"], "source_ids": [sid]})
            bridges.append({"corpus_candidate_id": corpus, "status": "UNIQUE", "candidate_ids": [cid], "provenance_sha256": label_sha})
            mentions.append({"candidate_id": cid, "source_span": span, "roles": [role],
                "provenance": {"grade": "SYNTHETIC_FIXTURE", "artifact_sha256": label_sha,
                    "reviewer": "synthetic author", "scope": "MENTION_ROLE"}})
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
        # 실제 고정 corpus→BM25→의미 producer를 사용한다. label의 역할 배열은 입력하지 않는다.
        entries = []
        for exposure, title in zip(exposures, titles):
            corpus_text = title + " 리뷰한다 전작이다"
            entries.append({"corpus_candidate_id": exposure["corpus_candidate_id"],
                **{key: exposure[key] for key in ("work_id", "edition_id", "media_type")},
                "title": title, "aliases": [], "text": corpus_text,
                "content_sha256": retrieval.candidate_content_sha256(title, [], corpus_text),
                "sources": [{"source_ref": sid, "source_sha256": sha(encoded),
                    "lineage_id": f"cal-lineage-{i}", "observed_at": "2026-10-10T00:00:00+09:00",
                    "rights": {"status": "SYNTHETIC_FIXTURE", "basis": "시험 작성자의 합성 원문"}}]})
        corpus = {"schema_version": retrieval.CORPUS_SCHEMA, "corpus_id": f"semantic-cal-{i}",
                  "data_kind": "SYNTHETIC_FIXTURE", "entries": entries}
        if alias_fixture is not None:
            corpus = alias_fixture["corpus"]
        corpus_path = tmp_path / f"corpus_{i}.json"
        corpus_raw = raw(corpus)
        with corpus_path.open("xb") as stream: stream.write(corpus_raw)
        source_view = {"schema_version": retrieval.SOURCE_VIEW_SCHEMA, "post_id": post,
                      "fragments": [{"raw_path": "/content", "kind": "BODY", "text": text}]}
        retrieved = retrieval.load_corpus(corpus_path, expected_sha256=sha(corpus_raw)).observe(source_view)
        original_view = adapter.build_frozen_view(source_view, retrieved)
        if alias_fixture is None:
            artifact = semantic.build_semantic_input(original_view, retrieval_receipt=retrieved)
        else:
            from src.llm_batch.grounding.candidate_reranker_alias_evidence import build_alias_community_source_view
            evidence.update(alias_fixture["evidence_payloads"])
            alias_evidence = {**alias_fixture["alias_evidence"], "retrieval_receipt": retrieved,
                "community_source_view": build_alias_community_source_view(source_view,
                    community={"value": "synthetic-novel-community", "status": "EXPLICIT", "source_path": "/gallery_id"},
                    as_of={"value": "2026-10-08T00:00:00Z", "status": "EXPLICIT", "source_path": "/created_at"})}
            artifact = semantic.build_semantic_input(original_view, retrieval_receipt=retrieved,
                alias_evidence=alias_evidence, evidence_payloads=evidence)
            requirements = semantic.semantic_exposure_requirements(artifact)
            assert len(requirements) == 1 and requirements[0]["alias"] == "아생갤"
            for required in requirements:
                exposed = next(item for item in exposures if item["corpus_candidate_id"] == required["candidate_id"])
                exposed["alias_family_ids"].append(required["alias_family_id"])
                for added_sid, digest in ((required["source_id"], required["payload_sha256"]),
                                          (required["review_source_id"], required["review_payload_sha256"])):
                    source_payloads[added_sid] = evidence[digest]
                    sources.append({"source_id": added_sid, "payload_sha256": digest,
                        "source_group_id": "semantic-group:" + required["lineage_root_id"],
                        "lineage_root_id": required["lineage_root_id"], "rights_status": "SYNTHETIC_FIXTURE"})
                    row["source_ids"].append(added_sid)
                    exposed["source_ids"].append(added_sid)
                payload = source_payloads[required["source_id"]]
                alias_raw = required["alias"].encode("utf-8")
                start = payload.index(alias_raw)
                next(item for item in text_bindings if item["candidate_id"] == required["candidate_id"])["aliases"].append({
                    "source_id": required["source_id"], "raw_path": "/content", "utf8_byte_span_start": start,
                    "utf8_byte_span_end": start + len(alias_raw), "text": required["alias"], "span_sha256": sha(alias_raw)})
            source_by_id = {item["source_id"]: item for item in sources}
            assignment["source_group_fingerprint"] = split.canonical_sha256(sorted({
                source_by_id[key]["source_group_id"] for key in row["source_ids"]}))
        view = artifact["enriched_view"]
        assert len(view["candidates"]) == 2 and view["generation_status"] == "COMPLETE"
        assert artifact["observation"]["counts"]["primary"] >= 1
        assert artifact["observation"]["counts"]["previous"] >= 1
        assert artifact["observation"]["counts"]["comparison"] >= 1
        semantic_inputs[assignment["example_id"]] = artifact
        artifact_raw = raw(artifact)
        evidence[sha(artifact_raw)] = artifact_raw
        binding_by_id = {item["candidate_id"]: item for item in text_bindings}
        example = {"example_id": assignment["example_id"], "frozen_view": view,
            "candidate_text_bindings": [binding_by_id[c["candidate_id"]] for c in view["candidates"]],
            "capture_sha256": None}
        capture = {"schema_version": "reranker_preselection_capture_v2", "stage": "PRE_SELECTION",
            "feature_authority": "SOURCE_OBSERVATION_NOT_GOLD", "example_id": example["example_id"], "post_id": post,
            "binding": row["binding"], "source_spans_sha256": bridge.canonical_sha256(row["source_spans"]),
            "candidate_set_fingerprint": assignment["candidate_set_fingerprint"],
            "frozen_view_sha256": bridge.canonical_sha256(view),
            "candidate_text_bindings_sha256": bridge.canonical_sha256(example["candidate_text_bindings"]),
            "semantic_input_sha256": sha(artifact_raw)}
        capture_raw = raw(capture)
        example["capture_sha256"] = sha(capture_raw)
        evidence[sha(capture_raw)] = capture_raw
        examples[example["example_id"]], bases[example["example_id"]] = example, base
        proofs[example["example_id"]] = complete_proof(titles)
    manifest = split.seal_manifest({"schema_version": split.SCHEMA_VERSION, "data_kind": "SYNTHETIC_FIXTURE",
        "split_policy_version": split.POLICY_VERSION, "sources": sources, "rows": rows})
    train_examples = [examples[r["assignment"]["example_id"]] for r in rows if r["assignment"]["split"] == "TRAIN"]
    trained = nil.train_model(manifest, source_payloads=source_payloads, evidence_payloads=evidence, examples=train_examples,
        config={"base": {"epochs": 2}, "nil_head": {"epochs": 2}}, feature_schema=nil.FEATURE_SCHEMA_V2)
    model = trained["model"]
    envelope = {"schema_version": adapter.NIL_MANIFEST_SCHEMA, "scorer_id": "synthetic-calibration-bridge",
        "backend": nil.BACKEND, "data_kind": "SYNTHETIC_FIXTURE", "feature_schema": nil.FEATURE_SCHEMA_V2, "model": model}
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
        item = {"example": examples[eid], "raw_receipt": scorer.score(examples[eid]["frozen_view"], semantic_input=semantic_inputs[eid], evidence_payloads=evidence),
            "base_shadow": bases[eid], "generation_proof": proofs[eid], "retrieval_state": RetrievalState(),
            "publication_scope_id": "synthetic-calibration-scope"}
        args = {**common, **item}
        _bind_semantic_graph(args)
        item["source_binding_sha256"] = args["source_binding_sha256"]
        if assignment["split"] == "CALIBRATION":
            cal_rows.append(item)
        else:
            frozen_args.append(args)
    expected_ids = [r["assignment"]["example_id"] for r in rows if r["assignment"]["split"] == "CALIBRATION"]
    cal_kwargs = {**common, "rows": cal_rows, "expected_example_ids": expected_ids}
    events = bridge.build_calibration_fit_events(**cal_kwargs)
    vectors = {a["example"]["example_id"]: bridge.build_frozen_event_score(**a) for a in frozen_args}
    return {"semantic_inputs": semantic_inputs, "training_manifest": manifest, "calibration_manifest": calibration, "policy": _policy(),
        "source_payloads": source_payloads, "evidence_payloads": evidence, "model": model,
        "model_manifest": envelope, "model_manifest_path": path, "model_manifest_sha256": sha(model_raw),
        "scorer": scorer, "scorer_summary": summary, "common_kwargs": common, "cal_rows": cal_rows,
        "expected_calibration_example_ids": expected_ids, "cal_kwargs": cal_kwargs, "calibration_events": events,
        "frozen_args": frozen_args, "frozen_vectors": vectors,
        "frozen_base_shadows": {eid: bases[eid] for eid in vectors},
        "frozen_assignments": {a.example_id: a for a in calibration.assignments if a.split == "FROZEN_HOLDOUT"}}
