"""단계 예산, limiter, cache, singleflight를 묶는 runtime 제어 계층.

기본값은 OFF이며 명시적으로 주입된 경우에만 동작한다. runtime 최적화가
grounding 또는 publication 판정을 우회하지 않는 것이 핵심 불변식이다.
"""

__all__: list[str] = []
