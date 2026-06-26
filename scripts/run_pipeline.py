#!/usr/bin/env python3
"""aikorea24 데일리 파이프라인

전체 뉴스 브리핑 워크플로우를 자동화합니다:
1. 뉴스 선정 (auto_news_selector)
2. 브리핑 생성 (auto_briefing)
3. 심층글 생성 (auto_deep_article)
4. 썸네일 생성 (auto_thumbnail)
5. 이메일 발송 (auto_email_sender)

Usage:
    python3 scripts/run_pipeline.py [--skip-news] [--skip-briefing] [--skip-deep]
    python3 scripts/run_pipeline.py [--skip-email] [--skip-thumbnails]
    python3 scripts/run_pipeline.py [--date YYYY-MM-DD] [--dry-run]
"""

import argparse
import sys
import traceback
from datetime import datetime
from pathlib import Path

# Ensure scripts/ is importable
sys.path.insert(0, str(Path(__file__).resolve().parent))


def log(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}")


def step_news_selection():
    """Step 1: 뉴스 선정"""
    import auto_news_selector

    log("═══ Step 1: 뉴스 선정 ═══")
    selected = auto_news_selector.main()
    if not selected:
        log("선정된 뉴스가 없습니다.")
        return []
    return selected


def step_briefing():
    """Step 2: 브리핑 생성"""
    import auto_briefing

    log("═══ Step 2: 브리핑 생성 ═══")
    auto_briefing.main()


def step_deep_articles(articles):
    """Step 3: 심층글 생성"""
    import auto_deep_article

    log("═══ Step 3: 심층글 생성 ═══")
    results = []
    for i, art in enumerate(articles, 1):
        title = art.get("title", "")
        url = art.get("link", "")
        log(f"  [{i}/{len(articles)}] {title[:60]}")

        if not url:
            log("    URL 없음, 스킵")
            continue

        try:
            content = auto_deep_article.crawl_article(url)
            if not content:
                log("    크롤링 실패")
                continue

            article_md = auto_deep_article.generate_deep_article(title, content, url)
            if not article_md:
                log("    글 생성 실패")
                continue

            filepath = auto_deep_article.save_article(article_md, title)
            log(f"    ✅ 저장: {filepath.name}")
            results.append({"title": title, "filepath": str(filepath)})
        except Exception as e:
            log(f"    ❌ 에러: {e}")

    return results


def step_thumbnails(articles):
    """Step 4: 썸네일 생성"""
    import auto_thumbnail

    log("═══ Step 4: 썸네일 생성 ═══")
    import re as re_mod

    results = []
    for i, art in enumerate(articles, 1):
        title = art.get("title", "")
        url = art.get("link", "")
        slug = re_mod.sub(r"[^a-z0-9가-힣]+", "-", title.lower())[:60].strip("-")
        log(f"  [{i}/{len(articles)}] {title[:60]}")

        if not url:
            log("    URL 없음, 스킵")
            continue

        try:
            rel_path = auto_thumbnail.process_thumbnail(url, slug)
            if rel_path:
                log(f"    ✅ {rel_path}")
                results.append({"title": title, "thumbnail": rel_path})
            else:
                log("    ❌ 썸네일 생성 실패")
        except Exception as e:
            log(f"    ❌ 에러: {e}")

    return results


def step_email():
    """Step 5: 이메일 발송"""
    import auto_email_sender

    log("═══ Step 5: 이메일 발송 ═══")
    auto_email_sender.main()


def main():
    parser = argparse.ArgumentParser(
        description="aikorea24 데일리 파이프라인",
        epilog="전체 워크플로우: 뉴스선정 → 브리핑 → 심층글 → 썸네일 → 이메일",
    )
    parser.add_argument("--skip-news", action="store_true", help="뉴스 선정 단계 건너뜀")
    parser.add_argument("--skip-briefing", action="store_true", help="브리핑 생성 단계 건너뜀")
    parser.add_argument("--skip-deep", action="store_true", help="심층글 생성 단계 건너뜀")
    parser.add_argument("--skip-thumbnails", action="store_true", help="썸네일 생성 단계 건너뜀")
    parser.add_argument("--skip-email", action="store_true", help="이메일 발송 단계 건너뜀")
    parser.add_argument("--date", help="날짜 지정 (YYYY-MM-DD 형식, 기본값: 오늘)")
    parser.add_argument("--dry-run", action="store_true", help="실행하지 않고 계획만 출력")
    args = parser.parse_args()

    log("╔══════════════════════════════════════╗")
    log("║  aikorea24 데일리 파이프라인 시작    ║")
    log("╚══════════════════════════════════════╝")
    log("")

    start_time = datetime.now()
    summary = {
        "news": [],
        "deep_articles": [],
        "thumbnails": [],
        "errors": [],
    }

    if args.dry_run:
        log("DRY RUN 모드 - 실행하지 않음")
        steps = []
        if not args.skip_news:
            steps.append("1. 뉴스 선정")
        if not args.skip_briefing:
            steps.append("2. 브리핑 생성")
        if not args.skip_deep:
            steps.append("3. 심층글 생성")
        if not args.skip_thumbnails:
            steps.append("4. 썸네일 생성")
        if not args.skip_email:
            steps.append("5. 이메일 발송")
        for s in steps:
            log(f"  → {s}")
        return

    # Step 1: 뉴스 선정
    articles = []
    if not args.skip_news:
        try:
            articles = step_news_selection()
            summary["news"] = [a.get("title", "") for a in articles]
        except Exception as e:
            log(f"뉴스 선정 에러: {e}")
            traceback.print_exc()
            summary["errors"].append(f"뉴스 선정: {e}")
    else:
        log("⏭ 뉴스 선정 건너뜀")

    log("")

    # Step 2: 브리핑 생성
    if not args.skip_briefing:
        try:
            step_briefing()
        except Exception as e:
            log(f"브리핑 생성 에러: {e}")
            traceback.print_exc()
            summary["errors"].append(f"브리핑 생성: {e}")
    else:
        log("⏭ 브리핑 생성 건너뜀")

    log("")

    # Step 3: 심층글 생성
    if not args.skip_deep:
        try:
            if not articles:
                log("선정된 뉴스가 없어 심층글을 건너뜁니다.")
            else:
                deep_results = step_deep_articles(articles)
                summary["deep_articles"] = [r["title"] for r in deep_results]
        except Exception as e:
            log(f"심층글 생성 에러: {e}")
            traceback.print_exc()
            summary["errors"].append(f"심층글 생성: {e}")
    else:
        log("⏭ 심층글 생성 건너뜀")

    log("")

    # Step 4: 썸네일 생성
    if not args.skip_thumbnails:
        try:
            if not articles:
                log("선정된 뉴스가 없어 썸네일을 건너뜁니다.")
            else:
                thumb_results = step_thumbnails(articles)
                summary["thumbnails"] = [r["thumbnail"] for r in thumb_results]
        except Exception as e:
            log(f"썸네일 생성 에러: {e}")
            traceback.print_exc()
            summary["errors"].append(f"썸네일 생성: {e}")
    else:
        log("⏭ 썸네일 생성 건너뜀")

    log("")

    # Step 5: 이메일 발송
    if not args.skip_email:
        try:
            step_email()
        except Exception as e:
            log(f"이메일 발송 에러: {e}")
            traceback.print_exc()
            summary["errors"].append(f"이메일 발송: {e}")
    else:
        log("⏭ 이메일 발송 건너뜀")

    # Summary
    elapsed = (datetime.now() - start_time).total_seconds()
    log("")
    log("╔══════════════════════════════════════╗")
    log("║  파이프라인 완료                      ║")
    log("╚══════════════════════════════════════╝")
    log(f"  소요 시간: {elapsed:.1f}초")
    log(f"  선정 뉴스: {len(summary['news'])}건")
    log(f"  심층글:   {len(summary['deep_articles'])}건")
    log(f"  썸네일:   {len(summary['thumbnails'])}건")

    if summary["errors"]:
        log(f"  ⚠️  에러: {len(summary['errors'])}건")
        for err in summary["errors"]:
            log(f"    - {err}")
    else:
        log("  ✅ 에러 없음")


if __name__ == "__main__":
    main()
