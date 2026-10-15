"""새 provider 계약용 합성 원본. 실제 모델·원격 검색·과거 자료를 사용하지 않는다."""
from copy import deepcopy
import hashlib
from pathlib import Path

from src.llm_batch.ledger.publication_commit import (
    PUBLICATION_COMMIT_EVENT_SCHEMA, build_publication_scope_descriptor,
    compute_publication_decision_commit,
)
from src.llm_batch.ledger.recovery_activation import _create_event, extract_direct_ocr_review_proposals
from src.llm_batch.measurement.semantic_review_router import build_semantic_review_router_receipt
from src.llm_batch.measurement.semantic_recovery_plan import build_semantic_recovery_plan_receipt
from src.llm_batch.measurement.recovery_provider_contract import (
    SOURCE_SCHEMA, bind_recovery_provider_plan, build_recovery_provider_plan,
)
from tests.recovery_execution_fixtures import HMAC_KEY, _hold_result, json_bytes


def build_recovery_provider_fixture(root: Path, *, post_id=101, relation_role="primary",
        export_run_id="provider-export-fixture", input_format="JSONL_POST_COMMENT_V1",
        publication_post_id=None) -> dict:
    """실제 typed validators를 사용하는 TEST_SYNTHETIC 자료다.

    publication_post_id는 커밋 선택 인자만 바꾸며 원문 post_id를 변환하지 않는다.
    숫자 문자열 선택 인자는 공개 계약이 정규화하지만 원문·WAL 타입은 그대로 검산한다.
    """
    root = Path(root).resolve()
    source_dir = root / "source"
    source_dir.mkdir(parents=True, exist_ok=False)
    ids = [post_id, 202 if post_id != 202 else 203]
    results = [_hold_result(identifier, relation_role) for identifier in ids]
    results[0]["comments"] = ["합성 독자 원문 댓글"]
    inputs = [{key: deepcopy(result[key]) for key in ("gallery_id", "post_id", "title", "content", "comments")}
              for result in results]
    if input_format == "JSONL_POST_COMMENT_V1":
        inputs[0]["comments"] = []
        records = [inputs[0], {"post_id": post_id, "comment_id": "synthetic-comment-1",
                               "content": results[0]["comments"][0]}, inputs[1]]
        input_raw = b"".join(json_bytes(row) + b"\n" for row in records)
    else:
        records = inputs
        input_raw = json_bytes(inputs)
    input_sha = hashlib.sha256(input_raw).hexdigest()
    scope = build_publication_scope_descriptor(input_file_sha256=input_sha, post_ids=ids,
        config_hash="provider-contract-test-only", release_fingerprint="TEST_SYNTHETIC")
    receipts = [compute_publication_decision_commit(result, publication_scope_id=scope.publication_scope_id,
        attempt_run_id="original-owner-fixture", input_index=index,
        post_id=publication_post_id if index == 1 and publication_post_id is not None else result["post_id"])
        for index, result in enumerate(results, 1)]
    receipt = receipts[0]
    result = results[0]
    router = build_semantic_review_router_receipt(result, receipt, attempt_run_id=receipt.attempt_run_id)
    recovery = build_semantic_recovery_plan_receipt(result, receipt, attempt_run_id=receipt.attempt_run_id)
    proposals = extract_direct_ocr_review_proposals(result)
    assert len(proposals) == 1, "합성 fixture의 원본 OCR proposal은 정확히 하나여야 한다"
    proposal = proposals[0]
    event = _create_event(receipt=receipt, proposal=proposal, raw_capability="fixture-audit-token-only",
        hmac_key=HMAC_KEY, sequence=1, prev_event_sha256="GENESIS")
    item = result["analysis_result"]["identity"]["image_evidence_catalog"][0]
    query = proposal.raw_candidate_title
    capture = {"schema_version": SOURCE_SCHEMA, "data_kind": "TEST_SYNTHETIC",
        "input_raw_sha256": input_sha, "input_index": 1, "post_id": post_id,
        "source_locator": proposal.source_locator, "item": deepcopy(item)}
    source_binding = {"source_locator": proposal.source_locator,
        "source_item_sha256": hashlib.sha256(json_bytes(item)).hexdigest(), "field_pointer": "/ocr_text",
        "span_start": 0, "span_end": len(query.encode("utf-8")), "span_unit": "UTF8_FIELD_VALUE",
        "query": query, "query_sha256": hashlib.sha256(query.encode("utf-8")).hexdigest(),
        "relation_role": proposal.relation_role}
    policy = {"max_calls": 1, "max_elapsed_ms": 1000, "request_timeout_ms": 100,
              "max_response_bytes": 4096, "max_total_response_bytes": 4096}
    manifest = {"run_id": export_run_id, "output_file": str(source_dir / "result.json"),
        "publication_scope_id": scope.publication_scope_id,
        "publication_input_snapshot_sha256": input_sha,
        "publication_scope_descriptor_sha256": scope.descriptor_sha256,
        "terminal_artifacts_finalized": True, "completed_count": 2, "flushed_count": 2,
        "pending_count": 0, "partial_flush_gap": False, "data_kind": "TEST_SYNTHETIC"}
    raw = {"input": input_raw, "result": json_bytes(results), "manifest": json_bytes(manifest),
        "publication_wal": b"".join(json_bytes({"schema_version": PUBLICATION_COMMIT_EVENT_SCHEMA,
            "receipt": rec.to_dict(), "result": value}) + b"\n" for rec, value in zip(receipts, results)),
        "activation_journal": json_bytes(event.to_dict()) + b"\n", "router": json_bytes(router),
        "recovery_plan": json_bytes(recovery), "source_capture": json_bytes(capture),
        "scope_descriptor": json_bytes(scope.to_dict())}
    refs = {}
    for role, data in raw.items():
        path = source_dir / (role + (".jsonl" if role in {"input", "publication_wal", "activation_journal"} else ".json"))
        with path.open("xb") as stream:
            stream.write(data)
        refs[role] = {"path": str(path), "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}
    kwargs = {"source_refs": refs, "source_bytes": raw, "input_format": input_format,
        "result_pointer": "/0", "router_pointer": "", "recovery_plan_pointer": "",
        "publication_decision_id": receipt.decision_id, "activation_event_sha256": event.event_sha256,
        "source_binding": source_binding, "endpoint": "http://127.0.0.1:9/mcp/search",
        "payload": {"query": query, "num_results": 2, "purpose": recovery["plan"]["query_plan"]["purposes"][0]},
        "policy": policy, "output_dir": str(root / "output"), "hmac_key": HMAC_KEY}
    plan = build_recovery_provider_plan(**kwargs)
    bound = bind_recovery_provider_plan(plan, hmac_key=HMAC_KEY)
    return {"plan": plan, "bound": bound, "build_kwargs": kwargs, "hmac_key": HMAC_KEY,
        "source_refs": refs, "source_bytes": raw, "result": result, "results": results,
        "receipt": receipt, "receipts": receipts, "event": event, "manifest": manifest,
        "router": router, "recovery_plan": recovery, "source_binding": source_binding,
        "source_capture": capture, "scope": scope, "input_records": records, "input_posts": inputs}
