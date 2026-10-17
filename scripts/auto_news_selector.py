#!/usr/bin/env python3
"""aikorea24 브리핑 선정기 v3 (AIK24-PIPE-03)

v2 는 "한국인 초보자가 오늘 무료로 쓸 수 있는가?"를 LLM 도움 점수(실용성·이해도·유용성)로
봤고, v3 는 선정 기준을 **"이 LLM을 OpenCode 같은 CLI 서비스에서 무료로 쓸 수 있는가?"**
로 바꾼다 (지시서 §4-3).

브리핑은 뉴스 3건이다 (2026-10-16 개편):

  1. 무료 기회 1건 : v2_tag='free-opportunity' 최신 1건. 없으면 빈 슬롯 (강제 충전 금지).
  2. Zen 변경   : source='OpenCode Zen' 무료 목록 변경 감지분을 최신순으로. LLM 점수 무관 우선.
  3. 일반 뉴스  : 나머지 슬롯을 LLM 도움 점수 상위로. 프로바이더 행은 제외.

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
MAX_COUNT = 3  # 브리핑은 뉴스 3건 (2026-10-16 개편 — 모델 3 + 뉴스 1 폐지)
PER_TAG_LIMIT = 10
POOL_LIMIT = 50
# AIK24-EFFICIENCY-02: LLM 평가 대상 30 → 8. 1건당 16.4초가 걸려 30건=345초였다.
# 선택 규칙이 실제로 경쟁하는 건 태그별 상위 몇 건뿐이라, 나머지는 평가해도
# select_top_articles() 의 출처 중복 제약에 걸려 버려졌다(2026-10-13 실행: 후보 21건, 탈락 0건).
CANDIDATE_LIMIT = 8  # LLM 평가 대상
PER_TAG_CANDIDATES = 3  # 태그별 상위 3건만 후보로
NEWS_CANDIDATES = 4  # 뉴스 슬롯 최대 4건 (태그별 상위 3건 중 라운드로빈)
# AIK24-PIPE-04: 재충원 후보 상한 = 무료 기회 3 + Zen 3 + 일반 뉴스 9(태그 3종×3건).
# 선정(CANDIDATE_LIMIT=8)보다 넓게 잡는다 — 중복 제거로 빈 슬롯이 생겼을 때만 쓰이고,
# 그때는 이미 후보가 소진된 뒤라 더 깊은 풀이 필요하다.
REFILL_POOL_LIMIT = 15
SCORE_MIN = 6  # 3개 기준 평균 2점 미만 탈락
TAG_ORDER = ("free-llm", "opensource", "tool")
KST = timezone(timedelta(hours=9))
SCORE_RE = re.compile(r"실용성\s*[:=]\s*(\d)|이해도\s*[:=]\s*(\d)|유용성\s*[:=]\s*(\d)")

_COLS = "id, title, link, description, source, category, pub_date, v2_tag, original_title, created_at"


def log(msg):
    print(f"[{datetime.now(KST).strftime('%H:%M:%S')}] [selector] {msg}")


# 4개 CLI 프로바이더 출처. v3 에서는 이 출처를 "일반 뉴스 슬롯에서 제외"하는 용도로만
# 쓴다 (과거의 "모델 3건 슬롯"은 2026-10-16 개편으로 폐지). Zen 행은 별도 우선 슬롯을 갖는다.
PROVIDER_SOURCES = ("OpenCode Zen", "OpenRouter Free Models", "Kilo Free Models", "NVIDIA NIM Free")


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
        "source NOT IN (" + _sql_in(PROVIDER_SOURCES) + ")" if exclude_models else "",
        "v2_tag = '" + v2_tag + "'" if v2_tag else "",
    ]
    return d1_query("""
        SELECT %s FROM news
        WHERE %s
        ORDER BY pub_date DESC
        LIMIT %d
    """ % (_COLS, " AND ".join(w for w in where if w), PER_TAG_LIMIT if v2_tag else POOL_LIMIT))


def get_opportunity_news(limit=1):
    """슬롯 1: 무료 기회 (v2_tag='free-opportunity') 최신순.

    2026-10-16 개편 — 대표님이 매주 월요일 큐레이션하는 scripts/weekly_opportunity.py
    입력분이 여기로 들어온다. 있으면 1건, 없으면 빈 슬롯 (강제 충전 금지).

    2026-10-16 (2차) — **이미 브리핑에 실린 행은 SQL 로 영구 제외**한다.
    왜: 3.5단계 dedup 히스토리(briefing_dedup.get_history_articles)는 최근 3일만 본다
    (DEDUP_LOOKBACK_DAYS=3). 슬롯은 `LIMIT MAX_COUNT(=3)` 로 후보를 뽑으므로, 주 1회
    8건을 하루 1건씩 소진하면 4일째에 상위 3건이 전부 3일 창 안에 남아 중복 제외되고
    → 슬롯 1 이 비고, 5일째부터는 창을 벗어난 1일차 항목이 다시 후보로 살아나 같은
    안내가 반복된다 (4~8번째 항목 영구 미노출). 큐레이션 항목은 한 번 소개하면 끝이므로
    공개된 브리핑 이력(briefing_items) 전체로 제외하고, pub_date 동률은 id 오름차순으로
    고정해 소진 순서를 결정적으로 만든다.
    """
    return d1_query("""
        SELECT %s FROM news
        WHERE v2_pass = 1 AND v2_tag = 'free-opportunity'
          AND created_at >= '%s'
          AND id NOT IN (
              SELECT bi.news_id FROM briefing_items bi
              JOIN briefings b ON b.id = bi.briefing_id
              WHERE b.status IN ('published', 'superseded')
          )
        ORDER BY pub_date DESC, id ASC
        LIMIT %d
    """ % (_COLS, _opportunity_cutoff(), limit))


def get_zen_changes(limit=MAX_COUNT):
    """슬롯 2: Zen 무료 목록 변경 감지분 (model_catalog.record_diff_to_news 가 넣은 행).

    source='OpenCode Zen' + v2_tag='free-llm'. 기계 감지된 사실이라 LLM 도움 점수와
    무관하게 pub_date 최신순으로 우선 배정한다 (2026-10-16 개편).
    """
    return d1_query("""
        SELECT %s FROM news
        WHERE v2_pass = 1 AND source = 'OpenCode Zen' AND v2_tag = 'free-llm'
          AND created_at >= '%s'
        ORDER BY pub_date DESC
        LIMIT %d
    """ % (_COLS, _slot_cutoff(), limit))


def _slot_cutoff():
    """Zen 슬롯의 조회 하한 (7일). created_at 창이 없으면 아주 오래된 미발행 행이
    되살아나므로 7일로 끊는다 — dedup 이 이미 브리핑된 행을 걷어내므로 실질 하한은 더 짧다.

    2026-10-16: 슬롯 1(무료 기회)은 _opportunity_cutoff() 로 분리됐다 (7일로는 주간 8건이
    다 소진되지 못해 마지막 1건이 만료로 사라졌다 — 아래 함수 주석 참조).
    """
    return (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")


def _opportunity_cutoff():
    """슬롯 1(무료 기회)의 조회 하한 (21일).

    근거: 무료 기회는 대표님이 주 1회(월) 큐레이션해 8건을 한꺼번에 넣고, 브리핑은
    하루 1건(MAX_COUNT=3)이라 슬롯 1은 하루 1건씩 소진된다 → 8건이 다 보이려면 8일이
    필요한데 7일 창에서는 마지막 1건이 창 밖으로 밀려 영구 미노출이 된다 (2026-10-16
    실측: 8건 중 7건이 같은 pub_date 로 묶여 하루 1건씩 7일 소진 → 8번째는 8일째).
    21일 = 8일 소진 + 재실행·휴일 여유. 이미 브리핑된 행은 dedup 이 걷어내므로
    되살아나는 위험은 없다 (미발행으로 남은 큐레이션분만 후보가 된다).
    """
    return (datetime.now(timezone.utc) - timedelta(days=21)).strftime("%Y-%m-%d %H:%M:%S")


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


def select_top_articles(clusters, max_count=MAX_COUNT):
    """클러스터 dict → ① 무료 기회 1 ② Zen 변경(최신순) ③ LLM 점수 상위 일반 뉴스.

    ②까지는 LLM 점수와 무관하게 우선하고, ③만 점수순이다. 가치 있는 후보가 3건
    미만이면 있는 만큼만 선정한다 (물타기 금지 — 2026-10-16 개편).
    """
    articles = [a for group in (clusters or {}).values() for a in group]
    ranked = sorted(articles, key=lambda a: (-(a.get("_score") or 0), _date_key(a)))
    used, picked = set(), []

    # 슬롯 1: 무료 기회 1건 (최신). 없으면 빈 슬롯.
    opp = [a for a in articles if a.get("v2_tag") == "free-opportunity"
           and a.get("source") not in PROVIDER_SOURCES]
    opp.sort(key=_date_key)
    if opp:
        picked.append(opp[0])
        used.add(opp[0]["id"])
    else:
        log("  ⓘ 무료 기회 후보 없음 — 슬롯 1 비움 (강제 충전 없음)")

    # 슬롯 2: Zen 변경 최신순. LLM 점수와 무관하게 우선한다.
    zen = [a for a in articles if a.get("source") == "OpenCode Zen" and a["id"] not in used]
    zen.sort(key=_date_key)
    for a in zen:
        if len(picked) >= max_count:
            break
        picked.append(a)
        used.add(a["id"])
    if zen:
        log(f"  ⓘ Zen 변경 {len(zen)}건 우선 배정")

    # 슬롯 3: 나머지 = LLM 점수 상위 일반 뉴스 (프로바이더 행 제외, 출처 1건씩).
    rest = [a for a in ranked if a["id"] not in used
            and a.get("source") not in PROVIDER_SOURCES
            and a.get("v2_tag") != "free-opportunity"]
    picked += _take(rest, max_count - len(picked))
    return picked


def _date_key(article):
    """'YYYY-MM-DD HH:MM:SS' → 내림차순 정렬용 음수 정수. 파싱 실패면 0(최후)."""
    p = (article.get("pub_date") or "").replace("-", "").replace(":", "").replace(" ", "")
    return -int(p) if p.isdigit() and len(p) >= 8 else 0


def interleave_candidates(limit):
    """무료 기회 + Zen 변경 + 일반 뉴스 후보(태그 교차)를 합친다.

    기회·Zen 행은 LLM 점수 대상이 아니지만 dedup(3.5단계)이 필요하므로 pool 에 함께
    넣는다. 일반 뉴스 슬롯 = 태그별 상위 3건 중 라운드로빈. 데이터가 적으면 있는 만큼만
    반환한다(에러 아님).
    """
    opp = get_opportunity_news(MAX_COUNT)
    zen = get_zen_changes(MAX_COUNT)
    per_tag = {t: get_recent_news(v2_tag=t, exclude_models=True)[:PER_TAG_CANDIDATES]
               for t in TAG_ORDER}
    news = [art for row in zip_longest(*(per_tag[t] for t in TAG_ORDER))
            for art in row if art is not None][:NEWS_CANDIDATES]
    seen, head = set(), []
    for a in opp + zen:
        if a["id"] not in seen:
            seen.add(a["id"])
            head.append(a)
    counts = {"opportunity": len(opp), "zen": len(zen)}
    counts.update({t: len(per_tag[t]) for t in TAG_ORDER})
    return (head + news)[:limit], counts


def _is_mechanical(article):
    """Zen 변경·무료 기회 등 기계 감지 행 — LLM 도움 점수 대상이 아니다.
    점수를 매기지 않고(호출 절약) 탈락시키지도 않는다 (2026-10-16 개편).
    프로바이더 목록 변경(OpenRouter/Kilo/NVIDIA 포함)은 전부 카탈로그 diff 가 만든 행이다."""
    return (article.get("source") in PROVIDER_SOURCES
            or article.get("v2_tag") == "free-opportunity")


# ---------------------------------------------------------------------------
# AIK24-PIPE-04 — 중복 제거 후 재충원
#
# 실측(2026-10-17 07:00 실행): selector 는 3건을 선정했는데 auto_briefing 의 Phase 2
# 중복 제거가 2건(local_semantic · local_exact_id)을 탈락시켜 브리핑이 1건으로 발행됐다.
# selector 의 3.5단계 dedup 은 D1 이력만 보고 local history(briefing_dedup.json)는
# 보지 않으므로, local 히스토리 중복은 선정 이후에야 드러난다 → 빈 슬롯을 다시 채우는
# 로직이 없으면 그대로 빈 채 발행된다. 여기서 그 슬롯을 계단식으로 채운다.
# ---------------------------------------------------------------------------

# 같은 프로세스의 selector.main() 이 평가를 마친 후보 풀. auto_briefing 이 재충원할 때
# 재사용해 LLM 점수를 두 번 매기지 않는다 (run_pipeline 은 selector → briefing 을
# 한 프로세스에서 돌리므로 캐시가 산다). 캐시가 없으면 DB 에서 새로 뽑아 평가한다.
_LAST_SCORED_POOL = []


def remember_scored_pool(pool):
    """selector.main() 이 평가한 후보 풀을 기억한다 (재충원용 방어적 복사)."""
    global _LAST_SCORED_POOL
    _LAST_SCORED_POOL = [dict(a) for a in (pool or []) if isinstance(a, dict)]


def get_scored_pool():
    """기억된 후보 풀 (없으면 빈 리스트)."""
    return [dict(a) for a in _LAST_SCORED_POOL]


def _article_key(article):
    """후보 동일성 키 — id 가 없으면 link+title 로 대체한다."""
    aid = article.get("id") or article.get("news_id")
    if aid not in (None, ""):
        return "id:" + str(aid)
    return "lt:" + ((article.get("link") or "") + "|" + (article.get("title") or "")).lower()


def _model_key(article):
    """모델 통합(merge_same_models) 키 — 프로바이더 행에만 존재한다."""
    if article.get("source") not in PROVIDER_SOURCES:
        return ""
    return (article.get("original_title") or "").lower()


def _refill_candidates(d1_query_func):
    """재충원 후보 풀(평가 전)을 DB 에서 만든다 (선택기 실행 캐시가 없을 때의 폴백).

    일반 뉴스의 LLM 평가는 여기서 하지 않는다 — 계단식 3단계까지 내려갔고 중복 검사를
    통과한 후보에 한해 매긴다 (중복으로 버려질 후보에 호출을 쓰지 않는다).
    """
    pool, _ = interleave_candidates(REFILL_POOL_LIMIT)
    return pool


def _score_candidates(articles, scorer):
    """점수 없는 일반 뉴스 후보에 LLM 도움 점수를 매긴다 (기계 감지 행은 면제)."""
    for art in articles:
        if _is_mechanical(art) or art.get("_score") is not None:
            continue
        score = scorer(art)
        log(f"  [재충원 후보] {score}점 {(art.get('title') or '')[:50]}")
        time.sleep(2)
    return articles


def refill_after_dedup(kept, dropped=(), max_count=MAX_COUNT,
                       d1_query_func=None, pool=None, scorer=None):
    """중복 제거로 빈 슬롯이 생기면 계단식으로 재충원한다 (AIK24-PIPE-04 §작업1).

    계단식 순서:
      1) 남은 free-opportunity 후보 최신순
      2) 남은 source='OpenCode Zen' AND v2_tag='free-llm' 후보 최신순
      3) 남은 일반 뉴스 LLM 평가 점수 상위순 (동점은 최신순)

    - 이미 선정된 항목(kept)과 중복 제거로 탈락한 항목(dropped)은 후보에서 제외한다.
    - 재충원 후보도 중복 검사(2차 방어)를 다시 통과한 것만 쓴다.
    - 후보가 부족하면 있는 만큼만 채우고, 없으면 빈 슬롯으로 둔다 (강제 충전 금지).
    - 모델 행은 merge_same_models 와 같은 키(original_title)로 중복 통합을 방어한다.
    """
    if d1_query_func is None:
        d1_query_func = d1_query
    kept = list(kept or [])
    needed = (max_count or 0) - len(kept)
    if needed <= 0:
        return kept

    excluded = {_article_key(a) for a in kept}
    for item in (dropped or []):
        art = item[0] if isinstance(item, (tuple, list)) else item
        if isinstance(art, dict):
            excluded.add(_article_key(art))
    merged_models = {_model_key(a) for a in kept if _model_key(a)}

    candidates = ([dict(a) for a in pool] if pool
                  else _refill_candidates(d1_query_func))

    # 재충원 후보도 중복 검사(3중 방어 2차)를 그대로 통과해야 한다.
    # briefing_dedup → auto_news_selector 를 import 하므로 순환 → 지연 import.
    from briefing_dedup import filter_duplicates
    fresh, blocked = filter_duplicates(candidates, d1_query_func)
    if blocked:
        log(f"  [재충원] 중복 제외 {len(blocked)}건: "
            + ", ".join(reason for _, reason in blocked))

    def _is_available(art):
        """아직 안 쓴 후보인가 — 선정분·탈락분·모델 중복을 걸러낸다."""
        if _article_key(art) in excluded:
            return False
        mkey = _model_key(art)
        if mkey and mkey in merged_models:
            log(f"  [재충원] 모델 중복 제외: {art.get('original_title')}")
            return False
        return True

    picked = []

    def take(rows, want, tier):
        got = []
        for art in rows:
            if len(got) >= want:
                break
            if not _is_available(art):
                continue
            excluded.add(_article_key(art))
            mkey = _model_key(art)
            if mkey:
                merged_models.add(mkey)
            got.append(art)
            log(f"  [재충원 {tier}] [{art.get('_score', 0)}점 {art.get('v2_tag')}] "
                f"{(art.get('title') or '')[:55]} ({art.get('source')} · {art.get('pub_date')})")
        return got

    # 1) 무료 기회 최신순
    opp = sorted([a for a in fresh if a.get("v2_tag") == "free-opportunity"
                  and a.get("source") not in PROVIDER_SOURCES], key=_date_key)
    picked += take(opp, needed - len(picked), "1 기회")

    # 2) Zen 변경 최신순
    if len(picked) < needed:
        zen = sorted([a for a in fresh if a.get("source") == "OpenCode Zen"
                      and a.get("v2_tag") == "free-llm"], key=_date_key)
        picked += take(zen, needed - len(picked), "2 Zen")

    # 3) 일반 뉴스 — LLM 평가 점수 상위순 (동점은 최신순). 3단계까지 왔을 때만 평가한다.
    if len(picked) < needed:
        rest = [a for a in fresh
                if a.get("source") not in PROVIDER_SOURCES
                and a.get("v2_tag") != "free-opportunity"
                and _article_key(a) not in excluded
                and not (_model_key(a) and _model_key(a) in merged_models)]
        _score_candidates([a for a in rest if a.get("_score") is None],
                          scorer or score_helpfulness)
        rest = [a for a in rest if (a.get("_score") or 0) >= SCORE_MIN]
        rest.sort(key=lambda a: (-(a.get("_score") or 0), _date_key(a)))
        picked += take(rest, needed - len(picked), "3 뉴스")

    if picked:
        log(f"  재충원 {len(picked)}건 완료 (빈 슬롯 {needed}개 중 {len(picked)}개 충원)")
    else:
        log(f"  ⓘ 재충원 후보 없음 — 빈 슬롯 {needed}개 유지 (강제 충전 없음)")
    return kept + picked


def main(dedup=True):
    _ = dedup  # v1의 브리핑 중복 제거는 briefing_dedup.filter_duplicates가 담당
    pool, tag_counts = interleave_candidates(CANDIDATE_LIMIT)
    log(f"v2_pass=1 후보: {len(pool)}건 (기회={tag_counts['opportunity']}, zen={tag_counts['zen']}, " +
        ", ".join(f"{t}={tag_counts[t]}" for t in TAG_ORDER) + ") — LLM 도움 점수 평가 시작")
    if not pool:
        log("선정 대상 없음 — 브리핑 건너뜀")
        return []

    # 2. 평가 (429 보호 위해 직렬 + 간격). 기회·Zen 행은 평가 없이 통과시킨다.
    for i, art in enumerate(pool, 1):
        if _is_mechanical(art):
            log(f"  [{i}/{len(pool)}] 평가 생략 (기계 감지 행) {(art.get('title') or '')[:55]}")
            if i < len(pool):
                time.sleep(2)
            continue
        s = score_helpfulness(art)
        d = art.get("_detail")
        log(f"  [{i}/{len(pool)}] {s}점 {'(실용성·이해도·유용성=%s)' % (d,) if d else '(파싱 실패)'} "
            f"{(art.get('title') or '')[:55]}")
        if i < len(pool):
            time.sleep(2)

    # 3. 탈락 제거 (6점 미만 = 평균 2점 미만). 기회·Zen 행은 면제.
    passed = [a for a in pool if _is_mechanical(a) or (a.get("_score") or 0) >= SCORE_MIN]
    dropped = len(pool) - len(passed)
    log(f"탈락 {dropped}건 (점수 < {SCORE_MIN}) → 통과 {len(passed)}건")
    # AIK24-PIPE-04: 같은 프로세스의 브리핑 생성기가 중복 제거 후 재충원할 때 쓰는 풀.
    remember_scored_pool(passed)
    if not passed:
        log("통과 후보 없음 — 브리핑 건너뜀")
        return []

    # 3.5 이미 브리핑된 기사 제거 — 슬롯 배정 전에 해야 한다 (AIK24-PIPE-DEDUP-01).
    # v1은 슬롯을 채운 뒤 auto_briefing 이 dedup 해서 슬롯이 빈 채로 끝났다
    # (2026-10-15 실측: 상위 4건 전부 과거 브리핑분 → "선정된 기사 없음",
    #  신선한 4건은 슬롯 밖으로 밀려남). 같은 판정 함수를 여기서 재사용한다.
    # briefing_dedup 은 auto_news_selector 를 import 하므로 순환 → 지연 import.
    from briefing_dedup import get_history_articles, is_duplicate_article
    history = get_history_articles(d1_query)
    fresh = [a for a in passed if not is_duplicate_article(a, history)[0]]
    if len(fresh) != len(passed):
        log(f"이미 브리핑됨 {len(passed) - len(fresh)}건 제외 → 신선 후보 {len(fresh)}건")
    passed = fresh
    if not passed:
        log("신선 후보 없음 — 브리핑 건너뜀")
        return []

    # 4. 기회 1 + Zen 변경 + 점수순 일반 뉴스
    selected = select_top_articles({"v2": passed}, MAX_COUNT)

    log(f"선정 {len(selected)}건" + ("" if len(selected) == MAX_COUNT
                                    else f" (요청 {MAX_COUNT}건, 데이터 부족 — 강제 선정 없음)"))
    for art in selected:
        log(f"  [{art.get('_score', 0)}점 {art.get('_detail')}] [{art.get('v2_tag')}] "
            f"{(art.get('title') or '')[:60]} ({art.get('source')} · {art.get('pub_date')})")
    return selected


if __name__ == "__main__":
    main()