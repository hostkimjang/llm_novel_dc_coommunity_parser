"""기존 합성 복구 원장을 읽어 새 보고서만 저장한다. 실행 기능 없음."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from pathlib import Path
import stat
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.llm_batch.ledger.private_file import private_file_permissions_ok
from src.llm_batch.measurement.recovery_execution_contract import bind_recovery_execution_plan
from src.llm_batch.measurement.recovery_execution_readback import (
    build_recovery_execution_readback, read_strict_json, render_korean_report,
    validate_recovery_execution_readback,
)


def _file(path: str | Path, maximum: int) -> Path:
    path = Path(path).absolute()
    for component in (path, *path.parents):
        if component.is_symlink() or (hasattr(component, 'is_junction') and component.is_junction()):
            raise ValueError('연결 경로는 판독 입력으로 허용하지 않습니다')
    info = path.stat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > maximum:
        raise ValueError('판독 입력은 크기 제한 안의 단일 일반 파일이어야 합니다')
    return path.resolve()


def write_readback_reports(*, plan_path: str | Path, hmac_key_path: str | Path,
                           output_json: str | Path, output_md: str | Path,
                           journal_path: str | Path | None = None) -> dict:
    """원래 key를 읽기만 하며 두 새 보고서를 배타 생성한다. 부분 실패는 보존한다."""
    source = _file(plan_path, 65536)
    key_path = _file(hmac_key_path, 4096)
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
    report = build_recovery_execution_readback(bound, journal_path=journal_path)
    destinations = [bound.assert_output_path(output_json), bound.assert_output_path(output_md)]
    report_root = bound.output_dir / 'reports'
    if destinations[0] == destinations[1]:
        raise ValueError('JSON과 Markdown 출력 경로가 같을 수 없습니다')
    for path in destinations:
        if (not path.is_relative_to(report_root) or path == report_root
                or path in (source, key_path, bound.journal_path) or os.path.lexists(path)):
            raise ValueError('보고서는 지정 output_dir/reports 안의 새 경로에만 저장합니다')
    payloads = [(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode('utf-8'),
                render_korean_report(report).encode('utf-8')]
    for path, raw in zip(destinations, payloads):
        path.parent.mkdir(parents=True, exist_ok=True)
        bound.assert_output_path(path)
        with path.open('xb') as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        if path.read_bytes() != raw:
            raise OSError('보고서 저장 후 재판독 불일치')
    validate_recovery_execution_readback(report, bound_plan=bound)
    if source.read_bytes() != source_raw or key_path.read_bytes() != key_raw:
        raise ValueError('판독 중 계획 또는 기존 key 파일이 변경되었습니다')
    return {'status': report['verification_status'], 'execution_status': report['execution_status'],
            'actual_external_calls': 0,
            'outputs': [{'path': str(path), 'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw)}
                        for path, raw in zip(destinations, payloads)]}


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', required=True, help='저장된 고정 계획 JSON')
    parser.add_argument('--hmac-key-file', required=True, help='기존 감사 HMAC key 읽기 전용 경로(ASCII hex64)')
    parser.add_argument('--journal', help='계획에 고정된 원장 경로 확인값')
    parser.add_argument('--output-json', required=True, help='output_dir/reports 아래 새 JSON 경로')
    parser.add_argument('--output-md', required=True, help='output_dir/reports 아래 새 Markdown 경로')
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    try:
        result = write_readback_reports(plan_path=args.plan, hmac_key_path=args.hmac_key_file,
            output_json=args.output_json, output_md=args.output_md, journal_path=args.journal)
    except (OSError, ValueError):
        print('복구 기록 판독 실패: 입력 결속·권한·새 출력 경로를 확인하세요. 기존 자료는 변경하지 않습니다.', file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
