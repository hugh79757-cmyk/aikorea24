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

KST = timezone(timedelta(hours=9))

# ============================================
# 고단가 키워드 테이블
# ============================================
KEYWORDS = {
    "A": ["챗GPT", "ChatGPT", "OpenAI", "클로드", "Anthropic", "AI에이전트", "AI 에이전트"],
    "B": ["엔비디아", "NVIDIA", "제미나이", "Gemini", "생성형AI", "생성형 AI", "GPT", "딥시크"],
    "C": ["인공지능", "LLM", "AI자동화", "AI 자동화", "AI반도체", "AI 반도체", "코파일럿"],
}
GRADE_SCORE = {"A": 100, "B": 60, "C": 30}

# ============================================
# 경로 / 설정
# ============================================
PROJECT_DIR = "/Users/twinssn/Projects/aikorea24"
ENV_PATH = os.path.join(PROJECT_DIR, ".env")
DB_ID = "bec650ce-f732-46bc-87c0-bd76ed17e42a"

# ============================================
# 로깅
# ============================================
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
# D1 쿼리 (REST API)
# ============================================
def query_d1(sql):
    import requests
    account_id = os.environ.get("CLOUDFLARE_ACCOUNT_ID", "")
    api_token = os.environ.get("CLOUDFLARE_API_TOKEN", "")
    if not account_id or not api_token:
        raise RuntimeError("CLOUDFLARE_ACCOUNT_ID 또는 CLOUDFLARE_API_TOKEN 없음")
    url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/d1/database/{DB_ID}/query"
    r = requests.post(url,
        headers={"Authorization": f"Bearer {api_token}", "Content-Type": "application/json"},
        json={"sql": sql}
    )
    data = r.json()
    if not data.get("success"):
        raise RuntimeError(f"D1 query failed: {data.get('errors')}")
    return data["result"][0]["results"]

# ============================================
# 오늘 뉴스 조회
# ============================================
def get_today_articles():
    """오늘 수집된 글로벌/국내 AI 뉴스 조회"""
    today = date.today().strftime("%Y-%m-%d")
    sql = f"""
        SELECT title, description, source, category, link
        FROM news
        WHERE DATE(created_at) = '{today}'
          AND category IN ('global', 'news')
        ORDER BY
          CASE category WHEN 'global' THEN 0 ELSE 1 END,
          created_at DESC
    """
    rows = query_d1(sql)
    log(f"오늘 수집 기사: {len(rows)}건")
    return rows

# ============================================
# 키워드 매칭
# ============================================
def match_keywords(articles):
    """기사 제목/설명에서 고단가 키워드 매칭 → 키워드별 그룹"""
    matches = {}
    for a in articles:
        text = (a["title"] + " " + (a.get("description") or "")).upper()
        for grade in ["A", "B", "C"]:
            for kw in KEYWORDS[grade]:
                if kw.upper() in text:
                    if kw not in matches:
                        matches[kw] = {"articles": [], "grade": grade, "score": GRADE_SCORE[grade]}
                    matches[kw]["articles"].append(a)
    log(f"매칭된 키워드: {len(matches)}개")
    return matches

# ============================================
# 블로그 초안 생성 (OpenAI)
# ============================================
def generate_draft(keyword, articles, grade):
    from openai import OpenAI
    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
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
            "주어진 기사 하나를 깊이 분석하여 블로그 초안을 작성해주세요."
        )
        user_prompt = (
            f"아래 '{keyword}' 관련 기사를 분석한 블로그 초안을 작성해주세요.\n\n"
            f"## 요구사항\n"
            f"- 제목: '{keyword}' 키워드가 자연스럽게 포함된 SEO 최적화 제목\n"
            f"- 본문: 1500자 이상, 소제목(##) 3개 이상 포함\n"
            f"- 기사의 배경/의미/전망을 분석, 독자가 쉽게 이해할 수 있도록\n"
            f"- 마지막에 📌 **요약** 섹션 포함\n"
            f"- 순한국어, 전문적이면서도 친근한 어조\n\n"
            f"## 출력 형식\n"
            f"TITLE: [SEO에 최적화된 제목]\n"
            f"---\n"
            f"[마크다운 본문]\n\n"
            f"## 기사\n{articles_str}"
        )
    else:
        system_prompt = (
            "당신은 AI/테크 뉴스를 분석하는 한국어 블로거입니다. "
            "여러 기사를 종합하여 트렌드 분석 블로그 초안을 작성해주세요."
        )
        user_prompt = (
            f"아래 '{keyword}' 관련 여러 기사를 종합한 블로그 초안을 작성해주세요.\n\n"
            f"## 요구사항\n"
            f"- 제목: '{keyword}' 관련 트렌드가 드러나는 SEO 최적화 제목\n"
            f"- 본문: 2000자 이상, 소제목(##) 3개 이상 포함\n"
            f"- 각 기사의 핵심 내용을 비교/종합하여 트렌드 분석\n"
            f"- 마지막에 📌 **요약** 섹션 포함\n"
            f"- 순한국어, 전문적이면서도 친근한 어조\n\n"
            f"## 출력 형식\n"
            f"TITLE: [SEO에 최적화된 제목]\n"
            f"---\n"
            f"[마크다운 본문]\n\n"
            f"## 기사들\n{articles_str}"
        )

    resp = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        max_completion_tokens=3000,
        temperature=0.7,
    )
    content = resp.choices[0].message.content.strip()
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
    return slug.lower() if slug.isascii() else slug

# ============================================
# 블로그 파일 저장
# ============================================
def save_draft(gpt_output, keyword, file_num, today_str):
    """GPT 출력 파싱 → .md 파일 저장"""
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

    # description: 앞 150자 평문
    desc_raw = re.sub(r"[#*>\n\s]+", " ", content)[:150].strip()

    now_kst = datetime.now(KST)
    date_str = now_kst.strftime("%Y-%m-%dT%H:%M:%S+09:00")

    md = f"""---
title: "{seo_title}"
description: "{desc_raw}"
date: {date_str}
category: "뉴스"
tags:
  - "{keyword}"
draft: false
image: "/images/{slug}/thumbnail.webp"
---

{content}
"""
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(md)
    log(f"  저장: {filename}")
    return filepath, seo_title

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

    # 1. 오늘 뉴스 조회
    log("[1/5] 뉴스 조회 중...")
    try:
        articles = get_today_articles()
    except Exception as e:
        log(f"  뉴스 조회 실패: {e}")
        send_telegram(f"❌ [{today_str}] 블로그 초안 생성 실패: 뉴스 조회 오류")
        sys.exit(1)

    if not articles:
        log("  오늘 수집된 기사 없음, 종료")
        send_telegram(f"📭 [{today_str}] 블로그 초안 생성 스킵: 수집된 기사 없음")
        return
    print()

    # 2. 키워드 매칭
    log("[2/5] 키워드 매칭 중...")
    matches = match_keywords(articles)
    if not matches:
        log("  매칭된 고단가 키워드 없음, 종료")
        send_telegram(f"📭 [{today_str}] 블로그 초안 생성 스킵: 매칭 키워드 없음")
        return

    # 통계 출력
    for grade in ["A", "B", "C"]:
        grade_matches = {k: v for k, v in matches.items() if v["grade"] == grade}
        if grade_matches:
            for kw, info in sorted(grade_matches.items(), key=lambda x: -x[1]["score"]):
                log(f"  [{grade}] {kw} ({len(info['articles'])}건, {info['score']}점)")
    print()

    # 3. 점수순 정렬 후 생성 (최대 5개)
    log("[3/5] 블로그 초안 생성 중...")
    sorted_matches = sorted(matches.items(), key=lambda x: -x[1]["score"])
    file_num = next_file_number(today_str)
    created = []

    for kw, info in sorted_matches[:5]:
        art_count = len(info["articles"])
        dtype = "심층형" if art_count == 1 else "종합형"
        log(f"  → [{info['grade']}] '{kw}' ({dtype}, {art_count}건)")
        try:
            gpt_output = generate_draft(kw, info["articles"], info["grade"])
            filepath, seo_title = save_draft(gpt_output, kw, file_num, today_str)
            created.append((filepath, seo_title, kw, art_count))
            file_num += 1
        except Exception as e:
            log(f"  ❌ '{kw}' 생성 실패: {e}")
    print()

    # 4. 텔레그램 알림
    log("[4/5] 텔레그램 알림...")
    if created:
        msg_lines = [f"🤖 <b>[{today_str}] 블로그 초안 생성 완료</b>"]
        for fp, title, kw, cnt in created:
            fname = os.path.basename(fp)
            msg_lines.append(f"\n📄 <b>{kw}</b> ({cnt}건) → {title}")
            msg_lines.append(f"   file://{fp}")
        send_telegram("\n".join(msg_lines))
    else:
        send_telegram(f"❌ [{today_str}] 블로그 초안 생성 실패 (모든 키워드 실패)")
    print()

    # 5. 완료
    log(f"[5/5] 완료! {len(created)}건 생성")
    for fp, title, kw, cnt in created:
        log(f"  ✅ {os.path.basename(fp)}")


if __name__ == "__main__":
    main()
