"""명시 raw SHA로 고정한 기존 CAL/model/corpus 파일을 새 일반 추론 bundle로 묶는다."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def build_bundle(*, scorer_summary, artifact, calibration_manifest, policy, corpus_snapshot,
                 source_files, output_dir):
    """파일 인수는 {path,sha256,bytes}. source_files는 raw SHA→동일 참조다.

    새 온도 학습이나 model score를 호출하지 않는다. 이미 학습된 artifact의
    고정 CAL 수치 재생 검산은 수행하며 입력과 기존 출력은 변경하지 않는다.
    """
    from tools import run_candidate_reranker_training as local
    from src.llm_batch.runtime.candidate_inference import (
        BUNDLE_SCHEMA, MAX_JSON_BYTES, MAX_PAYLOAD_BYTES, read_inference_bundle,
    )
    from src.llm_batch.grounding.candidate_retrieval_shadow import load_corpus_bytes, MAX_CORPUS_BYTES
    from src.llm_batch.grounding.candidate_reranker_calibration_inference import prepare_inference_calibration
    snapshots = {}

    def read(ref, limit):
        local._require(type(ref) is dict and set(ref) == {"path", "sha256", "bytes"}, "입력 참조 필드 불일치")
        local._require(local._hex(ref["sha256"]) and type(ref["bytes"]) is int and 0 <= ref["bytes"] <= limit,
                       "입력 SHA/크기 제한 불일치")
        path = local._local_path(ref["path"])
        raw = local._read(path, ref["bytes"])
        local._require(len(raw) == ref["bytes"] and local._sha(raw) == ref["sha256"], "입력 raw SHA/크기 불일치")
        local._require(str(path) not in snapshots or snapshots[str(path)] == raw, "입력 참조 판독 중 변경")
        snapshots[str(path)] = raw
        return raw

    refs = {"artifact": artifact, "calibration_manifest": calibration_manifest, "policy": policy}
    files = {name: read(ref, MAX_JSON_BYTES) for name, ref in refs.items()}
    summary = local._strict_json(read(scorer_summary, MAX_JSON_BYTES))
    core = prepare_inference_calibration(scorer_summary=summary,
        **{name: local._strict_json(raw) for name, raw in files.items()})
    corpus = read(corpus_snapshot, MAX_CORPUS_BYTES)
    r2 = load_corpus_bytes(corpus, expected_sha256=local._sha(corpus))
    local._require(r2.summary()["data_kind"] == summary["data_kind"], "모델/corpus data_kind 불일치")
    local._require(type(source_files) is dict and len(source_files) <= 4096, "원문 파일 목록 제한")
    sources, total = {}, 0
    for digest, ref in source_files.items():
        local._require(local._hex(digest) and type(ref) is dict and ref.get("sha256") == digest, "원문 키/SHA 불일치")
        raw = read(ref, MAX_PAYLOAD_BYTES)
        total += len(raw)
        local._require(total <= MAX_PAYLOAD_BYTES, "원문 전체 byte 제한")
        sources[digest] = raw
    declared = {source["source_sha256"] for entry in local._strict_json(corpus)["entries"] for source in entry["sources"]}
    local._require(declared <= set(sources), "corpus 원문 payload 누락")
    local._check_inputs(snapshots)
    output = local._local_path(output_dir)
    output.mkdir(parents=True, exist_ok=False)

    def write_bytes(name, raw):
        path = local._local_path(output / name)
        with path.open("xb") as stream:
            local._require(stream.write(raw) == len(raw), "출력 부분 쓰기")
            stream.flush()
            os.fsync(stream.fileno())
        local._require(local._read(path, len(raw)) == raw, "출력 재판독 불일치")
        return {"path": name, "sha256": local._sha(raw), "bytes": len(raw)}

    value = {"schema_version": BUNDLE_SCHEMA, "expected_scorer_summary_sha256": local._sha(local._json_bytes(summary)),
        **{name: write_bytes(name + ".json", raw) for name, raw in files.items()},
        "corpus_snapshot": write_bytes("corpus.json", corpus),
        "source_files": {digest: write_bytes(digest + ".source", raw) for digest, raw in sorted(sources.items())}}
    local._write(output / "bundle.json", value)
    bundle_raw = local._read(output / "bundle.json", 1024 * 1024)
    read_inference_bundle(output / "bundle.json", expected_sha256=local._sha(bundle_raw))
    local._check_inputs(snapshots)
    receipt = {"schema_version": "candidate_inference_bundle_build_receipt_v1", "status": "PASS",
        "bundle_path": str(output / "bundle.json"), "bundle_sha256": local._sha(bundle_raw),
        "bundle_bytes": len(bundle_raw), "input_raw_sha256": {name: local._sha(raw) for name,raw in snapshots.items()},
        "calibration_summary": core.summary(), "training_calls": 0, "new_temperature_fit_calls": 0,
        "calibration_numeric_replay_performed": True,
        "score_calls": 0, "network_calls": 0, "actual_quality_evaluated": False,
        "publication_authority": False, "public_apply": False, "central_db_write": False}
    local._write(output / "build_receipt.json", receipt)
    return receipt


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", required=True, help="모든 입력의 명시 path/SHA/bytes와 source_files를 담은 JSON")
    parser.add_argument("--spec-sha256", required=True)
    parser.add_argument("--output-dir", required=True, help="존재하지 않는 새 출력 폴더")
    args = parser.parse_args(argv)
    from tools import run_candidate_reranker_training as local
    raw = local._read(local._local_path(args.spec), 1024 * 1024)
    local._require(local._hex(args.spec_sha256) and local._sha(raw) == args.spec_sha256, "spec SHA 불일치")
    spec = local._strict_json(raw)
    local._require(set(spec) == {"scorer_summary", "artifact", "calibration_manifest", "policy", "corpus_snapshot", "source_files"},
                   "spec 필드 불일치")
    receipt = build_bundle(**spec, output_dir=args.output_dir)
    print(json.dumps(receipt, ensure_ascii=False, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
