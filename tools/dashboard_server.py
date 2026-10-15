"""
Standalone 대시보드 서버 — expert_main과 독립된 프로세스로 실행

사용법:
    python tools/dashboard_server.py                    # 127.0.0.1:8080
    python tools/dashboard_server.py --port 8081
    python tools/dashboard_server.py --host 0.0.0.0 --port 8080

동작:
- 과거 런 조회(/api/runs → out/*.json, logs/*.log)는 즉시 동작한다.
- expert_main이 시작되면 /api/health 핸드셰이크로 이 서버를 감지하고,
  자체 대시보드를 띄우지 않은 채 이벤트를 POST /api/ingest 로 전달한다.
  → expert_main이 끝나도 이 서버는 계속 살아 있고, 다음 런이 시작되면
    batch_start 이벤트가 상태를 리셋하며 이어서 표시한다.
- 포트가 이미 사용 중이면 fail-fast 한다 (내장 대시보드와 달리 포트 호핑을
  하지 않는다 — expert_main이 DASHBOARD_PORT 기준 고정 URL로 감지하므로).

환경 변수:
- DASHBOARD_PORT: 기본 포트 (기본 8080; expert_main 감지 URL과 맞출 것)
- DASHBOARD_INGEST_TOKEN: 설정 시 /api/ingest 에 X-Ingest-Token 헤더 요구
  (expert_main 쪽도 같은 env를 읽어 자동 첨부)
"""

from __future__ import annotations

import argparse
import os
import socket
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT))
sys.path.insert(0, str(_REPO_ROOT / "src"))

# server.py import 전에 설정해야 /api/health 가 standalone=True 로 응답한다.
os.environ["DASHBOARD_STANDALONE"] = "1"


def _port_available(host: str, port: int) -> bool:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((host, port))
        return True
    except OSError:
        return False
    finally:
        s.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Expert Pipeline standalone dashboard")
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="바인드 주소 (기본 127.0.0.1; LAN 노출 시 0.0.0.0 + DASHBOARD_INGEST_TOKEN 권장)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("DASHBOARD_PORT", "8080")),
        help="포트 (기본: DASHBOARD_PORT env 또는 8080)",
    )
    args = parser.parse_args()

    if not _port_available(args.host, args.port):
        print(
            f"[dashboard_server] ❌ 포트 사용 중: {args.host}:{args.port}\n"
            f"  다른 포트로 띄우려면: python tools/dashboard_server.py --port <PORT>\n"
            f"  expert_main이 감지하게 하려면 같은 값으로 DASHBOARD_PORT=<PORT> "
            f"(또는 DASHBOARD_URL=http://127.0.0.1:<PORT>)를 expert_main 쪽에 설정하세요.",
            file=sys.stderr,
            flush=True,
        )
        return 1

    if args.host not in {"127.0.0.1", "localhost"} and not os.environ.get("DASHBOARD_INGEST_TOKEN", "").strip():
        print(
            "[dashboard_server] ⚠️ 비-루프백 바인드인데 DASHBOARD_INGEST_TOKEN이 없습니다 — "
            "/api/ingest 가 네트워크에 노출됩니다. 토큰 설정을 권장합니다.",
            file=sys.stderr,
            flush=True,
        )

    from llm_batch.monitor.server import app  # noqa: E402 (sys.path 설정 후 import)
    import uvicorn

    print(
        f"[dashboard_server] 📊 Standalone dashboard: http://127.0.0.1:{args.port} "
        f"(bind={args.host}, ingest_token={'on' if os.environ.get('DASHBOARD_INGEST_TOKEN') else 'off'})",
        file=sys.stderr,
        flush=True,
    )
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning", access_log=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
