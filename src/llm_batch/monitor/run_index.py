"""저장 결과를 읽기만 하는 제한된 실행 인덱스와 manifest 결속 계약."""
from __future__ import annotations

from collections import OrderedDict, deque
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import threading
import time
from typing import Any

FINAL_RESULT = re.compile(r"^expert_result_(\d{8}_\d{6}_\d+)\.json$")
RUN_ID = re.compile(r"^\d{8}_\d{6}_\d+$")
RUN_KEY = re.compile(r"^run_[0-9a-f]{32}$")
MANIFEST_LIMIT = 2 * 1024 * 1024
RESULT_LIMIT = 128 * 1024 * 1024
RECENT_CURRENT_LIMIT = 24
MANIFEST_KEYS = (
    "run_id", "publication_scope_id", "terminal_artifacts_finalized", "completed_count",
    "completed_subset_count", "completed_subset_written", "completed_subset_only", "input_post_count",
    "failed_count", "pending_count", "flushed_count",
    "requested_parallel", "effective_parallel", "vlm_enabled", "ocr_enabled",
    "publication_execution_mode", "execution_mode", "execution_config",
    "source_context_diagnostics_policy", "decision_call_measurement",
    "candidate_retrieval_policy",
    "candidate_reranker_policy",
    "candidate_calibration_policy",
    "candidate_inference_policy",
    "candidate_reranker_semantics_policy",
    "community_knowledge_policy",
    "decision_call_ledger_summary", "decision_ledger_v2_shadow_status",
    "paired_execution_observation", "paired_execution_runtime_fields",
    "recovery_activation_schema", "recovery_activation_requested_mode",
    "recovery_activation_mode", "recovery_activation_public_apply",
    "recovery_activation_status", "recovery_activation_journal",
    "recovery_activation_event_count", "recovery_activation_proposals_observed",
    "recovery_activation_events_created", "recovery_activation_events_replayed",
    "recovery_activation_append_errors", "recovery_activation_tail_repair_count",
    "recovery_activation_error_samples",
    "native_recovery_policy", "native_recovery_policy_file_sha256", "native_recovery_view_path",
    "native_recovery_application_mode", "native_recovery_mutable_learning",
)
ROW_META_KEYS = (
    "run_id", "publication_scope_id", "requested_parallel", "effective_parallel",
    "model", "llm_mode", "measurement_execution_source", "decision_call_ledger",
    "decision_call_ledger_summary", "decision_call_attempt_receipt",
    "decision_call_measurement", "decision_cost_trace", "execution_config",
    "source_context_diagnostics",
    "candidate_retrieval_shadow",
    "candidate_reranker_shadow",
    "candidate_calibration_shadow", "candidate_reranker_capture",
    "candidate_reranker_inference", "candidate_inference_capture",
    "candidate_reranker_semantics", "candidate_reranker_semantics_capture",
    "paired_execution_observation", "paired_execution_runtime_fields",
    "community_knowledge_readback",
    "semantic_review_router_receipt", "semantic_recovery_plan_receipt",
)


def inside(path: Path, root: Path) -> Path | None:
    try:
        resolved = path.resolve()
        resolved.relative_to(root.resolve())
        return resolved
    except (OSError, ValueError, RuntimeError):
        return None


def read_object(path: Path, root: Path) -> dict[str, Any] | None:
    safe = inside(path, root)
    if safe is None:
        return None
    try:
        stat = safe.stat()
        if stat.st_size > MANIFEST_LIMIT:
            return None
        data = json.loads(safe.read_text(encoding="utf-8"))
        after = safe.stat()
        if (after.st_mtime_ns, after.st_size) != (stat.st_mtime_ns, stat.st_size):
            raise ValueError("result changed while reading; retry after the writer finishes")
        return data if isinstance(data, dict) else None
    except (OSError, ValueError, UnicodeError):
        return None


def manifest_output(payload: dict[str, Any], root: Path, manifest: Path | None = None) -> Path | None:
    name = payload.get("output_file")
    if not isinstance(name, str) or not name.strip():
        return None
    path = Path(name)
    if ".." in path.parts:
        return None
    safe = inside(path if path.is_absolute() else root / path, root)
    # 과거 CLI는 repo-relative out/...를 기록했다. 정확한 sidecar를
    # 읽는 경우에만 허용하며 out-relative 동명 파일이 있으면 추측하지 않는다.
    if (not path.is_absolute() and path.parts and path.parts[0] == "out"
            and root.resolve().name == "out" and manifest is not None):
        compatibility = inside(root.resolve().parent / path, root)
        safe_manifest = inside(manifest, root)
        if (compatibility is not None and safe is not None and safe != compatibility
                and safe.exists() and compatibility.exists()):
            return None
        if (compatibility is not None and safe_manifest == compatibility.with_name(
                f"{compatibility.stem}_manifest.json")):
            if safe is None or (safe != compatibility and safe.exists()):
                return None
            safe = compatibility
    if safe is None or safe.suffix.lower() != ".json":
        return None
    if safe.stem.endswith(("_manifest", "_pending_snapshot", "_checkpoint")):
        return None
    return safe


def manifest_target(payload: dict[str, Any], root: Path, manifest: Path) -> Path | None:
    output = manifest_output(payload, root, manifest)
    if output is None:
        return None
    safe_manifest = inside(manifest, root)
    if safe_manifest == output.with_name(f"{output.stem}_manifest.json"):
        return output
    # expert_main의 실제 subset sidecar는 output_file을 주 결과로 유지한다.
    subset_name = payload.get("completed_subset_json")
    if isinstance(subset_name, str) and subset_name:
        subset = Path(subset_name)
        subset = inside(subset if subset.is_absolute() else root / subset, root)
        if (subset is not None and subset.suffix.lower() == ".json"
                and subset.parent == output.parent and subset.stem == f"{output.stem}_completed_subset"
                and safe_manifest == subset.with_name(f"{subset.stem}_manifest.json")):
            return subset
    return None


def summary(payload: dict[str, Any]) -> dict[str, Any]:
    return {key: payload[key] for key in MANIFEST_KEYS if key in payload}


def row_meta(item: dict[str, Any]) -> dict[str, Any]:
    meta = item.get("run_meta")
    return {key: meta[key] for key in ROW_META_KEYS if key in meta} if isinstance(meta, dict) else {}


def _row_bindings(meta: dict[str, Any], key: str) -> set[str]:
    values = {str(meta[key])} if meta.get(key) else set()
    for name in ("decision_call_ledger", "decision_call_attempt_receipt", "decision_cost_trace"):
        value = meta.get(name)
        if isinstance(value, dict):
            if value.get(key):
                values.add(str(value[key]))
            row = value.get("row")
            row_key = "attempt_run_id" if key == "run_id" else key
            if isinstance(row, dict) and row.get(row_key):
                values.add(str(row[row_key]))
    # 저장된 새 관측의 좌표도 독립 비교한다. 참조 artifact 파일은 읽지 않는다.
    for name in ("candidate_calibration_shadow", "candidate_reranker_capture",
                 "candidate_reranker_inference", "candidate_inference_capture",
                 "candidate_reranker_semantics", "candidate_reranker_semantics_capture"):
        value = meta.get(name)
        if isinstance(value, dict):
            if value.get(key):
                values.add(str(value[key]))
            binding = value.get("binding")
            if isinstance(binding, dict) and binding.get(key):
                values.add(str(binding[key]))
    return values


def bound_manifest(output: Path, root: Path, *, item: dict[str, Any] | None = None,
                   manifest_path: Path | None = None, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    """행 기록과 종료 기록을 섞지 않고 출처·결속 상태를 따로 반환한다."""
    path = manifest_path or output.with_name(f"{output.stem}_manifest.json")
    payload = payload if payload is not None else read_object(path, root)
    if payload is None:
        return {"binding_status": "MISSING", "reason_codes": ["MANIFEST_MISSING_OR_INVALID"], "summary": {}}
    safe_output = inside(output, root)
    if safe_output is None or manifest_target(payload, root, path) != safe_output:
        return {"binding_status": "MISMATCH", "reason_codes": ["MANIFEST_OUTPUT_MISMATCH"], "summary": {}}
    reasons: list[str] = []
    missing: list[str] = []
    if item is not None:
        meta = row_meta(item)
        for name, row_values, run_value in (
            ("RUN_ID", _row_bindings(meta, "run_id"), payload.get("run_id")),
            ("PUBLICATION_SCOPE", _row_bindings(meta, "publication_scope_id"), payload.get("publication_scope_id")),
        ):
            if len(row_values) > 1:
                reasons.append(f"{name}_ROW_CONFLICT")
            elif row_values and run_value:
                if row_values != {str(run_value)}:
                    reasons.append(f"{name}_MISMATCH")
            else:
                missing.append(f"{name}_NOT_RECORDED")
    if reasons:
        return {"binding_status": "MISMATCH", "reason_codes": reasons, "summary": {}}
    # 판독 대상이 원본 result인지 명시된 completed subset인지 구별한다.
    # terminal 확정은 저장 마감이며 전체 행의 성공/실패 판정이 아니다.
    artifact_kind = "COMPLETED_SUBSET" if inside(output, root) != manifest_output(payload, root, path) else "RESULT"
    return {"binding_status": "PARTIAL" if missing else "BOUND", "reason_codes": missing,
            "artifact_kind": artifact_kind, "summary": summary(payload)}


def bound_manifest_rows(output: Path, root: Path, items: list[dict[str, Any]],
                        manifest_path: Path | None = None) -> dict[str, Any]:
    path = manifest_path or output.with_name(f"{output.stem}_manifest.json")
    payload = read_object(path, root)
    binding = bound_manifest(output, root, manifest_path=path, payload=payload)
    if binding["binding_status"] in ("MISSING", "MISMATCH"):
        return binding
    missing = set()
    for item in items:
        nested = item.get("result")
        item = nested if isinstance(nested, dict) else item
        checked = bound_manifest(output, root, item=item, manifest_path=path, payload=payload)
        if checked["binding_status"] == "MISMATCH":
            return checked
        missing.update(checked["reason_codes"])
    if missing:
        binding["binding_status"] = "PARTIAL"
        binding["reason_codes"] = sorted(missing)
    return binding


@dataclass
class RunRecord:
    path: Path
    manifest: Path | None
    payload: dict[str, Any]
    public: dict[str, Any]


class RunIndex:
    """탐색·JSON 크기·캐시를 제한하며 URL에는 파일 경로를 받지 않는다."""

    def __init__(self, *, ttl: float = 30.0, max_entries: int = 50000,
                 max_manifests: int = 2000, max_depth: int = 12):
        self.ttl = ttl
        self.max_entries = max_entries
        self.max_manifests = max_manifests
        self.max_depth = max_depth
        self._lock = threading.RLock()
        self._root: Path | None = None
        self._expires = 0.0
        self._records: dict[str, RunRecord] = {}
        # 현재 실행으로 실제 관측한 경로/실행 ID만 제한적으로 기억한다.
        # payload는 권위로 캐시하지 않고 records()마다 sidecar를 다시 읽는다.
        self._recent_current: OrderedDict[str, tuple[Path, str]] = OrderedDict()
        self._result_cache: OrderedDict[tuple[str, int, int], list[dict[str, Any]]] = OrderedDict()
        self.truncated = False

    def load_result(self, path: Path, root: Path) -> list[dict[str, Any]]:
        safe = inside(path, root)
        if safe is None:
            raise ValueError("result is outside the configured output directory")
        stat = safe.stat()
        if stat.st_size > RESULT_LIMIT:
            raise ValueError("result exceeds dashboard read limit")
        key = (str(safe), stat.st_mtime_ns, stat.st_size)
        with self._lock:
            cached = self._result_cache.get(key)
            if cached is not None:
                self._result_cache.move_to_end(key)
                return cached
        data = json.loads(safe.read_text(encoding="utf-8"))
        after = safe.stat()
        if (after.st_mtime_ns, after.st_size) != (stat.st_mtime_ns, stat.st_size):
            raise ValueError("result changed while reading; retry after the writer finishes")
        if not isinstance(data, list) or any(not isinstance(row, dict) for row in data):
            raise ValueError("top-level JSON must be an array of objects")
        # 큰 결과는 요청할 때만 읽으며 상주 캐시 총 원본 크기도 제한한다.
        if stat.st_size <= 16 * 1024 * 1024:
            with self._lock:
                for old in list(self._result_cache):
                    if old[0] == key[0]:
                        del self._result_cache[old]
                self._result_cache[key] = data
                while len(self._result_cache) > 4 or sum(k[2] for k in self._result_cache) > 32 * 1024 * 1024:
                    self._result_cache.popitem(last=False)
        return data

    def _paths(self, root: Path):
        # 깊은 ledger/frame 디렉터리가 얕은 실행 sidecar 탐색을 굶기지 않는다.
        pending = deque([(root, 0)])
        seen = 0
        manifests = 0
        self.truncated = False
        while pending:
            parent, depth = pending.popleft()
            try:
                with os.scandir(parent) as entries:
                    for entry in entries:
                        seen += 1
                        if seen > self.max_entries:
                            self.truncated = True
                            return
                        if entry.is_symlink():
                            continue
                        if entry.is_dir(follow_symlinks=False):
                            if inside(Path(entry.path), root) is None:
                                continue
                            # 기본 URL fetch 캐시는 실행 저장소가 아니다. 루트 직계 namespace만 제외한다.
                            # 디렉터리 항목 자체는 기존 예산에 세되 그 하위 캐시 파일은 열거하지 않는다.
                            if depth == 0 and entry.name == "url_fetch_cache":
                                continue
                            if depth < self.max_depth:
                                pending.append((Path(entry.path), depth + 1))
                            else:
                                self.truncated = True
                        elif entry.is_file(follow_symlinks=False):
                            if depth == 0 and FINAL_RESULT.fullmatch(entry.name):
                                yield Path(entry.path), False
                            elif entry.name.endswith("_manifest.json"):
                                manifests += 1
                                if manifests > self.max_manifests:
                                    self.truncated = True
                                    return
                                yield Path(entry.path), True
            except OSError:
                continue

    def _record(self, path: Path, manifest: Path | None, payload: dict[str, Any], root: Path) -> RunRecord | None:
        safe = inside(path, root)
        if safe is None:
            return None
        try:
            stat = safe.stat()
            if not safe.is_file():
                return None
            # 배열 여부는 고정 크기만 읽는다. 전체 파싱은 선택한 실행에 한정한다.
            with safe.open("r", encoding="utf-8") as stream:
                if not stream.read(256).lstrip().startswith("["):
                    return None
        except (OSError, UnicodeError):
            return None
        rel = safe.relative_to(root).as_posix()
        match = FINAL_RESULT.fullmatch(safe.name)
        run_id = payload.get("run_id") or (match.group(1) if match else None)
        run_id = run_id if isinstance(run_id, str) and RUN_ID.fullmatch(run_id) else None
        key = "run_" + hashlib.sha256(f"{rel}\0{run_id or ''}".encode()).hexdigest()[:32]
        is_subset = safe.stem.endswith("_completed_subset") and payload.get("completed_subset_json")
        count = payload.get("completed_subset_count" if is_subset else "completed_count")
        count_source = "manifest" if isinstance(count, int) and not isinstance(count, bool) and count >= 0 else "unknown"
        if count_source == "unknown":
            count = None
            # 기존 최상위 소형 파일 건수는 호환 제공하되 파일 캐시를 재사용한다.
            if manifest is None and stat.st_size <= 16 * 1024 * 1024:
                try:
                    count = len(self.load_result(safe, root))
                    count_source = "result"
                except (OSError, ValueError, UnicodeError):
                    return None
        finalized = payload.get("terminal_artifacts_finalized")
        state = "FINAL" if finalized is True else "PARTIAL" if finalized is False else "UNKNOWN"
        if is_subset or payload.get("completed_subset_only") is True:
            state = "PARTIAL"
        mode = payload.get("publication_execution_mode") or payload.get("execution_mode")
        mode = mode if isinstance(mode, str) and mode.strip() else "UNKNOWN"
        public = {
            "run_key": key, "filename": safe.name, "relative_path": rel, "run_id": run_id,
            "timestamp": None, "size_kb": round(stat.st_size / 1024, 1), "post_count": count,
            "post_count_source": count_source, "completion_status": state,
            "artifact_kind": "COMPLETED_SUBSET" if is_subset else "RESULT",
            "execution_mode": mode,
            "log_file": None, "manifest_summary": summary(payload),
            "modified_at": stat.st_mtime,
        }
        return RunRecord(safe, manifest, payload, public)

    def _current_record(self, output: Path | None, root: Path) -> RunRecord | None:
        """탐색 상한과 별개로 현재 실행 한 건의 유효한 sidecar만 읽는다."""
        safe = inside(output, root) if output is not None else None
        if safe is None or safe.suffix.lower() != ".json":
            return None
        manifest = safe.with_name(f"{safe.stem}_manifest.json")
        payload = read_object(manifest, root)
        if payload is None or manifest_target(payload, root, manifest) != safe:
            return None
        return self._record(safe, manifest, payload, root)

    def _retained_current_record(self, output: Path, run_id: str, root: Path) -> RunRecord | None:
        """이전에 본 current 경로도 매번 경계·링크·sidecar·실행 ID를 재검산한다."""
        if inside(output, root) != output:
            return None
        try:
            for target in (output, output.with_name(f"{output.stem}_manifest.json")):
                for part in (target, *target.parents):
                    if part == root:
                        break
                    if part.is_symlink() or (hasattr(part, "is_junction") and part.is_junction()):
                        return None
        except (OSError, ValueError, RuntimeError):
            return None
        record = self._current_record(output, root)
        if record is None or record.public["run_id"] != run_id:
            return None
        return record

    def records(self, root: Path, *, current_output: Path | None = None) -> dict[str, RunRecord]:
        root = root.resolve()
        with self._lock:
            if root != self._root:
                self._recent_current.clear()
                self._result_cache.clear()
            if root == self._root and time.monotonic() < self._expires:
                records = dict(self._records)
            else:
                by_path: dict[Path, RunRecord] = {}
                for path, is_manifest in self._paths(root):
                    payload = read_object(path, root) if is_manifest else {}
                    if payload is None:
                        continue
                    output = manifest_target(payload, root, path) if is_manifest else path
                    if output is None:
                        continue
                    record = self._record(output, path if is_manifest else None, payload, root)
                    if record and (record.path not in by_path or record.manifest is not None):
                        by_path[record.path] = record
                self._records = {r.public["run_key"]: r for r in sorted(by_path.values(), key=lambda r: r.public["run_id"] or "", reverse=True)}
                self._root, self._expires = root, time.monotonic() + self.ttl
                records = dict(self._records)
            # 일반 탐색 캐시와 별개로 최근 current 좌표만 보존한다.
            # 현재 실행이 바뀌어도 탐색 상한 밖의 직전 실행을 선택할 수 있다.
            current = self._current_record(current_output, root)
            if current is not None and current.public["run_id"] is not None:
                # symlink를 통해 들어온 별도 표면 경로는 보존 권한으로 추가하지 않는다.
                if current_output is not None and current_output.absolute() == current.path:
                    fresh = self._retained_current_record(current.path, current.public["run_id"], root)
                    if fresh is not None:
                        for key, (output, _) in list(self._recent_current.items()):
                            if output == fresh.path:
                                del self._recent_current[key]
                        self._recent_current[fresh.public["run_key"]] = (fresh.path, fresh.public["run_id"])
                        while len(self._recent_current) > RECENT_CURRENT_LIMIT:
                            self._recent_current.popitem(last=False)
            for key, (output, run_id) in list(self._recent_current.items()):
                retained = self._retained_current_record(output, run_id, root)
                if retained is None or retained.public["run_key"] != key:
                    del self._recent_current[key]
                    records.pop(key, None)
                    continue
                records = {k: record for k, record in records.items() if record.path != retained.path}
                records[key] = retained
            if current is not None:
                records = {key: record for key, record in records.items() if record.path != current.path}
                records[current.public["run_key"]] = current
            return dict(sorted(records.items(), key=lambda pair: pair[1].public["run_id"] or "", reverse=True))

    def resolve(self, name: str, root: Path, *, current_output: Path | None = None) -> RunRecord | None:
        if RUN_KEY.fullmatch(name):
            # 최근 current의 정확한 키는 만료된 전체 탐색보다 먼저 확인한다.
            # 이 경로도 파일/manifest/run_id를 다시 읽으며 무효 좌표는
            # 일반 탐색으로 재허용하지 않고 즉시 실패시킨다.
            resolved_root = root.resolve()
            with self._lock:
                retained = self._recent_current.get(name) if resolved_root == self._root else None
                if retained is not None:
                    record = self._retained_current_record(retained[0], retained[1], resolved_root)
                    if record is None or record.public["run_key"] != name:
                        self._recent_current.pop(name, None)
                        self._records.pop(name, None)
                        return None
                else:
                    record = self.records(resolved_root, current_output=current_output).get(name)
            if record is None:
                return None
        elif FINAL_RESULT.fullmatch(name):
            path = inside(root / name, root)
            if path is None:
                return None
            manifest = path.with_name(f"{path.stem}_manifest.json")
            payload = read_object(manifest, root)
            if payload is not None and manifest_target(payload, root, manifest) != path:
                return None
            record = self._record(path, manifest if payload is not None else None, payload or {}, root.resolve())
        else:
            return None
        if record is None or inside(record.path, root) != record.path:
            return None
        if record.manifest is not None:
            payload = read_object(record.manifest, root)
            if payload is None or manifest_target(payload, root, record.manifest) != record.path:
                return None
            if payload.get("run_id") != record.payload.get("run_id"):
                return None
            record = self._record(record.path, record.manifest, payload, root.resolve())
        return record
