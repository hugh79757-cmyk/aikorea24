#!/Users/twinssn/Projects/aikorea24/.venv/bin/python3
"""
aikorea24 스레드 글감 파인더 v1.0
- 오늘 뉴스 → 주제별 클러스터링 → 스레드 아웃라인 생성
- scripts/thread_topics/topics/YYYY-MM-DD-소재슬러그_thread.md 저장
"""
import os, re, json, sys, time
from datetime import datetime, date, timezone, timedelta
from typing import Any

_script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_script_dir, '..', '..'))
sys.path.insert(0, os.path.join(_script_dir, '..', '..', 'scripts', 'threads', 'v3'))

from pipeline.infra.logger import get_scrubbed_logger
from pipeline.infra.telegram import send_telegram
logger = get_scrubbed_logger(__name__)
from pipeline.infra import project_root; PROJECT_DIR = project_root()

KST = timezone(timedelta(hours=9))
from model_router import chat_completion
ENV_PATH = os.path.join(PROJECT_DIR, ".env")
THREADS_DIR = os.path.join(PROJECT_DIR, "scripts", "thread_topics", "topics")
DB_ID = "bec650ce-f732-46bc-87c0-bd76ed17e42a"

# 해외 주요 매체 목록 (source 기준)
FOREIGN_SOURCES = {
    "TechCrunch", "VentureBeat", "Reuters", "BBC", "CNN",
    "The Guardian", "Wired", "MIT Technology Review",
    "ArsTechnica", "Bloomberg", "Fast Company AI",
    "Financial Times AI", "Financial Times",
}


# ============================================
# 로깅
# ============================================
def log(msg: str) -> None:
    ts = datetime.now(KST).strftime("%H:%M:%S")
    print(f"[{ts}] {msg}")


# ============================================
# 환경변수 로딩
# ============================================
def load_env() -> None:
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

def query_d1(sql: str) -> list[dict]:
    import subprocess, json, re
    cmd = [_WRANGLER, "d1", "execute", _DB, "--remote", "--command", sql]
    env = dict(os.environ)
    env.pop("CLOUDFLARE_API_TOKEN", None)
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=30, env=env, cwd=PROJECT_DIR)
        if r.returncode != 0:
            raise RuntimeError(f"wrangler D1 error (rc={r.returncode}): {r.stderr[:200]}")
        m = re.search(r'"results"\s*:\s*(\[.*?\])\s*,\s*"success"', r.stdout, re.DOTALL)
        return json.loads(m.group(1)) if m else []
    except json.JSONDecodeError:
        return []
    except Exception as e:
        raise RuntimeError(f"D1 query failed: {e}")


# ============================================
# 해외/국내 판별
# ============================================
def classify_source(source: str) -> str:
    """source 문자열로 해외/국내 구분"""
    if source in FOREIGN_SOURCES:
        return "해외"
    # source에 영문 매체명이 포함되어 있는지 추가 체크
    source_lower = source.lower()
    foreign_keywords = ["techcrunch", "venturebeat", "reuters", "bbc", "cnn",
                        "the guardian", "guardian", "wired", "mit technology",
                        "arstechnica", "bloomberg", "nytimes", "new york times",
                        "washington post", "wsj", "wall street journal",
                        "forbes", "business insider", "ap news", "associated press",
                        "fast company", "financial times", "ft.com"]
    for kw in foreign_keywords:
        if kw in source_lower:
            return "해외"
    return "국내"


# ============================================
# STEP 1: D1에서 오늘 뉴스 로드
# ============================================
def load_today_news() -> tuple[list[dict], str]:
    """오늘+어제 날짜 기사 동시 조회 (UTC 시차 대응)"""
    today = date.today()
    yesterday = today - timedelta(days=1)
    today_str = today.strftime("%Y-%m-%d")
    yesterday_str = yesterday.strftime("%Y-%m-%d")

    sql = f"""
        SELECT id, title, description, source, link, pub_date
        FROM news
        WHERE DATE(created_at) IN ('{today_str}', '{yesterday_str}')
          AND category IN ('global', 'news')
          AND title IS NOT NULL
        ORDER BY created_at DESC
        LIMIT 200
    """
    try:
        rows = query_d1(sql)
    except Exception as e:
        log(f"  D1 쿼리 실패: {e}")
        return [], ""

    if rows:
        log(f"D1 조회: {today_str} / {yesterday_str} ({len(rows)}건)")
        return rows, today_str

    log("  오늘/어제 기사 없음")
    return [], ""


# ============================================
# STEP 2: OpenAI 기사 클러스터링 (1차 - title only)
# ============================================
def cluster_articles(articles: list[dict]) -> list[dict]:
    """gpt-4o-mini로 title 기반 클러스터링 (최대 10개 클러스터)"""
    from openai import OpenAI
    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

    # 기사 목록 문자열 조립 (id + title + source + 해외/국내)
    article_lines = []
    for a in articles:
        region = classify_source(a.get("source", ""))
        title = (a.get("title") or "")[:200]
        article_lines.append(
            f'ID:{a["id"]} | [{region}] {title} (출처: {a.get("source", "")})'
        )

    articles_str = "\n".join(article_lines)

    system_prompt = (
        "You are a news clustering specialist. "
        "Group news articles by topic, connecting related stories across sources. "
        "Output valid JSON only."
    )

    user_prompt = f"""아래 오늘의 뉴스 기사 목록을 분석하여 같은 주제로 묶을 수 있는 클러스터를 찾아주세요.

# 필수 확인 — 먼저 아래 질문에 "예"라고 답할 수 있어야만 클러스터로 묶으세요
→ "왜 이 기사들이 연결되는가?"를 한 문장으로 설명할 수 있는가?

# 클러스터링 인정 조건 (아래 중 하나는 반드시 충족)
1. 같은 사건/현상을 다룬 기사 (예: 같은 제품 출시를 국내외에서 보도)
2. 원인-결과 관계가 있는 기사 (예: 미국 규제 → 한국 반도체 영향)
3. 명확한 대비 구조 (예: 미국은 금지, 한국은 허용)

# 금지 규칙
- 표면적 키워드(AI, 규제, 기술, 법률, 데이터)만 겹친다고 같은 클러스터로 묶지 말 것
- 실제 인과관계/대비구조/동일사건 중 하나가 없으면 절대 클러스터로 인정하지 말 것
- 확신이 없으면 묶지 말 것. 억지로 묶은 클러스터는 점수 0점보다 나쁨

# 기타 규칙
- 해외 기사 + 국내 기사가 같은 주제면 반드시 같은 클러스터로 묶으세요
- 클러스터당 최소 2개 기사 (단독 기사는 제외)
- 최대 10개 클러스터까지 출력
- 뻔한 주제 말고, 독자가 흥미로워할 연결고리를 발견하세요

# 기사 목록
{articles_str}

# 출력 형식 (반드시 JSON)
{{
  "clusters": [
    {{
      "topic": "클러스터 주제 (한 줄, 구체적으로)",
      "connection": "두 기사를 묶는 핵심 연결고리 (한 줄)",
      "article_ids": [정수 ID들],
      "has_foreign": true 또는 false,
      "has_domestic": true 또는 false,
      "contrast_possible": true 또는 false (해외vs국내 시각차이나 대비가 가능한지),
      "data_points": ["기사에서 발견한 핵심 수치/데이터"]
    }}
  ]
}}"""

    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        response_format={"type": "json_object"},
        max_completion_tokens=4000,
        temperature=0.3,
    )

    content = resp.choices[0].message.content.strip()
    try:
        data = json.loads(content)
        clusters = data.get("clusters", [])
        log(f"클러스터링 완료: {len(clusters)}개 클러스터 발견")
        return clusters
    except json.JSONDecodeError:
        log(f"  OpenAI 응답 파싱 실패: {content[:200]}")
        return []


# ============================================
# STEP 3: 스코어링 (소재 우선순위)
# ============================================
def score_clusters(clusters: list[dict]) -> list[dict]:
    """
    스코어링 기준:
    - 해외 + 국내 교차: +3점
    - data_points 3개 이상: +2점
    - contrast_possible == true: +2점
    - 클러스터 기사 수 3개 이상: +1점
    """
    scored = []
    for c in clusters:
        score = 0
        article_ids = c.get("article_ids", [])
        data_points = c.get("data_points", [])

        # 해외+국내 교차
        if c.get("has_foreign") and c.get("has_domestic"):
            score += 3

        # data_points 3개 이상
        if len(data_points) >= 3:
            score += 2

        # contrast_possible
        if c.get("contrast_possible"):
            score += 2

        # 기사 3개 이상
        if len(article_ids) >= 3:
            score += 1

        scored.append({
            "topic": c.get("topic", ""),
            "connection": c.get("connection", ""),
            "article_ids": article_ids,
            "has_foreign": c.get("has_foreign", False),
            "has_domestic": c.get("has_domestic", False),
            "contrast_possible": c.get("contrast_possible", False),
            "data_points": data_points,
            "score": score,
        })

    # 점수 내림차순 정렬 → 상위 5개
    scored.sort(key=lambda x: -x["score"])
    top = scored[:5]

    log(f"스코어링 완료: 상위 {len(top)}개 선택")
    for i, c in enumerate(top, 1):
        log(f"  {i}. [{c['score']}점] {c['topic']} (기사 {len(c['article_ids'])}개)")

    return top


# ============================================
# STEP 4: 스레드 아웃라인 생성 (2차 - gpt-4o)
# ============================================
def generate_thread_outline(
    cluster: dict,
    articles_map: dict[int, dict],
) -> str:
    """MiMo v2.5로 클러스터별 스레드 아웃라인 생성 (description 포함)"""

    article_ids = cluster["article_ids"]
    data_points = cluster.get("data_points", [])

    # 클러스터 기사 본문 조립
    article_lines = []
    for aid in article_ids:
        a = articles_map.get(aid)
        if not a:
            continue
        region = classify_source(a.get("source", ""))
        title = (a.get("title") or "").strip()
        desc = (a.get("description") or "").strip()[:500]
        source = a.get("source", "")
        link = a.get("link", "")
        pub_date = a.get("pub_date", "")
        article_lines.append(
            f"[{region}] {title}\n"
            f"출처: {source} | 날짜: {pub_date} | URL: {link}\n"
            f"내용: {desc}"
        )

    articles_str = "\n\n---\n\n".join(article_lines)
    data_points_str = "\n".join(f"- {dp}" for dp in data_points) if data_points else "없음"

    system_prompt = (
        "You are a thread/social media content strategist. "
        "Create engaging thread outlines for Korean Naver/Instagram audiences. "
        "Focus on connecting dots that readers wouldn't notice on their own."
    )

    user_prompt = f"""# 주제
{cluster['topic']}

# 연결고리
{cluster['connection']}

# 핵심 수치 (참고용)
{data_points_str}

# 기사 원문
{articles_str}

---

위 정보를 바탕으로 아래 마크다운 형식의 스레드 아웃라인을 작성해주세요.

## 출력 형식

## 📰 원문 기사
(클러스터에 포함된 기사 전부 나열)
- [해외 or 국내] 제목 / 출처 / 날짜 / URL

## 🔗 연결고리
두 기사를 관통하는 핵심 키워드 또는 공통 주제 한 줄

## ❓ 독자가 궁금해할 포인트
Q1.
Q2.
Q3.
Q4.
Q5.
(독자 입장에서 이 주제로 가장 궁금해할 질문. 뻔한 질문 금지)

## 📊 핵심 수치/데이터
- 수치와 출처 함께 표기
- 독자가 체감할 수 있는 비유로 변환 가능하면 추가

## 🧵 스레드 아웃라인
1. 훅: (왜?/반전/충격적 사실로 시작. 한 줄)
2. 반대 질문: (독자가 당연히 품을 반론이나 의문)
3. 데이터 근거: (핵심 수치로 뒷받침)
4. 대비 구조: (A는 이렇고 B는 저렇다)
5. 반전 포인트: (독자가 몰랐던 연결고리)
6. 결론: (한 줄 요약)
7. 귀환: (처음 질문의 답으로 마무리)

※ 위 7단계 레이블은 반드시 출력하되, 내용은 주제에 맞게 gpt-4o가 판단하여 유연하게 변형 가능

## 🏷 추천 해시태그
(5개 이내, 네이버/인스타 검색 기준)"""

    content = chat_completion(
        messages=[{"role": "user", "content": user_prompt}],
        system_prompt=system_prompt,
        max_tokens=3000,
        temperature=0.6,
    )
    if not content:
        log("  ❌ 아웃라인 생성 실패")
        return ""

    log(f"  아웃라인 생성 완료: {len(content)}자")
    return content


# ============================================
# STEP 5: md 파일 저장
# ============================================
def make_slug(topic: str) -> str:
    """topic → 파일명 슬러그 (최대 30자)"""
    # 특수문자 제거 (공백, 한글, 영문, 숫자, 하이픈만)
    slug = re.sub(r"[^\w\s가-힣-]", "", topic)
    slug = re.sub(r"\s+", "-", slug.strip())
    slug = slug[:30].rstrip("-")
    return slug


def save_thread_md(
    cluster: dict,
    outline_text: str,
    date_str: str,
) -> tuple[str, str]:
    """클러스터 → md 파일 저장 (YYYYMMDD/슬러그_thread.md)"""
    date_dir = date_str.replace("-", "")  # 2026-06-10 → 20260610
    thread_date_dir = os.path.join(THREADS_DIR, date_dir)
    os.makedirs(thread_date_dir, exist_ok=True)

    topic = cluster["topic"]
    score = cluster["score"]
    article_count = len(cluster["article_ids"])
    has_foreign = cluster["has_foreign"]
    has_domestic = cluster["has_domestic"]
    교차 = "✅ 해외+국내 교차" if (has_foreign and has_domestic) else "해외 또는 국내 단독"

    slug = make_slug(topic)
    filename = f"{date_str}-{slug}_thread.md"
    filepath = os.path.join(thread_date_dir, filename)

    md = f"""---
소재: {topic}
점수: {score}
기사수: {article_count}
교차: {교차}
---

{outline_text}

---
생성일시: {datetime.now(KST).strftime('%Y-%m-%d %H:%M:%S %z')}
"""

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(md)
    log(f"  저장: {filename}")
    return filepath, topic


# ============================================
# 메인
# ============================================
def main() -> None:
    load_env()
    today_str = date.today().strftime("%Y-%m-%d")
    print(f"[{datetime.now(KST).strftime('%H:%M:%S')}] 스레드 글감 파인더 시작 ({today_str})")
    print()

    # ── STEP 1 ──────────────────────────────────────────
    log("=" * 55)
    log("STEP 1/6: D1 뉴스 조회")
    log("=" * 55)
    articles, news_date = load_today_news()
    if not articles:
        log("  → 조회 가능한 뉴스 없음, 종료")
        return

    # 해외/국내 분류 통계
    foreign_count = sum(1 for a in articles if classify_source(a.get("source", "")) == "해외")
    domestic_count = len(articles) - foreign_count
    log(f"  전체: {len(articles)}건 (해외 {foreign_count}건 / 국내 {domestic_count}건)")
    print()

    # ── STEP 2 ──────────────────────────────────────────
    log("=" * 55)
    log("STEP 2/6: 기사 클러스터링 (gpt-4o-mini)")
    log("=" * 55)
    clusters = cluster_articles(articles)
    if not clusters:
        log("  → 클러스터 없음, 종료")
        return
    print()

    # ── STEP 3 ──────────────────────────────────────────
    log("=" * 55)
    log("STEP 3/6: 스코어링 (소재 우선순위)")
    log("=" * 55)
    top_clusters = score_clusters(clusters)
    if not top_clusters:
        log("  → 상위 클러스터 없음, 종료")
        return
    print()

    # articles_map 구축 (id → article)
    articles_map = {a["id"]: a for a in articles}

    # ── STEP 4 ──────────────────────────────────────────
    log("=" * 55)
    log("STEP 4/6: 스레드 아웃라인 생성 (gpt-4o)")
    log("=" * 55)
    results = []  # (filepath, topic, score, article_count, has_foreign, has_domestic)
    for i, cluster in enumerate(top_clusters, 1):
        topic = cluster["topic"]
        log(f"  [{i}/{len(top_clusters)}] {topic} (점수: {cluster['score']})")
        try:
            outline = generate_thread_outline(cluster, articles_map)
            filepath, name = save_thread_md(cluster, outline, news_date)
            results.append((
                filepath, name, cluster["score"],
                len(cluster["article_ids"]),
                cluster["has_foreign"], cluster["has_domestic"],
            ))
        except Exception as e:
            log(f"    ❌ 생성 실패: {e}")
    print()

    # ── STEP 5 ──────────────────────────────────────────
    log("=" * 55)
    log("STEP 5/6: md 파일 저장 완료")
    log("=" * 55)
    for fp, name, score, cnt, hf, hd in results:
        cross = "🌍" if (hf and hd) else "📌"
        log(f"  {cross} [{score}점] {os.path.basename(fp)} ({cnt}개 기사)")
    print()

    # ── STEP 6 ──────────────────────────────────────────
    log("=" * 55)
    log("STEP 6/6: 텔레그램 알림")
    log("=" * 55)
    if results:
        msg_lines = [f"🧵 [{today_str}] 스레드 글감 생성 완료 ({len(results)}개)"]
        for i, (fp, name, score, cnt, hf, hd) in enumerate(results, 1):
            cross = "해외+국내 교차" if (hf and hd) else "단독"
            msg_lines.append(
                f"\n{i}. [{score}점] {name}\n"
                f"   📰 기사 {cnt}개 ({cross})"
            )
        send_telegram("\n".join(msg_lines))
    else:
        send_telegram(f"🧵 [{today_str}] 스레드 글감 생성 실패 (모든 클러스터 실패)")
    print()

    log("✅ 스레드 글감 파인더 완료!")


if __name__ == "__main__":
    main()
