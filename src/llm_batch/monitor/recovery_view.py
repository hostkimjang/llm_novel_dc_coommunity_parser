"""명시적으로 연결한 복구 판독 보고서만 읽는다. GET은 실행·원장 수리를 하지 않는다."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import stat

from ..measurement.recovery_execution_contract import canonical_sha256
from ..measurement.recovery_execution_readback import (
    read_strict_json, validate_recovery_execution_readback,
)

SCHEMA = 'recovery_dashboard_reference_v1'
REPORT_LIMIT = 2 * 1024 * 1024
SOURCE_LIMIT = 16 * 1024 * 1024


def _safe(path: Path, root: Path) -> Path:
    path, root = Path(path).absolute(), Path(root).resolve()
    path.relative_to(root)
    for part in (path, *path.parents):
        if not os.path.lexists(part):
            continue
        info = part.lstat()
        if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
            raise ValueError('복구 표시에는 연결 경로를 사용할 수 없습니다')
    path.resolve().relative_to(root)
    return path


def _read(path: Path, root: Path, limit: int) -> bytes:
    path = _safe(path, root)
    with path.open('rb') as stream:
        before = os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or before.st_size > limit:
            raise ValueError('복구 표시 파일 형식 또는 크기 제한 위반')
        raw = stream.read(limit + 1)
        after = os.fstat(stream.fileno())
    final = _safe(path, root).stat()
    identity = lambda value: (value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns)
    if len(raw) > limit or identity(before) != identity(after) or identity(after) != identity(final):
        raise ValueError('복구 표시 판독 중 파일 변경')
    return raw


def _ref(path: Path, raw: bytes) -> dict:
    return {'path': str(path), 'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw)}


def _read_ref(ref: dict, root: Path, limit: int) -> bytes:
    if type(ref) is not dict or set(ref) != {'path', 'sha256', 'bytes'}:
        raise ValueError('잘못된 복구 파일 참조')
    if type(ref['path']) is not str or type(ref['bytes']) is not int or not 0 <= ref['bytes'] <= limit:
        raise ValueError('잘못된 복구 파일 참조 크기')
    raw = _read(Path(ref['path']), root, limit)
    if _ref(Path(ref['path']), raw) != ref:
        raise ValueError('복구 파일 지문 불일치')
    return raw


def _view_path(output: Path) -> Path:
    return output.with_name(output.stem + '_recovery_view.json')


def _check_report(report: dict, base: dict) -> None:
    if type(base) is not dict or type(report) is not dict or report.get('schema_version') != 'recovery_execution_readback_v1':
        raise ValueError('지원하지 않는 복구 보고서')
    if report.get('report_sha256') != canonical_sha256({k: v for k, v in report.items() if k != 'report_sha256'}):
        raise ValueError('복구 보고서 자체 지문 불일치')
    if canonical_sha256(report.get('base')) != canonical_sha256(base):
        raise ValueError('복구 보고서 원래 판정 결속 불일치')
    fixed = {'execution_mode': 'LOCAL_SIMULATION_ONLY', 'data_kind': 'SYNTHETIC_CONTRACT_ONLY',
             'actual_external_call_count': 0, 'public_apply': False, 'publication_authority': False,
             'central_db_write': False, 'formal_kpi_status': 'NOT_ESTIMABLE'}
    if any(type(report.get(key)) is not type(value) or report.get(key) != value for key, value in fixed.items()):
        raise ValueError('합성 복구 표시 계약 불일치')


def publish_recovery_view(bound_plan, report_path: str | Path, *, root: str | Path) -> dict:
    """독립 재판독 후 새 companion을 만든다. 기존 companion은 덮어쓰지 않는다."""
    root = Path(root).resolve()
    bound_plan.verify_protected_sources()
    plan = bound_plan.plan
    output = _safe(Path(plan['artifacts']['result']['path']), root)
    manifest = _safe(Path(plan['artifacts']['manifest']['path']), root)
    report_path = _safe(Path(report_path), root)
    report_raw = _read(report_path, root, REPORT_LIMIT)
    report = read_strict_json(report_raw, maximum_bytes=REPORT_LIMIT)
    validate_recovery_execution_readback(report, bound_plan=bound_plan)
    _check_report(report, plan['base'])
    payload = {'schema_version': SCHEMA, 'base': plan['base'],
               'result': _ref(output, _read(output, root, SOURCE_LIMIT)),
               'manifest': _ref(manifest, _read(manifest, root, SOURCE_LIMIT)),
               'report': _ref(report_path, report_raw)}
    raw = (json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode('utf-8')
    target = _safe(_view_path(output), root)
    if target in (output, manifest, report_path):
        raise ValueError('복구 표시 출력과 입력 경로 충돌')
    if os.path.lexists(target):
        if _read(target, root, 65536) != raw:
            raise ValueError('이 결과에는 이미 다른 복구 보고서가 연결되어 있습니다')
    else:
        with target.open('xb') as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
    if _read(target, root, 65536) != raw:
        raise ValueError('복구 표시 참조 저장 검산 실패')
    bound_plan.verify_protected_sources()
    if _read(report_path, root, REPORT_LIMIT) != report_raw:
        raise ValueError('복구 표시 저장 중 보고서 변경')
    return _ref(target, raw)


def read_recovery_view(output_path: str | Path, root: str | Path, *, item: dict | None = None) -> dict:
    """표시용 파일·base 결속만 검산한다. 원장/HMAC 재검산으로 주장하지 않는다."""
    result = {'binding_status': 'MISSING', 'verification_scope': 'FILE_AND_BASE_BINDING_ONLY',
              'reason_codes': ['RECOVERY_REPORT_NOT_ATTACHED']}
    try:
        root = Path(root).resolve()
        output = _safe(Path(output_path), root)
        target = _safe(_view_path(output), root)
        if not os.path.lexists(target):
            return result
        raw = _read(target, root, 65536)
        ref = read_strict_json(raw)
        if type(ref) is not dict or set(ref) != {'schema_version', 'base', 'result', 'manifest', 'report'} or ref['schema_version'] != SCHEMA:
            raise ValueError('지원하지 않는 복구 표시 참조')
        if Path(ref['result']['path']).absolute() != output:
            raise ValueError('선택 결과 경로와 복구 참조 불일치')
        _read_ref(ref['result'], root, SOURCE_LIMIT)
        manifest_raw = _read_ref(ref['manifest'], root, SOURCE_LIMIT)
        manifest = read_strict_json(manifest_raw, maximum_bytes=SOURCE_LIMIT)
        if type(manifest) is not dict:
            raise ValueError('복구 원본 manifest는 객체여야 합니다')
        report_raw = _read_ref(ref['report'], root, REPORT_LIMIT)
        report = read_strict_json(report_raw, maximum_bytes=REPORT_LIMIT)
        base = ref['base']
        _check_report(report, base)
        if (manifest.get('publication_scope_id') != base['publication_scope_id']
                or manifest.get('run_id') != base['base_attempt_run_id']):
            raise ValueError('복구 base와 원본 manifest 불일치')
        if _read(target, root, 65536) != raw:
            raise ValueError('판독 중 복구 표시 참조 변경')
        view = {**result, 'binding_status': 'BOUND', 'reason_codes': [], 'report': report}
        return bind_recovery_view_row(view, item) if item is not None else view
    except (OSError, ValueError, KeyError, TypeError, RecursionError):
        return {**result, 'binding_status': 'INVALID', 'reason_codes': ['RECOVERY_REFERENCE_OR_BASE_INVALID']}


def bind_recovery_view_row(view: dict, item: dict) -> dict:
    """한 응답의 전체 행 조회에서 파일은 한 번 읽고 각 행만 따로 대조한다."""
    if view.get('binding_status') != 'BOUND':
        return view
    result = {k: v for k, v in view.items() if k != 'report'}
    try:
        base = view['report']['base']
        # 동일 숫자로 보이더라도 문자열 ID와 정수 ID는 서로 다른 입력이다.
        if type(item.get('post_id')) is not type(base['post_id']) or item.get('post_id') != base['post_id']:
            return {**result, 'binding_status': 'NO_PLAN_PROVIDED', 'reason_codes': ['NO_PLAN_FOR_SELECTED_ROW']}
        if canonical_sha256(item) != base['result_sha256']:
            raise ValueError('선택 행 원시 판정과 복구 base 불일치')
        meta = item.get('run_meta') or {}
        if type(meta) is not dict:
            raise ValueError('선택 행 run_meta 형식 불일치')
        for key in ('semantic_review_router_receipt', 'semantic_recovery_plan_receipt'):
            receipt = meta.get(key)
            if receipt is not None and (type(receipt) is not dict or any(
                type(receipt.get(k)) is not type(v) or receipt.get(k) != v for k, v in {
                    'publication_scope_id': base['publication_scope_id'], 'input_index': base['input_index'],
                    'post_id': base['post_id'], 'publication_decision_id': base['publication_decision_id'],
                    'stable_result_sha256': base['stable_result_sha256'],
                    'public_projection_sha256': base['public_projection_sha256']}.items())):
                raise ValueError('행 검토 수령증과 복구 base 불일치')
        return view
    except (OSError, ValueError, KeyError, TypeError, RecursionError):
        return {**result, 'binding_status': 'INVALID', 'reason_codes': ['RECOVERY_REFERENCE_OR_BASE_INVALID']}
