#!/usr/bin/env python3
"""aikorea24 브리핑 자동 생성기"""

import json
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
from auto_news_selector import (CANDIDATE_LIMIT, MAX_COUNT, PROVIDER_SOURCES,
                                 cluster_by_topic, d1_query,
                                 interleave_candidates, select_top_articles)
import model_eval

# PIPE-03 §4-4: news.source → OpenCode 설정 접두어
CLI_PROVIDER_PREFIX = {
    "OpenCode Zen": "opencode",
    "OpenRouter Free Models": "openrouter",
    "Kilo Free Models": "kilo",
    "NVIDIA NIM Free": "nvidia",
}
# 오픈 웨이트(GGUF/양자화) — OpenCode 가 직접 받아 쓰진 못하지만 Ollama·LM Studio 를
# 경유해 무료 로컬 실행된다. 존재하지 않는 모델 문자열을 만들지 않고 링크로만 안내.
OPEN_WEIGHT_SOURCES = {"HuggingFace Trending"}


def cli_free_block(article):
    """'이 LLM을 OpenCode 같은 CLI에서 무료로 쓸 수 있는가?' 의 답을 코멘트에 붙인다.

    2026-10-16 개편 §작업4: (a) OpenCode 모델 선택기에서 바로 선택 가능 / (b) 커스텀
    프로바이더 연결 필요 — 를 반드시 구분한다. (b)를 (a)처럼 표현하면 안 된다.
    """
    mid = article.get("original_title") or ""
    if not mid:
        return ""
    if article.get("source") in OPEN_WEIGHT_SOURCES:
        return ("OpenCode에서 무료로 사용 가능 (오픈 웨이트·로컬 실행)\n"
                "로컬 브리지(Ollama 등) 필요\n"
                f"모델: {article.get('link') or 'https://huggingface.co/' + mid}\n"
                "사용법: Ollama 또는 LM Studio 로 먼저 띄운 뒤 OpenCode 의 "
                f'"ollama" 프로바이더에서 {{"model": "ollama/<로컬 모델명>"}} 으로 연결')
    if article.get("source") == "OpenCode Zen":
        return ("(a) OpenCode 모델 선택기에서 바로 선택 가능\n"  # EVAL-02 §4-1: 이모티콘 제거
                f'설정: {{"model": "opencode/{mid}"}}')
    prefix = CLI_PROVIDER_PREFIX.get(article.get("source"))
    if not prefix:
        return ""
    # 같은 모델이 여러 프로바이더로 수집되면 하나로 합쳐 표기한다 (EMAIL-02 §4-1).
    providers = article.get("_providers") or [article.get("source")]
    settings = " 또는 ".join(
        f'{{"model": "{CLI_PROVIDER_PREFIX[p]}/{mid}"}}' for p in providers
    )
    names = "·".join(CLI_PROVIDER_PREFIX[p] for p in providers)
    return ("(b) 커스텀 프로바이더 설정 후 연결 가능 (API 키 필요)\n"
            + (f"프로바이더: {names}\n" if len(providers) > 1 else "")
            + f"설정: {settings}")


LEADERBOARD_PATH = Path(PROJECT_DIR) / "scripts" / "logs" / "model_leaderboard.json"
VERIFY_PATH = Path(PROJECT_DIR) / "scripts" / "logs" / "free_models_verify.json"
CLI_MODELS_PATH = Path(PROJECT_DIR) / "scripts" / "logs" / "free_models_cli.json"


def _top3_avg():
    """리더보드 상위 3개(현재 문항 버전) 평균 점수. 실패하면 None → 비교 줄 생략."""
    try:
        rows = [r for r in json.loads(LEADERBOARD_PATH.read_text(encoding="utf-8"))
                if r.get("qv") == model_eval.EVAL_QUESTIONS_VERSION and r.get("score")]
    except Exception as e:  # noqa: BLE001 — 비교 실패가 브리핑을 막지 않는다
        log(f"    ⚠️ 리더보드 조회 실패: {type(e).__name__}")
        return None
    if not rows:
        return None
    rows.sort(key=lambda r: -r["score"])
    top = rows[:3]
    return sum(r["score"] for r in top) / len(top)


def _core_name(model_id):
    """`:free`/`-free` 접미사를 떼고 소문자로 — 프로바이더마다 표기가 달라도 같은 모델을 찾는다."""
    c = (model_id or "").split("/")[-1].lower()
    for suf in (":free", "-free"):
        if c.endswith(suf):
            c = c[: -len(suf)]
    return c


def _verified_running():
    """OpenCode에서 동작 확인된 모델 이름 집합 — 12문항 점수는 없는 층 (2026-10-16 대표님 지시)."""
    names = set()
    for path in (VERIFY_PATH, CLI_MODELS_PATH):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001 — 파일이 없으면 그 층은 비어 있는 것으로 본다
            continue
        if isinstance(data, dict):
            for cid in (data.get("pass") or []):
                names.add(_core_name(cid))
        elif isinstance(data, list):
            for row in data:
                if isinstance(row, dict):
                    names.add(_core_name(row.get("model_id") or row.get("cli_id") or ""))
    names.discard("")
    return names


def verdict_block(model_id, source=None):
    """모델 판단 문구 — 3단계 (2026-10-16 대표님 지시로 개편).

    1) 12문항 점수 있음 → 점수 + Top 3 대비
    2) 동작 확인됨·점수 없음 → "OpenCode 동작 확인됨 (12문항 평가 전)"
    3) 미검증 → "12문항 평가 전 — 판단 보류"
    추측하지 않는다. 이 함수는 브리핑을 막지 않는다.
    """
    _ = source  # 인터페이스 유지용 (지시서 지정 시그니처)
    try:
        # 캐시 전용 조회 — 캐시가 없으면 라이브 평가를 돌리지 않는다.
        # (2026-10-16 실측: eval_model_cached 는 캐시 미스 시 12문항을 실제로 호출해
        #  이미 제외된 모델에 48초를 낭비했다. 브리핑은 평가 파이프라인이 아니다.)
        ev = model_eval.cache_get(model_id)
    except Exception as e:  # noqa: BLE001
        log(f"    ⚠️ 모델 평가 예외: {type(e).__name__}: {str(e)[:100]}")
        ev = None
    if not ev or ev.get("score") is None:
        try:
            verified = bool(model_id) and _core_name(model_id) in _verified_running()
        except Exception:  # noqa: BLE001 — 확인 실패는 미검증으로 본다
            verified = False
        if verified:
            log(f"    ⓘ 12문항 평가 전 (동작 확인됨): {model_id}")
            return "OpenCode 동작 확인됨 (12문항 평가 전)"
        if model_id:
            log(f"    ⓘ 12문항 평가 전 (캐시 없음): {model_id} → 판단 보류")
        return "12문항 평가 전 — 판단 보류"
    lines = [f"12문항 평가: {ev['score']}/{ev['max_score']} — {ev.get('label') or ''}".rstrip()]
    avg = _top3_avg()
    if avg is not None:
        lines.append("현재 추천 Top 3 대비: " + ("추천 모델과 동급" if ev["score"] >= avg
                                             else f"현재 추천 모델 대비 {avg - ev['score']:g}점 낮음"))
    return "\n".join(lines)


def merge_same_models(articles):
    """같은 모델 ID가 여러 프로바이더로 들어온 항목을 1건으로 합친다 (EMAIL-02 §4-1).
    대표님 결정 옵션 A — 같은 모델을 두 번 소개하면 독자에게 혼란이다.
    """
    merged, index = [], {}
    for art in articles:
        mid = art.get("original_title") or ""
        if not mid or art.get("source") not in CLI_PROVIDER_PREFIX:
            merged.append(art)
            continue
        key = mid.lower()
        if key in index:
            first = index[key]
            srcs = first.setdefault("_providers", [first.get("source")])
            if art.get("source") not in srcs:
                srcs.append(art.get("source"))
        else:
            index[key] = art
            merged.append(art)
    for art in merged:
        srcs = art.get("_providers") or []
        if len(srcs) > 1:
            log(f"  모델 통합: {art.get('original_title')} → {'·'.join(srcs)}")
    return merged

def log(msg):
    ts = datetime.now(KST).strftime("%H:%M:%S")
    print(f"[{ts}] {msg}")

def d1_execute(sql):
    """D1 INSERT/UPDATE/DELETE 실행"""
    cmd = ["/opt/homebrew/bin/wrangler", "d1", "execute", "aikorea24-db", "--remote", "--command", sql]
    env = dict(os.environ)
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
        comment = chat_completion(
            messages=[{"role": "user", "content": user_prompt}],
            system_prompt=system_prompt,
            temperature=0.3,
            max_tokens=500,
            model_override=None,  # 무료 LLM 폴백 체인 사용 (16개 무료 → 최후 수단 DeepSeek)
        )
        if not comment:
            log(f"  코멘트 생성 실패 (LLM 응답 없음)")
            return None
        # 중국어 문자 제거 (안전망)
        cleaned = remove_chinese(comment)
        if cleaned != comment:
            removed = len(comment) - len(cleaned)
            log(f"    ⚠️ 중국어 문자 {removed}개 제거됨 (comment)")

        # free-llm 항목에 verdict 부착 (2026-10-16 개편 §작업4) — eval_comment_block 폐지.
        # 평가 실패 시에도 "판단 보류"만 붙이고 브리핑을 절대 막지 않는다.
        if article.get("v2_tag") == "free-llm":
            model_id = model_eval.extract_model_id(article) or (article.get("original_title") or "")
            if not model_id:
                log("    ⚠️ 모델 ID 판별 실패 → verdict 생략")
            else:
                log(f"    📊 verdict 조회: {model_id} ({article.get('source')})")
                return cleaned + "\n\n" + verdict_block(model_id, article.get("source"))
        return cleaned
    except Exception as e:
        log(f"  LLM 예외: {e}")
        return None


def build_briefing(articles):
    """브리핑 데이터 구성 (intro + items)"""
    today = datetime.now(KST).strftime("%Y-%m-%d")

    intro = (
        f"오늘의 AI 브리핑 ({today})\n\n"
        f"{len(articles)}건의 AI 소식을 선정했습니다."
    )

    items = []
    for i, a in enumerate(articles):
        items.append({
            "news_id": a.get("id"),
            "sort_order": i + 1,
            "comment": a.get("comment", ""),
        })

    return {"date": today, "intro": intro, "status": "published", "items": items}


def _published_briefings_on(base_date):
    """해당 날짜(YYYY-MM-DD)에 published 상태로 남아 있는 브리핑 — 최신 id 순."""
    return d1_query(
        "SELECT id, date FROM briefings WHERE date LIKE '%s%%' AND status = 'published' ORDER BY id DESC"
        % base_date
    ) or []


def _force_requested():
    """재발행 강제 여부. 기본은 하루 1회 발행 정책 (2026-10-16)."""
    return os.environ.get("AIK24_BRIEFING_FORCE") == "1"


def save_briefing(data, force=None):
    """D1 DB에 브리핑 저장. 성공 시 briefing_id, 실패 시 None 반환.

    2026-10-16 정책 — 하루 1회 발행.
    실측: 07:03 KST 자동 실행이 3건짜리 브리핑(id=354)을 만든 뒤 12:07 에 1건짜리
    재실행이 '-2'(id=355)로 붙었고, API(latest.ts)는 최신 1건만 서빙하므로 3건짜리가
    화면에서 가려졌다(이메일도 2회 발송됐다). 그래서 같은 날짜에 published 브리핑이
    이미 있으면 재실행은 저장을 건너뛴다(None 반환, 호출측이 record_briefing 을 건너뜀).
    강제 재발행은 env AIK24_BRIEFING_FORCE=1 — 이때 기존 published 는
    status='superseded' 로 내려 '하루 published 1건' 원칙을 지킨다(행은 보존).
    """
    force = _force_requested() if force is None else force
    today_base = data["date"][:10]
    existing_pub = _published_briefings_on(today_base)
    if existing_pub:
        if not force:
            log(f"  이미 오늘 브리핑이 published 입니다 (id={existing_pub[0]['id']}, "
                f"date={existing_pub[0]['date']}) — 건너뜀 (하루 1회 발행)")
            log("  재발행이 필요하면 AIK24_BRIEFING_FORCE=1 로 실행하세요")
            return None
        for row in existing_pub:
            if d1_execute(f"UPDATE briefings SET status = 'superseded' WHERE id = {row['id']}"):
                log(f"  기존 브리핑 superseded (id={row['id']}, date={row['date']})")
            else:
                log(f"  ⚠️ superseded 실패 (id={row['id']}) — published 가 2건 남을 수 있음")

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

    # 2026-10-16 정책 — 하루 1회 발행. 오늘 published 브리핑이 이미 있으면 LLM 비용을
    # 쓰기 전에 조기 종료한다 (같은 날 재실행이 3건짜리 브리핑을 1건짜리로 가리는 사고 방지).
    today_base = datetime.now(KST).strftime("%Y-%m-%d")
    if not _force_requested():
        already = _published_briefings_on(today_base)
        if already:
            log(f"이미 오늘 브리핑 발행됨 (id={already[0]['id']}, date={already[0]['date']}) "
                "— 건너뜀 (하루 1회 발행)")
            log("  재발행이 필요하면 AIK24_BRIEFING_FORCE=1 로 실행하세요")
            log("=== 완료 ===")
            return None

    # 1. 뉴스 선정
    log("[1/4] 뉴스 조회 및 선정")
    from briefing_dedup import filter_duplicates, record_briefing

    if selected_articles is not None:
        selected = selected_articles
        log(f"  외부 선정 사용: {len(selected)}개 기사")
    else:
        # PIPE-03: 모델이 161건으로 풀을 덮으면 뉴스 1건 슬롯이 비므로 태그 교차로 섞는다.
        articles, tag_counts = interleave_candidates(CANDIDATE_LIMIT)
        if not articles:
            log("  수집된 뉴스 없음")
            return
        log(f"  후보 {len(articles)}건 (태그별 " + ", ".join(f"{t}={n}" for t, n in tag_counts.items()) + ")")

        clusters = cluster_by_topic(articles)
        for cluster_name, cluster_articles in clusters.items():
            for art in cluster_articles:
                art["cluster"] = cluster_name
        selected = select_top_articles(clusters, max_count=MAX_COUNT)  # PIPE-03: 뉴스 3건
        log(f"  선정: {len(selected)}개 기사")

    # Phase 2 중복 방어 (저장 전 재검증). AIK24-BLOG-01: run_pipeline가 기사를 넘기는
    # 파이프라인 경로에서도 반드시 걸어야 한다 — 이전엔 else 분기에만 있어 중복이 그대로 저장됐다.
    cutoff, removed = filter_duplicates(selected, d1_query)
    if removed:
        log(f"  ⚠️ 중복 제거: {len(removed)}건")
        for art, reason in removed:
            title = (art.get("title") or "")[:50]
            log(f"    [{reason}] {title}")
    selected = cutoff
    selected = merge_same_models(selected)

    if not selected:
        log("  ⚠️ 선정된 기사 없음")
        print()
        return

    print()

    # 2. 코멘트 생성
    log("[2/4] 코멘트 생성")
    for art in selected:
        title = (art.get("title") or "")[:50]
        log(f"  → {title}")
        comment = generate_comment(art)
        block = cli_free_block(art)
        if block:
            comment = f"{comment}\n\n{block}".strip()
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
    print()

    log("=== 완료 ===")
    return briefing_id


if __name__ == "__main__":
    main()
