#!/usr/bin/env python3
"""aikorea24 데일리 파이프라인 (Blog Pipeline)

뉴스 → 브리핑 → 썸네일 → 이메일 → 배포:
1. 뉴스 선정 (auto_news_selector)
2. 브리핑 생성 (auto_briefing)
3. 썸네일 생성
4. 이메일 발송
5. 빌드 + 배포

Usage:
    python3 scripts/run_pipeline.py [--collect] [--skip-news] [--skip-briefing]
    python3 scripts/run_pipeline.py [--skip-email] [--skip-thumbnails] [--skip-deploy]
    python3 scripts/run_pipeline.py [--date YYYY-MM-DD] [--dry-run]
"""
import argparse
import os
import subprocess
import sys
import traceback
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Ensure scripts/ is importable
sys.path.insert(0, str(Path(__file__).resolve().parent))


KST = timezone(timedelta(hours=9))


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


def step_briefing(articles):
    """Step 2: 브리핑 생성 (articles 전달 시 해당 기사로 생성). briefing_id 반환."""
    import auto_briefing

    log("═══ Step 2: 브리핑 생성 ═══")
    if articles:
        return auto_briefing.main(articles)
    elif articles is None:
        return auto_briefing.main()
    else:
        log("  선정된 기사가 없어 브리핑을 건너뜁니다.")
        return None


def step_blog_link():
    """Step 1.5: AIK24-PIPE-05 — 무료 모델 news 행 ↔ AIK24 블로그 글 매칭.

    무료 모델 브리핑 항목의 "원문 보기" 링크를 AIK24 블로그 글로 연결한다
    (models.dev 는 제3자 카탈로그라 원문이 아니다 — 지시서 §3-2·§3-4).
    blog_link 가 없으면 기존 link 로 폴백하며, auto_briefing 이 경고를 로그로 남긴다.
    """
    import blog_link_resolver

    log("═══ Step 1.5: 무료 모델 → 블로그 링크 매칭 ═══")
    try:
        stats = blog_link_resolver.resolve()
    except Exception as e:
        log(f"  ⚠️ blog_link 매칭 실패 (브리핑은 계속): {type(e).__name__}: {str(e)[:160]}")
        return None
    log(f"  모델 {stats['models']}개 중 매칭 {stats['matched_models']}개 · "
        f"연결 {stats['linked_rows']}행 · 글 필요 큐 {stats['queued_models']}개")
    return stats


def step_thumbnails(articles):
    """Step 4: 썸네일 생성"""
    import auto_thumbnail

    log("═══ Step 3: 썸네일 생성 ═══")
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
            rel_path = auto_thumbnail.process_thumbnail(url, slug, title=title, description=art.get("description", ""))
            if rel_path:
                log(f"    ✅ {rel_path}")
                results.append({"title": title, "thumbnail": rel_path})
            else:
                log("    ❌ 썸네일 생성 실패")
        except Exception as e:
            log(f"    ❌ 에러: {e}")

    return results


def step_email():
    """Step 4: 이메일 발송"""
    import auto_email_sender

    log("═══ Step 4: 이메일 발송 ═══")
    auto_email_sender.main()


def step_deploy():
    """Step 5: 빌드 + Cloudflare Pages 배포"""
    log("═══ Step 5: 빌드 + 배포 ═══")
    deploy_script = str(Path(__file__).resolve().parent / "deploy.sh")
    if not Path(deploy_script).exists():
        log("  deploy.sh 없음, 건너뜀")
        return

    result = subprocess.run(
        ["/bin/bash", deploy_script],
        capture_output=True, text=True, timeout=300, cwd=str(Path(__file__).resolve().parent.parent)
    )
    for line in result.stdout.splitlines():
        log(f"  {line}")
    if result.returncode != 0:
        log(f"  ❌ 배포 실패 (rc={result.returncode})")
        if result.stderr:
            for line in result.stderr.splitlines()[-5:]:
                log(f"  ⚠ {line}")
        raise RuntimeError(f"배포 실패 (rc={result.returncode})")
    else:
        log("  ✅ 배포 완료")


def main():
    parser = argparse.ArgumentParser(
        description="aikorea24 데일리 파이프라인",
        epilog="전체 워크플로우: 뉴스선정 → 브리핑 → 썸네일 → 이메일 → 빌드/배포",
    )
    parser.add_argument("--collect", action="store_true",
                        help="Step 0 v2 소스 수집 실행 (기본: 05:30 수집기에 이관되어 스킵)")
    parser.add_argument("--skip-news", action="store_true", help="뉴스 선정 단계 건너뜀")
    parser.add_argument("--skip-briefing", action="store_true", help="브리핑 생성 단계 건너뜀")
    parser.add_argument("--skip-blog-link", action="store_true",
                        help="무료 모델 → 블로그 링크 매칭 단계 건너뜀 (AIK24-PIPE-05)")
    parser.add_argument("--skip-thumbnails", action="store_true", help="썸네일 생성 단계 건너뜀")
    parser.add_argument("--skip-email", action="store_true", help="이메일 발송 단계 건너뜀")
    parser.add_argument("--no-email", action="store_true",
                        help="이메일 발송 안 함 (수동 실행용, --skip-email과 동일. 자동 스케줄 실행에는 사용 금지)")
    parser.add_argument("--skip-deploy", action="store_true", help="빌드/배포 단계 건너뜀")
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
        if not args.skip_thumbnails:
            steps.append("3. 썸네일 생성")
        if not args.skip_email and not args.no_email:
            steps.append("4. 이메일 발송")
        if not args.skip_deploy:
            steps.append("5. 빌드/배포")
        for s in steps:
            log(f"  → {s}")
        return

    # Step 0: v2 소스 수집 (AIK24-PIPE-02 Step 2/4)
    # AIK24-EFFICIENCY-02: 05:30 launchd 수집기(kr.aikorea24.news-unified)가 같은 소스를
    # 수집한다. Step 0 은 205건 중 신규 2건(99% 중복)에 228초를 썼다.
    # → 기본 스킵. 수집기 실패 시 `run_pipeline.py --collect` 로 수동 복구한다.
    #   (호출부와 수집기 코드는 지시서 §4-2 에 따라 남겨둔다)
    if not args.collect:
        log("⏭ Step 0 수집 스킵 (05:30 수집기에 이관) — 수동 실행 시 --collect")
    else:
        try:
            log("Step 0: v2 소스 수집 (OpenRouter free / HF trending / 공식 RSS)")
            r = subprocess.run(
                [sys.executable, str(Path(__file__).resolve().parent / "news_collector_v2.py")],
                capture_output=True, text=True, timeout=300,
            )
            for line in (r.stdout or "").splitlines()[-4:]:
                log(f"  {line}")
            if r.returncode != 0:
                log(f"  v2 수집기 실패 rc={r.returncode}: {(r.stderr or '')[:200]}")
        except Exception as e:
            log(f"v2 수집 에러(무시하고 계속): {e}")

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

    # Step 2: 브리핑 생성 (step 1의 기사 목록 전달)
    briefing_id = None
    if not args.skip_briefing:
        try:
            briefing_id = step_briefing(articles)
        except Exception as e:
            log(f"브리핑 생성 에러: {e}")
            traceback.print_exc()
            summary["errors"].append(f"브리핑 생성: {e}")
    else:
        log("⏭ 브리핑 생성 건너뜀")

    log("")

    # Step 1.5: 무료 모델 → 블로그 링크 매칭 (AIK24-PIPE-05)
    # 브리핑 생성 전에 blog_link 를 채운다 — auto_briefing 이 링크 사용 여부를 로그로 남기고,
    # 이메일·웹 카드의 "원문 보기" 는 렌더링 시점에 COALESCE(n.blog_link, n.link) 로 연결된다.
    if not args.skip_blog_link:
        try:
            step_blog_link()
        except Exception as e:
            log(f"blog_link 매칭 단계 오류(무시하고 계속): {e}")
            traceback.print_exc()
            summary["errors"].append(f"blog_link 매칭: {e}")
    else:
        log("⏭ Step 1.5 blog_link 매칭 건너뜀")

    log("")

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

    # Step 5: 이메일 발송 (--no-email이면 절대 발송 금지: 수동 실행용)
    if args.no_email:
        log("[pipeline] --no-email: 이메일 발송 건너뜀")
    elif not args.skip_email:
        if not briefing_id:
            # 2026-10-16: 새 브리핑이 없으면(이미 오늘 발행됨/후보 없음) 이메일도 보내지 않는다.
            # 종전에는 브리핑 생성과 무관하게 발송해, 같은 날 재실행마다 같은 브리핑이
            # 중복 발송됐다 (실측: 10-16 브리핑 2건 → 이메일 2회).
            log("⏭ 새 브리핑이 없어 이메일 발송 건너뜀 (중복 발송 방지)")
        else:
            try:
                step_email()
            except Exception as e:
                log(f"이메일 발송 에러: {e}")
                traceback.print_exc()
                summary["errors"].append(f"이메일 발송: {e}")
    else:
        log("⏭ 이메일 발송 건너뜀")

    log("")

    # Step 6: 빌드 + 배포
    if not args.skip_deploy:
        try:
            step_deploy()
        except Exception as e:
            log(f"배포 에러: {e}")
            traceback.print_exc()
            summary["errors"].append(f"배포: {e}")
    else:
        log("⏭ 빌드/배포 건너뜀")

    # Summary
    elapsed = (datetime.now() - start_time).total_seconds()
    log("")
    log("╔══════════════════════════════════════╗")
    log("║  파이프라인 완료                      ║")
    log("╚══════════════════════════════════════╝")
    log(f"  소요 시간: {elapsed:.1f}초")
    log(f"  선정 뉴스: {len(summary['news'])}건")
    log(f"  썸네일:   {len(summary['thumbnails'])}건")

    if summary["errors"]:
        log(f"  ⚠️  에러: {len(summary['errors'])}건")
        for err in summary["errors"]:
            log(f"    - {err}")
        sys.exit(1)
    else:
        log("  ✅ 에러 없음")


if __name__ == "__main__":
    main()
