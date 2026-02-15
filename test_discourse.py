"""Quick test for DiscourseAnalyzer"""
import sys
sys.path.insert(0, 'c:/Users/kimjang/Documents/GitHub/llm_novel_dc_coommunity_parser/src')

from llm_batch.llm.client import LLMClient
from llm_batch.experts.discourse import DiscourseAnalyzer

# Initialize
llm = LLMClient()
analyzer = DiscourseAnalyzer(llm)

# Test data - medical post
post = {
    "post_id": 11718070,
    "title": "ect 개무섭네",
    "author": "ㅇㅇ",
    "content_blocks": [
        {"type": "text", "text": "뇌 찌릿찌릿해서 우울증 치료하는거"},
        {"type": "text", "text": "효과 좋긴 한데 케바케고 기억력 문제 생긴다함"},
        {"type": "text", "text": "ㄷㄷ"}
    ]
}

comments = []

# Run analysis
print("=" * 60)
print("Testing DiscourseAnalyzer on medical post")
print("=" * 60)

result = analyzer.analyze(post, comments)

print("\n" + "=" * 60)
print("DISCOURSE ANALYSIS RESULT:")
print("=" * 60)

import json
print(json.dumps(result, ensure_ascii=False, indent=2))

# Check if domain is correctly identified
analysis = result.get("discourse_analysis", {})
domain = analysis.get("primary_domain")
print(f"\n✅ Domain: {domain}")
print(f"✅ Confidence: {analysis.get('domain_confidence')}")
print(f"✅ Is Association: {analysis.get('is_association_not_discussion')}")
print(f"✅ Real Subject: {analysis.get('real_subject')}")

if domain == "medical_health":
    print("\n🎉 SUCCESS! Medical domain correctly identified!")
else:
    print(f"\n❌ FAILED! Expected 'medical_health', got '{domain}'")
