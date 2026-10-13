#!/usr/bin/env python3
"""aikorea24 데일리 파이프라인 (Blog Pipeline)

뉴스 → 브리핑 → 블로그 → 썸네일 → 이메일 → 배포:
1. 뉴스 선정 (auto_news_selector)
2. 브리핑 생성 (auto_briefing)
3. 블로그 초안 생성 (blog_draft_generator)
4. 썸네일 생성 (auto_thumbnail)
5. 이메일 발송 (auto_email_sender)
6. 빌드 + 배포 (scripts/deploy.sh)

Usage:
    python3 scripts/run_pipeline.py [--collect] [--skip-news] [--skip-briefing]
    python3 scripts/run_pipeline.py [--skip-blog] [--skip-email] [--skip-thumbnails] [--skip-deploy]
    python3 scripts/run_pipeline.py [--date YYYY-MM-DD] [--dry-run]
"""
import argparse
import os
import re
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


def step_blog():
    """Step 3: 블로그 초안 생성 (브리핑 기반)"""
    log("═══ Step 3: 블로그 초안 생성 ═══")
    # AIK24-EFFICIENCY-02: 생성기 내부의 자체 배포(62초)를 끈다. 이 경로에선
    # Step 6(deploy.sh)이 1분 뒤에 한 번 더 배포하므로 중복이었다.
    blog_env = dict(os.environ, PIPELINE_MODE="1")
    result = subprocess.run(
        [sys.executable, str(Path(__file__).resolve().parent / "blog_draft_generator.py")],
        capture_output=True, text=True, timeout=600,
        cwd=str(Path(__file__).resolve().parent.parent), env=blog_env
    )
    for line in (result.stdout or "").splitlines()[-10:]:
        log(f"  {line}")
    if result.returncode != 0:
        log(f"  ⚠️ 블로그 생성 실패 (rc={result.returncode}), 계속 진행")
        if result.stderr:
            for line in result.stderr.splitlines()[-3:]:
                log(f"  ⚠ {line}")
    else:
        log("  ✅ 블로그 초안 생성 완료")


def step_link_blogs():
    """Step 3b: 브리핑에 블로그 링크 연결 (모델 심층 분석)

    오늘 생성된 모델 심층 분석 블로그 글을 찾아,
    오늘 브리핑의 해당 free-llm 항목 코멘트에 블로그 URL을 추가한다.
    D1 briefing_items.comment에 '👉 자세한 분석: /blog/{slug}/' 형태로 삽입.
    """
    import glob
    import json
    log("═══ Step 3b: 브리핑-블로그 링크 연결 ═══")
    try:
        KST = timezone(timedelta(hours=9))
        today = datetime.now(KST).strftime("%Y-%m-%d")
        # 1. 오늘 생성된 블로그 파일에서 모델 심층 분석 글 찾기
        blog_dir = Path(__file__).resolve().parent.parent / "src" / "content" / "blog"
        # 모델 심층 분석 글은 frontmatter에 model_id 또는 제목에 [모델 분석] 포함으로 판별
        candidates = []
        for fp in glob.glob(str(blog_dir / f"{today}*.md")):
            try:
                text = Path(fp).read_text(encoding="utf-8")[:2000]
                # frontmatter에서 slug와 model_id 추출
                m_slug = re.search(r"^slug:\s*['\"]?([^'\"\s]+)", text, re.MULTILINE)
                slug = m_slug.group(1) if m_slug else Path(fp).stem
                m_model = re.search(r"model_id:\s*['\"]?([^'\"\s]+)", text)
                model_id = m_model.group(1) if m_model else None
                # 제목에서 모델명 추출 시도
                m_title = re.search(r"^title:\s*['\"]?(.+?)['\"]?\s*$", text, re.MULTILINE)
                title = m_title.group(1) if m_title else ""
                # 모델 심층 분석 글로 판별: model_id가 있거나 제목에 모델 패턴
                if model_id or "모델" in title or "LLM" in title:
                    candidates.append({"slug": slug, "model_id": model_id, "title": title, "file": fp})
            except Exception:
                continue
        if not candidates:
            log("  모델 분석 블로그 없음 → 건너뜀")
            return
        log(f"  모델 분석 블로그 {len(candidates)}건 발견")
        # 2. D1에서 오늘 브리핑 조회
        wrangler = "/opt/homebrew/bin/wrangler"
        proj = str(Path(__file__).resolve().parent.parent)
        env = dict(os.environ)
        env.pop("CLOUDFLARE_API_TOKEN", None)
        env.pop("CLOUDFLARE_ACCOUNT_ID", None)
        def d1(q):
            r = subprocess.run([wrangler, "d1", "execute", "aikorea24-db", "--remote",
                                "--command", q, "--json"],
                               capture_output=True, text=True, timeout=60, cwd=proj, env=env)
            if r.returncode != 0:
                return []
            try:
                data = json.loads(r.stdout)
                return data[0].get("results", []) if data else []
            except Exception:
                return []
        briefings = d1(f"SELECT id FROM briefings WHERE date LIKE '{today}%' AND status='published' ORDER BY id DESC LIMIT 1")
        if not briefings:
            log("  오늘 브리핑 없음 → 건너뜀")
            return
        bid = briefings[0]["id"]
        items = d1(f"SELECT rowid, news_id, comment FROM briefing_items WHERE briefing_id={bid}")
        # 3. 각 블로그 후보에 대해 매칭되는 브리핑 항목에 URL 삽입
        linked = 0
        for c in candidates:
            slug, model_id = c["slug"], c["model_id"]
            blog_url = f"https://aikorea24.kr/blog/{slug}/"
            for it in items:
                comment = it.get("comment") or ""
                if "👉 자세한 분석" in comment:
                    continue  # 이미 링크 있음
                # 매칭: model_id가 코멘트에 있거나 슬러그 관련
                hit = False
                if model_id and model_id.split("/")[-1].split(":")[0] in comment:
                    hit = True
                if not hit:
                    continue
                new_comment = comment + f"\n👉 자세한 분석: {blog_url}"
                # SQL 이스케이프
                esc = new_comment.replace("'", "''")
                r = subprocess.run([wrangler, "d1", "execute", "aikorea24-db", "--remote",
                                    "--command", f"UPDATE briefing_items SET comment='{esc}' WHERE rowid={it['rowid']} AND comment NOT LIKE '%👉 자세한 분석%'"],
                                   capture_output=True, text=True, timeout=60, cwd=proj, env=env)
                if r.returncode == 0:
                    linked += 1
                    log(f"  ✅ 링크 추가: {model_id} → {blog_url}")
        log(f"  완료: {linked}건 연결")
    except Exception as e:
        log(f"  ⚠️ 링크 연결 실패 (무시하고 계속): {e}")
        traceback.print_exc()


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
    parser.add_argument("--skip-blog", action="store_true", help="블로그 초안 생성 단계 건너뜀")
    parser.add_argument("--skip-thumbnails", action="store_true", help="썸네일 생성 단계 건너뜀")
    parser.add_argument("--skip-email", action="store_true", help="이메일 발송 단계 건너뜀")
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
        if not args.skip_email:
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

    log("")

    # Step 3: 블로그 초안 생성 (브리핑 기반)
    if not args.skip_blog:
        try:
            step_blog()
        except Exception as e:
            log(f"블로그 생성 에러 (무시하고 계속): {e}")
            traceback.print_exc()
    else:
        log("⏭ 블로그 초안 생성 건너뜀")

    log("")

    # Step 3b: 브리핑-블로그 링크 연결
    try:
        step_link_blogs()
    except Exception as e:
        log(f"링크 연결 에러 (무시하고 계속): {e}")

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
