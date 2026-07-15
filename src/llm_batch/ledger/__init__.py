"""결정 호출과 게시 판정의 불변 원장·재생·readback 구현.

원장 계층은 provider 응답 본문 대신 digest와 typed receipt를 보존한다.
기능 실패가 기존 공개 결과를 바꾸지 않도록 shadow 경계를 유지한다.
"""

__all__: list[str] = []
