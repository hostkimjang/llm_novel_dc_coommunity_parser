"""명시한 로컬 CAL 원문·graph·raw score만으로 temperature를 학습하고 배타 저장한다."""
from __future__ import annotations

import argparse
import errno
import json
import os
from pathlib import Path, PureWindowsPath
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import run_candidate_reranker_training as local

BUNDLE_SCHEMA = 'candidate_reranker_calibration_bundle_v1'
BUNDLE_KEYS = frozenset({'schema_version', 'model_manifest', 'expected_scorer_summary_sha256',
    'training_manifest', 'expected_training_manifest_sha256', 'calibration_manifest',
    'expected_calibration_manifest_sha256', 'policy', 'solver_config', 'source_files',
    'evidence_files', 'calibration_rows', 'expected_example_ids'})
MAX_ROWS = 256


def _reference(ref, *, limit, snapshots):
    local._require(type(ref) is dict and set(ref) == {'path', 'sha256', 'bytes'}, '파일 참조 스키마 불일치')
    name = ref['path']
    local._require(type(name) is str and bool(name) and not Path(name).is_absolute()
        and not PureWindowsPath(name).drive and '://' not in name and '\\' not in name
        and all(part not in ('', '.', '..') for part in name.split('/')),
        '참조는 프로젝트 내부의 명시적 상대 경로여야 합니다')
    local._require(local._hex(ref['sha256']) and type(ref['bytes']) is int
        and 0 <= ref['bytes'] <= limit, '파일 SHA 또는 크기 제한 불일치')
    path = local._local_path(ROOT / name)
    local._require(path.resolve().is_relative_to(local._local_path(ROOT).resolve()), '프로젝트 경계 밖 참조')
    raw = local._read(path, ref['bytes'])
    local._require(len(raw) == ref['bytes'] and local._sha(raw) == ref['sha256'], '파일 raw SHA/크기 불일치')
    if str(path) in snapshots:
        local._require(snapshots[str(path)] == raw, '반복 참조 중 입력 변경')
    snapshots[str(path)] = raw
    return path, raw


def read_calibration_bundle(bundle_path, *, expected_sha256):
    local._require(local._hex(expected_sha256), 'bundle raw SHA256이 필요합니다')
    path = local._local_path(bundle_path)
    raw = local._read(path, local.MAX_BUNDLE_BYTES)
    local._require(local._sha(raw) == expected_sha256, 'bundle raw SHA256 불일치')
    value = local._strict_json(raw)
    local._require(set(value) == BUNDLE_KEYS and value['schema_version'] == BUNDLE_SCHEMA, 'calibration bundle 스키마 불일치')
    for field in ('training_manifest', 'calibration_manifest', 'policy', 'solver_config'):
        local._require(type(value[field]) is dict, field + ' object가 필요합니다')
    for field in ('expected_scorer_summary_sha256', 'expected_training_manifest_sha256', 'expected_calibration_manifest_sha256'):
        local._require(local._hex(value[field]), field + ' 형식 오류')
    ids, rows = value['expected_example_ids'], value['calibration_rows']
    local._require(type(ids) is list and 0 < len(ids) <= MAX_ROWS
        and all(type(item) is str and 0 < len(item) <= 512 for item in ids)
        and len(set(ids)) == len(ids), 'ordered 전체 CAL example ID 목록 오류')
    local._require(type(rows) is list and len(rows) == len(ids) and all(type(row) is dict for row in rows), 'CAL 행 개수/형식 오류')
    local._require([row.get('example', {}).get('example_id') if type(row.get('example')) is dict else None
                    for row in rows] == ids, 'CAL 행과 외부 ordered ID 순서 불일치')
    snapshots = {str(path): raw}
    model_path, _ = _reference(value['model_manifest'], limit=local.MAX_BUNDLE_BYTES, snapshots=snapshots)
    maps, files, size = {}, 0, 0
    for field in ('source_files', 'evidence_files'):
        refs = value[field]
        local._require(type(refs) is dict, field + ' map 형식 오류')
        files += len(refs)
        local._require(files <= local.MAX_FILES, '원문 파일 개수 제한 초과')
        payloads = {}
        for identifier, ref in refs.items():
            local._require(type(identifier) is str and bool(identifier), '원문 map 키 오류')
            target, data = _reference(ref, limit=local.MAX_PAYLOAD_BYTES, snapshots=snapshots)
            local._require(target != path and target != model_path, '원문을 bundle/model 파일로 대체할 수 없습니다')
            size += len(data)
            local._require(size <= local.MAX_PAYLOAD_BYTES, '원문 bytes 총량 제한 초과')
            if field == 'evidence_files':
                local._require(identifier == ref['sha256'], 'evidence map 키와 raw SHA 불일치')
            payloads[identifier] = data
        maps[field] = payloads
    return {'bundle': value, 'snapshots': snapshots, 'model_path': model_path,
            'source_payloads': maps['source_files'], 'evidence_payloads': maps['evidence_files']}


def _replay_rows(scorer, rows, *, training_manifest=None, source_payloads=None, evidence_payloads=None,
                 required_split='CALIBRATION'):
    from src.llm_batch.grounding import candidate_reranker_event_bridge as bridge
    semantic = bridge.event_model_feature_schema(scorer.summary()) == bridge.FEATURE_SCHEMA_V2
    local._require(required_split in ('CALIBRATION', 'FROZEN_HOLDOUT'), 'raw 재생 분할 오류')
    fields = ('ranked_candidates', 'event_logits', 'nil_score', 'input_sha256', 'model_sha256',
              'training_split_manifest_sha256', 'candidate_ranker_model_sha256')
    for row in rows:
        example, supplied = row.get('example'), row.get('raw_receipt')
        local._require(type(example) is dict and type(supplied) is dict and 'frozen_view' in example,
                       'CAL example/raw receipt 누락')
        if semantic:
            local._require(type(training_manifest) is dict and type(source_payloads) is dict
                and type(evidence_payloads) is dict, '의미 입력 CAL 원문과 전체 분할 근거가 필요합니다')
            bound_rows = [r for r in training_manifest['rows'] if r['assignment']['example_id'] == example.get('example_id')]
            local._require(len(bound_rows) == 1 and bound_rows[0]['assignment']['split'] == required_split,
                           '의미 입력 행과 요청 분할 결속 불일치')
            artifact = bridge.resolve_example_semantic_input(example, bound_rows[0], source_payloads,
                evidence_payloads, split_manifest=training_manifest)
            local._require(artifact is not None, '새 모델에는 의미 입력 capture가 필요합니다')
            replay = scorer.score(example['frozen_view'], semantic_input=artifact, evidence_payloads=evidence_payloads)
            compared = fields + bridge.SEMANTIC_MODEL_FIELDS + ('semantic_input_sha256', 'semantic_consumption')
        else:
            replay = scorer.score(example['frozen_view'])
            compared = fields
        local._require(replay.get('status') == supplied.get('status') == 'SCORED_LEARNED', 'CAL raw score 재생 실패')
        local._require(all(field in supplied and field in replay
            and local._json_bytes(supplied[field]) == local._json_bytes(replay[field]) for field in compared),
            '공급 CAL raw score와 로컬 모델 재생 불일치')


def _typed_context(value):
    from src.llm_batch.grounding.candidate_set_calibration_shadow import (
        CalibrationEvaluationPolicy, CalibrationSplitAssignment, CalibrationSplitManifest,
    )
    manifest = dict(value['calibration_manifest'])
    local._require(type(manifest.get('assignments')) is list, 'calibration assignments 형식 오류')
    manifest['assignments'] = tuple(CalibrationSplitAssignment(**row) for row in manifest['assignments'])
    return CalibrationSplitManifest(**manifest), CalibrationEvaluationPolicy(**value['policy'])


def _typed_rows(rows):
    from src.llm_batch.grounding.candidate_set_shadow import selective_shadow_from_dict
    from src.llm_batch.grounding.candidate_generation import candidate_generation_proof_from_dict
    from src.llm_batch.promotion_gate import RetrievalState
    result = []
    for row in rows:
        local._require(set(row) == {'example', 'raw_receipt', 'base_shadow', 'generation_proof',
                                   'retrieval_state', 'publication_scope_id', 'source_binding_sha256'}, 'CAL 행 스키마 불일치')
        result.append({**row, 'base_shadow': selective_shadow_from_dict(row['base_shadow']),
            'generation_proof': candidate_generation_proof_from_dict(row['generation_proof']),
            'retrieval_state': RetrievalState(**row['retrieval_state'])})
    return result


def _validate_report(report, artifact, summary):
    local._require(type(report) is dict and report.get('schema_version') == 'candidate_reranker_temperature_fit_report_v1'
        and report.get('status') == 'FITTED' and report.get('method') == 'TEMPERATURE_SCALING', 'fit report 스키마 불일치')
    local._require(report.get('report_sha256') == local._sha(local._json_bytes({k: v for k, v in report.items()
                                                                            if k != 'report_sha256'})), 'fit report SHA 불일치')
    evidence = artifact.fit_receipt.to_dict()['learning_evidence']
    binding = {'training_split_manifest_sha256': summary['training_split_manifest_sha256'],
        'calibration_manifest_sha256': artifact.split_manifest_sha256, 'scorer_fingerprint': summary['scorer_sha256'],
        'scorer_summary_sha256': local._sha(local._json_bytes(summary)), 'model_sha256': summary['model_sha256'],
        'base_model_sha256': summary['candidate_ranker_model_sha256'], 'data_kind': summary['data_kind']}
    local._require(local._json_bytes(report.get('binding')) == local._json_bytes(binding)
        and local._json_bytes(evidence['binding']) == local._json_bytes(binding)
        and report.get('data_kind') == summary['data_kind'], 'fit report 모델/자료 결속 불일치')
    local._require(all(local._json_bytes(report.get(key)) == local._json_bytes(evidence[key])
                       for key in ('solver', 'counts', 'config'))
        and report.get('learning_evidence_sha256') == evidence['evidence_sha256']
        and report.get('calibration_artifact_sha256') == artifact.artifact_sha256
        and report.get('fit_receipt_sha256') == artifact.fit_receipt.receipt_sha256
        and report.get('policy_sha256') == artifact.policy_sha256
        and evidence['solver']['temperature'] == artifact.temperature, 'fit report 온도/근거 결속 불일치')
    local._require(report.get('optimizer_executed') is True and all(report.get(key) is False for key in
        ('model_parameters_updated', 'thresholds_fitted', 'publication_authority', 'actual_performance_evaluated')),
        'fit report 실행/권한 주장 불일치')


def _read_saved(ref):
    raw = local._read(Path(ref['path']), ref['bytes'])
    local._require(len(raw) == ref['bytes'] and local._sha(raw) == ref['sha256'], '저장 파일 raw SHA/크기 불일치')
    return local._strict_json(raw)


def _rename_noreplace(source, destination):
    """같은 폴더의 검산된 파일을 기존 이름을 덮지 않고 원자적으로 확정한다."""
    if os.name == 'nt':
        # Windows rename은 목적지가 존재하면 실패한다. os.replace는 사용하지 않는다.
        os.rename(source, destination)
        return
    if sys.platform.startswith('linux'):
        import ctypes
        library = ctypes.CDLL(None, use_errno=True)
        rename = getattr(library, 'renameat2', None)
        if rename is not None:
            rename.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
            rename.restype = ctypes.c_int
            # AT_FDCWD=-100, RENAME_NOREPLACE=1. 지원하지 않는 FS/커널도 덮어쓰기 없이 실패한다.
            if rename(-100, os.fsencode(source), -100, os.fsencode(destination), 1) == 0:
                return
            error = ctypes.get_errno()
            raise OSError(error, os.strerror(error), os.fspath(destination))
    raise OSError(errno.ENOTSUP, '덮어쓰기 없는 원자 rename을 지원하지 않는 환경입니다')


def _publish_workflow_receipt(output, receipt):
    pending = output / '.pending_receipt.json'
    final = output / 'workflow_receipt.json'
    ref = local._write(pending, receipt)
    # _write는 fsync와 raw readback까지 성공해야 반환한다. 확정 후에는 실패 가능한
    # 재판독/정리 단계가 없으며, 실패한 staging 파일은 진단 근거로 그대로 보존한다.
    final_ref = {**ref, 'path': str(final)}
    _rename_noreplace(pending, final)
    return final_ref


def calibrate_bundle(*, bundle_path, expected_sha256, output_dir):
    output = local._local_path(output_dir)
    local._require(not os.path.lexists(output), 'calibration 출력 폴더는 새 경로여야 합니다')
    from src.llm_batch.runtime.execution_config import apply_profile_resources, observe_process_resources
    resources_start = apply_profile_resources('low-load-validation', os.environ)
    local._resources(resources_start)
    loaded = read_calibration_bundle(bundle_path, expected_sha256=expected_sha256)
    value = loaded['bundle']
    calibration, policy = _typed_context(value)
    from src.llm_batch.grounding.candidate_reranker_shadow import load_scorer
    scorer = load_scorer(loaded['model_path'], expected_sha256=value['model_manifest']['sha256'])
    summary = scorer.summary()
    local._require(local._sha(local._json_bytes(summary)) == value['expected_scorer_summary_sha256'],
                   'scorer summary SHA 불일치')
    local._require(summary.get('status') == 'AVAILABLE_LEARNED'
        and summary.get('backend') == 'NIL_AUGMENTED_LINEAR_V1' and summary.get('nil_head_available') is True,
        'CAL에는 고정된 NIL 학습 모델이 필요합니다')
    _replay_rows(scorer, value['calibration_rows'], training_manifest=value['training_manifest'],
        source_payloads=loaded['source_payloads'], evidence_payloads=loaded['evidence_payloads'])
    from src.llm_batch.grounding.candidate_reranker_event_bridge import build_calibration_fit_events
    events = build_calibration_fit_events(rows=_typed_rows(value['calibration_rows']), expected_example_ids=value['expected_example_ids'],
        scorer_summary=summary, expected_scorer_summary_sha256=value['expected_scorer_summary_sha256'],
        training_manifest=value['training_manifest'], expected_training_manifest_sha256=value['expected_training_manifest_sha256'],
        calibration_manifest=calibration, expected_calibration_manifest_sha256=value['expected_calibration_manifest_sha256'],
        source_payloads=loaded['source_payloads'], evidence_payloads=loaded['evidence_payloads'])
    from src.llm_batch.grounding.candidate_reranker_calibration import fit_temperature
    fitted = fit_temperature(events, split_manifest=calibration, policy=policy, config=value['solver_config'])
    local._require(type(fitted) is dict and set(fitted) == {'artifact', 'fit_report'}, 'temperature 학습 반환 스키마 불일치')
    artifact, report = fitted['artifact'], fitted['fit_report']
    from src.llm_batch.grounding.candidate_set_calibration_shadow import CalibrationArtifact, calibration_artifact_from_dict
    local._require(isinstance(artifact, CalibrationArtifact)
                   and artifact.schema_version == 'candidate_set_calibration_artifact_v2', '실제 학습 artifact v2가 필요합니다')
    artifact.validate_against(calibration, policy)
    artifact_payload = artifact.to_dict()
    fit_payload = artifact.fit_receipt.to_dict()
    local._require(local._json_bytes(fit_payload['learning_evidence']['events'])
                   == local._json_bytes([event.to_dict() for event in events]), 'fit 근거와 요청 CAL event 불일치')
    _validate_report(report, artifact, summary)
    local._check_inputs(loaded['snapshots'])
    output.mkdir(parents=True, exist_ok=False)
    artifact_ref = local._write(output / 'calibration_artifact.json', artifact_payload)
    fit_ref = local._write(output / 'fit_receipt.json', fit_payload)
    report_ref = local._write(output / 'fit_report.json', report)
    stored_payload = _read_saved(artifact_ref)
    stored = calibration_artifact_from_dict(stored_payload)
    stored.validate_against(calibration, policy)
    local._require(local._json_bytes(stored.to_dict()) == local._json_bytes(artifact_payload),
                   '저장 artifact 전체 typed readback 불일치')
    stored_fit = _read_saved(fit_ref)
    stored_report = _read_saved(report_ref)
    local._require(local._json_bytes(stored_fit) == local._json_bytes(stored.fit_receipt.to_dict())
                   and local._json_bytes(stored_report) == local._json_bytes(report), '저장 fit 근거 재판독 불일치')
    _validate_report(stored_report, stored, summary)
    local._check_inputs(loaded['snapshots'])
    resources_end = observe_process_resources(os.environ)
    local._resources(resources_end)
    local._require(all(resources_start[key] == resources_end[key] for key in
        ('pid', 'priority_class', 'affinity_mask', 'logical_cpu_count', 'numeric_threads')), 'CAL 학습 중 자원 설정 변경')
    for ref in (artifact_ref, fit_ref, report_ref):
        _read_saved(ref)
    receipt = {'schema_version': 'candidate_reranker_calibration_workflow_v1', 'status': 'FITTED_AND_READBACK_VERIFIED',
        'bundle_sha256': expected_sha256, 'data_kind': summary['data_kind'], 'backend': summary['backend'],
        'inputs': [{'path': path, 'sha256': local._sha(raw), 'bytes': len(raw)} for path, raw in loaded['snapshots'].items()],
        'expected_example_ids': value['expected_example_ids'], 'calibration_artifact': artifact_ref,
        'fit_receipt': fit_ref, 'fit_report': report_ref, 'scorer_summary': summary,
        'temperature': stored.temperature, 'resources_start': resources_start, 'resources_end': resources_end,
        'local_score_replay_executed': True, 'calibration_executed': True, 'model_training_executed': False,
        'frozen_holdout_evaluated': False, 'actual_quality_evaluated': False, 'actual_performance_evaluated': False,
        'formal_kpi_status': 'NOT_ESTIMABLE', 'publication_authority': False, 'public_apply': False, 'central_db_write': False,
        'limitations': ['LOCAL_CAL_FIT_ONLY', 'NO_ACTUAL_QUALITY_CLAIM', 'NO_FROZEN_HOLDOUT_EVALUATION',
                        'SOURCE_BINDING_NOT_INDEPENDENT_PROVENANCE_VERIFICATION'],
        'receipt_hash_excludes': ['receipt_sha256', 'workflow_receipt']}
    receipt['receipt_sha256'] = local._sha(local._json_bytes(receipt))
    ref = _publish_workflow_receipt(output, receipt)
    return {**receipt, 'workflow_receipt': ref}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument('--bundle', required=True)
    parser.add_argument('--bundle-sha256', required=True)
    parser.add_argument('--output-dir', required=True)
    args = parser.parse_args(argv)
    try:
        result = calibrate_bundle(bundle_path=args.bundle, expected_sha256=args.bundle_sha256, output_dir=args.output_dir)
    except (OSError, ValueError, TypeError) as exc:
        print('로컬 temperature 학습 실패: ' + str(exc), file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
