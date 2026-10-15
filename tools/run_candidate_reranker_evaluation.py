"""고정 로컬 NIL 모델·FROZEN 관측을 평가하고 원문 결속 보고서를 새 폴더에 저장한다."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path, PureWindowsPath
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import run_candidate_reranker_training as local
from tools import run_candidate_reranker_calibration as calibration_io

BUNDLE_SCHEMA = 'candidate_reranker_evaluation_bundle_v1'
BUNDLE_KEYS = frozenset({'schema_version', 'model_manifest', 'expected_scorer_summary_sha256',
    'training_manifest', 'expected_training_manifest_sha256', 'calibration_manifest',
    'expected_calibration_manifest_sha256', 'policy', 'calibration_artifact',
    'source_files', 'evidence_files', 'expected_rows', 'observations', 'frozen_rows'})
MAX_ROWS = 256
MAX_REPORT_BYTES = 16 * 1024 * 1024


def _reference(ref, *, bundle_path, limit, snapshots):
    local._require(type(ref) is dict and set(ref) == {'path', 'sha256', 'bytes'}, '파일 참조 스키마 불일치')
    name = ref['path']
    local._require(type(name) is str and bool(name) and not Path(name).is_absolute()
        and not PureWindowsPath(name).drive and '://' not in name and '\\' not in name
        and all(part not in ('', '.', '..') for part in name.split('/')),
        '참조는 bundle 폴더 내부의 명시적 상대 경로여야 합니다')
    local._require(local._hex(ref['sha256']) and type(ref['bytes']) is int
        and 0 <= ref['bytes'] <= limit, '파일 SHA 또는 크기 제한 불일치')
    target = local._local_path(bundle_path.parent / name)
    local._require(target.resolve().is_relative_to(bundle_path.parent.resolve())
        and target != bundle_path, 'bundle 밖 또는 자기 참조는 허용하지 않습니다')
    raw = local._read(target, ref['bytes'])
    local._require(len(raw) == ref['bytes'] and local._sha(raw) == ref['sha256'], '파일 raw SHA/크기 불일치')
    local._require(str(target) not in snapshots or snapshots[str(target)] == raw, '반복 참조 중 입력 변경')
    snapshots[str(target)] = raw
    return target, raw


def read_evaluation_bundle(bundle_path, *, expected_sha256):
    local._require(local._hex(expected_sha256), 'bundle raw SHA256이 필요합니다')
    path = local._local_path(bundle_path)
    raw = local._read(path, local.MAX_BUNDLE_BYTES)
    local._require(local._sha(raw) == expected_sha256, 'bundle raw SHA256 불일치')
    value = local._strict_json(raw)
    local._require(set(value) == BUNDLE_KEYS and value['schema_version'] == BUNDLE_SCHEMA, '평가 bundle 스키마 불일치')
    for field in ('training_manifest', 'calibration_manifest', 'policy'):
        local._require(type(value[field]) is dict, field + ' object가 필요합니다')
    for field in ('expected_scorer_summary_sha256', 'expected_training_manifest_sha256', 'expected_calibration_manifest_sha256'):
        local._require(local._hex(value[field]), field + ' 형식 오류')
    rows, observations = value['expected_rows'], value['observations']
    local._require(type(rows) is list and 0 < len(rows) <= MAX_ROWS
        and all(type(row) is dict for row in rows), '전체 FROZEN 행 개수/형식 오류')
    ids = [row.get('example_id') for row in rows]
    local._require(all(type(eid) is str and 0 < len(eid) <= 512 for eid in ids)
        and len(set(ids)) == len(ids), 'FROZEN example ID 중복/형식 오류')
    local._require(type(observations) is list and len(observations) == len(rows)
        and all(type(row) is dict for row in observations)
        and [row.get('example_id') for row in observations] == ids, '전체 관측 순서/집합 불일치')
    graph = value['frozen_rows']
    local._require(type(graph) is list and len(graph) <= len(rows)
        and all(type(row) is dict for row in graph), 'FROZEN graph 행 형식 오류')
    graph_ids = [row.get('example', {}).get('example_id') if type(row.get('example')) is dict else None for row in graph]
    local._require(all(type(eid) is str and eid in ids for eid in graph_ids)
        and len(set(graph_ids)) == len(graph_ids)
        and graph_ids == [eid for eid in ids if eid in graph_ids], 'FROZEN graph 순서/집합 불일치')
    snapshots = {str(path): raw}
    model_path, _ = _reference(value['model_manifest'], bundle_path=path, limit=local.MAX_BUNDLE_BYTES, snapshots=snapshots)
    artifact_path, artifact_raw = _reference(value['calibration_artifact'], bundle_path=path,
        limit=local.MAX_PAYLOAD_BYTES, snapshots=snapshots)
    local._require(model_path != artifact_path, '모델과 교정 artifact는 별도 파일이어야 합니다')
    maps, count, size = {}, 0, 0
    for field in ('source_files', 'evidence_files'):
        refs = value[field]
        local._require(type(refs) is dict, field + ' map 형식 오류')
        count += len(refs)
        local._require(count <= local.MAX_FILES, '원문 파일 개수 제한 초과')
        payloads = {}
        for key, ref in refs.items():
            local._require(type(key) is str and bool(key), '원문 map 키 오류')
            target, data = _reference(ref, bundle_path=path, limit=local.MAX_PAYLOAD_BYTES, snapshots=snapshots)
            local._require(target not in (model_path, artifact_path), '원문을 모델/교정 파일로 대체할 수 없습니다')
            size += len(data)
            local._require(size <= local.MAX_PAYLOAD_BYTES, '원문 bytes 총량 제한 초과')
            if field == 'evidence_files':
                local._require(key == ref['sha256'], 'evidence map 키와 raw SHA 불일치')
            payloads[key] = data
        maps[field] = payloads
    return {'bundle': value, 'snapshots': snapshots, 'model_path': model_path,
        'artifact_payload': local._strict_json(artifact_raw),
        'source_payloads': maps['source_files'], 'evidence_payloads': maps['evidence_files']}


def _replay_rows(scorer, expected_rows, observations, *, training_manifest=None,
                 source_payloads=None, evidence_payloads=None):
    successful = []
    for expected, observed in zip(expected_rows, observations):
        receipt = observed.get('receipt')
        local._require(type(receipt) is dict, '관측 receipt object가 필요합니다')
        if receipt.get('status') == 'SCORED_LEARNED':
            example = {key: expected.get(key) for key in
                ('example_id', 'frozen_view', 'candidate_text_bindings', 'capture_sha256')}
            successful.append({'example': example, 'raw_receipt': receipt})
    calibration_io._replay_rows(scorer, successful, training_manifest=training_manifest,
        source_payloads=source_payloads, evidence_payloads=evidence_payloads,
        required_split='FROZEN_HOLDOUT')
    return len(successful)


def _validate_report(report):
    from src.llm_batch.measurement import candidate_reranker_nil_evaluation as evaluation
    local._require(type(report) is dict and report.get('schema_version') == evaluation.SCHEMA,
        '평가 report 스키마 불일치')
    local._require(report.get('report_sha256') == local._sha(local._json_bytes({k: v for k, v in report.items()
        if k != 'report_sha256'})), '평가 report SHA 불일치')
    local._require(all(report.get(key) is False for key in
        ('publication_authority', 'public_apply', 'central_db_write', 'quality_acceptance_claimed'))
        and report.get('formal_kpi_status') == 'NOT_ESTIMABLE', '평가 report 권한/품질 주장 불일치')
    local._require(len(local._json_bytes(report)) <= MAX_REPORT_BYTES, '평가 report 크기 제한 초과')


def evaluate_bundle(*, bundle_path, expected_sha256, output_dir):
    output = local._local_path(output_dir)
    local._require(not os.path.lexists(output), '평가 출력 폴더는 새 경로여야 합니다')
    from src.llm_batch.runtime.execution_config import apply_profile_resources, observe_process_resources
    resources_start = apply_profile_resources('low-load-validation', os.environ)
    local._resources(resources_start)
    loaded = read_evaluation_bundle(bundle_path, expected_sha256=expected_sha256)
    value = loaded['bundle']
    manifest, policy = calibration_io._typed_context(value)
    from src.llm_batch.grounding.candidate_set_calibration_shadow import calibration_artifact_from_dict
    artifact = calibration_artifact_from_dict(loaded['artifact_payload'])
    artifact.validate_against(manifest, policy)
    from src.llm_batch.grounding.candidate_reranker_shadow import load_scorer
    scorer = load_scorer(loaded['model_path'], expected_sha256=value['model_manifest']['sha256'])
    summary = scorer.summary()
    local._require(local._sha(local._json_bytes(summary)) == value['expected_scorer_summary_sha256'], 'scorer summary SHA 불일치')
    local._require(summary.get('status') == 'AVAILABLE_LEARNED'
        and summary.get('backend') == 'NIL_AUGMENTED_LINEAR_V1' and summary.get('nil_head_available') is True,
        '평가에는 고정된 NIL 학습 모델이 필요합니다')
    replay_count = _replay_rows(scorer, value['expected_rows'], value['observations'],
        training_manifest=value['training_manifest'], source_payloads=loaded['source_payloads'],
        evidence_payloads=loaded['evidence_payloads'])
    from src.llm_batch.measurement.candidate_reranker_nil_evaluation import evaluate_frozen_nil_scores
    report = evaluate_frozen_nil_scores(
        training_manifest=value['training_manifest'], expected_training_manifest_sha256=value['expected_training_manifest_sha256'],
        calibration_manifest=manifest, expected_calibration_manifest_sha256=value['expected_calibration_manifest_sha256'],
        scorer_summary=summary, expected_scorer_summary_sha256=value['expected_scorer_summary_sha256'],
        source_payloads=loaded['source_payloads'], evidence_payloads=loaded['evidence_payloads'],
        expected_rows=value['expected_rows'], observations=value['observations'],
        frozen_rows=calibration_io._typed_rows(value['frozen_rows']), policy=policy, calibration_artifact=artifact)
    _validate_report(report)
    local._check_inputs(loaded['snapshots'])
    output.mkdir(parents=True, exist_ok=False)
    pending = output / '.pending_report.json'
    report_ref = local._write(pending, report)
    stored = calibration_io._read_saved(report_ref)
    _validate_report(stored)
    local._require(local._json_bytes(stored) == local._json_bytes(report), '저장 평가 보고서 전체 재판독 불일치')
    calibration_io._rename_noreplace(pending, output / 'evaluation_report.json')
    report_ref = {**report_ref, 'path': str(output / 'evaluation_report.json')}
    local._check_inputs(loaded['snapshots'])
    calibration_io._read_saved(report_ref)
    resources_end = observe_process_resources(os.environ)
    local._resources(resources_end)
    local._require(all(resources_start[key] == resources_end[key] for key in
        ('pid', 'priority_class', 'affinity_mask', 'logical_cpu_count', 'numeric_threads')), '평가 중 자원 설정 변경')
    receipt = {'schema_version': 'candidate_reranker_evaluation_workflow_v1', 'status': 'EVALUATED_AND_READBACK_VERIFIED',
        'bundle_sha256': expected_sha256, 'data_kind': summary['data_kind'], 'backend': summary['backend'],
        'inputs': [{'path': path, 'sha256': local._sha(raw), 'bytes': len(raw)} for path, raw in loaded['snapshots'].items()],
        'evaluation_report': report_ref, 'report_sha256': report['report_sha256'], 'report_status': report['status'],
        'scorer_summary': summary, 'resources_start': resources_start, 'resources_end': resources_end,
        'local_score_replay_count': replay_count, 'expected_rows': len(value['expected_rows']),
        'model_training_executed': False, 'calibration_fit_executed': False,
        'actual_quality_evaluated': False, 'actual_performance_evaluated': False,
        'formal_kpi_status': 'NOT_ESTIMABLE', 'publication_authority': False, 'public_apply': False, 'central_db_write': False,
        'limitations': ['SAVED_OBSERVATION_ACCOUNTING_NOT_ACTUAL_QUALITY_ACCEPTANCE',
            'SOURCE_BINDING_NOT_INDEPENDENT_PROVENANCE_VERIFICATION'],
        'receipt_hash_excludes': ['receipt_sha256', 'workflow_receipt']}
    receipt['receipt_sha256'] = local._sha(local._json_bytes(receipt))
    reference = calibration_io._publish_workflow_receipt(output, receipt)
    return {**receipt, 'workflow_receipt': reference}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument('--bundle', required=True)
    parser.add_argument('--bundle-sha256', required=True)
    parser.add_argument('--output-dir', required=True)
    args = parser.parse_args(argv)
    try:
        result = evaluate_bundle(bundle_path=args.bundle, expected_sha256=args.bundle_sha256, output_dir=args.output_dir)
    except (OSError, ValueError, TypeError) as exc:
        print('로컬 FROZEN 평가 실패: ' + str(exc), file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
