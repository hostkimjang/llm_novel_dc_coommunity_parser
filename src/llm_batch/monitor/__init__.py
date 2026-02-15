"""
Monitor 패키지 — 웹 대시보드 + 이벤트 버스

사용법:
    from llm_batch.monitor.event_bus import monitor
    from llm_batch.monitor.server import start_dashboard

    # 대시보드 서버 기동 (데몬 스레드)
    start_dashboard(port=8080)

    # 이벤트 발행
    monitor.emit("batch_start", {"total": 100, "input_file": "sample.jsonl"})
"""

from .event_bus import monitor
from .server import start_dashboard

__all__ = ["monitor", "start_dashboard"]
