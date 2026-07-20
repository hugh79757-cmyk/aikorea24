#!/usr/bin/env python3
"""
aikorea24 블로그 아웃라인(재료) 생성기 v2.0
- scripts/thread_topics/keywords.json 기반 키워드 테이블 로딩
- 각 키워드의 db_query 항목으로 D1 뉴스 DB 검색 (오늘 + 어제)
- 매칭 기사 있으면 → 키워드 intent + 기사 내용으로 아웃라인 생성
- 매칭 기사 없으면 → 키워드 intent 만으로 아웃라인 생성 (뉴스 없음 표기)
- scripts/thread_topics/outlines/YYYY-MM-DD-키워드슬러그.md 저장
- 텔레그램 알림
"""
import os, re, json, glob, sys
from datetime import datetime, date, timezone, timedelta

from pipeline.infra.logger import get_scrubbed_logger
logger = get_scrubbed_logger(__name__)

KST = timezone(timedelta(hours=9))

# ============================================
# 경로 / 설정
# ============================================
from pipeline.infra import project_root; PROJECT_DIR = project_root()
sys.path.insert(0, os.path.join(PROJECT_DIR, 'scripts', 'threads', 'v3'))
from model_router import chat_completion
ENV_PATH = os.path.join(PROJECT_DIR, ".env")
KEYWORDS_PATH = os.path.join(PROJECT_DIR, "scripts", "thread_topics", "keywords.json")
OUTLINES_DIR = os.path.join(PROJECT_DIR, "scripts", "thread_topics", "outlines")
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
# keywords.json 로딩
# ============================================
def load_keywords():
    """keywords.json 로드 → {keyword_slug: keyword_info, ...}"""
    if not os.path.exists(KEYWORDS_PATH):
        raise FileNotFoundError(f"keywords.json 없음: {KEYWORDS_PATH}")
    with open(KEYWORDS_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    log(f"키워드 테이블 로드: {len(data)}개 키워드")
    return data

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
# 키워드별 D1 검색 (오늘 + 어제)
# ============================================
def search_articles_for_keyword(db_query_terms):
    """
    db_query 리스트의 각 항목으로 D1 LIKE 검색 (오늘 + 어제)
    중복 제거된 기사 리스트 반환
    """
    today = date.today()
    yesterday = today - timedelta(days=1)
    today_str = today.strftime("%Y-%m-%d")
    yesterday_str = yesterday.strftime("%Y-%m-%d")

    # LIKE 조건 생성 (title 또는 description에 매칭)
    like_clauses = []
    for term in db_query_terms:
        escaped = term.replace("'", "''")
        like_clauses.append(f"(title LIKE '%{escaped}%' OR description LIKE '%{escaped}%')")

    if not like_clauses:
        return []

    where_terms = " OR ".join(like_clauses)
    date_filter = f"DATE(created_at) IN ('{today_str}', '{yesterday_str}')"

    sql = f"""
        SELECT title, description, source, category, link, pub_date
        FROM news
        WHERE ({where_terms})
          AND {date_filter}
          AND category IN ('global', 'news')
        ORDER BY created_at DESC
        LIMIT 20
    """

    try:
        rows = query_d1(sql)
    except Exception as e:
        log(f"  D1 쿼리 실패: {e}")
        return []

    # link 기준 중복 제거
    seen_links = set()
    unique = []
    for r in rows:
        link = r.get("link", "")
        if link and link in seen_links:
            continue
        if link:
            seen_links.add(link)
        unique.append(r)

    return unique

# ============================================
# 아웃라인 생성 (OpenAI) — 기사 있음 버전
# ============================================
def generate_outline_with_articles(keyword_name, intent, articles):
    """매칭된 기사들을 바탕으로 아웃라인 생성"""

    # 기사 텍스트 조립
    article_lines = []
    for i, a in enumerate(articles, 1):
        desc = (a.get("description") or "")[:500]
        article_lines.append(
            f"[기사 {i}]\n"
            f"제목: {a['title']}\n"
            f"출처: {a['source']}\n"
            f"내용: {desc}"
        )
    articles_str = "\n\n".join(article_lines)

    system_prompt = "당신은 콘텐츠 분석 전문가입니다. 아래 [원문]을 읽고 핵심 정보만 추출하여 아웃라인을 작성합니다."

    user_prompt = f"""# 키워드 정보
- 키워드: {keyword_name}
- 검색의도: {intent}

# 절대 규칙
- 원문 문장을 그대로 옮기지 않는다. 정보(수치·날짜·URL)만 추출한다.
- [OUTLINE] 섹션 제목은 반드시 원문 H2 제목과 달라야 한다.
- [FAQ] 질문은 반드시 원문 FAQ 질문과 달라야 한다.
- 아래 출력 형식을 정확히 지켜서 출력한다.
- 형식 외 설명·인사말·코멘트는 일절 출력하지 않는다.

# 출력 형식

## [TOPIC]
핵심 주제를 한 줄로 요약한다. (검색의도를 반영할 것)

## [FACTS]
원문에 등장하는 수치·날짜·고유명사·URL만 추출한다.
(형식: - 항목: 값)

## [TARGET]
원문이 타겟으로 하는 독자층을 한 줄로 분석한다.

## [NEW_TARGET]
원문 독자층과 완전히 다른 새로운 독자층을 한 줄로 제안한다.

## [NEW_ANGLE]
'{intent}' 검색의도를 고려한 새로운 접근 각도를 한 줄로 제안한다.

## [OUTLINE]
새 글의 H2 섹션 제목 3~5개를 제안한다.
'{intent}' 검색의도를 반영한 소제목을 포함할 것.
원문에 없는 새로운 관점의 소제목을 최소 2개 포함한다.
(형식: 1. 제목 / 2. 제목 / ...)

## [FAQ]
[NEW_TARGET] 독자에게 맞는 새로운 질문 3~5개를 제안한다.
'{intent}' 검색의도를 고려한 질문을 포함할 것.
(형식: Q1. 질문 / Q2. 질문 / ...)

## [KEYWORDS]
새 글 SEO 태그 후보 5~8개를 나열한다.
'{keyword_name}'를 첫 번째 태그로 포함할 것.
(형식: 태그1, 태그2, 태그3, ...)

[원문]
{articles_str}"""

    content = chat_completion(
        messages=[{"role": "user", "content": user_prompt}],
        system_prompt=system_prompt,
        max_tokens=1500,
        temperature=0.5,
    )
    if not content:
        log("  ❌ 아웃라인 생성 실패")
        return ""
    log(f"  생성 완료: {len(content)}자")
    return content


# ============================================
# 아웃라인 생성 (OpenAI) — 기사 없음 버전
# ============================================
def generate_outline_no_articles(keyword_name, intent):
    """매칭 기사 없음 → 검색의도만으로 아웃라인 생성"""

    system_prompt = "당신은 콘텐츠 전략 전문가입니다. 주어진 키워드와 검색의도를 바탕으로 블로그 아웃라인을 기획합니다."

    user_prompt = f"""# 키워드 정보
- 키워드: {keyword_name}
- 검색의도: {intent}

※ 현재 이 키워드와 직접 매칭되는 최신 뉴스는 없습니다.
따라서 검색의도에 기반하여 독자에게 가치 있는 콘텐츠를 기획해주세요.

# 출력 형식

## [TOPIC]
이 키워드로 검색하는 독자가 궁금해할 핵심 주제를 한 줄로 요약한다.

## [FACTS]
이 주제와 관련된 상식적인 배경 정보나 일반적인 수치를 제시한다.
(형식: - 항목: 설명)

## [TARGET]
'{intent}' 검색의도를 가진 독자층을 분석한다.

## [NEW_TARGET]
이 키워드에 관심을 가질 또 다른 예상 독자층을 제안한다.

## [NEW_ANGLE]
'{intent}' 검색의도와 다른 새로운 접근 각도를 제안한다.

## [OUTLINE]
'{keyword_name}' 키워드에 관한 블로그 글의 H2 섹션 제목 3~5개를 제안한다.
'{intent}' 검색의도를 충족시키는 구성으로 작성한다.
(형식: 1. 제목 / 2. 제목 / ...)

## [FAQ]
독자가 궁금해할 만한 질문 3~5개를 제안한다.
(형식: Q1. 질문 / Q2. 질문 / ...)

## [KEYWORDS]
SEO 태그 후보 5~8개를 나열한다.
'{keyword_name}'를 첫 번째 태그로 포함할 것.
(형식: 태그1, 태그2, 태그3, ...)"""

    content = chat_completion(
        messages=[{"role": "user", "content": user_prompt}],
        system_prompt=system_prompt,
        max_tokens=1200,
        temperature=0.7,
    )
    if not content:
        log("  ❌ 아웃라인 생성 실패 (뉴스없음)")
        return ""
    log(f"  생성 완료 (뉴스없음): {len(content)}자")
    return content


# ============================================
# 슬러그 생성 (키워드 기준)
# ============================================
def make_slug(keyword_name):
    """키워드명 → 파일명용 슬러그"""
    slug = keyword_name.strip()
    # 특수문자 제거 (공백과 한글/영문/숫자만)
    slug = re.sub(r"[^\w\s가-힣]", "", slug)
    slug = re.sub(r"\s+", "-", slug)
    slug = slug[:60].rstrip("-")
    return slug


# ============================================
# 아웃라인 파일 저장
# ============================================
def save_outline(keyword_name, search_volume, grade, intent, outline_text, articles, today_str):
    date_dir = today_str.replace("-", "")  # 2026-06-10 → 20260610
    outline_date_dir = os.path.join(OUTLINES_DIR, date_dir)
    os.makedirs(outline_date_dir, exist_ok=True)

    now_kst = datetime.now(KST)
    slug = make_slug(keyword_name)
    filename = f"{today_str}-{slug}_outline.md"
    filepath = os.path.join(outline_date_dir, filename)

    article_count = len(articles)

    md = f"""---
키워드: {keyword_name}
검색량: {search_volume:,}
등급: {grade}
매칭기사: {article_count}건
검색의도: {intent}
---

{outline_text}

---
생성일시: {now_kst.strftime('%Y-%m-%d %H:%M:%S %z')}
"""
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(md)
    log(f"  저장: {filename}")
    return filepath, keyword_name


from pipeline.infra.telegram import send_telegram


# ============================================
# 메인
# ============================================
def main():
    load_env()
    today_str = date.today().strftime("%Y-%m-%d")
    log(f"아웃라인 생성 시작 ({today_str})")
    print()

    # 1. keywords.json 로드
    log("[1/5] keywords.json 로드 중...")
    try:
        keywords = load_keywords()
    except Exception as e:
        log(f"  keywords.json 로드 실패: {e}")
        send_telegram(f"❌ [{today_str}] 아웃라인 생성 실패: keywords.json 로드 오류")
        sys.exit(1)

    if not keywords:
        log("  키워드 테이블이 비어 있음, 종료")
        return
    print()

    # 2. 각 키워드별 D1 검색
    log("[2/5] 키워드별 D1 검색 중...")
    keyword_results = []  # (keyword_name, search_volume, grade, intent, articles)
    no_match_keywords = []  # (keyword_name, search_volume, grade, intent)
    total_with_articles = 0

    for kw_name, kw_info in keywords.items():
        db_query_terms = kw_info.get("db_query", [])
        if not db_query_terms:
            log(f"  ⏭ '{kw_name}': db_query 없음, 스킵")
            continue

        log(f"  → '{kw_name}' 검색 중... (쿼리: {db_query_terms[0]}{' 외 N개' if len(db_query_terms) > 1 else ''})")
        articles = search_articles_for_keyword(db_query_terms)

        if articles:
            keyword_results.append((
                kw_name,
                kw_info.get("search_volume", 0),
                kw_info.get("grade", "C"),
                kw_info.get("intent", ""),
                articles
            ))
            total_with_articles += 1
            log(f"    ✓ {len(articles)}건 매칭")
        else:
            no_match_keywords.append((
                kw_name,
                kw_info.get("search_volume", 0),
                kw_info.get("grade", "C"),
                kw_info.get("intent", ""),
            ))
            log(f"    ✗ 매칭 없음")

    log(f"\n  검색 결과: 매칭 {total_with_articles}개 / 미매칭 {len(no_match_keywords)}개")
    print()

    # 3. 등급순 정렬 (S > A > B > ...)
    grade_order = {"S": 0, "A": 1, "B": 2, "C": 3, "D": 4}
    def sort_key(item):
        kw_name, sv, grade, intent, articles = item
        return (grade_order.get(grade, 99), -sv)
    keyword_results.sort(key=sort_key)

    def sort_key_no_match(item):
        kw_name, sv, grade, intent = item
        return (grade_order.get(grade, 99), -sv)
    no_match_keywords.sort(key=sort_key_no_match)

    # 4. 아웃라인 생성
    log("[3/5] 아웃라인 생성 중...")
    created = []

    # 4a. 기사 있음 → intent + 기사로 생성
    for kw_name, sv, grade, intent, articles in keyword_results:
        log(f"  → [{grade}] '{kw_name}' (매칭 {len(articles)}건, 검색량 {sv:,})")
        try:
            outline = generate_outline_with_articles(kw_name, intent, articles)
            filepath, name = save_outline(kw_name, sv, grade, intent, outline, articles, today_str)
            created.append((filepath, name, len(articles), grade))
        except Exception as e:
            log(f"  ❌ '{kw_name}' 생성 실패: {e}")

    # 4b. 기사 없음 → intent만으로 생성
    for kw_name, sv, grade, intent in no_match_keywords:
        log(f"  → [{grade}] '{kw_name}' (뉴스 없음, 검색량 {sv:,})")
        try:
            outline = generate_outline_no_articles(kw_name, intent)
            filepath, name = save_outline(kw_name, sv, grade, intent, outline, [], today_str)
            created.append((filepath, name, 0, grade))
        except Exception as e:
            log(f"  ❌ '{kw_name}' 생성 실패: {e}")
    print()

    # 5. 텔레그램 알림
    log("[4/5] 텔레그램 알림...")
    if created:
        with_articles = [c for c in created if c[2] > 0]
        without_articles = [c for c in created if c[2] == 0]

        msg_lines = [f"📝 <b>[{today_str}] 아웃라인 생성 완료 ({len(created)}건)</b>"]
        if with_articles:
            msg_lines.append(f"\n📰 기사 기반 ({len(with_articles)}건):")
            for fp, name, cnt, grade in with_articles:
                fname = os.path.basename(fp)
                msg_lines.append(f"  [{grade}] <b>{name}</b> ({cnt}건)")
        if without_articles:
            msg_lines.append(f"\n📌 뉴스 없음·의도 기반 ({len(without_articles)}건):")
            for fp, name, cnt, grade in without_articles:
                fname = os.path.basename(fp)
                msg_lines.append(f"  [{grade}] <b>{name}</b>")
        send_telegram("\n".join(msg_lines))
    else:
        send_telegram(f"❌ [{today_str}] 아웃라인 생성 실패 (모든 키워드 실패)")
    print()

    # 완료
    log("[5/5] 완료!")
    log(f"  총 생성: {len(created)}건")
    with_articles = [c for c in created if c[2] > 0]
    without_articles = [c for c in created if c[2] == 0]
    if with_articles:
        log(f"  기사 기반: {len(with_articles)}건")
        for fp, name, cnt, grade in with_articles:
            log(f"    ✅ [{grade}] {os.path.basename(fp)} ({cnt}건)")
    if without_articles:
        log(f"  의도 기반(뉴스 없음): {len(without_articles)}건")
        for fp, name, cnt, grade in without_articles:
            log(f"    📌 [{grade}] {os.path.basename(fp)} (뉴스 없음)")


if __name__ == "__main__":
    main()
