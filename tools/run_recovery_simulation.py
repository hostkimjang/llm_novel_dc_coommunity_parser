"""고정 합성 계획만 별도 실행하고 독립 보고서를 기존 로컬 대시보드에 연결한다."""
from __future__ import annotations

import argparse
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import re
import sys
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.llm_batch.ledger.private_file import private_file_permissions_ok
from src.llm_batch.ledger.recovery_execution_journal import RecoveryExecutionJournal
from src.llm_batch.measurement.recovery_execution_contract import (
    bind_recovery_execution_plan, execution_journal_arguments,
)
from src.llm_batch.measurement.recovery_execution_readback import (
    build_recovery_execution_readback, read_strict_json, render_korean_report,
    validate_recovery_execution_readback,
)
from src.llm_batch.monitor.recovery_view import publish_recovery_view
from src.llm_batch.runtime.bounded_recovery import execute_recovery_simulation
from src.llm_batch.runtime.execution_config import (
    NUMERIC_THREAD_KEYS, apply_profile_resources, observe_process_resources,
)
from tools.run_recovery_execution_readback import _file, write_readback_reports


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        raise ValueError('복구 대시보드의 HTTP redirect는 허용하지 않습니다')


def _dashboard_url(value: str | None) -> str:
    value = value if value is not None else os.environ.get('DASHBOARD_URL', '').strip()
    if not value:
        value = 'http://127.0.0.1:' + os.environ.get('DASHBOARD_PORT', '8080')
    parsed = urlsplit(value)
    try:
        address = ipaddress.ip_address(parsed.hostname or '')
        valid = (parsed.scheme == 'http' and address.is_loopback
                 and parsed.username is None and parsed.password is None
                 and parsed.path in ('', '/') and not parsed.query and not parsed.fragment
                 and parsed.port is not None and 1 <= parsed.port <= 65535)
    except ValueError as exc:
        raise ValueError('기존 loopback HTTP 대시보드 주소가 필요합니다') from exc
    if not valid:
        raise ValueError('기존 loopback HTTP 대시보드 주소가 필요합니다')
    return value.rstrip('/')


def _dashboard_health(url: str) -> dict:
    # 네트워크 사용은 명시한 loopback 서버의 health 두 번뿐이다. 환경 proxy를 쓰지 않는다.
    url = _dashboard_url(url)
    opener = build_opener(ProxyHandler({}), _NoRedirect())
    request = Request(url + '/api/health', headers={'Accept': 'application/json'})
    with opener.open(request, timeout=2) as response:
        if response.status != 200 or response.geturl() != request.full_url:
            raise ValueError('대시보드 health 응답 경로 또는 상태 불일치')
        raw = response.read(8193)
    value = read_strict_json(raw, maximum_bytes=8192)
    if (type(value) is not dict or value.get('ok') is not True
            or value.get('service') != 'expert-pipeline-monitor'
            or value.get('standalone') is not True
            or type(value.get('pid')) is not int or value['pid'] <= 0):
        raise ValueError('기존 standalone 대시보드의 정상 응답이 필요합니다')
    return {'url': url, 'pid': value['pid'], 'service': value['service'], 'standalone': True}


def _identifier(value: str) -> None:
    if (type(value) is not str or not 0 < len(value) <= 128
            or value.strip() != value or any(ord(c) < 32 for c in value)):
        raise ValueError('명시적인 복구 attempt/session ID가 필요합니다')
    value.encode('utf-8')


def _ref(path: Path, raw: bytes) -> dict:
    return {'path': str(path), 'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw)}


def _check_resources(value: dict) -> None:
    if (value.get('pid') != os.getpid() or value.get('logical_cpu_count') != 1
            or set(value.get('numeric_threads', {})) != set(NUMERIC_THREAD_KEYS)
            or any(item != '1' for item in value['numeric_threads'].values())
            or (os.name == 'nt' and (value.get('priority_class') != 16384 or value.get('affinity_mask') != 2))):
        raise ValueError('합성 복구의 실제 저부하 자원 관측이 요청과 다릅니다')


def run_recovery_simulation(*, plan_path: str | Path, hmac_key_path: str | Path,
                            attempt_id: str, session_id: str, root: str | Path,
                            dashboard_url: str | None = None, clock=None, cancellation=None) -> dict:
    """실제 provider 없이 기존 R6 합성 executor만 호출한다. 원본/key는 만들거나 쓰지 않는다."""
    if (os.environ.get('PIPELINE_MEASUREMENT_EXECUTION_MODE', 'NORMAL').strip().upper() != 'NORMAL'
            or os.environ.get('EXPERT_EXECUTION_PROFILE', '').strip() == 'paired-measurement'
            or any(os.environ.get(key, '').strip() for key in (
                'PIPELINE_MEASUREMENT_RUN_SPEC_SHA256', 'PIPELINE_MEASUREMENT_PAIR_ID',
                'PIPELINE_MEASUREMENT_ARM', 'PIPELINE_MEASUREMENT_RUN_SPEC_PATH',
                'PIPELINE_MEASUREMENT_RUN_SPEC_FILE_SHA256', 'PIPELINE_PAIRED_EXECUTION_POLICY_PATH',
                'PIPELINE_PAIRED_EXECUTION_POLICY_SHA256'))):
        raise ValueError('합성 복구는 fresh/paired 계측 실행과 혼합할 수 없습니다')
    _identifier(attempt_id)
    _identifier(session_id)
    if attempt_id == session_id:
        raise ValueError('복구 attempt와 session ID는 달라야 합니다')
    source, key_path = _file(plan_path, 65536), _file(hmac_key_path, 4096)
    if source == key_path or private_file_permissions_ok(key_path) is not True:
        raise ValueError('기존 비공개 HMAC key 파일이 필요합니다')
    source_raw, key_raw = source.read_bytes(), key_path.read_bytes()
    try:
        key_hex = key_raw.decode('ascii').strip().lower()
    except UnicodeError as exc:
        raise ValueError('기존 감사 key는 ASCII hex64 형식이어야 합니다') from exc
    if not re.fullmatch(r'[0-9a-f]{64}', key_hex):
        raise ValueError('기존 감사 key는 ASCII hex64 형식이어야 합니다')
    bound = bind_recovery_execution_plan(read_strict_json(source_raw), hmac_key=bytes.fromhex(key_hex))
    if attempt_id == bound.plan['base']['base_attempt_run_id']:
        raise ValueError('원래 판정 attempt ID를 복구 attempt로 재사용할 수 없습니다')
    root = Path(root).resolve()
    # publisher와 동일한 root/path 검산을 실행 전에 한다. source와 key는 출력 폴더 밖에 둔다.
    from src.llm_batch.monitor.recovery_view import _safe, _view_path
    result_path = _safe(Path(bound.plan['artifacts']['result']['path']), root)
    _safe(Path(bound.plan['artifacts']['manifest']['path']), root)
    _safe(bound.output_dir, root)
    if source.is_relative_to(bound.output_dir) or key_path.is_relative_to(bound.output_dir):
        raise ValueError('계획과 기존 key는 복구 출력 폴더 밖에 있어야 합니다')
    basename = hashlib.sha256(attempt_id.encode('utf-8')).hexdigest()
    paths = [bound.assert_output_path(bound.output_dir / 'reports' / (basename + suffix))
             for suffix in ('.json', '.md')]
    present = [os.path.lexists(path) for path in paths]
    if any(present) and not all(present):
        raise ValueError('부분 저장된 보고서를 덮어쓰지 않습니다. 기존 자료를 먼저 판독하세요')
    view_path = _safe(_view_path(result_path), root)
    # 이미 연결한 결과는 같은 계획·보고서의 완료 replay만 허용한다.
    if os.path.lexists(view_path):
        if not all(present):
            raise ValueError('이미 연결한 원본 결과에 새 복구 attempt를 덮어 연결할 수 없습니다')
        publish_recovery_view(bound, paths[0], root=root)
    if all(present):
        existing = build_recovery_execution_readback(bound)
        _verify_reports(bound, paths, existing)
        attempt = next((row for row in existing['attempts']
                        if row['recovery_attempt_id'] == attempt_id), None)
        if attempt is None or not attempt.get('finalization_recorded'):
            raise ValueError('기존 보고서가 완료된 같은 attempt를 가리키지 않습니다')
        if attempt.get('recovery_session_id') != session_id:
            raise ValueError('기존 복구 attempt의 session과 다릅니다')
    dashboard_before = _dashboard_health(_dashboard_url(dashboard_url))
    resources_start = apply_profile_resources('low-load-validation', os.environ)
    _check_resources(resources_start)
    journal = RecoveryExecutionJournal(bound.journal_path, **execution_journal_arguments(bound.plan))
    execution = execute_recovery_simulation(bound, fixture=bound.fixture, journal=journal,
        attempt_id=attempt_id, session_id=session_id, clock=clock, cancellation=cancellation)
    report = build_recovery_execution_readback(bound)
    validate_recovery_execution_readback(report, bound_plan=bound)
    if all(present):
        outputs = _verify_reports(bound, paths, report)
    else:
        saved = write_readback_reports(plan_path=source, hmac_key_path=key_path,
                                       output_json=paths[0], output_md=paths[1])
        outputs = _verify_reports(bound, paths, report)
        if outputs != saved['outputs']:
            raise ValueError('독립 보고서 저장 지문 불일치')
    companion = publish_recovery_view(bound, paths[0], root=root)
    dashboard_after = _dashboard_health(dashboard_before['url'])
    if dashboard_after != dashboard_before:
        raise ValueError('복구 보고서 연결 중 대시보드가 바뀌었습니다. 저장 자료는 보존합니다')
    bound.verify_protected_sources()
    if source.read_bytes() != source_raw or key_path.read_bytes() != key_raw:
        raise ValueError('복구 실행 중 계획 또는 기존 key가 변경되었습니다')
    resources_end = observe_process_resources(os.environ)
    _check_resources(resources_end)
    if any(resources_start[key] != resources_end[key] for key in
           ('pid', 'priority_class', 'affinity_mask', 'logical_cpu_count', 'numeric_threads')):
        raise ValueError('합성 복구 실행 중 프로세스 자원 설정이 바뀌었습니다')
    receipt = {'schema_version': 'recovery_simulation_workflow_v1',
            'execution_mode': 'LOCAL_SIMULATION_ONLY', 'data_kind': 'SYNTHETIC_CONTRACT_ONLY',
            'execution_status': execution['status'], 'verification_status': report['verification_status'],
            'actual_external_call_count': 0, 'public_apply': False, 'publication_authority': False,
            'central_db_write': False, 'formal_kpi_status': 'NOT_ESTIMABLE',
            'recovery_attempt_id': attempt_id, 'recovery_session_id': session_id,
            'replayed': execution['replayed'], 'dispatches_this_invocation': execution['dispatches_this_invocation'],
            'reports': outputs, 'dashboard_reference': companion,
            'execution_profile': 'low-load-validation',
            'resources_start': resources_start, 'resources_end': resources_end,
            'resource_observation_scope': 'THROUGH_REPORT_EXPORT_AND_DASHBOARD_HEALTH',
            'receipt_hash_excludes': ['receipt_sha256', 'workflow_receipt'],
            'dashboard': {'status': 'CONNECTED_STANDALONE', 'before': dashboard_before,
                          'after': dashboard_after, 'visibility_verified': False}}
    receipt['receipt_sha256'] = hashlib.sha256(json.dumps(receipt, ensure_ascii=False, sort_keys=True,
        separators=(',', ':'), allow_nan=False).encode('utf-8')).hexdigest()
    # invocation 자원 관측은 매번 달라질 수 있다. companion이 참조하는 고정 readback와 분리한다.
    receipt_path = bound.assert_output_path(bound.output_dir / 'reports' /
        (basename + '_workflow_' + uuid4().hex + '.json'))
    raw = (json.dumps(receipt, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode('utf-8')
    with receipt_path.open('xb') as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    if _file(receipt_path, 2 * 1024 * 1024).read_bytes() != raw:
        raise OSError('실행 자원 수령증 저장 검산 실패')
    return {**receipt, 'workflow_receipt': _ref(receipt_path, raw)}


def _verify_reports(bound, paths: list[Path], report: dict) -> list[dict]:
    payloads = [(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode('utf-8'),
                render_korean_report(report).encode('utf-8')]
    for path, raw in zip(paths, payloads):
        bound.assert_output_path(path)
        if _file(path, 2 * 1024 * 1024).read_bytes() != raw:
            raise ValueError('기존 보고서와 현재 독립 판독 결과가 다릅니다')
    return [_ref(path, raw) for path, raw in zip(paths, payloads)]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument('--plan', required=True)
    parser.add_argument('--hmac-key-file', required=True)
    parser.add_argument('--attempt-id', required=True)
    parser.add_argument('--session-id', required=True)
    args = parser.parse_args(argv)
    try:
        result = run_recovery_simulation(plan_path=args.plan, hmac_key_path=args.hmac_key_file,
            attempt_id=args.attempt_id, session_id=args.session_id, root=ROOT / 'out')
    except (OSError, ValueError) as exc:
        print('합성 복구 연결 실패: ' + str(exc), file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
