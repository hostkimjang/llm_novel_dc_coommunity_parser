#!/usr/bin/env python3
"""Expert 시스템 결과 분석 스크립트 - 심도있는 분석"""
import json
import sys
from pathlib import Path
from collections import Counter, defaultdict

def load_results(file_path):
    """결과 파일 로드 (JSON 배열)"""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read().strip()
        if content.startswith('['):
            return json.loads(content)
        else:
            # JSONL 형식
            results = []
            for line in content.split('\n'):
                if line.strip():
                    results.append(json.loads(line))
            return results

def normalize_result(r):
    """결과를 일관된 구조로 변환"""
    ar = r.get("analysis_result", {})
    identity = ar.get("identity", {})
    novel_id = identity.get("novel_identity", {})
    
    return {
        "post_id": r.get("post_id"),
        "post_title": r.get("title", ""),
        "is_relevant": identity.get("is_relevant", False),
        "official_title": novel_id.get("official_title") if novel_id else None,
        "confidence": novel_id.get("confidence", "Unknown") if novel_id else "Unknown",
        "discussion_type": identity.get("discussion_type"),
        "reason": identity.get("reason", ""),
        "raw_result": r  # 원본 데이터 보존
    }

def main():
    # 최신 결과 파일 찾기
    out_dir = Path("out")
    result_files = sorted(out_dir.glob("expert_result_*.json"), reverse=True)
    
    if not result_files:
        print("❌ 결과 파일 없음 (out/expert_result_*.json)")
        sys.exit(1)
    
    result_file = result_files[0]
    print(f"📁 분석 파일: {result_file}")
    print("=" * 80)
    
    # 데이터 로드 및 정규화
    raw_results = load_results(result_file)
    results = [normalize_result(r) for r in raw_results]
    
    total = len(results)
    relevant = sum(1 for r in results if r["is_relevant"])
    identified = sum(1 for r in results if r["official_title"])
    
    # ========== 【1】 기본 통계 ==========
    print("\n【1】 기본 통계")
    print("-" * 80)
    print(f"전체 포스트:        {total}개")
    print(f"관련 포스트:        {relevant}개 ({relevant/total*100:.1f}%)")
    print(f"제목 식별 성공:     {identified}개 ({identified/total*100:.1f}%)")
    if relevant > 0:
        print(f"식별 성공률:        {identified/relevant*100:.1f}% (관련 포스트 대비)")
    print()
    
    # ========== 【2】 Confidence 분포 ==========
    print("【2】 Confidence 분포")
    print("-" * 80)
    
    conf_counter = Counter(r["confidence"] for r in results if r["official_title"])
    for conf, count in conf_counter.most_common():
        print(f"  {conf:15s}: {count:3d}개 ({count/identified*100:5.1f}%)" if identified > 0 else f"  {conf:15s}: 0개")
    print()
    
    # ========== 【3】 Discussion Type 분포 ==========
    print("【3】 Discussion Type 분포 (관련 포스트)")
    print("-" * 80)
    
    disc_counter = Counter(r["discussion_type"] for r in results if r["is_relevant"] and r["discussion_type"])
    for dtype, count in disc_counter.most_common():
        print(f"  {dtype:20s}: {count:3d}개 ({count/relevant*100:5.1f}%)" if relevant > 0 else f"  {dtype:20s}: 0개")
    print()
    
    # ========== 【4】 에러 케이스 분석 ==========
    print("【4】 에러 및 폴백 케이스")
    print("-" * 80)
    
    error_keywords = ["오류", "폴백", "Arbiter 오류", "error", "Error"]
    error_cases = [r for r in results if any(kw in r["reason"] for kw in error_keywords)]
    
    print(f"에러/폴백 케이스:   {len(error_cases)}개 ({len(error_cases)/total*100:.1f}%)")
    
    if error_cases:
        print("\n상위 에러 케이스:")
        for i, r in enumerate(error_cases[:5], 1):
            print(f"\n  [{i}] Post {r['post_id']}")
            print(f"      제목: {r['post_title'][:80]}")
            print(f"      사유: {r['reason'][:150]}")
    print()
    
    # ========== 【5】 실패 케이스 상세 ==========
    print("【5】 실패 케이스 상세 (관련인데 제목 미식별)")
    print("-" * 80)
    
    failed = [r for r in results if r["is_relevant"] and not r["official_title"]]
    print(f"실패 케이스:        {len(failed)}개")
    
    if failed:
        print("\n상위 실패 케이스:")
        for i, r in enumerate(failed[:5], 1):
            print(f"\n  [{i}] Post {r['post_id']}")
            print(f"      제목: {r['post_title'][:80]}")
            print(f"      Confidence: {r['confidence']}")
            print(f"      Discussion Type: {r['discussion_type']}")
            if r['reason']:
                print(f"      사유: {r['reason'][:150]}")
    print()
    
    # ========== 【6】 성공 케이스 샘플 ==========
    print("【6】 High Confidence 성공 케이스")
    print("-" * 80)
    
    high_conf = [r for r in results if r["official_title"] and r["confidence"] in ["High", "high", "HIGH"]]
    print(f"High Confidence:    {len(high_conf)}개")
    
    if high_conf:
        print("\n샘플:")
        for i, r in enumerate(high_conf[:3], 1):
            print(f"\n  [{i}] Post {r['post_id']}")
            print(f"      작품명: {r['official_title']}")
            print(f"      원본: {r['post_title'][:80]}")
    print()
    
    # ========== 【7】 식별된 작품 Top 10 ==========
    print("【7】 식별된 작품 빈도 Top 10")
    print("-" * 80)
    
    work_counter = Counter(r["official_title"] for r in results if r["official_title"])
    for i, (work, count) in enumerate(work_counter.most_common(10), 1):
        print(f"  {i:2d}. {work[:60]:60s} : {count}건")
    print()
    
    # ========== 【8】 성능 지표 ==========
    print("【8】 성능 지표 (Precision, Recall, F1)")
    print("-" * 80)
    
    # 가정: is_relevant=True가 ground truth positive
    # identified (official_title 있음) = predicted positive
    
    true_positive = sum(1 for r in results if r["is_relevant"] and r["official_title"])
    false_positive = sum(1 for r in results if not r["is_relevant"] and r["official_title"])
    false_negative = sum(1 for r in results if r["is_relevant"] and not r["official_title"])
    
    precision = true_positive / (true_positive + false_positive) if (true_positive + false_positive) > 0 else 0
    recall = true_positive / (true_positive + false_negative) if (true_positive + false_negative) > 0 else 0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
    
    print(f"True Positive:      {true_positive}개")
    print(f"False Positive:     {false_positive}개")
    print(f"False Negative:     {false_negative}개")
    print()
    print(f"Precision:          {precision*100:.1f}%")
    print(f"Recall:             {recall*100:.1f}%")
    print(f"F1 Score:           {f1*100:.1f}%")
    print()
    
    # ========== 【9】 개선 권장 사항 ==========
    print("【9】 개선 권장 사항")
    print("-" * 80)
    
    issues = []
    
    if len(error_cases) > total * 0.05:
        issues.append(f"⚠️ 에러 케이스 많음 ({len(error_cases)/total*100:.1f}%) - 안정성 개선 필요")
    
    if len(failed) > relevant * 0.2:
        issues.append(f"⚠️ 실패율 높음 ({len(failed)/relevant*100:.1f}%) - 식별 로직 강화 필요")
    
    if recall < 0.8:
        issues.append(f"⚠️ Recall 낮음 ({recall*100:.1f}%) - 더 많은 케이스 탐지 필요")
    
    if precision < 0.9:
        issues.append(f"⚠️ Precision 낮음 ({precision*100:.1f}%) - 잘못된 식별 감소 필요")
    
    if issues:
        for issue in issues:
            print(f"  {issue}")
    else:
        print("  ✅ 전반적으로 양호함")
    print()
    
    # ========== 【10】 요약 ==========
    print("【10】 종합 요약")
    print("=" * 80)
    print(f"✅ 전체 {total}개 포스트 중 {identified}개 작품 식별 성공 ({identified/total*100:.1f}%)")
    print(f"📊 Precision {precision*100:.1f}% / Recall {recall*100:.1f}% / F1 {f1*100:.1f}%")
    if len(high_conf) > 0:
        print(f"⭐ High confidence 케이스: {len(high_conf)}개 ({len(high_conf)/identified*100:.1f}%)")
    if len(error_cases) > 0:
        print(f"⚠️ 에러 케이스: {len(error_cases)}개 - 로그 확인 필요")
    print("=" * 80)

if __name__ == "__main__":
    main()
