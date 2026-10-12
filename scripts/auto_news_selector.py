#!/usr/bin/env python3
"""aikorea24 브리핑 선정기 v2 (AIK24-SELECTOR-01) + 도움 점수 (AIK24-HELPFUL-01)

v2_filter.py가 "오늘 무료로 쓸 수 있는 AI 소식" 큐레이션을 끝냈으므로 여기서는
DB 조회 + LLM 도움 점수(실용성·이해도·유용성) + 태그 다양성만 한다.
크롤링·엔티티 스코어링·2-pass 없음. 점수는 DB에 저장하지 않는다(선정 시점 한정).

旧 v1 (2-pass 임팩트 스코어러) → scripts/archive/auto_news_selector_v1_20261011.py
"""

import re
import sys
import time
from datetime import datetime, timedelta, timezone
from itertools import zip_longest
from pathlib import Path

_project_root = str(Path(__file__).resolve().parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)
sys.path.insert(0, str(Path(__file__).resolve().parent / "threads" / "v3"))

from pipeline.infra.d1_client import d1_query  # noqa: E402  (auto_briefing이 재사용)
from model_router import chat_completion  # noqa: E402  (무료 LLM 폴백 체인)

# auto_briefing.remove_chinese()를 재사용하면 auto_briefing ↔ auto_news_selector
# 순환 import가 생긴다(서로 상대에서 import). 한 줄짜리 정규식이므로 인라인.
def remove_chinese(text):
    return re.sub(r'[一-鿿㐀-䶿]', '', text)  # auto_briefing.py:41과 동일

WINDOW_HOURS = 36
MAX_COUNT = 4
PER_TAG_LIMIT = 5
POOL_LIMIT = 50
CANDIDATE_LIMIT = 20  # LLM 평가 대상
SCORE_MIN = 6  # 3개 기준 평균 2점 미만 탈락
MAX_PER_TAG = 2  # 태그 다양성 상한
TAG_ORDER = ("free-llm", "opensource", "tool")
KST = timezone(timedelta(hours=9))
SCORE_RE = re.compile(r"실용성\s*[:=]\s*(\d)|이해도\s*[:=]\s*(\d)|유용성\s*[:=]\s*(\d)")

_COLS = "id, title, link, description, source, category, pub_date, v2_tag, created_at"


def log(msg):
    print(f"[{datetime.now(KST).strftime('%H:%M:%S')}] [selector] {msg}")


def get_recent_news(hours=WINDOW_HOURS, v2_tag=None):
    """v2_pass=1 중 최근 hours시간 뉴스. v2_tag 지정 시 해당 태그만."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    return d1_query(f"""
        SELECT {_COLS} FROM news
        WHERE v2_pass = 1
          AND created_at >= '{cutoff.strftime("%Y-%m-%d %H:%M:%S")}'
          {"AND v2_tag = '" + v2_tag + "'" if v2_tag else ""}
        ORDER BY created_at DESC
        LIMIT {PER_TAG_LIMIT if v2_tag else POOL_LIMIT}
    """)


def cluster_by_topic(articles):
    """호환 shim. v2는 클러스터링하지 않는다 — 모든 기사를 단일 그룹으로."""
    return {"v2": list(articles)}





def score_helpfulness(article):
    """LLM 도움 점수 — 실용성·이해도·유용성 각 1~5점. 실패 시 0점(탈락)."""
    title = (article.get("title") or "")[:200]
    desc = (article.get("description") or "")[:300]
    user_prompt = (
        f"제목: {title}\n내용: {desc}\n\n"
        "위 기사를 아래 3개 기준으로 각각 1~5점 평가하세요.\n"
        "실용성: 독자가 직접 해볼 수 있는가? (무료 도구 체험·따라하기·활용법)\n"
        "이해도: 비전문가도 읽고 이해할 수 있는가? (전문 용어 과다·인프라 기술은 감점)\n"
        "유용성: 일이나 학습에 도움이 되는가? (시사점·인사이트)\n\n"
        "'실용성:X,이해도:Y,유용성:Z' 형식으로만 출력하세요."
    )
    try:
        out = chat_completion(
            messages=[{"role": "user", "content": user_prompt}],
            system_prompt="당신은 뉴스 큐레이터입니다. 아래 기사를 구독자 관점에서 평가하세요. "
                          "설명 없이 지정된 형식으로만 답하세요.",
            temperature=0.1, max_tokens=60, model_override=None,
        )
    except Exception as e:  # noqa: BLE001 — 평가 실패가 선정 전체를 막지 않게
        log(f"  점수 실패: {type(e).__name__}")
        return 0
    if not out:
        log(f"  점수 실패(응답 없음): {title[:40]}")
        return 0
    # 정규식 3그룹 → findall은 튜플 반환. (실용성,이해도,유용성) 순서로 뽑는다.
    nums = []
    for tup in SCORE_RE.findall(remove_chinese(out)):
        for g in tup:
            if g:
                nums.append(int(g))
    if len(nums) < 3:
        log(f"  점수 파싱 실패 → 0점: {title[:40]} ({out[:40]})")
        return 0
    total = sum(nums[:3])
    article["_score"] = total
    article["_detail"] = tuple(nums[:3])
    return total


def _pick_by_tag_pool(pools_by_tag, pool, max_count):
    """태그별 1건씩 먼저 확보 → 남은 슬롯은 전체 풀 최신순. 태그는 MAX_PER_TAG 초과 금지."""
    picked, used_sources, tag_count = [], set(), {t: 0 for t in TAG_ORDER}

    def over(tag):
        return tag_count.get(tag, 0) >= MAX_PER_TAG

    def take(candidates):
        for art in candidates:
            if len(picked) >= max_count:
                break
            src, tag = art.get("source"), art.get("v2_tag")
            if src in used_sources or over(tag):
                continue
            used_sources.add(src)
            tag_count[tag] = tag_count.get(tag, 0) + 1
            picked.append(art)

    for tag in TAG_ORDER:
        take(pools_by_tag.get(tag, []))
    take(pool)
    return picked


def select_top_articles(clusters, max_count=MAX_COUNT):
    """호환 shim. 클러스터 dict → 점수순 + 태그/출처 다양성 보장 후 max_count건."""
    articles = [a for group in (clusters or {}).values() for a in group]
    ranked = sorted(articles, key=lambda a: (-(a.get("_score") or 0), _newest_first(a)))
    by_tag = {t: [a for a in ranked if a.get("v2_tag") == t] for t in TAG_ORDER}
    return _pick_by_tag_pool(by_tag, ranked, max_count)


def _newest_first(article):
    return str(article.get("created_at") or "")


def _interleave_candidates(limit):
    """태그별 라운드로빈으로 후보를 섞는다.

    단순 created_at DESC LIMIT은 한 매체 배치가 후보를 통째로 차지해
    MAX_PER_TAG 상한이 붙으면 브리핑이 2건으로 줄어든다(2026-10-11 실측).
    """
    per_tag = {t: get_recent_news(v2_tag=t) for t in TAG_ORDER}
    mixed = []
    for row in zip_longest(*(per_tag[t] for t in TAG_ORDER)):
        for art in row:
            if art is not None:
                mixed.append(art)
    return mixed[:limit], {t: len(per_tag[t]) for t in TAG_ORDER}


def main(dedup=True):
    _ = dedup  # v1의 브리핑 중복 제거는 briefing_dedup.filter_duplicates가 담당
    pool, tag_counts = _interleave_candidates(CANDIDATE_LIMIT)
    log(f"v2_pass=1 후보: {len(pool)}건 (태그별 " +
        ", ".join(f"{t}={tag_counts[t]}" for t in TAG_ORDER) + ") — LLM 도움 점수 평가 시작")
    if not pool:
        log("선정 대상 없음 — 브리핑 건너뜀")
        return []

    # 2. 평가 (429 보호 위해 직렬 + 간격)
    for i, art in enumerate(pool, 1):
        s = score_helpfulness(art)
        d = art.get("_detail")
        log(f"  [{i}/{len(pool)}] {s}점 {'(실용성·이해도·유용성=%s)' % (d,) if d else '(파싱 실패)'} "
            f"{(art.get('title') or '')[:55]}")
        if i < len(pool):
            time.sleep(2)

    # 3. 탈락 제거 (6점 미만 = 평균 2점 미만)
    passed = [a for a in pool if (a.get("_score") or 0) >= SCORE_MIN]
    dropped = len(pool) - len(passed)
    log(f"탈락 {dropped}건 (점수 < {SCORE_MIN}) → 통과 {len(passed)}건")
    if not passed:
        log("통과 후보 없음 — 브리핑 건너뜀")
        return []

    # 4. 점수순(동점 최신) + 태그 다양성 상한
    ranked = sorted(passed, key=lambda a: _newest_first(a), reverse=True)  # 최신순 먼저
    ranked.sort(key=lambda a: -a["_score"])  # stable → 동점은 최신 유지
    by_tag = {t: [a for a in ranked if a.get("v2_tag") == t] for t in TAG_ORDER}
    selected = _pick_by_tag_pool(by_tag, ranked, MAX_COUNT)

    log(f"선정 {len(selected)}건" + ("" if len(selected) == MAX_COUNT
                                    else f" (요청 {MAX_COUNT}건, 데이터 부족 — 강제 선정 없음)"))
    for art in selected:
        log(f"  [{art['_score']}점 {art.get('_detail')}] [{art.get('v2_tag')}] "
            f"{(art.get('title') or '')[:60]} ({art.get('source')})")
    return selected


if __name__ == "__main__":
    main()