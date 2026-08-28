#!/usr/bin/env python3
"""
Weekly Contrast Deep Dive — orchestrator.

실행: python3 scripts/run_weekly_contrast.py [--dry-run] [--days N] [--max N]

흐름:
  S0: 주간 기사 수집 (D1)
  S1: 대비 클러스터 탐지 (LLM 2회)
  S2: 심층 분석 작성 (LLM N회)
  S3: 블로그 포스트 발행

launchd: 토요일 08:00 (kr.aikorea24.weekly-contrast)
"""

import json
import os
import sys
import time
from datetime import datetime

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_SCRIPT_DIR)
sys.path.insert(0, _PROJECT_ROOT)

from pipeline.infra.logger import get_scrubbed_logger

logger = get_scrubbed_logger(__name__)


def run_pipeline(dry_run: bool = False, days: int = 7, max_writes: int = 2) -> dict:
    """
    전체 파이프라인 실행.

    Args:
        dry_run: True면 블로그 발행 안 함
        days: 수집 기간 (일)
        max_writes: 최대 심층 분석 작성 수

    Returns:
        dict: 실행 결과 요약
    """
    start_time = time.time()
    result = {
        "timestamp": datetime.now().isoformat(),
        "dry_run": dry_run,
        "days": days,
        "s0_articles": 0,
        "s1_candidates": 0,
        "s2_dives": 0,
        "s3_posts": [],
        "errors": [],
    }

    # --- S0: 주간 기사 수집 ---
    logger.info("=== S0: weekly article collection ===")
    try:
        from scripts.weekly_contrast_collector import collect_weekly_articles
        articles = collect_weekly_articles(days=days)
        result["s0_articles"] = len(articles)
        logger.info("S0: %d articles collected", len(articles))
    except Exception as e:
        result["errors"].append(f"S0: {e}")
        logger.error("S0_failed: %s", e)
        return result

    if len(articles) < 4:
        result["errors"].append(f"S0: insufficient articles ({len(articles)} < 4)")
        logger.warning("S0: too few articles (%d), aborting", len(articles))
        return result

    # --- S1: 대비 클러스터 탐지 ---
    logger.info("=== S1: contrast cluster detection ===")
    try:
        from scripts.contrast_cluster_finder import find_contrast_candidates
        candidates = find_contrast_candidates(articles)
        result["s1_candidates"] = len(candidates)
        logger.info("S1: %d contrast candidates found", len(candidates))
    except Exception as e:
        result["errors"].append(f"S1: {e}")
        logger.error("S1_failed: %s", e)
        return result

    if not candidates:
        logger.info("S1: no contrast candidates, aborting")
        return result

    # 대비 후보 저장 (디버깅용)
    candidates_path = os.path.join(_PROJECT_ROOT, "tmp_test", "weekly_candidates.json")
    os.makedirs(os.path.dirname(candidates_path), exist_ok=True)
    with open(candidates_path, "w", encoding="utf-8") as f:
        json.dump(candidates, f, ensure_ascii=False, indent=2)
    logger.info("S1: candidates saved to %s", candidates_path)

    # --- S2: 심층 분석 작성 ---
    logger.info("=== S2: deep dive writing ===")
    try:
        from scripts.deep_dive_writer import write_all_deep_dives
        dives = write_all_deep_dives(candidates, max_writes=max_writes)
        result["s2_dives"] = len(dives)

        # 품질 판단 결과 저장
        result["s2_quality"] = []
        for d in dives:
            q = d.get("quality_judgment", {})
            result["s2_quality"].append({
                "title": d.get("title", ""),
                "verdict": q.get("verdict", "unknown"),
                "issues": q.get("issues", []),
                "verified_quotes": q.get("verified_quotes", 0),
                "unverified_quotes": q.get("unverified_quotes", 0),
                "source_links_count": q.get("source_links_count", 0),
            })

        logger.info("S2: %d deep dives written", len(dives))
    except Exception as e:
        result["errors"].append(f"S2: {e}")
        logger.error("S2_failed: %s", e)
        return result

    if not dives:
        logger.info("S2: no deep dives produced, aborting")
        return result

    # --- S3: 블로그 포스트 발행 ---
    logger.info("=== S3: blog publishing ===")
    if dry_run:
        logger.info("S3: dry-run, skipping publish")
        result["s3_posts"] = ["(dry-run)"]
    else:
        try:
            from scripts.weekly_blog_publisher import publish_all
            paths = publish_all(dives)
            result["s3_posts"] = paths
            logger.info("S3: %d blog posts published", len(paths))
        except Exception as e:
            result["errors"].append(f"S3: {e}")
            logger.error("S3_failed: %s", e)

    elapsed = time.time() - start_time
    result["elapsed_seconds"] = round(elapsed, 1)

    logger.info("=== Pipeline complete: %.1fs ===", elapsed)
    return result


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Weekly Contrast Deep Dive")
    parser.add_argument("--dry-run", action="store_true", help="발행하지 않고 테스트")
    parser.add_argument("--days", type=int, default=7, help="수집 기간 (일)")
    parser.add_argument("--max", type=int, default=2, help="최대 심층 분석 수")
    args = parser.parse_args()

    result = run_pipeline(dry_run=args.dry_run, days=args.days, max_writes=args.max)

    print(f"\n{'='*60}")
    print("Weekly Contrast Deep Dive — 결과 요약")
    print(f"{'='*60}")
    print(f"수집 기사: {result['s0_articles']}건")
    print(f"대비 후보: {result['s1_candidates']}건")
    print(f"심층 분석: {result['s2_dives']}건")
    print(f"발행 포스트: {len(result['s3_posts'])}건")
    print(f"소요 시간: {result.get('elapsed_seconds', 0)}초")

    # 품질 판단 출력
    if result.get("s2_quality"):
        print(f"\n{'─'*60}")
        print("품질 판단:")
        for q in result["s2_quality"]:
            icon = {"추천": "✅", "보류": "⚠️", "폐기": "❌"}.get(q["verdict"], "❓")
            print(f"  {icon} [{q['verdict']}] {q['title']}")
            print(f"     검증된 인용: {q['verified_quotes']}건, 미검증: {q['unverified_quotes']}건")
            print(f"     출처 링크: {q['source_links_count']}건")
            if q["issues"]:
                for issue in q["issues"]:
                    print(f"     - {issue}")

    if result["errors"]:
        print(f"\n에러:")
        for err in result["errors"]:
            print(f"  - {err}")

    # 결과 JSON 저장
    output_path = os.path.join(_PROJECT_ROOT, "tmp_test", "weekly_contrast_result.json")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"\n결과 저장: {output_path}")


if __name__ == "__main__":
    main()
