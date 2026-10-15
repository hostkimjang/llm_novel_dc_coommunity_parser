"""명시한 로컬 bundle로 작은 learned baseline을 학습·배타 저장한다. 성능 평가는 하지 않는다."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PureWindowsPath
import re
import stat
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

BUNDLE_SCHEMA = 'candidate_reranker_training_bundle_v1'
BUNDLE_V2_SCHEMA = 'candidate_reranker_training_bundle_v2'
BUNDLE_V3_SCHEMA = 'candidate_reranker_training_bundle_v3'
PAIRWISE_BACKEND = 'PAIRWISE_LINEAR_V1'
NIL_BACKEND = 'NIL_AUGMENTED_LINEAR_V1'
MAX_BUNDLE_BYTES = 16 * 1024 * 1024
MAX_PAYLOAD_BYTES = 8 * 1024 * 1024
MAX_FILES = 8000
BUNDLE_KEYS = frozenset({'schema_version', 'scorer_id', 'parameters', 'split_manifest',
    'source_files', 'evidence_files', 'examples', 'calibration_manifest', 'expected_calibration_sha256'})
BUNDLE_V2_KEYS = BUNDLE_KEYS | {'backend'}
BUNDLE_V3_KEYS = BUNDLE_V2_KEYS | {'semantic_feature_contract_sha256'}


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _hex(value) -> bool:
    return type(value) is str and re.fullmatch('[0-9a-f]{64}', value) is not None


def _json_bytes(value) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')


def _strict_json(raw: bytes) -> dict:
    def pairs(items):
        result = {}
        for key, value in items:
            _require(key not in result, '중복 JSON 키')
            result[key] = value
        return result
    def invalid_constant(value):
        raise ValueError('비유한 JSON 숫자')
    try:
        value = json.loads(raw.decode('utf-8'), object_pairs_hook=pairs, parse_constant=invalid_constant)
        _json_bytes(value)  # 1e999 등 JSON decoder의 float overflow도 거절한다.
    except (UnicodeError, RecursionError, OverflowError) as exc:
        raise ValueError('잘못된 UTF-8 JSON') from exc
    _require(type(value) is dict, 'JSON object가 필요합니다')
    return value


def _drive_type(path: Path):
    if os.name != 'nt':
        return None
    import ctypes
    from ctypes import wintypes
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.GetDriveTypeW.argtypes = [wintypes.LPCWSTR]
    kernel.GetDriveTypeW.restype = wintypes.UINT
    return kernel.GetDriveTypeW(path.anchor)


def _local_path(value: str | Path) -> Path:
    text = os.fspath(value)
    _require(type(text) is str and bool(text) and '://' not in text
             and not text.startswith(('\\\\', '//')), '명시적인 로컬 경로가 필요합니다')
    path = Path(text).absolute()
    drive = _drive_type(path)
    _require(drive is None or drive in (2, 3, 5, 6), 'mapped network drive 등 비로컬 드라이브는 허용하지 않습니다')
    for component in (path, *path.parents):
        if not os.path.lexists(component):
            continue
        info = component.lstat()
        _require(not stat.S_ISLNK(info.st_mode) and not getattr(info, 'st_file_attributes', 0) & 0x400,
                 '연결 경로는 허용하지 않습니다')
    return path


def _read(path: Path, limit: int) -> bytes:
    path = _local_path(path)
    with path.open('rb') as stream:
        before = os.fstat(stream.fileno())
        _require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_size <= limit,
                 '입력은 크기 제한 안의 단일 일반 파일이어야 합니다')
        raw = stream.read(limit + 1)
        after = os.fstat(stream.fileno())
    final = _local_path(path).stat()
    identity = lambda value: (value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns)
    _require(len(raw) <= limit and identity(before) == identity(after) == identity(final), '입력 판독 중 파일 변경')
    return raw


def read_training_bundle(bundle_path: str | Path, *, expected_sha256: str) -> dict:
    """원문을 보정하거나 label/bridge를 만들지 않고 exact bytes만 읽는다."""
    _require(_hex(expected_sha256), 'bundle raw SHA256을 명시해야 합니다')
    path = _local_path(bundle_path)
    raw = _read(path, MAX_BUNDLE_BYTES)
    _require(_sha(raw) == expected_sha256, 'bundle raw SHA256 불일치')
    value = _strict_json(raw)
    if value.get('schema_version') == BUNDLE_SCHEMA:
        _require(set(value) == BUNDLE_KEYS, 'bundle 스키마 불일치')
        backend = PAIRWISE_BACKEND
    else:
        semantic = value.get('schema_version') == BUNDLE_V3_SCHEMA
        _require(value.get('schema_version') in (BUNDLE_V2_SCHEMA, BUNDLE_V3_SCHEMA)
                 and set(value) == (BUNDLE_V3_KEYS if semantic else BUNDLE_V2_KEYS),
                 'bundle 스키마 불일치')
        backend = value['backend']
        _require(type(backend) is str and backend in (PAIRWISE_BACKEND, NIL_BACKEND),
                 'bundle backend는 명시한 로컬 허용 목록에 있어야 합니다')
        if semantic:
            from src.llm_batch.grounding.candidate_reranker_semantic_input import FEATURE_CONTRACT_SHA256
            _require(value['semantic_feature_contract_sha256'] == FEATURE_CONTRACT_SHA256,
                     'semantic feature 계약 SHA 불일치')
    _require(type(value['scorer_id']) is str and 0 < len(value['scorer_id']) <= 128
             and value['scorer_id'].strip() == value['scorer_id'], 'scorer_id 형식 오류')
    _require(type(value['parameters']) is dict and type(value['split_manifest']) is dict
             and type(value['examples']) is list, '학습 파라미터/manifest/examples 형식 오류')
    _require(value['calibration_manifest'] is None or type(value['calibration_manifest']) is dict,
             'calibration manifest 형식 오류')
    snapshots = {str(path): raw}
    payload_maps = {}
    total_bytes, total_files = 0, 0
    for key in ('source_files', 'evidence_files'):
        rows = value[key]
        _require(type(rows) is dict, 'source/evidence map 형식 오류')
        total_files += len(rows)
        _require(total_files <= MAX_FILES, '원문 파일 개수 제한 초과')
        payloads = {}
        for identifier, ref in rows.items():
            _require(type(identifier) is str and bool(identifier) and type(ref) is dict
                     and set(ref) == {'path', 'sha256', 'bytes'}, '원문 참조 스키마 불일치')
            _require(_hex(ref['sha256']) and type(ref['bytes']) is int and 0 <= ref['bytes'] <= MAX_PAYLOAD_BYTES,
                     '원문 SHA 또는 크기 오류')
            relative = ref['path']
            _require(type(relative) is str and bool(relative) and not Path(relative).is_absolute()
                     and not PureWindowsPath(relative).drive and '://' not in relative
                     and '\\' not in relative and all(part not in ('', '.', '..') for part in relative.split('/')),
                     '원문은 bundle 아래 명시적인 상대 경로여야 합니다')
            target = _local_path(path.parent / relative)
            _require(target.resolve().is_relative_to(path.parent.resolve()) and target != path,
                     '원문 경로가 bundle 경계를 벗어납니다')
            total_bytes += ref['bytes']
            _require(total_bytes <= MAX_PAYLOAD_BYTES, '원문 bytes 총량 제한 초과')
            data = _read(target, min(MAX_PAYLOAD_BYTES, ref['bytes']))
            _require(len(data) == ref['bytes'] and _sha(data) == ref['sha256'], '원문 raw SHA/크기 불일치')
            if key == 'evidence_files':
                _require(identifier == ref['sha256'], 'evidence map 키와 raw SHA 불일치')
            if str(target) in snapshots:
                _require(snapshots[str(target)] == data, '반복 참조 중 원문 변경')
            snapshots[str(target)] = data
            payloads[identifier] = data
        payload_maps[key] = payloads
    return {'bundle': value, 'bundle_path': path, 'bundle_sha256': expected_sha256, 'backend': backend,
            'source_payloads': payload_maps['source_files'], 'evidence_payloads': payload_maps['evidence_files'],
            'snapshots': snapshots}


def _check_inputs(snapshots: dict[str, bytes]) -> None:
    for name, before in snapshots.items():
        _require(_read(Path(name), max(MAX_BUNDLE_BYTES, len(before))) == before, '학습 중 입력 파일 변경')


def _resources(value: dict) -> None:
    from src.llm_batch.runtime.execution_config import NUMERIC_THREAD_KEYS
    _require(value.get('pid') == os.getpid() and value.get('logical_cpu_count') == 1
             and set(value.get('numeric_threads', {})) == set(NUMERIC_THREAD_KEYS)
             and all(item == '1' for item in value['numeric_threads'].values()), '저부하 자원 관측 불일치')
    if os.name == 'nt':
        _require(value.get('priority_class') == 16384 and value.get('affinity_mask') == 2,
                 'Windows BelowNormal/CPU2 관측 불일치')


def _write(path: Path, value: dict) -> dict:
    raw = (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode('utf-8')
    _local_path(path)
    with path.open('xb') as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    _require(_read(path, max(len(raw), MAX_BUNDLE_BYTES)) == raw, '출력 저장 후 raw 재판독 불일치')
    return {'path': str(path), 'sha256': _sha(raw), 'bytes': len(raw)}


def train_bundle(*, bundle_path: str | Path, expected_sha256: str, output_dir: str | Path) -> dict:
    output = _local_path(output_dir)
    _require(not os.path.lexists(output), '학습 출력 폴더는 새 경로여야 합니다')
    from src.llm_batch.runtime.execution_config import apply_profile_resources, observe_process_resources
    resources_start = apply_profile_resources('low-load-validation', os.environ)
    _resources(resources_start)
    loaded = read_training_bundle(bundle_path, expected_sha256=expected_sha256)
    value = loaded['bundle']
    from src.llm_batch.grounding.reranker_training_split import validate_training_split
    split_report = validate_training_split(value['split_manifest'], source_payloads=loaded['source_payloads'],
        evidence_payloads=loaded['evidence_payloads'], calibration_manifest=value['calibration_manifest'],
        expected_calibration_sha256=value['expected_calibration_sha256'])
    _require(split_report['status'] == 'VALID', '학습 split이 VALID가 아닙니다: ' + split_report['status'])
    backend = loaded['backend']
    if backend == NIL_BACKEND:
        from src.llm_batch.grounding import candidate_reranker_nil_learned as learned
        manifest_schema = 'candidate_reranker_manifest_v3'
    else:
        from src.llm_batch.grounding import candidate_reranker_learned as learned
        manifest_schema = 'candidate_reranker_manifest_v2'
    semantic = value['schema_version'] == BUNDLE_V3_SCHEMA
    feature_schema = learned.FEATURE_SCHEMA_V2 if semantic else learned.FEATURE_SCHEMA
    training_options = {'feature_schema': feature_schema} if semantic else {}
    trained = learned.train_model(value['split_manifest'], examples=value['examples'],
        source_payloads=loaded['source_payloads'], evidence_payloads=loaded['evidence_payloads'],
        config=value['parameters'], **training_options)
    _require(type(trained) is dict and set(trained) == {'model', 'training_report'}, '학습 반환 스키마 불일치')
    model, training_report = learned.validate_model(trained['model']), trained['training_report']
    _require(type(training_report) is dict and training_report.get('actual_performance_evaluated') is False,
             '학습 보고서는 실제 성능 평가를 주장할 수 없습니다')
    _require(training_report.get('model_sha256') == _sha(_json_bytes(model))
             and training_report.get('training_binding') == model['training_binding']
             and training_report.get('data_kind') == model['data_kind'], '학습 모델과 보고서의 결속 불일치')
    _require(model.get('backend') == backend and training_report.get('backend') == backend,
             '선택한 backend와 학습 결과 불일치')
    _require(model['feature_schema'] == feature_schema, '선택한 feature schema와 학습 결과 불일치')
    if semantic:
        _require(model['training_binding']['semantic_feature_contract_sha256'] == value['semantic_feature_contract_sha256'],
                 'semantic 학습 결과의 정책 결속 불일치')
    _check_inputs(loaded['snapshots'])
    manifest = {'schema_version': manifest_schema, 'scorer_id': value['scorer_id'],
        'backend': backend, 'data_kind': model['data_kind'],
        'feature_schema': model['feature_schema'], 'model': model}
    _require(manifest['data_kind'] == value['split_manifest']['data_kind'], '학습 결과 data_kind 불일치')
    output.mkdir(parents=True, exist_ok=False)
    model_ref = _write(output / 'model_manifest.json', manifest)
    report_ref = _write(output / 'training_report.json', training_report)
    from src.llm_batch.grounding.candidate_reranker_shadow import load_scorer
    scorer = load_scorer(model_ref['path'], expected_sha256=model_ref['sha256'])
    summary = scorer.summary()
    _require(summary.get('status') == 'AVAILABLE_LEARNED' and summary.get('backend') == backend
             and summary.get('data_kind') == manifest['data_kind']
             and summary.get('model_sha256') == _sha(_json_bytes(model))
             and summary.get('training_split_manifest_sha256') == model['training_binding']['split_manifest_sha256'],
             '저장 scorer 재판독 불일치')
    if semantic:
        _require(summary.get('semantic_input_required') is True
                 and summary.get('semantic_contract_sha256') == value['semantic_feature_contract_sha256'],
                 '저장 semantic scorer 정책 재판독 불일치')
    if backend == NIL_BACKEND:
        _require(summary.get('nil_head_available') is True
                 and summary.get('training_status') == 'TRAINED_PAIRWISE_PLUS_NIL_HEAD'
                 and summary.get('model_kind') == 'LEARNED_LINEAR_WITH_NIL_HEAD'
                 and summary.get('candidate_ranker_model_sha256') == _sha(_json_bytes(model['base_model'])),
                 '저장 NIL head 재판독 불일치')
    _check_inputs(loaded['snapshots'])
    resources_end = observe_process_resources(os.environ)
    _resources(resources_end)
    _require(all(resources_start[k] == resources_end[k] for k in
        ('pid', 'priority_class', 'affinity_mask', 'logical_cpu_count', 'numeric_threads')), '학습 중 자원 설정 변경')
    receipt = {'schema_version': 'candidate_reranker_training_workflow_v1', 'status': 'TRAINED_AND_READBACK_VERIFIED',
        'bundle_sha256': expected_sha256, 'data_kind': manifest['data_kind'], 'backend': backend,
        'inputs': [{'path': path, 'sha256': _sha(raw), 'bytes': len(raw)} for path, raw in loaded['snapshots'].items()],
        'model_manifest': model_ref, 'training_report': report_ref, 'split_report': split_report,
        'scorer_summary': summary, 'resources_start': resources_start, 'resources_end': resources_end,
        'formal_kpi_status': 'NOT_ESTIMABLE', 'actual_performance_evaluated': False,
        'local_model_training_executed': True, 'metric_evaluator_executed': False,
        'calibration_executed': False, 'frozen_holdout_evaluated': False,
        'publication_authority': False, 'public_apply': False, 'central_db_write': False,
        'limitations': ['LOCAL_BASELINE_ONLY', 'PROVENANCE_DECLARATIONS_NOT_INDEPENDENTLY_VERIFIED',
                        'NO_GENERALIZATION_CLAIM', 'NO_PROBABILITY_CALIBRATION'],
        'receipt_hash_excludes': ['receipt_sha256', 'workflow_receipt']}
    if semantic:
        receipt.update(schema_version='candidate_reranker_training_workflow_v2',
            semantic_feature_contract_sha256=model['training_binding']['semantic_feature_contract_sha256'],
            semantic_inputs_sha256=model['training_binding']['semantic_inputs_sha256'])
    receipt['receipt_sha256'] = _sha(_json_bytes(receipt))
    ref = _write(output / 'workflow_receipt.json', receipt)
    return {**receipt, 'workflow_receipt': ref}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument('--bundle', required=True)
    parser.add_argument('--bundle-sha256', required=True)
    parser.add_argument('--output-dir', required=True)
    args = parser.parse_args(argv)
    try:
        result = train_bundle(bundle_path=args.bundle, expected_sha256=args.bundle_sha256, output_dir=args.output_dir)
    except (OSError, ValueError) as exc:
        print('로컬 reranker 학습 실패: ' + str(exc), file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
