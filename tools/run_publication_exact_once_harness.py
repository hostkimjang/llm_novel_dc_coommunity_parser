from __future__ import annotations

"""P2 최종 공개 판정 exact-once 저장본/합성 공격 하네스.

이 도구는 새 LLM 실행을 만들지 않는다. 동결 Golden18 결과를 읽고 결과
JSON은 전혀 바꾸지 않은 채, 별도 임시 sidecar 저널에 최종 공개 판정
영수증을 기록해 개선 전/후의 증명 가능 범위를 비교한다.
"""

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime
import hashlib
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from typing import Any, Callable, Iterable, Mapping


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.llm_batch.ledger.publication_commit import (  # noqa: E402
    PUBLICATION_COMMIT_JOURNAL_SCHEMA,
    PUBLICATION_COMMIT_OWNER,
    PUBLICATION_COMMIT_SCHEMA,
    PublicationCommitError,
    PublicationCommitRegistry,
    PublicationDecisionCommit,
    PublicationScopeDescriptor,
    audit_publication_commits,
    build_publication_scope_descriptor,
    build_publication_scope_id,
    commit_publication_result,
    compute_publication_decision_commit,
    validate_publication_result_commit,
)


RUN_SPEC_SCHEMA = "publication-exact-once-runspec-v2"
REPORT_SCHEMA = "publication-exact-once-comparison-v2"
MODE = "SAVED_ARTIFACT_AND_SYNTHETIC_SHADOW_NO_RUNTIME"
TREATMENT = "scope_owned_sidecar_cas_fsync_v2"
OUTPUT_ROOT = ROOT / "out" / "publication_exact_once_harness_20260711"


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _resolve_path(value: str | Path) -> Path:
    path = Path(value)
    return (path if path.is_absolute() else ROOT / path).resolve()


def _stored_path(value: str | Path) -> str:
    path = _resolve_path(value)
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _canonical_hash(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _artifact_ref(value: str | Path) -> dict[str, Any]:
    path = _resolve_path(value)
    if not path.is_file():
        raise ValueError(f"artifact missing: {path}")
    return {
        "path": _stored_path(path),
        "sha256": _sha256_file(path),
        "bytes": path.stat().st_size,
    }


def _read_json(value: str | Path) -> Any:
    return json.loads(_resolve_path(value).read_text(encoding="utf-8-sig"))


def _post_id(value: Any) -> int | str:
    if isinstance(value, bool) or value in (None, ""):
        raise ValueError("post_id must be non-empty")
    if isinstance(value, int):
        if value <= 0:
            raise ValueError("post_id must be positive")
        return value
    text = str(value).strip()
    if not text:
        raise ValueError("post_id must be non-empty")
    try:
        number = int(text)
    except ValueError:
        return text
    if number <= 0:
        raise ValueError("post_id must be positive")
    return number


def _post_contract(rows: list[dict[str, Any]]) -> dict[str, Any]:
    # P1/P0 계약은 숫자형 ID도 문자열로 정규화한다.
    post_ids = [str(_post_id(row.get("post_id"))) for row in rows]
    counts = Counter(post_ids)
    duplicates = sorted(value for value, count in counts.items() if count > 1)
    if duplicates:
        raise ValueError(f"duplicate post_id: {','.join(duplicates)}")
    return {
        "row_count": len(post_ids),
        "post_id_order_sha256": _canonical_hash(post_ids),
        "post_id_set_sha256": _canonical_hash(sorted(post_ids)),
        "post_ids": post_ids,
    }


def _assert_contract(left: Mapping[str, Any], right: Mapping[str, Any], label: str) -> None:
    for key in ("row_count", "post_id_order_sha256", "post_id_set_sha256"):
        if left.get(key) != right.get(key):
            raise ValueError(f"{label} {key} mismatch")


def _implementation_contract() -> dict[str, Any]:
    refs = {
        "harness_tool": _artifact_ref(Path(__file__)),
        "publication_commit": _artifact_ref(ROOT / "src/llm_batch/publication_commit.py"),
        "expert_main": _artifact_ref(ROOT / "expert_main.py"),
        "promotion_gate": _artifact_ref(ROOT / "src/llm_batch/promotion_gate.py"),
        "recovery_tool": _artifact_ref(ROOT / "tools/recover_expert_run_from_checkpoint.py"),
        "decision_call_independent_reader": _artifact_ref(
            ROOT / "src/llm_batch/decision_call_readback.py"
        ),
        "decision_call_reader_tests": _artifact_ref(
            ROOT / "tests/test_decision_call_readback.py"
        ),
        "fresh_measurement_recovery_tests": _artifact_ref(
            ROOT / "tests/test_fresh_measurement_recovery.py"
        ),
        "convergence_audit": _artifact_ref(
            ROOT / "tools/audit_publication_contract_convergence.py"
        ),
    }
    hashes = {name: ref["sha256"] for name, ref in sorted(refs.items())}
    return {"artifacts": refs, "sha256": _canonical_hash(hashes)}


def _validate_artifact_ref(value: Any, label: str) -> Path:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} reference missing")
    path = _resolve_path(str(value.get("path") or ""))
    if _artifact_ref(path) != dict(value):
        raise ValueError(f"{label} reference mismatch")
    return path


def _parent_chain(
    p1_path: Path,
    producer_path: Path,
) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    from tools.run_candidate_generation_completeness_harness import (
        validate_run_spec as validate_producer,
    )
    from tools.run_candidate_set_nil_shadow_harness import validate_run_spec as validate_p1

    p1, p1_rows, _ = validate_p1(p1_path, verify_implementation=False)
    producer, producer_rows = validate_producer(
        producer_path,
        verify_implementation=False,
    )
    if [_post_id(row.get("post_id")) for row in producer_rows] != [
        _post_id(row.get("post_id")) for row in p1_rows
    ]:
        raise ValueError("P1/producer row order mismatch")
    producer_artifacts = producer.get("artifacts")
    if not isinstance(producer_artifacts, Mapping):
        raise ValueError("producer artifacts missing")
    if dict(producer_artifacts.get("p1_parent_run_spec") or {}) != _artifact_ref(p1_path):
        raise ValueError("producer does not bind the selected P1 run spec")
    p1_artifacts = p1.get("artifacts")
    if not isinstance(p1_artifacts, Mapping):
        raise ValueError("P1 artifacts missing")
    if dict(producer_artifacts.get("baseline_result") or {}) != dict(
        p1_artifacts.get("baseline_result") or {}
    ):
        raise ValueError("P1/producer baseline binding mismatch")
    contract = _post_contract(p1_rows)
    _assert_contract(contract, p1.get("post_contract") or {}, "P1 post contract")
    _assert_contract(contract, producer.get("post_contract") or {}, "producer post contract")
    return p1, producer, p1_rows, contract


def _run_spec_self_hash(spec: Mapping[str, Any]) -> str:
    payload = {
        key: value
        for key, value in spec.items()
        if key not in {"generated_at", "run_spec_sha256"}
    }
    return _canonical_hash(payload)


def create_run_spec(
    *,
    parent_p1_run_spec_path: str | Path,
    parent_producer_run_spec_path: str | Path,
) -> dict[str, Any]:
    p1_path = _resolve_path(parent_p1_run_spec_path)
    producer_path = _resolve_path(parent_producer_run_spec_path)
    p1, producer, _rows, contract = _parent_chain(p1_path, producer_path)
    baseline_ref = dict(p1["artifacts"]["baseline_result"])
    implementation = _implementation_contract()
    scope_config_hash = _canonical_hash(
        {
            "treatment": TREATMENT,
            "p1": p1.get("run_spec_sha256"),
            "producer": producer.get("run_spec_sha256"),
        }
    )
    release_fingerprint = implementation["sha256"]
    scope_descriptor = build_publication_scope_descriptor(
        input_file_sha256=baseline_ref["sha256"],
        post_ids=contract["post_ids"],
        config_hash=scope_config_hash,
        release_fingerprint=release_fingerprint,
    )
    scope_id = scope_descriptor.publication_scope_id
    spec: dict[str, Any] = {
        "schema_version": RUN_SPEC_SCHEMA,
        "generated_at": _now(),
        "mode": MODE,
        "treatment": TREATMENT,
        "artifacts": {
            "p1_parent_run_spec": _artifact_ref(p1_path),
            "producer_parent_run_spec": _artifact_ref(producer_path),
            "baseline_result": baseline_ref,
        },
        "parent_contract": {
            "p1_run_spec_self_hash": p1.get("run_spec_sha256"),
            "producer_run_spec_self_hash": producer.get("run_spec_sha256"),
        },
        "post_contract": contract,
        "implementation_contract": implementation,
        "publication_commit_contract": {
            "schema_version": PUBLICATION_COMMIT_SCHEMA,
            "journal_schema": PUBLICATION_COMMIT_JOURNAL_SCHEMA,
            "owner": PUBLICATION_COMMIT_OWNER,
            "cas_key": ["publication_scope_id", "post_id"],
            "publication_scope_id": scope_id,
            "scope_descriptor": scope_descriptor.to_dict(),
            "scope_config_hash": scope_config_hash,
            "release_fingerprint": release_fingerprint,
            "result_json_receipt_embedded": False,
            "receipt_raw_title_or_url_copied": False,
            "journal_event_contains_recoverable_result_row": True,
        },
        "approval_boundary": {
            "runtime_validation": "NOT_RUN",
            "saved_artifact_only": True,
            "synthetic_attacks": True,
            "semantic_quality": "REVIEW-LOCKED",
            "full_scan_approval": False,
        },
    }
    spec["run_spec_sha256"] = _run_spec_self_hash(spec)
    return spec


def _assert_output_paths(paths: Iterable[Path]) -> None:
    root = OUTPUT_ROOT.resolve()
    resolved = [path.resolve() for path in paths]
    if len(resolved) != len(set(resolved)):
        raise ValueError("output paths must be distinct")
    for path in resolved:
        if root not in path.parents:
            raise ValueError(f"output must stay under {_stored_path(root)}: {path}")
        if path.exists():
            raise ValueError(f"refusing to overwrite existing output: {path}")


def write_run_spec(spec: Mapping[str, Any], output: str | Path) -> Path:
    path = _resolve_path(output)
    _assert_output_paths([path])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(spec, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return path


def _validate_frozen_implementation_contract(implementation: Any) -> None:
    if not isinstance(implementation, Mapping) or not isinstance(implementation.get("artifacts"), Mapping):
        raise ValueError("implementation contract missing")
    hashes: dict[str, str] = {}
    for name, ref in implementation["artifacts"].items():
        if not isinstance(name, str) or not isinstance(ref, Mapping):
            raise ValueError("frozen implementation artifact invalid")
        path, digest, size = ref.get("path"), ref.get("sha256"), ref.get("bytes")
        if not isinstance(path, str) or Path(path).is_absolute() or not path:
            raise ValueError(f"frozen implementation path invalid: {name}")
        if not isinstance(digest, str) or len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
            raise ValueError(f"frozen implementation sha256 invalid: {name}")
        if not isinstance(size, int) or size <= 0:
            raise ValueError(f"frozen implementation bytes invalid: {name}")
        hashes[name] = digest
    if not hashes or implementation.get("sha256") != _canonical_hash(dict(sorted(hashes.items()))):
        raise ValueError("frozen implementation contract sha256 mismatch")


def validate_run_spec(
    path: str | Path,
    *,
    verify_implementation: bool = True,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    spec = _read_json(path)
    if (
        not isinstance(spec, dict)
        or spec.get("schema_version") != RUN_SPEC_SCHEMA
        or spec.get("mode") != MODE
        or spec.get("treatment") != TREATMENT
    ):
        raise ValueError("unsupported publication exact-once RunSpec")
    if spec.get("run_spec_sha256") != _run_spec_self_hash(spec):
        raise ValueError("RunSpec self hash mismatch")
    artifacts = spec.get("artifacts")
    if not isinstance(artifacts, Mapping):
        raise ValueError("RunSpec artifacts missing")
    p1_path = _validate_artifact_ref(artifacts.get("p1_parent_run_spec"), "P1 parent")
    producer_path = _validate_artifact_ref(
        artifacts.get("producer_parent_run_spec"), "producer parent"
    )
    baseline_path = _validate_artifact_ref(artifacts.get("baseline_result"), "baseline")
    p1, producer, rows, contract = _parent_chain(p1_path, producer_path)
    if _resolve_path(str(p1["artifacts"]["baseline_result"]["path"])) != baseline_path:
        raise ValueError("RunSpec baseline path differs from parent baseline")
    _assert_contract(contract, spec.get("post_contract") or {}, "RunSpec post contract")
    parent = spec.get("parent_contract") or {}
    if parent.get("p1_run_spec_self_hash") != p1.get("run_spec_sha256"):
        raise ValueError("P1 self-hash binding mismatch")
    if parent.get("producer_run_spec_self_hash") != producer.get("run_spec_sha256"):
        raise ValueError("producer self-hash binding mismatch")
    implementation = spec.get("implementation_contract")
    _validate_frozen_implementation_contract(implementation)
    if verify_implementation and implementation != _implementation_contract():
        raise ValueError("implementation contract mismatch")
    commit = spec.get("publication_commit_contract")
    if not isinstance(commit, Mapping):
        raise ValueError("publication commit contract missing")
    if commit.get("schema_version") != PUBLICATION_COMMIT_SCHEMA:
        raise ValueError("publication commit schema mismatch")
    if commit.get("journal_schema") != PUBLICATION_COMMIT_JOURNAL_SCHEMA:
        raise ValueError("publication journal schema mismatch")
    if commit.get("owner") != PUBLICATION_COMMIT_OWNER:
        raise ValueError("publication owner mismatch")
    if commit.get("cas_key") != ["publication_scope_id", "post_id"]:
        raise ValueError("publication CAS key mismatch")
    expected_descriptor = build_publication_scope_descriptor(
        input_file_sha256=artifacts["baseline_result"]["sha256"],
        post_ids=contract["post_ids"],
        config_hash=commit.get("scope_config_hash"),
        release_fingerprint=commit.get("release_fingerprint"),
    )
    if commit.get("scope_descriptor") != expected_descriptor.to_dict():
        raise ValueError("publication scope descriptor binding mismatch")
    if commit.get("publication_scope_id") != expected_descriptor.publication_scope_id:
        raise ValueError("publication scope binding mismatch")
    return spec, rows


def _identity(row: Mapping[str, Any]) -> Mapping[str, Any]:
    analysis = row.get("analysis_result")
    if isinstance(analysis, Mapping) and isinstance(analysis.get("identity"), Mapping):
        return analysis["identity"]
    return {}


def _public_snapshot(row: Mapping[str, Any]) -> dict[str, Any]:
    identity = _identity(row)
    ledger = identity.get("candidate_ledger")
    ledger = ledger if isinstance(ledger, Mapping) else {}
    novel = identity.get("novel_identity")
    novel = novel if isinstance(novel, Mapping) else {}
    return {
        "post_id": row.get("post_id"),
        "official_title": novel.get("official_title"),
        "official_url": novel.get("heretic_url") or novel.get("official_url"),
        "promotion_decision": deepcopy(
            identity.get("promotion_decision") or ledger.get("promotion_decision")
        ),
        "publish_contract_trace": deepcopy(
            identity.get("publish_contract_trace") or ledger.get("publish_contract_trace")
        ),
        "publish_ledger": deepcopy(
            identity.get("publish_ledger") or ledger.get("publish_ledger")
        ),
        "publish_contract_input_fingerprint": identity.get(
            "publish_contract_input_fingerprint"
        ),
        "publish_contract_version": identity.get("publish_contract_version"),
    }


def _receipt_copies_public_value(
    row: Mapping[str, Any], receipt: PublicationDecisionCommit
) -> bool:
    payload = json.dumps(receipt.to_dict(), ensure_ascii=False, sort_keys=True)
    snapshot = _public_snapshot(row)
    public_values = [
        str(snapshot.get("official_title") or "").strip(),
        str(snapshot.get("official_url") or "").strip(),
    ]
    return any(value and value in payload for value in public_values)


def _rejected(action: Callable[[], Any]) -> tuple[bool, str]:
    try:
        action()
    except (PublicationCommitError, ValueError) as exc:
        return True, str(exc)
    return False, "accepted unexpectedly"


def _case(name: str, passed: bool, expected: str, observed: Any) -> dict[str, Any]:
    return {
        "case": name,
        "passed": bool(passed),
        "expected": expected,
        "observed": observed,
    }


def _synthetic_cases(
    rows: list[dict[str, Any]],
    receipts: list[PublicationDecisionCommit],
    scope_descriptor: PublicationScopeDescriptor,
) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    scope_id = scope_descriptor.publication_scope_id
    base = deepcopy(rows[0])
    base_post_id = _post_id(base.get("post_id"))

    with TemporaryDirectory() as tmp:
        path = Path(tmp) / "journal-only-crash.jsonl"
        registry = PublicationCommitRegistry(
            path, scope_descriptor=scope_descriptor, create_new=True
        )
        first, first_created = commit_publication_result(
            base,
            registry=registry,
            attempt_run_id="before-checkpoint-crash",
            input_index=1,
            post_id=base_post_id,
        )
        # checkpoint를 쓰기 전에 process가 죽었다고 가정하고 registry만 재개한다.
        reloaded = PublicationCommitRegistry(
            path, scope_descriptor=scope_descriptor, create_new=False
        )
        replay, replay_created = commit_publication_result(
            deepcopy(base),
            registry=reloaded,
            attempt_run_id="new-output-retry",
            input_index=1,
            post_id=base_post_id,
        )
        cases.append(
            _case(
                "journal_only_crash_then_new_attempt_replay",
                first_created
                and not replay_created
                and first.decision_id == replay.decision_id
                and reloaded.result(base_post_id) == base
                and len(path.read_text(encoding="utf-8").splitlines()) == 1,
                "새 output attempt에서 무쓰기 재생, journal line 1",
                {"first_created": first_created, "replay_created": replay_created},
            )
        )

    with TemporaryDirectory() as tmp:
        path = Path(tmp) / "conflict.jsonl"
        registry = PublicationCommitRegistry(
            path, scope_descriptor=scope_descriptor, create_new=True
        )
        _, first_created = commit_publication_result(
            base,
            registry=registry,
            attempt_run_id="first-attempt",
            input_index=1,
            post_id=base_post_id,
        )
        changed_input = deepcopy(base)
        changed_input["content"] = list(changed_input.get("content") or []) + ["입력 변조"]
        rejected, detail = _rejected(
            lambda: commit_publication_result(
                changed_input,
                registry=registry,
                attempt_run_id="conflicting-attempt",
                input_index=1,
                post_id=base_post_id,
            )
        )
        cases.append(
            _case(
                "same_scope_post_conflicting_decision",
                first_created and rejected,
                "첫 결정 1회 기록 후 상충 결정 거부",
                detail,
            )
        )

    with TemporaryDirectory() as tmp:
        path = Path(tmp) / "attempt-envelope.jsonl"
        registry = PublicationCommitRegistry(
            path, scope_descriptor=scope_descriptor, create_new=True
        )
        first_row = deepcopy(base)
        first_row["run_meta"] = {
            **dict(first_row.get("run_meta") or {}),
            "run_id": "attempt-a",
            "worker_id": 1,
            "worker_log_file": "logs/a.log",
            "main_log_file": "logs/main-a.log",
        }
        retry_row = deepcopy(first_row)
        retry_row["run_meta"].update(
            {
                "run_id": "attempt-b",
                "worker_id": 9,
                "worker_log_file": "logs/b.log",
                "main_log_file": "logs/main-b.log",
            }
        )
        first_receipt, first_created = commit_publication_result(
            first_row,
            registry=registry,
            attempt_run_id="attempt-a",
            input_index=1,
            post_id=base_post_id,
        )
        retry_receipt, retry_created = commit_publication_result(
            retry_row,
            registry=registry,
            attempt_run_id="attempt-b",
            input_index=1,
            post_id=base_post_id,
        )
        cases.append(
            _case(
                "attempt_local_envelope_first_writer_canonical",
                first_created
                and not retry_created
                and first_receipt.decision_id == retry_receipt.decision_id
                and registry.result(base_post_id) == first_row,
                "run_id/로그 경로 차이는 무쓰기 재생, 첫 WAL row 보존",
                {
                    "first_created": first_created,
                    "retry_created": retry_created,
                },
            )
        )

    with TemporaryDirectory() as tmp:
        path = Path(tmp) / "stable-result-conflict.jsonl"
        registry = PublicationCommitRegistry(
            path, scope_descriptor=scope_descriptor, create_new=True
        )
        first_row = deepcopy(base)
        second_row = deepcopy(base)
        first_row.setdefault("analysis_result", {})["analysis"] = {
            "notes": "first stable analysis"
        }
        second_row.setdefault("analysis_result", {})["analysis"] = {
            "notes": "different stable analysis"
        }
        commit_publication_result(
            first_row,
            registry=registry,
            attempt_run_id="stable-a",
            input_index=1,
            post_id=base_post_id,
        )
        rejected, detail = _rejected(
            lambda: commit_publication_result(
                second_row,
                registry=registry,
                attempt_run_id="stable-b",
                input_index=1,
                post_id=base_post_id,
            )
        )
        cases.append(
            _case(
                "non_attempt_stable_result_conflict",
                rejected,
                "실제 분석 내용 차이는 상충 거부",
                detail,
            )
        )

    cross_post = deepcopy(base)
    other_post_id = _post_id(rows[1].get("post_id"))
    cross_post["post_id"] = other_post_id
    rejected, detail = _rejected(
        lambda: compute_publication_decision_commit(
            cross_post,
            publication_scope_id=scope_id,
            attempt_run_id="cross-post",
            input_index=1,
            post_id=other_post_id,
        )
    )
    cases.append(_case("cross_post_typed_state_replay", rejected, "거부", detail))

    forged = deepcopy(base)
    forged_identity = forged["analysis_result"]["identity"]
    forged_identity["publish_contract_version"] = "evil_contract"
    forged_identity["candidate_ledger"]["publish_contract_version"] = "evil_contract"
    rejected, detail = _rejected(
        lambda: compute_publication_decision_commit(
            forged,
            publication_scope_id=scope_id,
            attempt_run_id="forged-contract",
            input_index=1,
            post_id=base_post_id,
        )
    )
    cases.append(_case("forged_contract_version", rejected, "거부", detail))

    missing_typed = deepcopy(base)
    missing_typed["analysis_result"]["identity"].pop("promotion_gate_state", None)
    rejected, detail = _rejected(
        lambda: compute_publication_decision_commit(
            missing_typed,
            publication_scope_id=scope_id,
            attempt_run_id="missing-typed",
            input_index=1,
            post_id=base_post_id,
        )
    )
    cases.append(_case("missing_typed_state", rejected, "거부", detail))

    hold_index = next(
        (index for index, receipt in enumerate(receipts) if receipt.outcome == "HOLD"),
        None,
    )
    if hold_index is None:
        cases.append(
            _case("alternate_public_key_leak_on_hold", False, "거부", "HOLD row missing")
        )
    else:
        leaked_hold = deepcopy(rows[hold_index])
        leaked_hold["analysis_result"]["identity"]["novel_identity"] = {
            "resolved_title": "숨은 공개값",
            "official_url": "https://example.com/hidden",
        }
        rejected, detail = _rejected(
            lambda: compute_publication_decision_commit(
                leaked_hold,
                publication_scope_id=scope_id,
                attempt_run_id="alternate-public-key",
                input_index=hold_index + 1,
                post_id=leaked_hold["post_id"],
            )
        )
        cases.append(_case("alternate_public_key_leak_on_hold", rejected, "거부", detail))

        nested_leak = deepcopy(rows[hold_index])
        nested_identity = nested_leak["analysis_result"]["identity"]
        for projection in (
            nested_identity["publish_contract_trace"]["post_gate_identity"],
            nested_identity["publish_ledger"]["public_publish"],
        ):
            projection["resolved_title"] = "NESTED LEAK"
            projection["resolved_url"] = "https://leak.example"
        nested_identity["candidate_ledger"]["publish_contract_trace"] = deepcopy(
            nested_identity["publish_contract_trace"]
        )
        nested_identity["candidate_ledger"]["publish_ledger"] = deepcopy(
            nested_identity["publish_ledger"]
        )
        rejected, detail = _rejected(
            lambda: compute_publication_decision_commit(
                nested_leak,
                publication_scope_id=scope_id,
                attempt_run_id="nested-public-leak",
                input_index=hold_index + 1,
                post_id=nested_leak["post_id"],
            )
        )
        cases.append(
            _case(
                "nested_alternate_public_key_leak_on_hold",
                rejected,
                "거부",
                detail,
            )
        )

    publish_index = next(
        (index for index, receipt in enumerate(receipts) if receipt.outcome == "PUBLISH"),
        None,
    )
    if publish_index is None:
        cases.append(_case("post_commit_public_mutation", False, "거부", "PUBLISH row missing"))
    else:
        public_changed = deepcopy(rows[publish_index])
        public_changed["analysis_result"]["identity"]["novel_identity"][
            "official_title"
        ] = "변조된 공개 작품명"
        rejected, detail = _rejected(
            lambda: validate_publication_result_commit(
                public_changed,
                receipts[publish_index],
            )
        )
        cases.append(_case("post_commit_public_mutation", rejected, "거부", detail))

    tampered = receipts[0].to_dict()
    tampered["owner"] = "other.writer"
    rejected, detail = _rejected(lambda: PublicationDecisionCommit.from_dict(tampered))
    cases.append(_case("forged_receipt_owner", rejected, "거부", detail))

    duplicate_audit = audit_publication_commits(
        [deepcopy(base), deepcopy(base)],
        [receipts[0]],
        expected_post_ids=[base_post_id],
        expected_scope_id=scope_id,
    )
    cases.append(
        _case(
            "duplicate_terminal_result_row",
            duplicate_audit["gate"] == "NO-GO"
            and duplicate_audit["duplicate_row_post_ids"] == [base_post_id],
            "NO-GO",
            duplicate_audit["gate"],
        )
    )

    missing_audit = audit_publication_commits(
        [base],
        [],
        expected_post_ids=[base_post_id],
        expected_scope_id=scope_id,
    )
    cases.append(
        _case(
            "missing_sidecar_receipt",
            missing_audit["gate"] == "NO-GO"
            and missing_audit["missing_receipt_post_ids"] == [base_post_id],
            "NO-GO",
            missing_audit["gate"],
        )
    )

    other_scope = build_publication_scope_id(
        input_file_sha256="b" * 64,
        post_ids=[base_post_id],
        config_hash="other-config",
        release_fingerprint="other-release",
    )
    other_receipt = compute_publication_decision_commit(
        base,
        publication_scope_id=other_scope,
        attempt_run_id="other-scope",
        input_index=1,
        post_id=base_post_id,
    )
    mixed_audit = audit_publication_commits(
        [base],
        [other_receipt],
        expected_post_ids=[base_post_id],
        expected_scope_id=scope_id,
    )
    cases.append(
        _case(
            "mixed_publication_scope",
            mixed_audit["gate"] == "NO-GO" and not mixed_audit["scope_match"],
            "NO-GO",
            mixed_audit["gate"],
        )
    )

    wrong_index = compute_publication_decision_commit(
        base,
        publication_scope_id=scope_id,
        attempt_run_id="wrong-index",
        input_index=99,
        post_id=base_post_id,
    )
    index_audit = audit_publication_commits(
        [base],
        [wrong_index],
        expected_post_ids=[base_post_id],
        expected_scope_id=scope_id,
    )
    cases.append(
        _case(
            "noncontiguous_input_index",
            index_audit["gate"] == "NO-GO" and not index_audit["input_indices_contiguous"],
            "NO-GO",
            index_audit["gate"],
        )
    )

    wrong_member_row = deepcopy(rows[1])
    wrong_member_post_id = _post_id(wrong_member_row.get("post_id"))
    wrong_member_receipt = compute_publication_decision_commit(
        wrong_member_row,
        publication_scope_id=scope_id,
        attempt_run_id="wrong-scope-member",
        input_index=1,
        post_id=wrong_member_post_id,
    )
    with TemporaryDirectory() as tmp:
        registry = PublicationCommitRegistry(
            Path(tmp) / "membership.jsonl",
            scope_descriptor=scope_descriptor,
            create_new=True,
        )
        rejected, detail = _rejected(
            lambda: registry.record(wrong_member_receipt, result=wrong_member_row)
        )
    cases.append(_case("scope_index_post_membership_mismatch", rejected, "거부", detail))

    legacy = {
        "post_id": 9001,
        "analysis_result": {
            "identity": {
                "is_relevant": True,
                "novel_identity": {
                    "official_title": "검증되지 않은 레거시 값",
                    "heretic_url": "https://example.com/unowned",
                },
            }
        },
    }
    legacy_scope = build_publication_scope_id(
        input_file_sha256="c" * 64,
        post_ids=[9001],
        config_hash="legacy",
    )
    rejected, detail = _rejected(
        lambda: compute_publication_decision_commit(
            legacy,
            publication_scope_id=legacy_scope,
            attempt_run_id="legacy",
            input_index=1,
            post_id=9001,
        )
    )
    cases.append(_case("legacy_unowned_publication", rejected, "거부", detail))

    error_row = {
        "post_id": 9002,
        "title": "",
        "error": "private upstream detail",
        "analysis_result": {"identity": {"is_relevant": False, "reason": "처리 오류"}},
    }
    error_scope = build_publication_scope_id(
        input_file_sha256="d" * 64,
        post_ids=[9002],
        config_hash="error",
    )
    error_receipt = compute_publication_decision_commit(
        error_row,
        publication_scope_id=error_scope,
        attempt_run_id="error",
        input_index=1,
        post_id=9002,
    )
    error_text = json.dumps(error_receipt.to_dict(), ensure_ascii=False)
    cases.append(
        _case(
            "pipeline_error_terminal_hold",
            error_receipt.outcome == "ERROR_HOLD"
            and not error_receipt.publish_allowed
            and "private upstream detail" not in error_text,
            "ERROR_HOLD이며 원문 오류 비복사",
            error_receipt.outcome,
        )
    )

    error_leak = deepcopy(error_row)
    error_leak["official_title"] = "TOP LEAK"
    error_leak["analysis_result"]["identity"]["promotion_decision"] = {
        "status": "publish",
        "publish_allowed": None,
        "bypassed_gate": True,
        "official_title": None,
        "official_url": None,
    }
    rejected, detail = _rejected(
        lambda: compute_publication_decision_commit(
            error_leak,
            publication_scope_id=error_scope,
            attempt_run_id="error-split-leak",
            input_index=1,
            post_id=9002,
        )
    )
    cases.append(
        _case(
            "error_hold_split_signal_public_leak",
            rejected,
            "거부",
            detail,
        )
    )

    with TemporaryDirectory() as tmp:
        journal = Path(tmp) / "independent-cas.jsonl"
        first_registry = PublicationCommitRegistry(
            journal, scope_descriptor=scope_descriptor, create_new=True
        )
        registries = [first_registry] + [
            PublicationCommitRegistry(
                journal, scope_descriptor=scope_descriptor, create_new=False
            )
            for _ in range(15)
        ]

        def race(index: int) -> bool:
            _, created = commit_publication_result(
                deepcopy(base),
                registry=registries[index],
                attempt_run_id=f"race-{index}",
                input_index=1,
                post_id=base_post_id,
            )
            return created

        with ThreadPoolExecutor(max_workers=16) as pool:
            created_count = sum(pool.map(race, range(16)))
        line_count = len(journal.read_text(encoding="utf-8").splitlines())
        cases.append(
            _case(
                "independent_owner_16way_race",
                created_count == 1 and line_count == 1,
                "신규 commit 1, journal line 1",
                {"created": created_count, "lines": line_count},
            )
        )

    with TemporaryDirectory() as tmp:
        journal = Path(tmp) / "truncated.jsonl"
        registry = PublicationCommitRegistry(
            journal, scope_descriptor=scope_descriptor, create_new=True
        )
        commit_publication_result(
            base,
            registry=registry,
            attempt_run_id="truncated",
            input_index=1,
            post_id=base_post_id,
        )
        with journal.open("a", encoding="utf-8") as handle:
            handle.write("{truncated")
        repaired_registry = PublicationCommitRegistry(
            journal,
            scope_descriptor=scope_descriptor,
            create_new=False,
        )
        repair_records = repaired_registry.tail_repair_records()
        cases.append(
            _case(
                "uncommitted_journal_tail_repair",
                repaired_registry.count == 1
                and journal.read_bytes().endswith(b"\n")
                and len(repair_records) == 1
                and repair_records[0].get("discarded_tail_sha256")
                == hashlib.sha256(b"{truncated").hexdigest(),
                "정상 commit 1건 보존 + 미완료 꼬리 감사 기록 1건 + newline 경계 복구",
                {
                    "commit_count": repaired_registry.count,
                    "repair_count": len(repair_records),
                    "journal_newline_terminated": journal.read_bytes().endswith(b"\n"),
                },
            )
        )

    return cases


def build_comparison(
    run_spec_path: str | Path,
    *,
    verify_implementation: bool = True,
) -> dict[str, Any]:
    spec, baseline_rows = validate_run_spec(
        run_spec_path,
        verify_implementation=verify_implementation,
    )
    post_ids = [_post_id(row.get("post_id")) for row in baseline_rows]
    scope_id = spec["publication_commit_contract"]["publication_scope_id"]
    scope_descriptor = PublicationScopeDescriptor.from_dict(
        spec["publication_commit_contract"]["scope_descriptor"]
    )
    before_audit = audit_publication_commits(
        baseline_rows,
        [],
        expected_post_ids=post_ids,
        expected_scope_id=scope_id,
    )
    before_public = [_public_snapshot(row) for row in baseline_rows]
    before_full_hashes = [_canonical_hash(row) for row in baseline_rows]

    with TemporaryDirectory() as tmp:
        journal = Path(tmp) / f"{scope_id}.jsonl"
        registry = PublicationCommitRegistry(
            journal,
            scope_descriptor=scope_descriptor,
            create_new=True,
        )
        shadow_rows = deepcopy(baseline_rows)
        receipts: list[PublicationDecisionCommit] = []
        new_commit_count = 0
        for index, row in enumerate(shadow_rows, 1):
            receipt, created = commit_publication_result(
                row,
                registry=registry,
                attempt_run_id="p2-shadow-first",
                input_index=index,
                post_id=row["post_id"],
            )
            receipts.append(receipt)
            new_commit_count += int(created)

        first_journal_bytes = journal.read_bytes()
        first_journal_lines = len(first_journal_bytes.splitlines())
        reloaded = PublicationCommitRegistry(
            journal,
            scope_descriptor=scope_descriptor,
            create_new=False,
        )
        replay_noop_count = 0
        for index, row in enumerate(shadow_rows, 1):
            authoritative, created = commit_publication_result(
                deepcopy(row),
                registry=reloaded,
                attempt_run_id="p2-shadow-restart",
                input_index=index,
                post_id=row["post_id"],
            )
            replay_noop_count += int(not created)
            if authoritative.decision_id != receipts[index - 1].decision_id:
                raise ValueError("restart replay returned a different logical decision")
        restart_journal_unchanged = journal.read_bytes() == first_journal_bytes
        reloaded_count = reloaded.count

    after_audit = audit_publication_commits(
        shadow_rows,
        receipts,
        expected_post_ids=post_ids,
        expected_scope_id=scope_id,
    )
    after_public = [_public_snapshot(row) for row in shadow_rows]
    after_full_hashes = [_canonical_hash(row) for row in shadow_rows]
    public_unchanged_count = sum(
        before == after for before, after in zip(before_public, after_public)
    )
    full_row_unchanged_count = sum(
        before == after for before, after in zip(before_full_hashes, after_full_hashes)
    )
    raw_public_copy_count = sum(
        _receipt_copies_public_value(row, receipt)
        for row, receipt in zip(shadow_rows, receipts)
    )
    cases = _synthetic_cases(shadow_rows, receipts, scope_descriptor)
    synthetic_passed = sum(case["passed"] for case in cases)
    false_go_count = len(cases) - synthetic_passed
    row_count = len(baseline_rows)
    saved_artifact_go = all(
        (
            before_audit["gate"] == "NO-GO",
            after_audit["gate"] == "GO",
            after_audit["valid_commit_count"] == row_count,
            new_commit_count == row_count,
            first_journal_lines == row_count,
            reloaded_count == row_count,
            replay_noop_count == row_count,
            restart_journal_unchanged,
            public_unchanged_count == row_count,
            full_row_unchanged_count == row_count,
            raw_public_copy_count == 0,
            false_go_count == 0,
        )
    )
    outcomes = dict(sorted(Counter(receipt.outcome for receipt in receipts).items()))
    return {
        "schema_version": REPORT_SCHEMA,
        "generated_at": _now(),
        "mode": MODE,
        "treatment": TREATMENT,
        "run_spec": {
            "path": _stored_path(run_spec_path),
            "file_sha256": _artifact_ref(run_spec_path)["sha256"],
            "self_hash": spec["run_spec_sha256"],
        },
        "source": {
            "baseline_result": spec["artifacts"]["baseline_result"],
            "row_count": row_count,
            "post_contract": spec["post_contract"],
        },
        "before": {
            "meaning": "최종 결과 행은 있으나 scope-owned durable sidecar 영수증이 없어 판정 사건의 유일성을 증명할 수 없음",
            "exact_once_status": "NOT_PROVABLE_NO_DURABLE_RECEIPT",
            "audit_gate": before_audit["gate"],
            "valid_commit_count": before_audit["valid_commit_count"],
            "missing_receipt_count": len(before_audit["missing_receipt_post_ids"]),
        },
        "after": {
            "meaning": "동일 scope/post_id의 hash-only 영수증과 복구용 결과 행을 WAL 사건으로 1회 기록하고 재시작 재생은 무쓰기 처리함",
            "exact_once_status": "PROVABLE_IN_BOUND_SAVED_ARTIFACT_HARNESS",
            "audit_gate": after_audit["gate"],
            "valid_commit_count": after_audit["valid_commit_count"],
            "new_commit_count": new_commit_count,
            "journal_line_count": first_journal_lines,
            "journal_sha256": hashlib.sha256(first_journal_bytes).hexdigest(),
            "registry_reload_count": reloaded_count,
            "recoverable_wal_result_count": reloaded_count,
            "restart_replay_noop_count": replay_noop_count,
            "restart_journal_unchanged": restart_journal_unchanged,
            "outcomes": outcomes,
            "receipt_raw_public_copy_count": raw_public_copy_count,
            "receipts": [receipt.to_dict() for receipt in receipts],
        },
        "noninterference": {
            "public_projection_unchanged_count": public_unchanged_count,
            "full_result_row_unchanged_count": full_row_unchanged_count,
            "row_count": row_count,
            "result_json_receipt_embedded": False,
            "receipt_is_hash_only": True,
            "wal_event_contains_recoverable_result_row": True,
        },
        "synthetic_attacks": {
            "total": len(cases),
            "passed": synthetic_passed,
            "false_go_count": false_go_count,
            "cases": cases,
        },
        "gates": {
            "saved_artifact_and_synthetic": (
                "GO" if saved_artifact_go else "NO-GO"
            ),
            "production_runtime": "NOT_RUN",
            "semantic_quality": "REVIEW-LOCKED",
            "full_scan_approval": False,
            "overall_goal": "ACTIVE_NOT_COMPLETE",
        },
        "limits": [
            "이 비교는 동결 Golden18 저장본과 합성 공격만 검증한다.",
            "실제 병렬 LLM 실행에서 journal/checkpoint/result 수가 일치하는지는 아직 검증하지 않았다.",
            "공개 내용의 의미 정확도나 보정 확률을 측정하지 않는다.",
            "ordered flush 완료와 exact-once 판정 영수증은 서로 다른 게이트다.",
            "WAL에 결과 행을 한 번 더 저장하므로 실제 runtime의 디스크 사용량·지연은 아직 측정하지 않았다.",
        ],
    }


def render_markdown(report: Mapping[str, Any]) -> str:
    before = report["before"]
    after = report["after"]
    non = report["noninterference"]
    attacks = report["synthetic_attacks"]
    gates = report["gates"]
    rows = int(report["source"]["row_count"])
    outcome_text = ", ".join(
        f"{key} {value}" for key, value in after["outcomes"].items()
    )
    lines = [
        "# P2 최종 공개 판정 exact-once 전후 비교",
        "",
        "## 이 기능이 하는 일",
        "",
        "한 게시글의 최종 작품명 공개 여부를 여러 단계가 다시 계산하더라도, 마지막 공개 판정은 `publication_scope_id + post_id` 기준으로 한 번만 확정합니다. 영수증 자체에는 작품명·URL 원문을 넣지 않고 해시만 둡니다. 다만 저널 기록 뒤 checkpoint 전에 죽어도 결과를 복구할 수 있도록, 같은 원자적 WAL 사건 안에는 영수증과 검증된 최종 결과 행을 함께 저장합니다.",
        "",
        "## 결론",
        "",
        f"- 저장본·합성 공격 게이트: `{gates['saved_artifact_and_synthetic']}`",
        f"- 실제 새 runtime: `{gates['production_runtime']}`",
        f"- 의미 품질: `{gates['semantic_quality']}`",
        f"- 전체 스캔 승인: `{str(gates['full_scan_approval']).lower()}`",
        f"- 전체 목표: `{gates['overall_goal']}`",
        "",
        "`GO`는 Golden18 저장본과 합성 공격 범위에만 해당합니다. 실제 새 LLM 실행, 의미 정확도, 확률 보정, 전체 스캔 승인을 뜻하지 않습니다.",
        "",
        "## 개선 전과 개선 후",
        "",
        "| 구분 | 개선 전 | 개선 후 |",
        "| --- | --- | --- |",
        f"| 사람이 읽는 의미 | {before['meaning']} | {after['meaning']} |",
        f"| exact-once 상태 | `{before['exact_once_status']}` | `{after['exact_once_status']}` |",
        f"| 유효 영수증 | `{before['valid_commit_count']}/{rows}` | `{after['valid_commit_count']}/{rows}` |",
        f"| 첫 기록 | 증명 불가 | `{after['new_commit_count']}/{rows}` |",
        f"| 재시작 재생 | 증명 불가 | 무쓰기 `{after['restart_replay_noop_count']}/{rows}` |",
        f"| 최종 판정 분포 | 측정 대상 아님 | `{outcome_text}` |",
        "",
        "## 결과 JSON 비간섭",
        "",
        f"- 공개 필드 불변: `{non['public_projection_unchanged_count']}/{rows}`",
        f"- 전체 결과 행 불변: `{non['full_result_row_unchanged_count']}/{rows}`",
        f"- 결과 JSON 내부 receipt: `{str(non['result_json_receipt_embedded']).lower()}`",
        f"- receipt의 작품명·URL 원문 복사: `{after['receipt_raw_public_copy_count']}`건",
        f"- WAL에서 복구 가능한 결과 행: `{after['recoverable_wal_result_count']}/{rows}`",
        "",
        "## 공격 검증",
        "",
        f"합성 공격 `{attacks['passed']}/{attacks['total']}` 통과, false GO `{attacks['false_go_count']}`건입니다.",
        "",
        "| 공격 | 기대 결과 | 관측 | 통과 |",
        "| --- | --- | --- | --- |",
    ]
    for case in attacks["cases"]:
        observed = json.dumps(case["observed"], ensure_ascii=False, sort_keys=True)
        lines.append(
            f"| `{case['case']}` | {case['expected']} | `{observed}` | {'PASS' if case['passed'] else 'FAIL'} |"
        )
    lines.extend(
        [
            "",
            "## 아직 증명하지 않은 것",
            "",
            *[f"- {item}" for item in report["limits"]],
            "",
            "## 근거",
            "",
            f"- RunSpec: `{report['run_spec']['path']}`",
            f"- RunSpec 파일 SHA: `{report['run_spec']['file_sha256']}`",
            f"- RunSpec 자체 SHA: `{report['run_spec']['self_hash']}`",
            f"- sidecar journal SHA: `{after['journal_sha256']}`",
            "",
        ]
    )
    return "\n".join(lines)


def write_comparison(
    report: Mapping[str, Any],
    *,
    json_output: str | Path,
    md_output: str | Path,
) -> tuple[Path, Path]:
    json_path = _resolve_path(json_output)
    md_path = _resolve_path(md_output)
    _assert_output_paths([json_path, md_path])
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    md_path.write_text(render_markdown(report), encoding="utf-8", newline="\n")
    return json_path, md_path


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    freeze = sub.add_parser("freeze", help="부모 artifact와 현재 구현을 RunSpec에 고정")
    freeze.add_argument("--parent-p1-run-spec", required=True)
    freeze.add_argument("--parent-producer-run-spec", required=True)
    freeze.add_argument("--output", required=True)
    status = sub.add_parser("status", help="RunSpec 결속을 재검증")
    status.add_argument("--run-spec", required=True)
    compare = sub.add_parser("compare", help="저장본·합성 공격 전후 비교")
    compare.add_argument("--run-spec", required=True)
    compare.add_argument("--json-output", required=True)
    compare.add_argument("--md-output", required=True)
    return parser


def main() -> int:
    args = _parser().parse_args()
    if args.command == "freeze":
        spec = create_run_spec(
            parent_p1_run_spec_path=args.parent_p1_run_spec,
            parent_producer_run_spec_path=args.parent_producer_run_spec,
        )
        output = write_run_spec(spec, args.output)
        print(
            json.dumps(
                {
                    "status": "FROZEN",
                    "output": _stored_path(output),
                    "run_spec_sha256": spec["run_spec_sha256"],
                },
                ensure_ascii=False,
            )
        )
        return 0
    if args.command == "status":
        spec, rows = validate_run_spec(args.run_spec)
        print(
            json.dumps(
                {
                    "status": "GO",
                    "mode": spec["mode"],
                    "row_count": len(rows),
                    "publication_scope_id": spec["publication_commit_contract"][
                        "publication_scope_id"
                    ],
                    "runtime_validation": spec["approval_boundary"]["runtime_validation"],
                },
                ensure_ascii=False,
            )
        )
        return 0
    report = build_comparison(args.run_spec)
    json_path, md_path = write_comparison(
        report,
        json_output=args.json_output,
        md_output=args.md_output,
    )
    print(
        json.dumps(
            {
                "status": report["gates"]["saved_artifact_and_synthetic"],
                "runtime": report["gates"]["production_runtime"],
                "json": _stored_path(json_path),
                "markdown": _stored_path(md_path),
            },
            ensure_ascii=False,
        )
    )
    return 0 if report["gates"]["saved_artifact_and_synthetic"] == "GO" else 1


if __name__ == "__main__":
    raise SystemExit(main())
