"""``expert_main.py``의 CLI 옵션 선언.

옵션 이름·순서·choices·default·help 문자열을 한곳에 둔다. 이 모듈은 parser만 만들고
``sys.argv``나 환경 변수를 읽지 않으며 무거운 모듈을 import하지 않는다. 인자 해석 규칙(알 수
없는 인자 허용, ``-pN``, ``--input`` 우선, 복구 옵션 검사)은 ``expert_main._parse_args``에 있다.

실행 동작을 정하는 선언이므로 ``runtime.execution_config.source_snapshot``의 선택 실행 소스에 포함된다.
"""
from __future__ import annotations

import argparse


def build_arg_parser(*, add_help: bool) -> argparse.ArgumentParser:
    """``expert_main`` CLI 옵션을 선언한 parser를 만든다. 인자 해석은 하지 않는다."""
    parser = argparse.ArgumentParser(
        description="Agentic Pipeline (유기적 전문가 시스템)",
        add_help=add_help,  # 기존 sys.argv[1] 호환성 유지
    )
    parser.add_argument("input", nargs="?", default=None, help="입력 JSONL 파일 경로")
    parser.add_argument("--input", dest="input_flag", default=None, help="입력 JSONL 파일 경로 (--input 형식)")
    parser.add_argument("--output", "-o", default=None, help="출력 JSON 파일 경로")
    parser.add_argument("--recovery-simulation-plan", default=None, help="일반 분석과 따로 실행하는 고정 합성 복구 계획 JSON")
    parser.add_argument("--recovery-provider-plan", default=None, help="명시한 provider로 근거를 수집하는 계획 JSON. 일반 분석과 따로 실행")
    parser.add_argument("--recovery-provider-plan-sha256", default=None, help="provider 계획 파일의 raw SHA-256(미리 고정해 둔 기대값)")
    parser.add_argument("--recovery-hmac-key-file", default=None, help="기존 감사 key 파일 경로(읽기 전용, ASCII hex64)")
    parser.add_argument("--recovery-attempt-id", default=None, help="명시적인 새 복구 attempt ID")
    parser.add_argument("--recovery-session-id", default=None, help="명시적인 복구 session ID")
    parser.add_argument("--native-recovery", choices=["OFF", "ON"], default=None,
                        help="일반 분석이 끝난 뒤 같은 호출의 문맥으로 native 복구를 따로 실행(기본 OFF)")
    parser.add_argument("--native-recovery-policy", default=None, help="자동 native 복구에 쓸 예산·endpoint·wire 정책 JSON(명시 지정)")
    parser.add_argument("--native-recovery-policy-sha256", default=None, help="자동 native 정책 파일의 raw SHA-256(미리 고정해 둔 기대값)")
    parser.add_argument("--parallel", "-p", type=int, default=1, help="최대 병렬 워커 수 (기본: 1, 실제 워커 수는 입력 게시글 수를 넘지 않음)")
    parser.add_argument("--no-dashboard", action="store_true", help="대시보드 비활성화")
    parser.add_argument("--execution-profile", choices=["general", "low-load-validation", "paired-measurement"],
                        default=None, help="실행 설정 묶음. 개별 CLI·환경 설정이 프로필 기본값보다 우선")
    parser.add_argument("--decision-call-ledger", choices=["OFF", "SHADOW", "REQUIRED"], default=None,
                        help="호출 원장 모드. REQUIRED는 기존 측정 연결 검증을 그대로 수행")
    parser.add_argument("--context-diagnostics", choices=["on", "off"], default=None,
                        help="원문 문맥과 발화 구조의 크기 제한 진단을 저장")
    parser.add_argument("--candidate-retrieval", choices=["OFF", "SHADOW"], default="OFF",
                        help="고정 작품 corpus에서 찾은 후보를 참고용으로 기록. 기본 OFF, 기존 판정에는 반영하지 않음")
    parser.add_argument("--candidate-corpus", default=None, help="명시적으로 고정한 작품 corpus JSON 경로")
    parser.add_argument("--candidate-corpus-sha256", default=None, help="corpus 파일의 SHA-256(미리 고정해 둔 기대값)")
    parser.add_argument("--candidate-retrieval-top-k", type=int, default=20, help="기록할 후보(점수가 양수인 후보) 수 상한 (1~100)")
    parser.add_argument("--candidate-reranker", choices=["OFF", "SHADOW"], default=None,
                        help="R2 고정 후보를 재정렬한 결과를 참고용으로 기록. 기본 OFF, 공개 판정에는 반영하지 않음")
    parser.add_argument("--reranker-manifest", default=None, help="명시적으로 고정한 scorer manifest 경로")
    parser.add_argument("--reranker-manifest-sha256", default=None, help="scorer manifest의 SHA-256(미리 고정해 둔 기대값)")
    parser.add_argument("--candidate-semantics", choices=["OFF", "SHADOW"], default=None,
                        help="후보를 고르기 전에 고정 후보의 의미 역할과 검증된 별칭을 참고용으로 기록. 기본 OFF, 점수·교정 입력에는 쓰지 않음")
    parser.add_argument("--semantic-alias-bundle", default=None, help="고정 R3·corpus 원문을 포함한 별칭 근거 bundle")
    parser.add_argument("--semantic-alias-bundle-sha256", default=None, help="별칭 근거 bundle의 SHA-256(미리 고정해 둔 기대값)")
    parser.add_argument("--candidate-calibration", choices=["OFF", "SHADOW"], default=None,
                        help="명시적으로 연결된 FROZEN 행의 교정 결과를 참고용으로 기록. 기본 OFF, 공개 판정에는 반영하지 않음")
    parser.add_argument("--calibration-bundle", default=None, help="고정 source/ID/graph와 CAL artifact bundle 경로")
    parser.add_argument("--calibration-bundle-sha256", default=None, help="calibration bundle의 SHA-256(미리 고정해 둔 기대값)")
    parser.add_argument("--candidate-inference", choices=["OFF", "SHADOW"], default=None,
                        help="일반 입력의 R2 후보·NIL에 고정 교정을 적용한 결과를 참고용으로 기록. 기본 OFF, 공개 판정에는 반영하지 않음")
    parser.add_argument("--inference-bundle", default=None, help="고정 모델/CAL과 현재 corpus 원문·출처를 연결한 bundle")
    parser.add_argument("--inference-bundle-sha256", default=None, help="inference bundle의 SHA-256(미리 고정해 둔 기대값)")
    parser.add_argument("--community-knowledge", choices=["OFF", "READ_ONLY"], default=None,
                        help="커뮤니티 후보 지식 문맥 모드. 기본 OFF, READ_ONLY에서는 Slang DB와 배치 학습을 끔")
    parser.add_argument("--community-snapshot", default=None, help="고정 커뮤니티 snapshot manifest 경로")
    parser.add_argument("--community-snapshot-sha256", default=None, help="snapshot manifest의 SHA-256(미리 고정해 둔 기대값)")
    parser.add_argument(
        "--server-type", "-s",
        choices=["llama", "vllm"],
        default=None,
        help="LLM 서빙 엔진 선택: vllm 또는 llama (llama-server). 지정하지 않으면 환경 변수 LLM_SERVER_TYPE을 쓰고, 그것도 없으면 vllm(기본)",
    )
    parser.add_argument("--llm-endpoint", default=None, help="LLM 서버 엔드포인트 URL (예: http://a100:8000)")
    parser.add_argument("--llm-model", default=None, help="사용할 모델명 (예: Qwen/Qwen3-32B)")
    parser.add_argument("--vlm", choices=["on", "off"], default=None, help="멀티모달/VLM 보강 사용 여부")
    parser.add_argument("--ocr", choices=["on", "off"], default=None, help="VLM 경로에서 OCR 텍스트 추출 여부")
    parser.add_argument("--vlm-fetch-timeout", type=float, default=None, help="이미지 fetch timeout (초)")
    parser.add_argument("--vlm-max-image-bytes", type=int, default=None, help="개별 이미지 최대 바이트")
    parser.add_argument("--vlm-max-total-bytes", type=int, default=None, help="게시글당 이미지 총 바이트 상한")
    parser.add_argument("--vlm-chunk-max-images", type=int, default=None, help="멀티모달 청크당 최대 이미지 수")
    parser.add_argument("--vlm-chunk-max-bytes", type=int, default=None, help="멀티모달 청크당 최대 바이트")
    parser.add_argument(
        "--require-vlm-ocr-for-images",
        action="store_true",
        help="이미지가 있는 게시글이 있는데 VLM/OCR이 완전히 켜져 있지 않으면 run을 시작 전에 실패 처리",
    )
    parser.add_argument(
        "--llm-suspend-on-anomaly",
        choices=["on", "off"],
        default=None,
        help="LLM 서버의 무응답·이상 응답이 쌓이면 일시중지하고 사용자 확인 후 재개",
    )
    parser.add_argument(
        "--llm-suspend-threshold",
        type=int,
        default=None,
        help="일시중지할 LLM 서버 이상 응답 누적 횟수 (0=비활성)",
    )
    parser.add_argument(
        "--llm-stream-first-token-timeout",
        type=float,
        default=None,
        help="스트리밍 첫 토큰 대기 제한(초). 0 이하이면 비활성",
    )
    parser.add_argument(
        "--llm-stream-idle-timeout",
        type=float,
        default=None,
        help="스트리밍 청크 간 idle 대기 제한(초). 0 이하이면 비활성",
    )
    parser.add_argument("--slang-db", choices=["on", "off"], default=None, help="검토용 중앙 slang DB 저장 사용 여부")
    parser.add_argument("--slang-db-path", default=None, help="중앙 slang DB JSON 경로")
    parser.add_argument("--slang-db-flush-posts", type=int, default=None, help="slang DB flush 간격(게시글 수)")
    parser.add_argument("--slang-db-flush-seconds", type=int, default=None, help="slang DB flush 시간 간격(초)")
    parser.add_argument(
        "--auto-up-shards",
        action="store_true",
        help="로컬 MCP/WARP shard가 부족할 때 docker compose up 자동 실행을 명시적으로 허용",
    )
    parser.add_argument("--no-auto-up-shards", action="store_true", help="로컬 MCP/WARP shard 자동 기동 비활성화")
    parser.add_argument(
        "--auto-recreate-shards",
        action="store_true",
        help="WARP/search 헬스 실패 시 docker compose force-recreate 자동 실행을 명시적으로 허용",
    )
    parser.add_argument(
        "--no-auto-recreate-shards",
        action="store_true",
        help="WARP/search 헬스 실패 시 docker compose force-recreate 자동 실행 비활성화",
    )
    parser.add_argument(
        "--reuse-shards-only",
        action="store_true",
        help="기존 MCP/WARP shard만 재사용하고 docker compose up/recreate 자동 실행을 모두 생략",
    )
    parser.add_argument(
        "--allow-goal-shard-lifecycle",
        action="store_true",
        help="Allow Docker shard up/recreate in small goal/test runs. Requires --auto-up-shards or --auto-recreate-shards.",
    )
    return parser
