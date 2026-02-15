"""
Agentic Pipeline 테스트
유기적 전문가 시스템 동작 확인
"""

import json
import os
import sys
from pathlib import Path

# 프로젝트 루트를 path에 추가
sys.path.insert(0, str(Path(__file__).parent / "src"))

from llm_batch.models import PostInput, ContentBlock
from llm_batch.agentic_pipeline import AgenticPipeline
from llm_batch.llm.client import LLMClient
from llm_batch.search.client import MCPClient


# 환경 설정
MCP_ENDPOINT = os.getenv("MCP_ENDPOINT", "http://localhost:3333")


def create_test_posts():
    """테스트용 포스트 생성"""
    return [
        # 1. 축약어 + 추천 (즉사무림)
        PostInput(
            post_id=2001,
            title="즉사무림 재밌네",
            author="테스터1",
            content_blocks=[
                ContentBlock(type="text", text="무림물 좋아하면 강추")
            ],
            gallery_id="test",
            comments=[
                {"content": "ㅇㅈ 꿀잼이야"},
                {"content": "나도 읽는중"},
            ],
        ),
        # 2. 작가명 언급 + 비평 (개돌청년)
        PostInput(
            post_id=2002,
            title="개돌 신작 초대남이 너무 좆같은데",
            author="테스터2",
            content_blocks=[
                ContentBlock(type="text", text="좆돼지 청소부는 너무 불쾌하잖아")
            ],
            gallery_id="test",
            comments=[
                {"content": "개꼴리노"},
                {"content": "초대남이 좆같아야하는거임"},
            ],
        ),
        # 3. ECT (노이즈 - 의료용어)
        PostInput(
            post_id=2003,
            title="ect 개무섭네",
            author="테스터3",
            content_blocks=[
                ContentBlock(type="text", text="뇌 찌릿찌릿해서 우울증 치료하는거")
            ],
            gallery_id="test",
            comments=[
                {"content": "기억력 떨어진다던데"},
            ],
        ),
        # 4. 순수 노이즈 (바나나 소금)
        PostInput(
            post_id=2004,
            title="바나나에 소금 조금 찍어먹으면 맛잇음",
            author="테스터4",
            content_blocks=[
                ContentBlock(type="text", text="수박에 소금이랑 비슷한 비밀 레시피임")
            ],
            gallery_id="test",
            comments=[
                {"content": "ㄹㅇ?"},
                {"content": "해볼까"},
            ],
        ),
    ]


def main():
    print("=" * 70)
    print("🤖 Agentic Pipeline 테스트 (유기적 전문가 시스템)")
    print("=" * 70)
    
    # 클라이언트 초기화
    llm = LLMClient()
    mcp = MCPClient(endpoint=MCP_ENDPOINT)
    
    # Pipeline 초기화
    pipeline = AgenticPipeline(
        llm=llm,
        mcp=mcp,
        max_iterations=5,
    )
    
    # 테스트 포스트
    posts = create_test_posts()
    print(f"\n📂 테스트 포스트 {len(posts)}개 준비 완료")
    
    results = []
    
    for i, post in enumerate(posts, 1):
        print(f"\n{'='*70}")
        print(f"[{i}/{len(posts)}] Post {post.post_id}: {post.title[:40]}...")
        print(f"{'='*70}")
        
        result = pipeline.process_post(post)
        results.append(result.model_dump() if hasattr(result, "model_dump") else result)
        
        # 결과 요약
        print(f"\n📋 Result:")
        print(f"   is_relevant: {result.identity.is_relevant}")
        if result.identity.novel_identity:
            print(f"   title: {result.identity.novel_identity.official_title}")
            print(f"   confidence: {result.identity.novel_identity.confidence}")
        print(f"   reason: {(result.identity.reason or '')[:60]}...")
    
    # 결과 저장
    output_path = Path("out/agentic_test_result.json")
    output_path.parent.mkdir(exist_ok=True)
    output_path.write_text(
        json.dumps(results, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    
    print(f"\n{'='*70}")
    print(f"✅ Complete! Results saved to: {output_path}")
    print(f"{'='*70}")
    
    # 요약
    relevant = sum(1 for r in results if r.get("identity", {}).get("is_relevant"))
    identified = sum(1 for r in results if (r.get("identity", {}).get("novel_identity") or {}).get("official_title"))
    print(f"\n📊 Summary:")
    print(f"   Total: {len(results)}")
    print(f"   Relevant: {relevant}")
    print(f"   Identified: {identified}")


if __name__ == "__main__":
    main()
