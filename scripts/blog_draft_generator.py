#!/usr/bin/env python3
"""
aikorea24 블로그 초안 자동 생성기
- D1 DB에서 오늘 수집된 뉴스 중 고단가 키워드 포함 기사 조회
- 키워드별 기사 그룹핑 → OpenAI 블로그 초안 생성
- src/content/blog/ 에 마크다운 파일 저장
- 텔레그램 알림
"""
import os, re, json, glob, sys
from datetime import datetime, date, timezone, timedelta

# launchd 환경: sys.path 미설정 상태이므로 __file__ 기반으로 먼저 추가
_script_dir = os.path.dirname(os.path.abspath(__file__))
_PROJECT_DIR = os.path.dirname(_script_dir)
sys.path.insert(0, _PROJECT_DIR)
sys.path.insert(0, _script_dir)
sys.path.insert(0, os.path.join(_PROJECT_DIR, 'scripts', 'threads', 'v3'))

from pipeline.infra.logger import get_scrubbed_logger
logger = get_scrubbed_logger(__name__)
from pipeline.infra import project_root; PROJECT_DIR = project_root()

KST = timezone(timedelta(hours=9))

def remove_chinese(text):
    """CJK 통합 한자 블록(U+4E00–U+9FFF, U+3400–U+4DBF) 제거"""
    return re.sub(r'[\u4e00-\u9fff\u3400-\u4dbf]', '', text)

# ============================================
# 고단가 키워드 테이블 (deprecated: 브리핑 기사 직접 사용)
# ============================================

# ============================================
# model_router (threads/v3)
# ============================================
from model_router import chat_completion
from auto_thumbnail import process_thumbnail

ENV_PATH = os.path.join(PROJECT_DIR, ".env")
DB_ID = "bec650ce-f732-46bc-87c0-bd76ed17e42a"

# ============================================
# 로깅
# ============================================
# Strangler Fig: replace with logger.info() in Phase 3
def log(msg):
    ts = datetime.now(KST).strftime("%H:%M:%S")
    print(f"[{ts}] {msg}")

# ============================================
# 환경변수 로딩
# ============================================
def load_env():
    # 공통 환경변수 먼저 로드 (~/.env.common)
    common = os.path.expanduser('~/.env.common')
    if os.path.exists(common):
        with open(common) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') \
                   and '=' in line and not line.startswith('source'):
                    k, v = line.split('=', 1)
                    os.environ.setdefault(k.strip(),
                                         v.strip().strip('"').strip("'"))

    if not os.path.exists(ENV_PATH):
        log(f"[WARN] .env 파일 없음: {ENV_PATH}")
        return
    with open(ENV_PATH) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ[k.strip()] = v.strip().strip('"').strip("'")

# ============================================
# D1 쿼리 (wrangler CLI — OAuth profile 사용)
# ============================================
_WRANGLER = "/opt/homebrew/bin/wrangler"
_DB = "aikorea24-db"

def _d1_run(sql):
    """wrangler d1 execute 실행, results 반환."""
    import subprocess, json, re
    cmd = [_WRANGLER, "d1", "execute", _DB, "--remote", "--command", sql]
    env = dict(os.environ)
    env.pop("CLOUDFLARE_API_TOKEN", None)  # profile 우선 사용
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=30, env=env, cwd=PROJECT_DIR)
        if r.returncode != 0:
            log(f"  wrangler 오류 (rc={r.returncode}): {r.stderr[:200]}")
            return None
        m = re.search(r'"results"\s*:\s*(\[.*?\])\s*,\s*"success"', r.stdout, re.DOTALL)
        return json.loads(m.group(1)) if m else []
    except Exception as e:
        log(f"  wrangler 예외: {e}")
        return None

def query_d1(sql):
    """D1 SELECT 실행, 결과 리스트 반환."""
    results = _d1_run(sql)
    if results is None:
        raise RuntimeError("D1 query failed")
    return results

def execute_d1(sql):
    """D1 UPDATE/INSERT 실행. 성공 여부 반환."""
    results = _d1_run(sql)
    return results is not None

def get_today_briefing_id():
    """오늘 발행된 브리핑 ID 조회 (없으면 None)."""
    today = date.today().strftime("%Y-%m-%d")
    try:
        rows = query_d1(
            f"SELECT id FROM briefings WHERE date LIKE '{today}%' AND status = 'published' ORDER BY date DESC LIMIT 1"
        )
        return rows[0]["id"] if rows else None
    except Exception as e:
        log(f"  브리핑 조회 실패: {e}")
        return None

def update_deep_dive_url(news_id, blog_url):
    """briefing_items의 deep_dive_url을 블로그 URL로 업데이트."""
    if not news_id or not blog_url:
        return False
    briefing_id = get_today_briefing_id()
    if not briefing_id:
        log(f"  ⚠️ 오늘 브리핑 없음, deep_dive_url 연결 불가 (news_id={news_id})")
        return False
    sql = (
        f"UPDATE briefing_items SET deep_dive_url = '{blog_url}' "
        f"WHERE briefing_id = {briefing_id} AND news_id = {news_id}"
    )
    if execute_d1(sql):
        log(f"  🔗 deep_dive_url 연결: {blog_url} (news_id={news_id})")
        return True
    else:
        log(f"  ⚠️ deep_dive_url 연결 실패 (news_id={news_id})")
        return False

# ============================================
# 오늘 뉴스 조회
# ============================================
def get_briefing_articles():
    """오늘 브리핑에 포함된 기사 목록 조회."""
    briefing_id = get_today_briefing_id()
    if not briefing_id:
        log("  오늘 발행된 브리핑 없음")
        return []
    sql = f"""
        SELECT n.id, n.title, n.description, n.source, n.category, n.link,
               bi.sort_order, bi.comment, bi.deep_dive_url
        FROM briefing_items bi
        JOIN news n ON bi.news_id = n.id
        WHERE bi.briefing_id = {briefing_id}
        ORDER BY bi.sort_order
    """
    rows = query_d1(sql)
    log(f"오늘 브리핑 기사: {len(rows)}건 (briefing_id={briefing_id})")
    return rows

# ============================================
# 블로그 초안 생성 (MiMo v2.5 via model_router)
# ============================================
def generate_draft(keyword, articles, grade):
    is_deep = len(articles) == 1

    # 기사 텍스트 조립
    article_lines = []
    for i, a in enumerate(articles, 1):
        desc = (a.get("description") or "")[:300]
        article_lines.append(f"[기사 {i}]\n"
                             f"제목: {a['title']}\n"
                             f"출처: {a['source']}\n"
                             f"내용: {desc}")
    articles_str = "\n\n".join(article_lines)

    # GPT 프롬프트
    if is_deep:
        system_prompt = (
            "당신은 AI/테크 뉴스를 분석하는 한국어 블로거입니다. "
            "주어진 기사 하나를 깊이 분석하여 블로그 초안을 작성해주세요. "
            "중국어(한자)는 절대 사용하지 말고 순수 한국어로만 작성하세요."
        )
        user_prompt = (
            f"아래 '{keyword}' 관련 기사를 분석한 블로그 초안을 작성해주세요.\n\n"
            f"## 요구사항\n"
            f"- 제목: '{keyword}' 키워드가 자연스럽게 포함된 SEO 최적화 제목\n"
            f"- 본문: 1500자 이상, 소제목(##) 3개 이상 포함\n"
            f"- 기사의 배경/의미/전망을 분석, 독자가 쉽게 이해할 수 있도록\n"
            f"- 마지막에 📌 **요약** 섹션 포함\n"
            f"- 순한국어, 전문적이면서도 친근한 ~습니다/~입니다 정중 비즈니스 톤\n"
            f"- [중요] 모든 문장은 '~합니다/~입니다/~했습니다' 체로 통일. 반말('~다/~했다/~임') 절대 금지\n"
            f"- [중요] 중국어(한자) 사용 금지. 반드시 순수 한국어로만 작성할 것\n\n"
            f"## 출력 형식\n"
            f"TITLE: [SEO에 최적화된 제목]\n"
            f"---\n"
            f"[마크다운 본문]\n\n"
            f"## 기사\n{articles_str}"
        )
    else:
        system_prompt = (
            "당신은 AI/테크 뉴스를 분석하는 한국어 블로거입니다. "
            "여러 기사를 종합하여 트렌드 분석 블로그 초안을 작성해주세요. "
            "중국어(한자)는 절대 사용하지 말고 순수 한국어로만 작성하세요."
        )
        user_prompt = (
            f"아래 '{keyword}' 관련 여러 기사를 종합한 블로그 초안을 작성해주세요.\n\n"
            f"## 요구사항\n"
            f"- 제목: '{keyword}' 관련 트렌드가 드러나는 SEO 최적화 제목\n"
            f"- 본문: 2000자 이상, 소제목(##) 3개 이상 포함\n"
            f"- 각 기사의 핵심 내용을 비교/종합하여 트렌드 분석\n"
            f"- 마지막에 📌 **요약** 섹션 포함\n"
            f"- 순한국어, 전문적이면서도 친근한 ~습니다/~입니다 정중 비즈니스 톤\n"
            f"- [중요] 모든 문장은 '~합니다/~입니다/~했습니다' 체로 통일. 반말('~다/~했다/~임') 절대 금지\n"
            f"- [중요] 중국어(한자) 사용 금지. 반드시 순수 한국어로만 작성할 것\n\n"
            f"## 출력 형식\n"
            f"TITLE: [SEO에 최적화된 제목]\n"
            f"---\n"
            f"[마크다운 본문]\n\n"
            f"## 기사들\n{articles_str}"
        )

    content = chat_completion(
        messages=[{"role": "user", "content": user_prompt}],
        system_prompt=system_prompt,
        max_tokens=3000,
        temperature=0.7,
    )
    if not content:
        log("  ❌ 블로그 초안 생성 실패")
        return ""
    # 중국어 문자 제거 (안전망)
    cleaned = remove_chinese(content)
    if cleaned != content:
        removed = len(content) - len(cleaned)
        log(f"  ⚠️ 중국어 문자 {removed}개 제거됨")
    content = cleaned
    log(f"  생성 완료: {len(content)}자")
    return content

# ============================================
# 파일 번호 결정
# ============================================
def next_file_number(today_str):
    pattern = os.path.join(PROJECT_DIR, "src", "content", "blog", f"{today_str}-*.md")
    existing = glob.glob(pattern)
    nums = []
    for f in existing:
        m = re.search(r"\d{4}-\d{2}-\d{2}-(\d+)-", f)
        if m:
            nums.append(int(m.group(1)))
    return max(nums) + 1 if nums else 1

# ============================================
# 슬러그 생성
# ============================================
def make_slug(title):
    slug = title.strip()
    slug = re.sub(r"[^\w\s가-힣]", "", slug)
    slug = re.sub(r"\s+", "-", slug)
    slug = slug[:80].rstrip("-")
    return slug.lower()

# ============================================
# 블로그 파일 저장
# ============================================
def save_draft(gpt_output, keyword, file_num, today_str, articles=None):
    """GPT 출력 파싱 → .md 파일 저장. articles 전달 시 deep_dive_url 연결."""
    filepath, seo_title = _save_file(gpt_output, keyword, file_num, today_str)
    # deep_dive_url 연결 (slug 소문자: Astro가 content collection ID를 lowercase로 정규화)
    if articles and filepath:
        slug = filepath.stem if hasattr(filepath, 'stem') else os.path.basename(filepath).replace('.md', '')
        slug = slug.lower()
        blog_url = f"https://aikorea24.kr/blog/{slug}/"
        for art in articles:
            news_id = art.get("id")
            if news_id:
                update_deep_dive_url(news_id, blog_url)
    return filepath, seo_title

def _save_file(gpt_output, keyword, file_num, today_str):
    """GPT 출력 파싱 → .md 파일 저장 (내부)."""
    # TITLE: ... / --- / 본문
    seo_title = keyword
    content = gpt_output
    if "TITLE:" in gpt_output:
        parts = gpt_output.split("TITLE:", 1)
        title_line = parts[1].split("\n", 1)[0].strip()
        if title_line:
            seo_title = title_line
        if "---" in gpt_output:
            body_parts = gpt_output.split("---", 1)
            if len(body_parts) > 1:
                content = body_parts[1].strip()

    slug = make_slug(seo_title)
    filename = f"{today_str}-{file_num:03d}-{slug}.md"
    filepath = os.path.join(PROJECT_DIR, "src", "content", "blog", filename)

    # description: "서론:", "들어가며:", "시작하며:", "개요:" 프리픽스 제거 + 250자 평문
    desc_raw = re.sub(r"^##?\s*(서론|들어가며|시작하며|개요)\s*[:：]?\s*", "", content)
    desc_raw = re.sub(r"[#*>\n\s]+", " ", desc_raw)[:250].strip()

    now_kst = datetime.now(KST)
    date_str = now_kst.strftime("%Y-%m-%dT%H:%M:%S+09:00")

    thumbnail_file = os.path.join(PROJECT_DIR, "public", "images", slug, "thumbnail.webp")
    image_line = f'image: "/images/{slug}/thumbnail.webp"\n' if os.path.exists(thumbnail_file) else ""

    md = f"""---
title: "{seo_title}"
description: "{desc_raw}"
date: {date_str}
category: "뉴스"
tags:
  - "{keyword}"
draft: false
{image_line}---

{content}
"""
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(md)
    log(f"  저장: {filename}")
    return filepath, seo_title

# ============================================
# 썸네일 삽입 (frontmatter image 필드)
# ============================================
def _add_image_to_frontmatter(filepath, image_rel_path):
    if not filepath or not image_rel_path:
        return
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()
    if re.search(r'^image:', content, re.MULTILINE):
        return
    updated = content.replace("draft: false\n---", f'draft: false\nimage: "{image_rel_path}"\n---', 1)
    if updated == content:
        log(f"  ⚠️ image 필드 삽입 실패 (frontmatter 구조 예상과 다름)")
        return
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(updated)
    log(f"  🖼️ image 필드 추가: {image_rel_path}")

# ============================================
# 텔레그램 알림
# ============================================
def send_telegram(message):
    import requests
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
    if not token or not chat_id:
        log("  텔레그램 토큰/챗ID 없음, 알림 스킵")
        return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        requests.post(url, json={
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        })
        log("  텔레그램 알림 전송 완료")
    except Exception as e:
        log(f"  텔레그램 전송 실패: {e}")

# ============================================
# 메인
# ============================================
def main():
    load_env()
    today_str = date.today().strftime("%Y-%m-%d")
    log(f"블로그 초안 생성 시작 ({today_str})")
    print()

    # 1. 오늘 브리핑 기사 조회
    log("[1/5] 브리핑 기사 조회 중...")
    try:
        articles = get_briefing_articles()
    except Exception as e:
        log(f"  브리핑 조회 실패: {e}")
        send_telegram(f"❌ [{today_str}] 블로그 초안 생성 실패: 브리핑 조회 오류")
        sys.exit(1)

    if not articles:
        log("  오늘 브리핑 없음, 종료")
        send_telegram(f"📭 [{today_str}] 블로그 초안 생성 스킵: 브리핑 없음")
        return
    print()

    # 2. 블로그 글 생성 (브리핑 기사별 1개씩)
    log("[2/5] 블로그 초안 생성 중...")
    file_num = next_file_number(today_str)
    created = []

    for i, art in enumerate(articles, 1):
        art_id = art.get("id")
        title = art.get("title", "")
        link = art.get("link", "")
        deep_dive = art.get("deep_dive_url")
        sort_order = art.get("sort_order", i)

        if deep_dive:
            log(f"  [{i}/{len(articles)}] '{title[:50]}...' — 이미 연결됨, 스킵")
            created.append((None, title, sort_order, 0))
            continue

        log(f"  [{i}/{len(articles)}] '{title[:50]}...' 생성 중...")
        try:
            gpt_output = generate_draft(title, [art], "A")
            if not gpt_output:
                log(f"    ❌ 생성 실패")
                continue

            filepath, seo_title = save_draft(gpt_output, title, file_num, today_str, articles=[art])
            created.append((filepath, seo_title or title, sort_order, 1))
            file_num += 1

            # 썸네일 생성 (Pexels)
            try:
                slug = os.path.basename(filepath).replace('.md', '').lower()
                thumb_rel = process_thumbnail(
                    link, slug,
                    title=title,
                    description=art.get("description", "")
                )
                if thumb_rel:
                    _add_image_to_frontmatter(filepath, thumb_rel)
            except Exception as thumb_e:
                log(f"  ⚠️ '{title[:40]}' 썸네일 생성 실패: {thumb_e}")
        except Exception as e:
            log(f"    ❌ '{title[:40]}' 생성 실패: {e}")

    # deep_dive_url이 없는 항목은 update_deep_dive_url이 save_draft 내에서 호출됨
    # (save_draft → articles 파라미터로 전달된 기사들의 id로 deep_dive_url 업데이트)
    print()

    # 3. 텔레그램 알림
    log("[3/5] 텔레그램 알림...")
    generated = [c for c in created if c[0] is not None]
    skipped = [c for c in created if c[0] is None]
    if generated:
        msg_lines = [f"🤖 <b>[{today_str}] 블로그 발행 완료</b>"]
        msg_lines.append(f"\n📝 생성: {len(generated)}건")
        for fp, title, sort_order, _ in generated:
            fname = os.path.basename(fp)
            msg_lines.append(f"\n  #{sort_order} {title[:60]} → {fname}")
        msg_lines.append(f"\n🔗 딥링크 연결 완료")
        if skipped:
            msg_lines.append(f"\n⏭ 이미 연결됨: {len(skipped)}건")
        send_telegram("\n".join(msg_lines))
    elif skipped:
        msg_lines = [f"📭 <b>[{today_str}] 블로그 발행</b>"]
        msg_lines.append(f"\n모두 이미 연결됨 ({len(skipped)}건)")
        send_telegram("\n".join(msg_lines))
    else:
        msg_lines = [f"📭 <b>[{today_str}] 블로그 발행</b>"]
        msg_lines.append(f"\n생성된 글 없음 (브리핑 없음)")
        send_telegram("\n".join(msg_lines))
    print()

    # 4. 완료
    log(f"[4/5] 완료! 생성: {len(generated)}건, 스킵(이미연결): {len(skipped)}건")
    for fp, title, sort_order, _ in generated:
        log(f"  ✅ #{sort_order} {title[:60]}")
    for _, title, sort_order, _ in skipped:
        log(f"  ⏭ #{sort_order} {title[:60]} (이미 연결됨)")

    # 5. 사후 검증 (중복 ID, frontmatter 정합성)
    log("[5] 블로그 포스트 검증 중...")
    try:
        import validate_blog_posts as vbp
        if not vbp.validate_all():
            log("  ⚠️ 블로그 포스트 검증 경고 발생 (계속 진행)")
        else:
            log("  ✅ 검증 통과")
    except Exception as e:
        log(f"  ⚠️ 검증 예외: {e}")


if __name__ == "__main__":
    main()
