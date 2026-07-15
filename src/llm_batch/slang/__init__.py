"""Slang DB 조회와 승인된 변경의 governance/transaction 경계.

읽기와 mutation sidecar를 분리한다. owner 승인과 exact hash 결속이 없는
변경은 중앙 DB에 적용하지 않는다.
"""

__all__: list[str] = []
