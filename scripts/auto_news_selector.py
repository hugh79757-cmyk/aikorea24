#!/usr/bin/env python3
"""aikorea24 브리핑 선정기 v3 (AIK24-PIPE-03)

v2 는 "한국인 초보자가 오늘 무료로 쓸 수 있는가?"를 LLM 도움 점수(실용성·이해도·유용성)로
봤고, v3 는 선정 기준을 **"이 LLM을 OpenCode 같은 CLI 서비스에서 무료로 쓸 수 있는가?"**
로 바꾼다 (지시서 §4-3).

  - 모델 3건 : 4개 CLI 프로바이더 행 중 최신 갱신일(pub_date) 순. 같은 프로바이더는
               1건만(로테이션). GitHub 이슈 언급 +2, Reddit 업보트 50+ +3.
  - 뉴스 1건 : HuggingFace trending/blog 등 정보성. "CLI 무료" 기준 미적용.

점수는 DB에 저장하지 않는다(선정 시점 한정).
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
MODEL_SLOTS = 3  # CLI 무료 모델 3건 (지시서 §4-3)
PER_TAG_LIMIT = 10
POOL_LIMIT = 50
# AIK24-EFFICIENCY-02: LLM 평가 대상 30 → 8. 1건당 16.4초가 걸려 30건=345초였다.
# 선택 규칙(모델 슬롯 3 + 뉴스 슬롯 1)이 실제로 경쟁하는 건 프로바이더별 최신 1건과
# 태그별 상위 몇 건뿐이라, 나머지는 평가해도 select_top_articles() 의 출처 중복
# 제약에 걸려 버려졌다(2026-10-13 실행: 후보 21건 중 탈락 0건, 최종 4건 전부 11점).
CANDIDATE_LIMIT = 8  # LLM 평가 대상
PER_TAG_CANDIDATES = 3  # 태그별 상위 3건만 후보로
NEWS_CANDIDATES = 4  # 뉴스 슬롯 최대 4건 (태그별 상위 3건 중 라운드로빈)
SCORE_MIN = 6  # 3개 기준 평균 2점 미만 탈락
TAG_ORDER = ("free-llm", "opensource", "tool")
KST = timezone(timedelta(hours=9))
SCORE_RE = re.compile(r"실용성\s*[:=]\s*(\d)|이해도\s*[:=]\s*(\d)|유용성\s*[:=]\s*(\d)")

_COLS = "id, title, link, description, source, category, pub_date, v2_tag, original_title, created_at"


def log(msg):
    print(f"[{datetime.now(KST).strftime('%H:%M:%S')}] [selector] {msg}")


MODEL_SOURCES = ("OpenCode Zen", "OpenRouter Free Models", "Kilo Free Models", "NVIDIA NIM Free")
MODEL_POOL = 12  # 모델 후보 fetch 깊이 (아래 MODEL_PER_SOURCE 로 추린다)
MODEL_PER_SOURCE = 1  # 프로바이더별 최신 1건씩 → 모델 슬롯 후보 최대 4건
MODEL_STALE_DAYS = 3  # AIK24-EFFICIENCY-04 §4-2: 이 기간 안에 갱신된 무료 모델이 없으면 모델 슬롯을 비운다


def _sql_in(values):
    return ", ".join("'" + str(v).replace("'", "''") + "'" for v in values)


def get_recent_news(hours=WINDOW_HOURS, v2_tag=None, exclude_models=False):
    """v2_pass=1 중 최근 hours시간 뉴스. v2_tag 지정 시 해당 태그만.

    exclude_models=True 면 4개 CLI 프로바이더 행을 뺀다 — 지시서 §4-3 의
    "모델 3건" 슬롯은 그 프로바이더에서만, "뉴스 1건" 슬롯은 나머지에서 뽑는다.
    ORDER BY 는 pub_date (레거시 수집기 행은 RFC-2822 문자열이라 뒤로 밀린다).
    """
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    where = [
        "v2_pass = 1",
        "created_at >= '" + cutoff.strftime("%Y-%m-%d %H:%M:%S") + "'",
        "source NOT IN (" + _sql_in(MODEL_SOURCES) + ")" if exclude_models else "",
        "v2_tag = '" + v2_tag + "'" if v2_tag else "",
    ]
    return d1_query("""
        SELECT %s FROM news
        WHERE %s
        ORDER BY pub_date DESC
        LIMIT %d
    """ % (_COLS, " AND ".join(w for w in where if w), PER_TAG_LIMIT if v2_tag else POOL_LIMIT))


def get_model_news(limit=MODEL_POOL):
    """4개 CLI 프로바이더의 무료 모델. pub_date 가 프로바이더 갱신일이므로
    이 정렬이 곧 "최신 추가/업데이트 순"(지시서 §4-3)이다."""
    return d1_query("""
        SELECT %s FROM news
        WHERE v2_pass = 1 AND source IN (%s)
        ORDER BY pub_date DESC
        LIMIT %d
    """ % (_COLS, _sql_in(MODEL_SOURCES), limit))


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


def _take(ranked, limit):
    """정렬된 목록에서 출처 중복 없이 limit 건. 같은 프로바이더가 3슬롯을 다 먹으면
    최신성·로테이션 의미가 사라지므로 프로바이더당 1건으로 막는다."""
    out, used = [], set()
    for a in ranked:
        if len(out) >= limit:
            break
        src = a.get("source")
        if src in used:
            continue
        used.add(src)
        out.append(a)
    return out


def has_fresh_model(models):
    """AIK24-EFFICIENCY-04 §4-2: 최근 3일 안에 갱신된 모델 카드가 하나라도 있는가.

    프로바이더가 새 무료 모델을 내놓지 않으면 후보가 며칠 전 카드로 남아 반복 출력이
    되므로, 그 경우 모델 슬롯을 비우고 뉴스로 채운다.
    """
    cutoff = (datetime.now(KST) - timedelta(days=MODEL_STALE_DAYS)).strftime('%Y-%m-%d')
    return any((a.get('pub_date') or '')[:10] >= cutoff for a in models)


def select_top_articles(clusters, max_count=MAX_COUNT):
    """클러스터 dict → 모델 3건(최신성·프로바이더 로테이션) + 뉴스 1건."""
    articles = [a for group in (clusters or {}).values() for a in group]
    # 최신 갱신일(pub_date) 순. 갱신일 없는 항목은 최후.
    ranked = sorted(articles, key=lambda a: (-(a.get("_score") or 0), _date_key(a)))

    models = [a for a in ranked if a.get("source") in MODEL_SOURCES]
    if models and not has_fresh_model(models):
        log(f"  ⚠ 최근 {MODEL_STALE_DAYS}일 신규 무료 모델 없음 — 모델 슬롯 {MODEL_SLOTS}칸을 뉴스로 채움")
        picked = []
    else:
        picked = _take(models, MODEL_SLOTS)
    # 뉴스 슬롯은 free-llm 을 받지 않는다 (지시서 §4-3 — 뉴스는 정보성이 기준).
    used = {p["id"] for p in picked}
    rest = [a for a in ranked if a["id"] not in used and a.get("source") not in MODEL_SOURCES]
    picked += _take(rest, max_count - len(picked))
    return picked


def _date_key(article):
    """'YYYY-MM-DD HH:MM:SS' → 내림차순 정렬용 음수 정수. 파싱 실패면 0(최후)."""
    p = (article.get("pub_date") or "").replace("-", "").replace(":", "").replace(" ", "")
    return -int(p) if p.isdigit() and len(p) >= 8 else 0


def _latest_per_source(rows):
    """rows 는 pub_date DESC 로 정렬돼 오므로 프로바이더별 첫 등장이 그 프로바이더 최신 1건."""
    seen, out = set(), []
    for a in rows:
        src = a.get("source")
        if src not in seen:
            seen.add(src)
            out.append(a)
    return out


def interleave_candidates(limit):
    """CLI 무료 모델 후보 + 일반 뉴스 후보(태그 교차)를 합친다.

    AIK24-EFFICIENCY-02: 평가 대상을 30건 → 8건으로 축소.
    모델 슬롯 = 프로바이더별 최신 1건씩(최대 4건), 뉴스 슬롯 = 태그별 상위 3건 중
    라운드로빈 최대 4건. 데이터가 적으면 있는 만큼만 반환한다(에러 아님).
    """
    models = _latest_per_source(get_model_news(MODEL_POOL))[:MODEL_PER_SOURCE * len(MODEL_SOURCES)]
    per_tag = {t: get_recent_news(v2_tag=t, exclude_models=True)[:PER_TAG_CANDIDATES]
               for t in TAG_ORDER}
    news = [art for row in zip_longest(*(per_tag[t] for t in TAG_ORDER))
            for art in row if art is not None][:NEWS_CANDIDATES]
    counts = {"model": len(models)}
    counts.update({t: len(per_tag[t]) for t in TAG_ORDER})
    return (models + news)[:limit], counts


def main(dedup=True):
    _ = dedup  # v1의 브리핑 중복 제거는 briefing_dedup.filter_duplicates가 담당
    pool, tag_counts = interleave_candidates(CANDIDATE_LIMIT)
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

    # 4. 점수순(동점 최신 갱신일) + 모델 3 + 뉴스 1
    selected = select_top_articles({"v2": passed}, MAX_COUNT)

    log(f"선정 {len(selected)}건" + ("" if len(selected) == MAX_COUNT
                                    else f" (요청 {MAX_COUNT}건, 데이터 부족 — 강제 선정 없음)"))
    for art in selected:
        log(f"  [{art.get('_score', 0)}점 {art.get('_detail')}] [{art.get('v2_tag')}] "
            f"{(art.get('title') or '')[:60]} ({art.get('source')} · {art.get('pub_date')})")
    return selected


if __name__ == "__main__":
    main()