#!/usr/bin/env python
"""
Test script for the Multi-Expert Staged Pipeline.

Usage:
    python test_staged.py [input_file] [limit]

Examples:
    python test_staged.py                      # Use default sample
    python test_staged.py tests/inputs/sample.jsonl 5
"""

import json
import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

def create_test_posts():
    """Create test posts for various scenarios."""
    return [
        # Case 1: Clear abbreviation with platform evidence
        {
            "post_id": 1001,
            "title": "즉사무림 재밌네",
            "author": "테스터",
            "content_blocks": [{"type": "text", "text": "무림물 좋아하면 강추"}],
            "comments": [],
        },
        # Case 2: Author mention pattern
        {
            "post_id": 1002,
            "title": "개돌 신작 초대남이 너무 좆같은데",
            "author": "바이콘",
            "content_blocks": [
                {"type": "text", "text": "좀 사람새끼처럼 생겨야지"},
                {"type": "text", "text": "좆돼지 청소부는 너무 불쾌하잖아"}
            ],
            "comments": ["개꼴리노", "초대남이 좆같아야하는거임"],
        },
        # Case 3: Medical term (should be noise)
        {
            "post_id": 1003,
            "title": "ect 개무섭네",
            "author": "ㅇㅇ",
            "content_blocks": [
                {"type": "text", "text": "뇌 찌릿찌릿해서 우울증 치료하는거"},
                {"type": "text", "text": "효과 좋긴 한데 케바케고 기억력 문제 생긴다함"}
            ],
            "comments": [],
        },
        # Case 4: URL evidence in comment
        {
            "post_id": 1004,
            "title": "망겜성은 이태동이 황건욱 따먹었던 건 맞는거임?",
            "author": "ㅇㅇ",
            "content_blocks": [{"type": "text", "text": "황건욱이 여고생쟝이었던 회차 때"}],
            "comments": ["합리적의심", "novelpia.com/viewer/5134451"],
        },
        # Case 5: Clear noise (food)
        {
            "post_id": 1005,
            "title": "바나나에 소금 조금 찍어먹으면 맛잇음",
            "author": "ㅇㅇ",
            "content_blocks": [{"type": "text", "text": "제 비밀 레시피임"}],
            "comments": ["웩", "근본적으로 수박에 소금 찍는거랑 똑같은가"],
        },
    ]


def main():
    # Parse args
    input_file = sys.argv[1] if len(sys.argv) > 1 else None
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else 5
    
    # Setup environment
    os.environ.setdefault("LLM_BACKEND", "http")
    os.environ.setdefault("LLM_ENDPOINT", "https://llama.kimjang.me")
    os.environ.setdefault("LLM_STREAM", "1")
    os.environ.setdefault("LLM_PRINT_TIMINGS", "1")
    os.environ.setdefault("MCP_ENDPOINT", "http://localhost:3333")
    
    # Import after path setup
    from llm_batch.staged_pipeline import StagedPipeline
    from llm_batch.models import PostInput, ContentBlock
    
    # Load or create test data
    if input_file:
        input_path = Path(input_file)
        print(f"📂 Loading from: {input_path}")
        with open(input_path, encoding="utf-8") as f:
            content = f.read().strip()
            if content.startswith("["):
                raw_posts = json.loads(content)
            else:
                raw_posts = [json.loads(line) for line in content.splitlines() if line.strip()]
    else:
        print("📂 Using built-in test posts")
        raw_posts = create_test_posts()
    
    # Convert to PostInput
    posts = []
    for raw in raw_posts[:limit]:
        content_blocks = []
        for block in raw.get("content_blocks", []):
            if isinstance(block, dict):
                content_blocks.append(ContentBlock(**block))
            elif isinstance(block, str):
                content_blocks.append(ContentBlock(text=block))
        
        post = PostInput(
            post_id=raw["post_id"],
            title=raw.get("title", ""),
            author=raw.get("author", ""),
            url=raw.get("url", ""),
            content_blocks=content_blocks,
            comments=raw.get("comments", []),
        )
        posts.append(post)
    
    print(f"📊 Processing {len(posts)} posts...\n")
    
    # Initialize pipeline
    pipeline = StagedPipeline()
    
    # Process each post
    results = []
    for i, post in enumerate(posts, 1):
        print(f"\n{'='*70}")
        print(f"[{i}/{len(posts)}] Post {post.post_id}: {post.title[:50]}...")
        print(f"{'='*70}")
        
        result = pipeline.process_post(post)
        results.append(result)
        
        # Print summary - handle both Pydantic model and dict
        if hasattr(result, 'identity'):
            identity = result.identity
            is_relevant = identity.is_relevant if hasattr(identity, 'is_relevant') else False
            novel_id = identity.novel_identity if hasattr(identity, 'novel_identity') else None
            reason = identity.reason if hasattr(identity, 'reason') else None
        else:
            identity = result.get('identity', {})
            is_relevant = identity.get('is_relevant', False)
            novel_id = identity.get('novel_identity', {})
            reason = identity.get('reason')
        
        print(f"\n📋 Result:")
        print(f"   is_relevant: {is_relevant}")
        
        # Handle Pydantic model or dict for novel_id
        if novel_id:
            title = novel_id.official_title if hasattr(novel_id, 'official_title') else novel_id.get('official_title') if isinstance(novel_id, dict) else None
            conf = novel_id.confidence if hasattr(novel_id, 'confidence') else novel_id.get('confidence') if isinstance(novel_id, dict) else None
            if title:
                print(f"   title: {title}")
                print(f"   confidence: {conf}")
        
        reason_str = reason if reason else 'N/A'
        print(f"   reason: {str(reason_str)[:100]}...")
    
    # Save results
    output_path = Path("out/staged_test_result.json")
    output_path.parent.mkdir(exist_ok=True)
    
    serialized = []
    for r in results:
        if hasattr(r, 'model_dump'):
            serialized.append(r.model_dump())
        else:
            serialized.append(r)
    
    output_path.write_text(
        json.dumps(serialized, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    
    print(f"\n\n{'='*70}")
    print(f"✅ Complete! Results saved to: {output_path}")
    print(f"{'='*70}")
    
    # Summary - handle Pydantic models properly
    def get_is_relevant(r):
        if hasattr(r, 'identity'):
            return r.identity.is_relevant if hasattr(r.identity, 'is_relevant') else False
        return r.get('identity', {}).get('is_relevant', False)
    
    def get_official_title(r):
        if hasattr(r, 'identity'):
            ni = r.identity.novel_identity
            return ni.official_title if ni and hasattr(ni, 'official_title') else None
        ni = r.get('identity', {}).get('novel_identity', {})
        return ni.get('official_title') if ni else None
    
    print("\n📊 Summary:")
    relevant = sum(1 for r in results if get_is_relevant(r))
    identified = sum(1 for r in results if get_official_title(r))
    print(f"   Total: {len(results)}")
    print(f"   Relevant: {relevant}")
    print(f"   Identified: {identified}")


if __name__ == "__main__":
    main()
