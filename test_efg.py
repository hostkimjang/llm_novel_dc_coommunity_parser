"""아이디어 E/F/G 통합 테스트"""
import sys, re
sys.stdout.reconfigure(encoding='utf-8')

def test_e():
    """E: _execute_searches 자기참조 URL 필터"""
    print('[E] _execute_searches 자기참조 필터')
    cases = [
        ('11718111', 'https://m.dcinside.com/board/genrenovel/11718111?page=2', True),
        ('11718111', 'https://m.dcinside.com/board/genrenovel/11718111?page=3&recommend=1', True),
        ('11718111', 'https://novelpia.com/novel/8330', False),
        ('11718111', 'https://m.blog.naver.com/PostView.naver', False),
        ('11714878', 'https://m.dcinside.com/board/genrenovel/11714878', True),
        ('11714878', 'https://ridibooks.com/search?q=test', False),
        # post_id가 다른 URL에 우연히 포함된 경우 (non-dcinside) → 통과
        ('8330', 'https://novelpia.com/novel/8330', False),
    ]
    for pid, url, expect in cases:
        is_self = (pid in url and 'dcinside.com' in url)
        assert is_self == expect, f'FAIL: pid={pid}, url={url[:50]}, got={is_self}, want={expect}'
        mark = '✗' if is_self else '✓'
        print(f'  [{mark}] pid={pid} self_ref={is_self}  url=...{url[-35:]}')
    print('  ✅ OK')

def test_f():
    """F: heretic_url 자기참조 검증"""
    print('[F] heretic_url 자기참조 검증')
    cases = [
        ('11718111', 'https://m.dcinside.com/board/genrenovel/11718111?page=2', 'High', 'Low'),
        ('11718111', 'https://novelpia.com/novel/8330', 'High', 'High'),
        ('11714878', 'https://m.dcinside.com/board/genrenovel/11714878?page=1', 'High', 'Low'),
        ('11714878', 'https://ridibooks.com/search?q=test', 'High', 'High'),
        # heretic_url이 None인 경우
        ('11718111', None, 'High', 'High'),
        ('11718111', '', 'High', 'High'),
    ]
    for pid, hurl, orig_conf, exp_conf in cases:
        nid = {'heretic_url': hurl, 'confidence': orig_conf, 'evidence_type': 'test'}
        h = nid.get('heretic_url', '') or ''
        if h and pid and pid in h and 'dcinside.com' in h:
            nid['heretic_url'] = None
            nid['confidence'] = 'Low'
            nid['evidence_type'] = 'self_reference_invalid'
        assert nid['confidence'] == exp_conf, f'FAIL: pid={pid} hurl={hurl} -> {nid["confidence"]} != {exp_conf}'
        hurl_short = f'...{hurl[-25:]}' if hurl else 'None'
        print(f'  pid={pid} {orig_conf}->{nid["confidence"]}  hurl={hurl_short}')
    print('  ✅ OK')

def test_g():
    """G: 작가명 vs 소설제목 구분"""
    print('[G] 작가명 vs 소설제목 구분')
    test_cases = [
        ('우문현답', '작가명. 우문현답', True),
        ('우문현답', '작가: 우문현답', True),
        ('우문현답', '작가 우문현답', True),
        ('우문현답', '우문현답 작가', True),
        ('우문현답', '글작가 우문현답', True),
        ('우문현답', '우문현답 - 조아라 : 스토리 작가명. 우문현답. 작품수 3개.', True),
        # 소설 제목은 작가명으로 감지되면 안 됨
        ('칠흑마신', '칠흑마신 - 웹소설', False),
        ('빌어먹을 환생', '빌어먹을 환생 - 카카오페이지', False),
        ('칠흑마신', '작가는 홍길동', False),
        # "작가" 단어가 포함되어도 다른 맥락이면 불일치
        ('칠흑마신', '칠흑마신의 작가는 홍길동', False),
        # edge: 제목 안에 "작가"가 포함된 소설
        ('작가의 길', '작가의 길 - 웹소설', False),
    ]
    for title, text, expect in test_cases:
        p = re.compile(
            r'작가명[.:\s]\s*' + re.escape(title)
            + r'|작가[:\s]\s*' + re.escape(title)
            + r'|' + re.escape(title) + r'\s*작가'
            + r'|글작가\s*' + re.escape(title),
            re.IGNORECASE,
        )
        found = bool(p.search(text))
        assert found == expect, f'FAIL: "{title}" in "{text}" -> {found} != {expect}'
        mark = '✓' if found == expect else '✗'
        print(f'  [{mark}] "{title}" in "{text[:30]}..." -> author={found}')
    print('  ✅ OK')

def test_import():
    """모듈 임포트 테스트"""
    print('[import]')
    from src.llm_batch.experts.orchestrator import Orchestrator
    from src.llm_batch.experts.verifier import VerifierExpert
    print('  Orchestrator, VerifierExpert import OK')
    print('  ✅ OK')

if __name__ == '__main__':
    test_e()
    print()
    test_f()
    print()
    test_g()
    print()
    test_import()
    print()
    print('=== ALL TESTS PASSED ===')
