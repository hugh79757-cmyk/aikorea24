#!/usr/bin/env python3
"""aikorea24 브리핑 자동 생성기"""

import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
import os
from pathlib import Path

KST = timezone(timedelta(hours=9))
PROJECT_DIR = "/Users/twinssn/Projects/aikorea24"

sys.path.insert(0, os.path.join(PROJECT_DIR, 'scripts', 'threads', 'v3'))
sys.path.insert(0, PROJECT_DIR)
from model_router import chat_completion
sys.path.insert(0, str(Path(__file__).parent))
from auto_news_selector import get_recent_news, cluster_by_topic, select_top_articles, d1_query
from auto_news_selector import get_recent_news, cluster_by_topic, select_top_articles, d1_query

def log(msg):
    ts = datetime.now(KST).strftime("%H:%M:%S")
    print(f"[{ts}] {msg}")

def d1_execute(sql):
    """D1 INSERT/UPDATE/DELETE 실행"""
    cmd = ["/opt/homebrew/bin/wrangler", "d1", "execute", "aikorea24-db", "--remote", "--command", sql]
    env = dict(os.environ)
    env.pop("CLOUDFLARE_API_TOKEN", None)
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=60, cwd=PROJECT_DIR, env=env)
        if r.returncode != 0:
            log(f"  D1 실행 오류 (rc={r.returncode}): {r.stderr[:200]}")
            return False
        return True
    except Exception as e:
        log(f"  D1 예외: {e}")
        return False

def remove_chinese(text):
    """중국어(한자) CJK 통합 한자 블록 제거"""
    return re.sub(r'[\u4e00-\u9fff\u3400-\u4dbf]', '', text)


# ============================================
# 언어/릭 게이트 (3중 방어) — pipeline.threads.pitch 기존 검증기 재사용
# ============================================
_HANGUL_RE = re.compile(r'[\uAC00-\uD7A3]')

# 브리핑 프롬프트 구조 미러링 패턴 (auto_briefing 고유 — pitch.py 원본에 없음)
_BRIEFING_LEAK_PATTERNS = [
    (re.compile(r'^\s*(제목|출처|내용|코멘트)\s*[:：]'), '프롬프트 라벨 미러링'),
    (re.compile(r'(제목|출처|내용|코멘트)\s*[:：].*\n.*(제목|출처|내용|코멘트)\s*[:：]'), '템플릿 구조 미러링'),
]


def looks_korean(text):
    """텍스트에 한글(가-힣)이 1자라도 있으면 True"""
    return bool(text and _HANGUL_RE.search(text))


def _detect_prompt_leak(text):
    """프롬프트 릭 검사 (pitch.py detect_prompt_leak lazy import + 브리핑 라벨 패턴)"""
    from pipeline.threads.pitch import detect_prompt_leak  # lazy import
    leaked, reason = detect_prompt_leak(text)
    if leaked:
        return True, reason
    for pattern, label in _BRIEFING_LEAK_PATTERNS:
        if pattern.search(text):
            return True, f"브리핑 {label}: {pattern.pattern}"
    return False, "OK"


def validate_briefing_comment(comment):
    """브리핑 코멘트 언어/릭 순수 검증기 (1차·3차 방어용).
    Returns: (valid: bool, reason: str)"""
    if not comment or not comment.strip():
        return False, "코멘트 비어있음"
    from pipeline.threads.pitch import validate_korean_output  # lazy import
    leaked, reason = _detect_prompt_leak(comment)
    if leaked:
        return False, reason
    # 코멘트는 1~2문장으로 짧다 — 첫 100자를 hook, 다음 200자를 narrative로 분할 전달
    return validate_korean_output(comment[:100], comment[100:300])


def ensure_korean_title(article):
    """제목 언어 게이트 — 한글 부재 시 번역 후 D1 news.title 갱신 (additive).
    번역 실패 시 원문 유지 (파이프라인 중단 없음), 경고 로그만."""
    title = (article.get("title") or "").strip()
    if not title or looks_korean(title):
        return title
    news_id = article.get("id")
    try:
        translated = chat_completion(
            messages=[{"role": "user", "content": f"다음 영어 AI/기술 뉴스 제목을 자연스러운 한국어로 번역해줘. 고유명사(GPT-6, CNBC 등)는 유지. 번역된 제목만 출력:\n\n{title}"}],
            system_prompt="당신은 AI 뉴스 제목 번역 전문가입니다. 반드시 자연스러운 한국어 제목만 출력하세요. 설명, 따옴표, 접두사 금지.",
            temperature=0.3,
            max_tokens=150,
            model_override=None,  # 무료 LLM 폴백 체인 사용
        )
        translated = (translated or "").strip().strip('"').strip("'")
        if not translated or not looks_korean(translated):
            log(f"    ⚠️ 제목 번역 실패 (한글 없음) — 원문 유지: {title[:50]}")
            return title
        translated_esc = translated.replace("'", "''")
        old_esc = title.replace("'", "''")
        if news_id:
            d1_execute(
                f"UPDATE news SET title='{translated_esc}', "
                f"original_title=CASE WHEN original_title IS NULL OR original_title='' THEN '{old_esc}' ELSE original_title END "
                f"WHERE id={news_id}"
            )
        article["title"] = translated
        log(f"    ✅ 제목 번역 적용: {translated[:50]}")
        return translated
    except Exception as e:
        log(f"    ⚠️ 제목 번역 예외 — 원문 유지: {e}")
        return title


def verify_briefing_items(briefing_id):
    """3차 방어: 저장 후 read-back 검증 — 실패 row는 comment=''로 라이브 렌더링 차단.
    Returns: 감지/처리된 row 수 (예외 시 0 — 저장 흐름 영향 없음)."""
    try:
        rows = d1_query(f"SELECT id, comment FROM briefing_items WHERE briefing_id = {int(briefing_id)}")
        if not rows:
            return 0
        bad = []
        for row in rows:
            comment = row.get("comment") or ""
            if not comment:
                continue
            valid, reason = validate_briefing_comment(comment)
            if not valid:
                bad.append((row["id"], reason))
        if not bad:
            log(f"  3차 게이트: {len(rows)}개 아이템 read-back 검증 통과")
            return 0
        log(f"  ⚠️ 3차 게이트: {len(bad)}개 row 검증 실패 → 라이브 렌더링 차단 (UPDATE comment='')")
        for row_id, reason in bad:
            log(f"    [id={row_id}] {reason}")
            d1_execute(f"UPDATE briefing_items SET comment='' WHERE id={int(row_id)}")
        return len(bad)
    except Exception as e:
        log(f"  3차 게이트 예외 (저장 흐름 영향 없음): {e}")
        return 0


def generate_comment(article):
    """무료 LLM 폴백 체인으로 기사 코멘트 생성 (한국어 출력)"""
    title = article.get("title", "")
    description = (article.get("description") or "")[:300]
    source = article.get("source", "")

    system_prompt = (
        "당신은 한국어 뉴스 코멘트 작성 전문가입니다.\n"
        "중요: 중국어(한자)를 절대 사용하지 마세요. 모든 내용을 순수 한국어로만 작성하세요.\n"
        "한자어가 필요한 경우 반드시 순수 한글로 풀어서 표현하세요."
    )
    user_prompt = (
        f"다음 AI 뉴스에 대해 1~2문장의 간결한 한국어 코멘트를 작성해줘.\n\n"
        f"제목: {title}\n"
        f"출처: {source}\n"
        f"내용: {description}\n\n"
        f"코멘트:"
    )

    try:
        # 1차 방어: 생성 직후 언어/릭 검증 — 실패 시 재생성 (총 3회 시도)
        comment = None
        for attempt in range(1, 4):
            raw = chat_completion(
                messages=[{"role": "user", "content": user_prompt}],
                system_prompt=system_prompt,
                temperature=0.3,
                max_tokens=500,
                model_override=None,  # 무료 LLM 폴백 체인 사용 (16개 무료 → 최후 수단 DeepSeek)
            )
            if not raw:
                log(f"  코멘트 생성 실패 (LLM 응답 없음, 시도 {attempt}/3)")
                continue
            # 중국어 문자 제거 (안전망)
            comment = remove_chinese(raw)
            if comment != raw:
                log(f"    ⚠️ 중국어 문자 {len(raw) - len(comment)}개 제거됨 (comment)")
            valid, reason = validate_briefing_comment(comment)
            if valid:
                return comment
            log(f"    ⚠️ 1차 게이트 실패 (시도 {attempt}/3): {reason}")
            comment = None
        return None
    except Exception as e:
        log(f"  LLM 예외: {e}")
        return None


def build_briefing(articles):
    """브리핑 데이터 구성 (intro + items)"""
    today = datetime.now(KST).strftime("%Y-%m-%d")

    intro = (
        f"오늘의 AI 뉴스 브리핑 ({today})\n\n"
        f"{len(articles)}건의 주요 AI 뉴스를 선정했습니다."
    )

    items = []
    for i, a in enumerate(articles):
        items.append({
            "news_id": a.get("id"),
            "sort_order": i + 1,
            "comment": a.get("comment", ""),
        })

    return {"date": today, "intro": intro, "status": "published", "items": items}


def save_briefing(data):
    """D1 DB에 브리핑 저장. 성공 시 briefing_id, 실패 시 None 반환."""
    today_base = data["date"][:10]
    intro_escaped = data["intro"].replace("'", "''")

    existing = d1_query(f"SELECT id, date FROM briefings WHERE date LIKE '{today_base}%' ORDER BY date DESC")
    if existing:
        last_date = existing[0]['date']
        last_seq = int(last_date.split('-')[-1]) if '-' in last_date[10:] else 0
        seq = last_seq + 1
    else:
        seq = 1

    date_with_seq = f"{today_base}-{seq}"
    data["date"] = date_with_seq

    sql_briefing = (
        f"INSERT INTO briefings (date, intro, status, published_at, created_at) "
        f"VALUES ('{date_with_seq}', '{intro_escaped}', 'published', datetime('now'), datetime('now'))"
    )
    if not d1_execute(sql_briefing):
        log("  브리핑 생성 실패")
        return None

    rows = d1_query(f"SELECT id FROM briefings WHERE date = '{date_with_seq}'")
    if not rows:
        log("  브리핑 ID 조회 실패")
        return None
    briefing_id = rows[0]["id"]
    log(f"  브리핑 id={briefing_id} 저장 (date={date_with_seq})")

    for item in data["items"]:
        comment_escaped = (item.get("comment") or "").replace("'", "''")
        news_id = item["news_id"]
        sort_order = item["sort_order"]
        # 2차 방어: INSERT 직전 릭 패턴 재검사 — 릭 감지 시 해당 아이템 저장 스킵
        comment_raw = item.get("comment") or ""
        leaked, leak_reason = _detect_prompt_leak(comment_raw)
        if leaked:
            log(f"  ⚠️ 2차 게이트: sort_order={sort_order} 릭 감지 → 저장 스킵 ({leak_reason})")
            continue
        sql_item = (
            f"INSERT INTO briefing_items (briefing_id, news_id, sort_order, comment) "
            f"VALUES ({briefing_id}, {news_id}, {sort_order}, '{comment_escaped}')"
        )
        if not d1_execute(sql_item):
            log(f"  sort_order={sort_order} 아이템 저장 실패")

    log(f"  {len(data['items'])}개 아이템 저장 완료")
    return briefing_id


def main(selected_articles=None):
    log("=== aikorea24 브리핑 자동 생성 ===")
    print()

    # 1. 뉴스 선정
    log("[1/4] 뉴스 조회 및 선정")
    from briefing_dedup import filter_duplicates, record_briefing

    if selected_articles is not None:
        selected = selected_articles
        log(f"  외부 선정 사용: {len(selected)}개 기사")
    else:
        articles = get_recent_news(hours=48)
        if not articles:
            log("  수집된 뉴스 없음")
            return

        clusters = cluster_by_topic(articles)
        for cluster_name, cluster_articles in clusters.items():
            for art in cluster_articles:
                art["cluster"] = cluster_name
        selected = select_top_articles(clusters, max_count=6)
        log(f"  선정: {len(selected)}개 기사")

        # Phase 2 중복 방어 (저장 전 재검증)
        cutoff, removed = filter_duplicates(selected, d1_query)
        if removed:
            log(f"  ⚠️ 중복 제거: {len(removed)}건")
            for art, reason in removed:
                title = (art.get("title") or "")[:50]
                log(f"    [{reason}] {title}")
        selected = cutoff

    if not selected:
        log("  ⚠️ 선정된 기사 없음")
        print()
        return

    print()

    # 2. 코멘트 생성
    log("[2/4] 코멘트 생성")
    for art in selected:
        ensure_korean_title(art)  # 제목 언어 게이트 — 영어 제목 번역 (4b)
        title = (art.get("title") or "")[:50]
        log(f"  → {title}")
        comment = generate_comment(art)
        if comment:
            art["comment"] = comment
            log(f"    ✅ {comment[:60]}...")
        else:
            art["comment"] = ""
            log(f"    ❌ 코멘트 생성 실패")
    print()

    # 3. 브리핑 구성
    log("[3/4] 브리핑 데이터 구성")
    briefing_data = build_briefing(selected)
    log(f"  날짜: {briefing_data['date']}")
    log(f"  아이템: {len(briefing_data['items'])}개")
    print()

    # 4. D1 저장
    log("[4/4] D1 DB 저장")
    briefing_id = save_briefing(briefing_data)
    if briefing_id:
        record_briefing(briefing_id, selected, d1_query)
        # 3차 방어: 저장 후 read-back 검증 (실패 row 라이브 렌더링 차단)
        verify_briefing_items(briefing_id)
    print()

    log("=== 완료 ===")
    return briefing_id


if __name__ == "__main__":
    main()
