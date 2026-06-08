#!/usr/bin/env python3
"""
aikorea24 블로그 아웃라인(재료) 추출기
- D1 DB에서 오늘 수집된 뉴스 중 고단가 키워드 포함 기사 조회
- 기사별로 아웃라인 추출 (OpenAI)
- scripts/outlines/YYYY-MM-DD-슬러그.md 로 저장
- 텔레그램 알림
"""
import os, re, json, glob, sys
from datetime import datetime, date, timezone, timedelta

KST = timezone(timedelta(hours=9))

# ============================================
# 고단가 키워드 테이블 (blog_draft_generator와 동일)
# ============================================
KEYWORDS = {
    "A": ["챗GPT", "ChatGPT", "OpenAI", "클로드", "Anthropic", "AI에이전트", "AI 에이전트"],
    "B": ["엔비디아", "NVIDIA", "제미나이", "Gemini", "생성형AI", "생성형 AI", "GPT", "딥시크"],
    "C": ["인공지능", "LLM", "AI자동화", "AI 자동화", "AI반도체", "AI 반도체", "코파일럿"],
}
GRADE_SCORE = {"A": 100, "B": 60, "C": 30}
GRADE_ORDER = {"A": 0, "B": 1, "C": 2}  # 낮을수록 우선

# ============================================
# 경로 / 설정
# ============================================
PROJECT_DIR = "/Users/twinssn/Projects/aikorea24"
ENV_PATH = os.path.join(PROJECT_DIR, ".env")
OUTLINES_DIR = os.path.join(PROJECT_DIR, "scripts", "outlines")
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
    """오늘 수집된 글로벌/국내 AI 뉴스 조회 (title + description + original_title)"""
    today = date.today().strftime("%Y-%m-%d")
    sql = f"""
        SELECT title, description, source, category, link, pub_date, original_title
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
# 키워드 매칭 (기사당 최고 등급 1개만)
# ============================================
def match_articles_to_keywords(articles):
    """
    각 기사에 대해 매칭되는 키워드 중 최고 등급 1개 선택.
    returns: [(article, best_keyword, best_grade), ...]
    """
    result = []
    for a in articles:
        text = (a["title"] + " " + (a.get("description") or "")).upper()
        best_kw = None
        best_grade = None
        for grade in ["A", "B", "C"]:
            for kw in KEYWORDS[grade]:
                if kw.upper() in text:
                    if best_grade is None or GRADE_ORDER.get(grade, 99) < GRADE_ORDER.get(best_grade, 99):
                        best_kw = kw
                        best_grade = grade
        if best_kw:
            result.append((a, best_kw, best_grade))
    log(f"키워드 매칭 기사: {len(result)}건")
    # 등급순 정렬
    result.sort(key=lambda x: GRADE_ORDER.get(x[2], 99))
    return result

# ============================================
# 아웃라인 추출 (OpenAI)
# ============================================
def extract_outline(article, keyword, grade):
    from openai import OpenAI
    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

    title = article["title"]
    description = article.get("description") or ""
    source = article["source"]
    link = article.get("link", "")
    original_title = article.get("original_title") or ""

    # 원문 조립: title + original_title(해외기사) + description
    raw_parts = [f"제목: {title}"]
    if original_title and original_title != title:
        raw_parts.append(f"원제목: {original_title}")
    raw_parts.append(f"출처: {source}")
    if link:
        raw_parts.append(f"URL: {link}")
    if description:
        raw_parts.append(f"\n본문:\n{description}")

    raw_text = "\n".join(raw_parts)

    system_prompt = "당신은 콘텐츠 분석 전문가입니다. 아래 [원문]을 읽고 핵심 정보만 추출하여 아웃라인을 작성합니다."

    user_prompt = f"""# 절대 규칙
- 원문 문장을 그대로 옮기지 않는다. 정보(수치·날짜·URL)만 추출한다.
- [OUTLINE] 섹션 제목은 반드시 원문 H2 제목과 달라야 한다.
- [FAQ] 질문은 반드시 원문 FAQ 질문과 달라야 한다.
- 아래 출력 형식을 정확히 지켜서 출력한다.
- 형식 외 설명·인사말·코멘트는 일절 출력하지 않는다.

# 출력 형식

## [TOPIC]
원문의 핵심 주제를 한 줄로 요약한다.

## [FACTS]
원문에 등장하는 수치·날짜·고유명사·URL만 추출한다.
(형식: - 항목: 값)

## [TARGET]
원문이 타겟으로 하는 독자층을 한 줄로 분석한다.

## [NEW_TARGET]
원문 독자층과 완전히 다른 새로운 독자층을 한 줄로 제안한다.

## [NEW_ANGLE]
원문의 공감 포인트와 다른 새로운 접근 각도를 한 줄로 제안한다.

## [OUTLINE]
새 글의 H2 섹션 제목 3~5개를 제안한다.
주의: 원문 H2 제목을 그대로 쓰거나 유사하게 쓰는 것은 금지한다.
원문에 없는 새로운 관점의 소제목을 최소 2개 포함한다.
(형식: 1. 제목 / 2. 제목 / ...)

## [FAQ]
[NEW_TARGET] 독자에게 맞는 새로운 질문 3~5개를 제안한다.
주의: 원문 FAQ 질문을 그대로 쓰거나 유사하게 쓰는 것은 금지한다.
(형식: Q1. 질문 / Q2. 질문 / ...)

## [KEYWORDS]
새 글 SEO 태그 후보 5~8개를 나열한다.
원문 tags를 그대로 복사하지 않는다.
(형식: 태그1, 태그2, 태그3, ...)

[원문]
{raw_text}"""

    resp = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        max_completion_tokens=1500,
        temperature=0.5,
    )
    content = resp.choices[0].message.content.strip()
    log(f"  추출 완료: {len(content)}자")
    return content

# ============================================
# 슬러그 생성 (기사 title에서 핵심 키워드 3~4개)
# ============================================
def make_slug(title, keyword):
    # keyword를 기준으로 삼고 title에서 추가 키워드 보강
    # 불용어 제거 후 명사 위주 추출
    stop_words = {"the", "a", "an", "of", "in", "on", "at", "to", "for", "with",
                  "and", "or", "is", "are", "was", "were", "be", "been", "has", "have",
                  "had", "do", "does", "did", "will", "would", "could", "should",
                  "may", "might", "this", "that", "these", "those", "it", "its",
                  "수", "위", "중", "내", "간", "등", "및", "향", "약", "최대",
                  "대한", "통한", "위한", "기반", "통해", "통한", "관련", "이용",
                  "차지", "기록", "선정", "달성", "발표", "공개", "출시", "확보",
                  "구축", "도입", "시작", "추진", "개발", "제공", "공개", "발표"}

    # keyword는 무조건 포함
    slug_parts = [keyword]

    # title에서 추가 토큰 추출
    # 한글/영단어 분리
    tokens = re.findall(r'[가-힣]{2,}|[A-Za-z][a-z]*', title)

    # 불용어 제거, keyword 중복 제거, 너무 짧은 토큰 제거
    for t in tokens:
        t_lower = t.lower()
        if t_lower in stop_words:
            continue
        if len(t) <= 1:
            continue
        if t.lower() == keyword.lower():
            continue
        if t.lower() in keyword.lower():
            continue
        if len(slug_parts) >= 4:
            break
        # 중복 체크
        if not any(t.lower() in p.lower() or p.lower() in t.lower() for p in slug_parts):
            slug_parts.append(t)

    slug = "-".join(slug_parts)
    slug = re.sub(r'[^\w\s가-힣-]', '', slug)
    slug = re.sub(r'\s+', '-', slug)
    slug = slug[:80].rstrip("-")
    return slug

# ============================================
# 아웃라인 파일 저장
# ============================================
def save_outline(article, outline_text, keyword, grade, today_str):
    os.makedirs(OUTLINES_DIR, exist_ok=True)

    title = article["title"]
    source = article["source"]
    pub_date = article.get("pub_date", "")
    link = article.get("link", "")
    now_kst = datetime.now(KST)

    slug = make_slug(title, keyword)
    filename = f"{today_str}-{slug}.md"
    filepath = os.path.join(OUTLINES_DIR, filename)

    md = f"""# {title}

> 원문 출처: {source} | {pub_date} | {link}
> 매칭 키워드: {keyword} ({grade}등급)

{outline_text}

---
생성일시: {now_kst.strftime('%Y-%m-%d %H:%M:%S %z')}
"""
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(md)
    log(f"  저장: {filename}")
    return filepath, title

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
    log(f"아웃라인 추출 시작 ({today_str})")
    print()

    # 1. 오늘 뉴스 조회
    log("[1/4] 뉴스 조회 중...")
    try:
        articles = get_today_articles()
    except Exception as e:
        log(f"  뉴스 조회 실패: {e}")
        send_telegram(f"❌ [{today_str}] 아웃라인 추출 실패: 뉴스 조회 오류")
        sys.exit(1)

    if not articles:
        log("  오늘 수집된 기사 없음, 종료")
        send_telegram(f"📭 [{today_str}] 아웃라인 추출 스킵: 수집된 기사 없음")
        return
    print()

    # 2. 키워드 매칭 (기사당 최고 등급 1개)
    log("[2/4] 키워드 매칭 중...")
    matched = match_articles_to_keywords(articles)
    if not matched:
        log("  매칭된 고단가 키워드 없음, 종료")
        send_telegram(f"📭 [{today_str}] 아웃라인 추출 스킵: 매칭 키워드 없음")
        return

    # 등급별 통계
    grade_counts = {"A": 0, "B": 0, "C": 0}
    for _, _, g in matched:
        grade_counts[g] = grade_counts.get(g, 0) + 1
    for g in ["A", "B", "C"]:
        if grade_counts[g]:
            log(f"  [{g}] {grade_counts[g]}건")
    print()

    # 3. 아웃라인 추출
    log("[3/4] 아웃라인 추출 중...")
    created = []
    for article, keyword, grade in matched:
        title_short = article["title"][:50]
        log(f"  → [{grade}] '{title_short}...'")
        try:
            outline = extract_outline(article, keyword, grade)
            filepath, orig_title = save_outline(article, outline, keyword, grade, today_str)
            created.append((filepath, orig_title, keyword, grade))
        except Exception as e:
            log(f"  ❌ '{title_short}' 추출 실패: {e}")
    print()

    # 4. 텔레그램 알림
    log("[4/4] 텔레그램 알림...")
    if created:
        msg_lines = [f"📝 <b>[{today_str}] 아웃라인 추출 완료 ({len(created)}건)</b>"]
        for fp, title, kw, grade in created:
            fname = os.path.basename(fp)
            title_short = title[:40] + ("…" if len(title) > 40 else "")
            msg_lines.append(f"\n📄 [{grade}] <b>{kw}</b> — {title_short}")
        send_telegram("\n".join(msg_lines))
    else:
        send_telegram(f"❌ [{today_str}] 아웃라인 추출 실패 (모든 기사 실패)")
    print()

    # 완료
    log(f"완료! {len(created)}건 생성")
    for fp, title, kw, grade in created:
        log(f"  ✅ {os.path.basename(fp)}")


if __name__ == "__main__":
    main()
