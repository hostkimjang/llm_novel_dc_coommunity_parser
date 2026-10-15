"""실제 합성 semantic NIL/CAL 모델과 학습 분할 밖 새 두 입력의 공용 자료."""
import hashlib
import json


def raw(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def sha(value):
    return hashlib.sha256(value).hexdigest()


def build_candidate_inference_fixture(tmp_path):
    """호출 시에만 합성 학습과 CAL fit. 실제 runtime/CLI에는 학습을 추가하지 않는다."""
    from src.llm_batch.domain.models import PostInput
    from src.llm_batch.grounding import candidate_retrieval_shadow as r2
    from src.llm_batch.grounding.candidate_reranker_calibration import fit_temperature
    from src.llm_batch.runtime.candidate_reranker import _source_view, observe_candidate_reranker_with_capture
    from src.llm_batch.runtime.candidate_semantics import CandidateSemanticsObserver, observe_candidate_semantics
    from src.llm_batch.runtime.candidate_inference import prepare_candidate_inference
    from tests.candidate_reranker_semantic_calibration_fixtures import build_semantic_calibration_fixture
    from tools.build_candidate_inference_bundle import build_bundle
    training_dir = tmp_path / "training"
    training_dir.mkdir(parents=True)
    trained = build_semantic_calibration_fixture(training_dir)
    artifact = fit_temperature(trained["calibration_events"], split_manifest=trained["calibration_manifest"],
                               policy=trained["policy"])["artifact"]
    files = tmp_path / "declared-inputs"
    files.mkdir()

    def write(name, value):
        path = files / name
        with path.open("xb") as stream:
            stream.write(value)
        return {"path": str(path), "sha256": sha(value), "bytes": len(value)}

    titles = ["새로운은하연대기", "새로운바다일대기"]
    entries, payloads, source_files = [], {}, {}
    for i, title in enumerate(titles):
        content = (title + " 리뷰 비교 전작").encode("utf-8")
        digest = sha(content)
        payloads[digest] = content
        source_files[digest] = write(f"source-{i}.txt", content)
        text = content.decode("utf-8")
        entries.append({"corpus_candidate_id": f"inference-unseen-candidate-{i}",
            "work_id": f"inference-unseen-work-{i}", "edition_id": f"inference-unseen-edition-{i}",
            "media_type": "WEB_NOVEL", "title": title, "aliases": [], "text": text,
            "content_sha256": r2.candidate_content_sha256(title, [], text),
            "sources": [{"source_ref": f"source-{i}.txt", "source_sha256": digest,
                "lineage_id": f"inference-unseen-lineage-{i}", "observed_at": "2026-10-10T00:00:00+09:00",
                "rights": {"status": "SYNTHETIC_FIXTURE", "basis": "시험 작성자가 만든 새 작품·원문"}}]})
    corpus = {"schema_version": r2.CORPUS_SCHEMA, "corpus_id": "unseen-inference-corpus",
        "data_kind": "SYNTHETIC_FIXTURE", "entries": entries}
    corpus_raw = raw(corpus)
    spec = {"scorer_summary": write("scorer-summary.json", raw(trained["scorer_summary"])),
        "artifact": write("artifact.json", raw(artifact.to_dict())),
        "calibration_manifest": write("calibration-manifest.json", raw(trained["calibration_manifest"].to_dict())),
        "policy": write("policy.json", raw(trained["policy"].to_dict())),
        "corpus_snapshot": write("corpus.json", corpus_raw), "source_files": source_files}
    built = build_bundle(**spec, output_dir=tmp_path / "inference-bundle")
    settings = {"mode": "SHADOW", "bundle_path": built["bundle_path"], "bundle_sha256": built["bundle_sha256"],
        "sources": {"mode": "CLI", "bundle_path": "CLI", "bundle_sha256": "CLI"}}
    retrieval = r2.load_corpus_bytes(corpus_raw, expected_sha256=sha(corpus_raw))
    semantic = CandidateSemanticsObserver()
    scorer = trained["scorer"]
    observer = prepare_candidate_inference(settings, scorer)
    assert observer.summary()["status"] == "AVAILABLE", observer.summary()
    rows = []
    for i in range(2):
        # 현재 BM25는 조사 분리 형태소 분석기가 아니다. 원문에 독립 제목도
        # 실제로 기록하여 corpus token과 매칭하고 역할 문장은 별도로 보존한다.
        text = f"작품 목록: {titles[0]} {titles[1]}. 나는 {titles[i]}를 리뷰한다. {titles[1-i]}은 김하늘 작가의 전작이다. {titles[1-i]}보다 {titles[i]}가 더 좋다."
        post = PostInput(post_id=64001+i, title=text, content_blocks=[], comments=[])
        retrieval_receipt = retrieval.observe(_source_view(post))
        assert retrieval_receipt["status"] == "OK" and len(retrieval_receipt["ranked_candidates"]) == 2, retrieval_receipt
        semantics = observe_candidate_semantics(semantic, post, retrieval_receipt, retrieval)
        scored = observe_candidate_reranker_with_capture(scorer, post, retrieval_receipt, retrieval,
            semantic_package=semantics, semantic_observer=semantic)
        assert scored["capture"] is not None, scored
        observed = observer.observe(post, scored["capture"], scored["receipt"])
        assert observed["status"] == "TEMPERATURE_APPLIED_BOUND_INFERENCE", observed
        rows.append({"post": post, "retrieval_receipt": retrieval_receipt, "semantic_package": semantics,
            "capture": scored["capture"], "reranker_receipt": scored["receipt"], "package": observed,
            "graph": observed["graph"], "inference": observed["inference"]})
    assert not {str(row["post"].post_id) for row in rows} & {a.post_id for a in trained["calibration_manifest"].assignments}
    return {"training": trained, "artifact": artifact, "calibration_manifest": trained["calibration_manifest"],
        "policy": trained["policy"], "scorer": scorer, "scorer_summary": scorer.summary(), "observer": observer,
        "retrieval_observer": retrieval, "semantic_observer": semantic, "rows": rows,
        "corpus": corpus, "corpus_snapshot": corpus_raw, "corpus_sha256": sha(corpus_raw), "source_payloads": payloads,
        "spec": spec, "settings": settings, "build_receipt": built,
        "input_paths": [ref["path"] for key,ref in spec.items() if key != "source_files"]
            + [ref["path"] for ref in source_files.values()]}


build_inference_fixture = build_candidate_inference_fixture
