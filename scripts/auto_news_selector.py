#!/usr/bin/env python3
"""aikorea24 브리핑 선정기 v3 (AIK24-PIPE-03)

v2 는 "한국인 초보자가 오늘 무료로 쓸 수 있는가?"를 LLM 도움 점수(실용성·이해도·유용성)로
봤고, v3 는 선정 기준을 **"이 LLM을 OpenCode 같은 CLI 서비스에서 무료로 쓸 수 있는가?"**
로 바꾼다 (지시서 §4-3).

브리핑은 뉴스 3건이다 (2026-10-16 개편):

  1. 무료 기회 1건 : v2_tag='free-opportunity' 최신 1건. 없으면 빈 슬롯
                   (남은 슬롯은 4. 폴백이 채운다 — 기회 큐를 강제 소진하지 않는다).
  2. Zen 변경   : source='OpenCode Zen' 무료 목록 **추가** 감지분 최신 **1건**까지.
                  LLM 점수 무관 우선. 제공 중단 알림(`[제외] ...`)은 대상에서 뺀다.
  3. 일반 뉴스  : 나머지 슬롯을 LLM 도움 점수 상위로. 프로바이더 행은 제외.
  4. 폴백 (AIK24-PIPE-12): 위 풀로 3건이 안 채워지면 **무료 태그 없는 일반 뉴스**로
                  남은 슬롯을 채운다 — 빈 슬롯을 남기지 않는다 (매일 브리핑은 항상 3건).
                  이 폴백 단계에서 2026-10-16 물타기 금지·2026-10-18 강제 충전 없음
                  규칙은 브리핑 슬롯 채우기에 한해 폐기됐다. 단, 제외 조건(이미 브리핑된
                  기사, [제외] 알림, 4개 CLI 프로바이더 행, 지원사업 공고 소스,
                  출처당 1건)은 폴백에서도 그대로 유지한다.
                  AIK24-PIPE-14(2026-11-01): main() 이 이 폴백을 **항상** 켠다 —
                  v2 풀이 전멸(점수 미달·이력 중복)해도 브리핑이 0건으로 끝나지
                  않는다. 예전에는 main() 의 조기 리턴이 폴백을 우회했다.

AIK24-BRIEF-17(2026-11-16 대표님 지시) — 선정 기준 3종 보강:
  · 인사·주가/실적·거시경제 단신은 슬롯에서 제외한다 (_is_briefing_misfit).
  · AI 직접 관련성(0/1/2)을 점수에 반영하고, 폴백 (b) 는 무관 기사보다 관련 기사를
    먼저 본다 (_ai_relevance · _rank_score · _relevance_first_key).
  · 24h 이내 +3 · 48h +2 · 72h +1 최신성 가점 (_recency_bonus) — 며칠 지난 기사보다
    오늘·어제 나온 기사가 먼저 온다.

점수는 DB에 저장하지 않는다(선정 시점 한정).
"""

import re
import sys
import time
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
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
# AIK24-PIPE-04: 재충원 후보 상한 = 무료 기회 3 + Zen 2 + 일반 뉴스 9(태그 3종×3건).
# 선정(CANDIDATE_LIMIT=8)보다 넓게 잡는다 — 중복 제거로 빈 슬롯이 생겼을 때만 쓰이고,
# 그때는 이미 후보가 소진된 뒤라 더 깊은 풀이 필요하다.
# AIK24-PIPE-08: REFILL_POOL_LIMIT=15 였을 때 interleave_candidates 가 만드는 최대 행은
# opp 3 + zen 2 + news 4 = 9행이었고(= 선정 풀과 동일) 상한 15는 사실상 무의미했다.
# 재충원 전용 상한을 아래처럼 분리해 풀 자체를 넓힌다.
REFILL_POOL_LIMIT = 30
# AIK24-PIPE-08: 재충원 전용 후보 범위 확장 (선정 경로 상한은 그대로).
# 원칙: **후보 범위만** 넓힌다 — 점수 관문(SCORE_MIN)과 dedup 기준은 바꾸지 않는다.
# 범위 안의 후보만 쓴다 — 그래도 부족하면 4단계 폴백(일반 뉴스)이 이어받는다
# (AIK24-PIPE-12).
REFILL_WINDOW_HOURS = 72          # 선정 창 36h → 재충원 72h
REFILL_PER_TAG_CANDIDATES = 9     # 태그별 상위 (선정 3)
REFILL_NEWS_CANDIDATES = 12       # 일반 뉴스 상위 (선정 4)
REFILL_OPP_CANDIDATES = 6         # 무료 기회 후보 (선정 3)
REFILL_ZEN_CANDIDATES = 6         # Zen 변경 후보 (선정 2)
# AIK24-PIPE-08: 재충원 슬롯을 **풀별로 분리**한다 — 한 풀이(기회·Zen)이 슬롯을 독식해
# 다른 풀을 막지 않게 한다. 값은 선정 슬롯 구조(기회 1 · Zen 1 · 뉴스 나머지)와 같다.
# Zen 슬롯을 2건으로 올리지는 않는다 — 2026-10-18 실측(Zen 3건 독식 → 실제 뉴스 밀림)
# 사고를 재발시키지 않기 위해 상한 1을 유지한다.
REFILL_OPP_SLOT_CAP = 1
REFILL_ZEN_SLOT_CAP = 1
SCORE_MIN = 6  # 3개 기준 평균 2점 미만 탈락
TAG_ORDER = ("free-llm", "opensource", "tool")
# 2026-10-18 대표님 지시 — "나오지 말아야 할 것이 나왔고, 나올 게 없다면 그 자리를 뉴스가 채워야 한다".
# 실측(2026-10-18 09:00 KST 실행): 후보 8건(기회=3, zen=3, free-llm=3) 중 Zen 변경 3건이
# 슬롯을 우선 독식해, 실제 뉴스 3건이 슬롯을 못 받고 제공 중단 알림 2건이 카드로 나갔다.
ZEN_SLOT_LIMIT = 1  # 슬롯 2 — Zen 목록 변경은 최신 1건만. 남은 슬롯은 일반 뉴스가 채운다.
# 제공 중단 알림([제외])은 브리핑 슬롯 대상이 아니다 — 독자가 오늘 할 행동이 없고,
# 자동 글 생성이 사라진 사유를 추측하게 만든다(2026-10-18: 사유 날조 사고).
EXCLUDED_TITLE_PREFIXES = ("[제외]",)
# Zen 후보 조회 상한 — 슬롯 2(1건) + 재충원 여유 1건. 2026-10-18 이전에는 MAX_COUNT(3)건을
# 조회해 pool 좌석(CANDIDATE_LIMIT=8)을 3석 차지했고, 그중 2석은 쓸 수 없어 실제 뉴스
# 후보가 그만큼 잘렸다(후보 로그: 기회=3, zen=3, free-llm=2). 슬롯 상한과 맞춘다.
ZEN_POOL_LIMIT = ZEN_SLOT_LIMIT + 1
# AIK24-PIPE-12: 브리핑은 항상 3건 — 무료 태그 풀(기회·Zen·무료 뉴스)로 3건이 안
# 채워지면 **무료 태그 없는 일반 뉴스**로 남은 슬롯을 채운다. 2026-10-28 실측:
# 무료 풀 7건 중 신선 1건 → 브리핑 1건 발행(빈 슬롯 2개 공개). "빈 슬롯 유지(강제
# 충전 없음)" 규칙은 브리핑 슬롯 채우기에 한해 폐기된다 (지시서 §규칙 2순위).
# 2026-11-06 실측: 72h 창 + 상한 40 이면 '수집은 272건인데 실제 후보 2건'까지 줄어
# 브리핑 발행이 중단됐다(35건 중 31건이 링크 중복). 창을 120h 로 넓히고 상한을 키운다.
FALLBACK_WINDOW_HOURS = 120  # 폴백 풀 조회 창 (구 72h — 2026-11-06 확대)
FALLBACK_POOL_LIMIT = 120   # 폴백 풀 1차 상한. 15 → 40 (2026-10-28) → 120 (2026-11-06):
#                             최신 15건이 공고·집계(네이버뉴스) 덩어리여서 출처당 1건
#                             규칙상 1건만 나오는 문제를 해결 — 상위 40건에
#                             인공지능신문·IT조선·전자신문 등 기사 소스가 올라온다.
# 2026-11-06: 1차 상한(40)이 **중복 제거 전에** 걸려 실후보가 2건으로 줄었다.
# 부족하면 상한을 키워 한 번 더 조회한다(아래 fallback_fill_general).
FALLBACK_POOL_LIMIT_WIDE = 300
FALLBACK_SCORE_LIMIT = 10   # 폴백 (a)단계 LLM 점수 평가 대상 상한
# 지원사업 공고 소스 — 브리핑 본문 슬롯 대상이 아니다 (지시서 §2순위 제외 조건).
# SQL(get_general_fallback_news)의 이 명시 목록이 1차 방어선이고, 부처·자치단체
# 별도 표기는 _is_announcement_source() 의 접미 방어선(2차)이 담당한다 (3중 방어 원칙).
ANNOUNCEMENT_SOURCES = ("기업마당", "창업진흥원", "정보화진흥원", "지식재산처")
ANNOUNCEMENT_SUFFIXES = ("부", "처", "청", "시", "도")
KST = timezone(timedelta(hours=9))
SCORE_RE = re.compile(r"실용성\s*[:=]\s*(\d)|이해도\s*[:=]\s*(\d)|유용성\s*[:=]\s*(\d)")

_COLS = "id, title, link, description, source, category, pub_date, v2_tag, original_title, created_at, blog_link, origin_link"


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

    AIK24-PIPE-08 — 위 근거는 그대로 유효하다. 3.5단계 dedup 이 D1 이력(3일)뿐이든
    local 이력(30일)까지 보든, 이 SQL 제외는 별개의 1차 방어선이다.
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


def _excluded_titles_sql():
    """슬롯에서 뺄 제목 접두 조건 (제공 중단 알림 등).

    제목 접두만 본다 — 제외 알림은 제목이 `[제외] {모델} — ...` 로 고정돼 있다
    (model_catalog.record_diff_to_news).
    """
    return " AND ".join(
        "title NOT LIKE '" + p.replace("'", "''").replace("%", "") + "%'"
        for p in EXCLUDED_TITLE_PREFIXES)


def get_zen_changes(limit=MAX_COUNT):
    """슬롯 2: Zen 무료 목록 변경 감지분 (model_catalog.record_diff_to_news 가 넣은 행).

    source='OpenCode Zen' + v2_tag='free-llm'. 기계 감지된 사실이라 LLM 도움 점수와
    무관하게 pub_date 최신순으로 우선 배정한다 (2026-10-16 개편).

    2026-10-18 대표님 지시: 제공 중단 알림(`[제외] ...`)은 후보에서 뺀다. 신규 추가
    (`[신규 무료] ...`)만 슬롯 대상이다. 실제 슬롯 상한은 select_top_articles 의
    ZEN_SLOT_LIMIT(=1) 이 적용된다.
    """
    return d1_query("""
        SELECT %s FROM news
        WHERE v2_pass = 1 AND source = 'OpenCode Zen' AND v2_tag = 'free-llm'
          AND created_at >= '%s'
          AND %s
        ORDER BY pub_date DESC
        LIMIT %d
    """ % (_COLS, _slot_cutoff(), _excluded_titles_sql(), limit))


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
        # AIK24-BRIEF-17: 브리핑 독자는 AI 뉴스를 읽으러 온다 — AI와 직접 무관한
        # 기사(인사·선임·부고, 단순 주가·실적·거시경제, 일반 설비 투자)는 3항목 모두
        # 1~2점으로 눌러 SCORE_MIN(6점)을 넘지 못하게 한다.
        "주의: AI(인공지능) 모델·도구·서비스·활용과 직접 관련 없는 기사"
        "(기업 인사·선임·부고, 단순 주가·실적·거시경제, 일반 설비 투자)는 "
        "실용성·이해도·유용성 모두 1~2점으로 평가하세요.\n\n"
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


def select_top_articles(clusters, max_count=MAX_COUNT, allow_fallback=False,
                        d1_query_func=None, scorer=None):
    """클러스터 dict → ① 무료 모델 변동 1 ② 무료 LLM·오픈소스·툴 1 ③ 점수순 일반 뉴스
    ④ (allow_fallback=True) 일반 뉴스 폴백 (AIK24-PIPE-12).

    2026-11-06 대표님 지시로 슬롯을 재설계했다:
      · 무료 기회(free-opportunity) 슬롯 **폐지** — 정보 품질이 낮다는 판단.
      · 슬롯 1 = 무료 모델 변동(OpenCode Zen · Kilo · OpenRouter 최신 1건)
      · 슬롯 2 = 무료 LLM/오픈소스/툴 태그 1건 (개발자용 콘텐츠 우선)
      · 슬롯 3 = 나머지 점수순 일반 뉴스
    "무료 LLM으로 개발하는 사람"을 위한 사이트이므로 1·2 슬롯이 먼저 채워진다.

    ④는 위 풀만으로 max_count 미만일 때 **무료 태그 없는 일반 뉴스**로 남은 슬롯을
    채운다(빈 슬롯을 남기지 않는다). 기본값(False)은 기존 경로(아카이브 v1·재충원
    선행 선정)가 그대로 동작하게 유지하고, 운영 경로인 main() 은 AIK24-PIPE-14
    (2026-11-01)부터 ④를 항상 켠다. ④를 켜는 테스트는 d1_query_func·scorer 를
    주입해 오프라인을 보장한다.
    """
    articles = [a for a in (a for group in (clusters or {}).values() for a in group)
                if a.get("v2_tag") != "free-opportunity"]      # 2026-11-06 폐지
    # AIK24-BRIEF-17: 인사·비AI 단신은 뉴스 슬롯 대상이 아니다 (기계 감지 행은 예외).
    # 정렬은 종합 점수(_rank_score = LLM 점수 + AI 관련성 + 최신성) 내림차순, 동점은 최신순.
    ranked = sorted([a for a in articles
                     if _is_mechanical(a) or not _is_briefing_misfit(a)],
                    key=_rank_key)
    used, picked = set(), []

    # 슬롯 1: 무료 모델 변동 — OpenCode Zen · Kilo · OpenRouter 등 PROVIDER_SOURCES 최신 1건.
    changes = [a for a in articles
               if a.get("source") in PROVIDER_SOURCES and not _is_excluded_notice(a)]
    changes.sort(key=_date_key)
    if changes:
        picked.append(changes[0])
        used.add(changes[0]["id"])
        log(f"  ⓘ 무료 모델 변동 {len(changes)}건 중 1건 배정 (슬롯 1)")
    else:
        log("  ⓘ 무료 모델 변동 없음 — 슬롯 2·3 으로 채움")

    # 슬롯 2: 무료 LLM/오픈소스/툴 태그 1건 — 개발자용 콘텐츠 우선.
    free_news = [a for a in ranked if a["id"] not in used
                 and a.get("source") not in PROVIDER_SOURCES
                 and a.get("v2_tag") in ("free-llm", "opensource", "tool")]
    if free_news and len(picked) < max_count:
        picked.append(free_news[0])
        used.add(free_news[0]["id"])
        log(f"  ⓘ 무료 LLM·개발자 콘텐츠 {len(free_news)}건 중 1건 배정 (슬롯 2)")
    elif len(picked) < max_count:
        log("  ⓘ 무료 LLM·개발자 콘텐츠 없음 — 일반 뉴스로 채움")

    # 슬롯 3: 나머지 = LLM 점수 상위 일반 뉴스 (프로바이더 행 제외, 출처 1건씩).
    rest = [a for a in ranked if a["id"] not in used
            and a.get("source") not in PROVIDER_SOURCES]
    picked += _take(rest, max_count - len(picked))

    # 슬롯 4 (AIK24-PIPE-12): 일반 뉴스 폴백 — 위 풀만으로 max_count 미만이면
    # 무료 태그 없는 일반 뉴스로 남은 슬롯을 채운다 (빈 슬롯을 남기지 않는다).
    if allow_fallback and len(picked) < max_count:
        fb_needed = max_count - len(picked)
        log(f"  [폴백] 무료 풀 부족 — 일반 뉴스 {fb_needed}건 충원 시도")
        picked += fallback_fill_general(
            fb_needed,
            {_article_key(a) for a in picked},
            {a.get("source") for a in picked if a.get("source")},
            {_model_key(a) for a in picked if _model_key(a)},
            d1_query_func, scorer, batch_history=picked)
    return picked


def _date_key(article):
    """'YYYY-MM-DD HH:MM:SS' → 내림차순 정렬용 음수 정수. 파싱 실패면 0(최후)."""
    p = (article.get("pub_date") or "").replace("-", "").replace(":", "").replace(" ", "")
    return -int(p) if p.isdigit() and len(p) >= 8 else 0


def interleave_candidates(limit, refill=False):
    """무료 기회 + Zen 변경 + 일반 뉴스 후보(태그 교차)를 합친다.

    기회·Zen 행은 LLM 점수 대상이 아니지만 dedup(3.5단계)이 필요하므로 pool 에 함께
    넣는다. 일반 뉴스 슬롯 = 태그별 상위 3건 중 라운드로빈. 데이터가 적으면 있는 만큼만
    반환한다(에러 아님).

    AIK24-PIPE-08 — refill=True 면 **재충원 전용**으로 후보 범위만 넓힌다
    (창 36h → 72h, 태그별 상한 해제). 점수 관문(SCORE_MIN)과 dedup 기준은 그대로다.
    선정 경로(기본값)는 아무것도 바뀌지 않는다.
    """
    if refill:
        opp = get_opportunity_news(REFILL_OPP_CANDIDATES)
        zen = get_zen_changes(REFILL_ZEN_CANDIDATES)
        per_tag = {
            t: get_recent_news(hours=REFILL_WINDOW_HOURS, v2_tag=t,
                               exclude_models=True)[:REFILL_PER_TAG_CANDIDATES]
            for t in TAG_ORDER
        }
        news_cap = REFILL_NEWS_CANDIDATES
    else:
        opp = get_opportunity_news(MAX_COUNT)
        zen = get_zen_changes(ZEN_POOL_LIMIT)
        per_tag = {t: get_recent_news(v2_tag=t, exclude_models=True)[:PER_TAG_CANDIDATES]
                   for t in TAG_ORDER}
        news_cap = NEWS_CANDIDATES
    news = [art for row in zip_longest(*(per_tag[t] for t in TAG_ORDER))
            for art in row if art is not None][:news_cap]
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


def _is_excluded_notice(article):
    """슬롯 대상이 아닌 알림 행 (제공 중단 등) — 제목 접두로 판정한다.

    SQL(get_zen_changes)에서 1차로 거르고, 여기서 2차로 거른다. 재충원 풀이나 다른
    경로로 들어온 같은 행이 슬롯을 먹지 않게 하는 방어선이다 (2026-10-18).
    """
    title = article.get("title") or ""
    return any(title.startswith(p) for p in EXCLUDED_TITLE_PREFIXES)


# ---------------------------------------------------------------------------
# AIK24-PIPE-12 — 일반 뉴스 폴백 (브리핑은 항상 3건)
#
# 실측(2026-10-28 07:00): 무료 풀 7건 중 신선 1건 → 재충원 풀 8건도 전부 이력
# 중복 → 빈 슬롯 2개가 그대로 발행됐다. 무료 태그 뉴스는 매일 3건씩 나오지 않으므로
# "빈 슬롯 유지" 원칙이 "매일 브리핑은 항상 3건" 원칙과 충돌한다. 지시서 AIK24-PIPE-12:
# 위 풀로 3건이 안 채워지면 무료 태그 없는 일반 뉴스로 채운다. 제외 조건(이미
# 브리핑된 기사, [제외] 알림, 프로바이더 4종, 지원사업 공고, 출처당 1건)은 그대로.
# ---------------------------------------------------------------------------


def _is_announcement_source(source):
    """지원사업 공고 소스 판정 — SQL(명시 목록) 다음의 2차 방어선 (3중 방어 원칙).

    정부 부처(~~부/~~처/~~청)·자치단체(~~시/~~도)·공고 전용 포털은 브리핑 독자가
    오늘 할 행동이 아니므로 제외한다 (지시서 §2순위 제외 조건).
    """
    s = (source or "").strip()
    if not s:
        return False
    return s in ANNOUNCEMENT_SOURCES or s.endswith(ANNOUNCEMENT_SUFFIXES)


def _pub_ts(article):
    """pub_date → epoch 초 (폴백 정렬용). 파싱 실패면 0 (최후순위).

    news 테이블은 영문 매체(RSS)가 RFC-2822("Tue, 27 Oct 2026 ..."), 국문 매체가
    "YYYY-MM-DD HH:MM:SS" 로 저장한다 — 두 형식이 섞인 상태에서 SQL ORDER BY 는
    비교가 불가하므로 폴백의 최신순 정렬은 파싱 후 비교한다.
    """
    raw = (article.get("pub_date") or "").strip()
    if not raw:
        return 0.0
    try:
        dt = parsedate_to_datetime(raw)
        if dt is not None:
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=KST)
            return dt.timestamp()
    except (TypeError, ValueError):
        pass
    for head, fmt in ((19, "%Y-%m-%d %H:%M:%S"), (10, "%Y-%m-%d")):
        try:
            return datetime.strptime(raw[:head], fmt).replace(tzinfo=KST).timestamp()
        except ValueError:
            continue
    return 0.0


# ---------------------------------------------------------------------------
# AIK24-BRIEF-17 (2026-11-16 대표님 지시) — 브리핑 선정 기준 3종 보강
#
# 사고: 2026-11-16 07:00 브리핑 슬롯 1·2 가 비어 4순위 폴백이 **최신순으로만** 3건을
# 채웠고, `[단독] 한국형 인큐텔 초대 대표에 윤효환 한국벤처투자 본부장 '유력'`(인사),
# `SK하이닉스 HBM4 증설`(설비 투자), `젠슨 황 악재`(인물 단신) 가 그대로 나갔다.
# 폴백 (b) 단계가 점수도, AI 관련성도 보지 않았기 때문이다. 세 가지 방어선을 둔다:
#
#   1) _is_briefing_misfit() — 인사(선임·취임·내정·부고…)와 주가·실적·거시경제 단신은
#      슬롯에서 제외한다. 제품 출시·오픈소스·도구 기사가 인사 표현을 곁들인 경우는
#      _PRODUCT_SIGNAL_RE 로 걸리지 않게 해 오탐을 막는다.
#   2) _ai_relevance() — AI 직접 관련성 0(무관)/1(반도체·GPU·데이터센터 등 인접)/2(AI 직접).
#      폴백 (b) 는 무관 기사보다 관련 기사를 먼저 보고, 점수 정렬(_rank_score)에도 더한다.
#   3) _recency_bonus() — 24h 이내 +3 · 48h +2 · 72h +1. 며칠 지난 기사보다 오늘·어제
#      나온 기사가 먼저 오게 한다 (대표님 요청 2번째 항목).
#
# 범위: 점수 관문(SCORE_MIN)·dedup 기준·슬롯 구조는 그대로다. 바뀌는 것은 **제외와 정렬**
# 뿐이다. AI 후보가 모자라면 폴백 (b) 의 맨 뒤 순서로 무관 기사도 쓸 수 있다 —
# "브리핑은 항상 3건"(AIK24-PIPE-12/14) 규칙을 깨지 않는다.
# ---------------------------------------------------------------------------

RECENCY_BONUS_TIERS = ((24, 3), (48, 2), (72, 1))  # (시간 상한, 가점) — 좁은 것부터
AI_RELEVANCE_BONUS = {2: 4, 1: 1, 0: 0}            # AI 직접 관련성별 점수 가점

# AI 직접 관련 신호 — 모델·도구·서비스·활용. 영문 약어는 단어 경계로 본다
# ("train"·"email" 안의 ai 를 잡지 않게 lookbehind/lookahead 사용).
_AI_DIRECT_RE = re.compile("|".join((
    r"(?<![a-z0-9])ai(?![a-z0-9])",
    r"인공지능", r"에이아이", r"생성형", r"(?:거대|대규모)?\s*언어\s*모델",
    r"멀티모달", r"파운데이션\s*모델", r"파인튜닝", r"프롬프트", r"머신러닝", r"딥러닝",
    r"신경망", r"챗봇", r"에이전트", r"코파일럿", r"환각", r"할루시네이션",
    r"오픈\s*ai",
    r"(?<![a-z0-9])(?:llm|sllm|vlm|slm|gpt|claude|gemini|grok|openai|anthropic|mistral"
    r"|deepseek|qwen|gemma|llama|huggingface|hugging\s*face|opencode|openrouter|ollama"
    r"|nvidia|cuda|pytorch|tensorflow|langchain|mcp)(?![a-z0-9])",
)))

# AI 인접 신호 — AI 기사는 아니지만 AI 산업·활용과 맞닿은 소재 (가점 1단계).
_AI_ADJACENT_RE = re.compile("|".join((
    r"반도체", r"gpu", r"hbm", r"npu", r"데이터\s*센터", r"클라우드", r"빅테크",
    r"로봇", r"자율주행", r"온디바이스", r"추론\s*칩", r"수퍼컴", r"양자컴",
    r"딥테크", r"테크\s*기업", r"엔비디아", r"하이닉스", r"마이크로소프트", r"구글",
)))

# 인사 단신 — 대표 선임·인사 발령·내정·취임·부고.
_PERSONNEL_STRONG_RE = re.compile(
    r"취임|선임|내정|임명|인사\s*발령|인사이동|인사\s*개편|인사\s*발표|신임|전보|승진"
    r"|부고|별세|타계|사임|퇴임|해임|영입|초대\s*(?:대표|사장|회장|원장|본부장)"
)
# "… '유력'" 처럼 직함과 함께 쓰인 경우만 인사로 본다 ("수주 유력" 오탐 방지).
_PERSONNEL_WEAK_RE = re.compile(
    r"(?:대표|사장|회장|원장|본부장|CEO|CTO|CFO|수장|인사|차기|후임)[^\n]{0,40}유력"
    r"|유력[^\n]{0,10}(?:대표|사장|회장|본부장|인사)"
)
# 제품·기술 신호가 있으면 인사 단신 판정을 접는다 — AI 기업/제품 기사를 오탐으로
# 걸러내지 않기 위해서다 (지시서의 "오탐 주의" 조건).
_PRODUCT_SIGNAL_RE = re.compile(
    r"출시|공개|배포|릴리스|업데이트|오픈소스|오픈\s*소스|무료|가격|요금|벤치마크|성능"
    r"|다운로드|플러그인|기능\s*추가|api|깃허브|github|데모|미리보기|정식\s*버전"
    r"|양산|수율|공정|모델\s*공개|서비스\s*개시"
)
# 주가·실적·거시경제·연예/스포츠 단신 (AI 관련성이 없을 때만 제외).
_OFFTOPIC_RE = re.compile(
    r"주가|시가총액|코스피|코스닥|공매도|배당|환율|기준금리|금리\s*(?:인상|인하|동결)"
    r"|소비자물가|물가\s*상승|무역수지|영업이익|분기\s*실적|실적\s*(?:발표|개선|악화)"
    r"|어닝|적자\s*전환|흑자\s*전환|부동산|아파트|전세|청약|프로야구|축구|배구"
    r"|연예|열애|이혼|음주운전|선거|대통령"
)


def _relevance_text(article):
    """제목·설명을 소문자로 합치고 **출처명을 걷어낸** 판정용 텍스트.

    출처명을 지우는 이유: `인공지능신문`·`AI타임스` 처럼 매체명 자체가 AI 키워드를
    담은 경우, 제목·설명에 섞인 매체명만으로 관련성이 부풀려진다 (2026-11-16).
    """
    text = "%s\n%s" % (article.get("title") or "", article.get("description") or "")
    src = (article.get("source") or "").strip()
    if src:
        text = text.replace(src, " ")
    return text.lower()


def _title_text(article):
    """제목만 (소문자·출처명 제거) — 인사·단신 판정은 제목으로 본다.

    설명에는 "공개"·"요금" 같은 단어가 흔해 제목 기준보다 판정이 느슨해진다. 인사·
    단신 판정은 오탐·미탐을 줄이려고 제목만 본다 (2026-11-16).
    """
    title = article.get("title") or ""
    src = (article.get("source") or "").strip()
    if src:
        title = title.replace(src, " ")
    return title.lower()


def _ai_relevance(article):
    """AI 직접 관련성 — 2(직접) / 1(인접) / 0(무관)."""
    text = _relevance_text(article)
    if _AI_DIRECT_RE.search(text):
        return 2
    if _AI_ADJACENT_RE.search(text):
        return 1
    return 0


def _recency_bonus(article, now_ts=None):
    """발행 시각 최신성 가점 — 24h 이내 +3 · 48h +2 · 72h +1 · 그 밖 0.

    pub_date 파싱 실패(0)면 가점 없음. 미래 시각(수집원 시계 오차)은 최신으로 본다.
    now_ts 는 테스트용 주입점이다.
    """
    ts = _pub_ts(article)
    if ts <= 0:
        return 0
    now = datetime.now(timezone.utc).timestamp() if now_ts is None else now_ts
    age_h = max(0.0, (now - ts) / 3600.0)
    for limit, bonus in RECENCY_BONUS_TIERS:
        if age_h <= limit:
            return bonus
    return 0


def _rank_score(article):
    """정렬용 종합 점수 = LLM 도움 점수 + AI 관련성 가점 + 최신성 가점.

    SCORE_MIN 관문은 **원래 LLM 점수(_score)** 로 판정한다 — 이 값은 순위에만 쓴다.
    """
    return ((article.get("_score") or 0)
            + AI_RELEVANCE_BONUS.get(_ai_relevance(article), 0)
            + _recency_bonus(article))


def _rank_key(article):
    """점수 기반 정렬 키 — 종합 점수 내림차순, 동점은 최신순."""
    return (-_rank_score(article), _date_key(article))


def _relevance_first_key(article):
    """폴백 (b) 정렬 키 — AI 관련성 → 최신성 → 발행 시각.

    점수를 보지 않는 단계이므로 "최신"만 보면 오늘 사고처럼 인사·설비 단신이 먼저
    온다. 관련성을 1차 키로 두어 AI 뉴스가 먼저 채워지고, 무관 기사는 같은 단계의
    맨 뒤(마지막 수단)로 밀린다.
    """
    return (-_ai_relevance(article), -_recency_bonus(article), -_pub_ts(article))


def _is_personnel_news(article):
    """인사 단신 판정 — 선임·취임·내정·부고.

    제목에 인사 신호가 있고, 같은 제목에 제품·기술 신호(_PRODUCT_SIGNAL_RE)가 없으면
    인사 단신으로 본다. 제품 출시·오픈소스·도구 기사가 인사 표현을 곁들인 경우는
    막지 않는다 (AI 기업/제품 기사 오탐 방지).
    """
    title = _title_text(article)
    if not (_PERSONNEL_STRONG_RE.search(title) or _PERSONNEL_WEAK_RE.search(title)):
        return False
    return not _PRODUCT_SIGNAL_RE.search(title)


def _is_offtopic_news(article):
    """주가·실적·거시경제 등 비AI 단신 — AI 직접 관련 기사는 예외로 둔다."""
    if _ai_relevance(article) >= 2:
        return False
    return bool(_OFFTOPIC_RE.search(_title_text(article)))


def _is_briefing_misfit(article):
    """브리핑 슬롯에 부적합한 단신 — 인사 또는 비AI 주가/실적·거시경제 기사.

    이 판정은 **슬롯 진입 방어선**이다. 무료 태그 풀·폴백 풀·재충원 풀이 모두 같은
    함수를 쓰므로, 어느 경로로 들어와도 브리핑 카드가 되지 않는다 (3중 방어 원칙).
    """
    return _is_personnel_news(article) or _is_offtopic_news(article)


def get_general_fallback_news(d1_query_func, exclude_ids=(), limit=None):
    """폴백 풀 — 무료 태그 없는 일반 뉴스 (지시서 §2순위).

    - v2_tag 가 없는 행 (무료 기회·Zen·무료 뉴스가 아니다 — v2_pass 관문은 적용 안 함)
    - SQL 1차 방어선: 프로바이더 4종·공고 소스(명시 목록)·[제외] 알림 제외,
      이미 브리핑된 행(briefing_items 전체 이력) 영구 제외
    - 72h 창, 최신순(id DESC — 수집 순서). 동일 기사·유사 기사 차단(2차)과
      출처당 1건(3차)은 fallback_fill_general 이 진행한다.
    """
    cutoff = (datetime.now(timezone.utc)
              - timedelta(hours=FALLBACK_WINDOW_HOURS)).strftime("%Y-%m-%d %H:%M:%S")
    excluded_sql = ""
    if exclude_ids:
        excluded_sql = " AND id NOT IN (%s)" % ", ".join(str(int(i)) for i in exclude_ids)
    rows = d1_query_func("""
        SELECT %s FROM news
        WHERE created_at >= '%s'
          AND (v2_tag IS NULL OR v2_tag = '')
          AND source NOT IN (%s)
          AND id NOT IN (
              SELECT bi.news_id FROM briefing_items bi
              JOIN briefings b ON b.id = bi.briefing_id
              WHERE b.status IN ('published', 'superseded')
          )
          AND %s%s
        ORDER BY id DESC
        LIMIT %d
    """ % (_COLS, cutoff, _sql_in(PROVIDER_SOURCES + ANNOUNCEMENT_SOURCES),
            _excluded_titles_sql(), excluded_sql,
            int(limit or FALLBACK_POOL_LIMIT)))

    # 2026-11-06: 같은 기사가 재수집되면 링크에 쿼리 파라미터만 달라져 SQL GROUP BY 로는
    # 안 묶인다(실측: 상위 40행의 정규화 고유 링크가 7개). 정규화 링크 기준으로 중복을
    # 걷어내 최신 1건만 남긴다 — 이걸 안 하면 상한이 재수집 복사본으로 소진된다.
    try:
        from briefing_dedup import normalize_url
    except Exception:
        return rows
    out, seen = [], set()
    for r in rows:
        key = normalize_url(r.get("link") or "")
        if key:
            if key in seen:
                continue
            seen.add(key)
        out.append(r)
    return out


def _is_nonrunnable_open_weight(art, runnable_max_b=None):
    """실행 불가 오픈 웨이트 판정 — AIK24-PIPE-16 (PIPE-13 로직 그대로 재사용).

    폴백 풀(`v2_tag IS NULL`)은 v2_filter 를 거치지 않으므로, 65B 같은 실행 불가
    오픈 웨이트가 폴백으로 들어올 수 있었다(2026-11-07 리플-65B 사고의 두 번째 진입로).
    판정은 briefing_scorer 의 is_open_weight + extract_param_scale_b + is_runnable_scale 만 쓴다.
    """
    try:
        from briefing_scorer import (extract_param_scale_b, is_open_weight,
                                     is_runnable_scale, load_weights)
    except Exception:  # noqa: BLE001 — 판정 불가면 기존 동작 유지(false positive 방지)
        return False
    text = "%s\n%s" % (art.get("title") or "", art.get("description") or "")
    if not is_open_weight(text):
        return False
    if runnable_max_b is None:
        try:
            runnable_max_b = (load_weights().get("free_usability") or {}).get(
                "runnable_max_b", 32)
        except Exception:  # noqa: BLE001
            runnable_max_b = 32
    return not is_runnable_scale(extract_param_scale_b(text), runnable_max_b)


def fallback_fill_general(needed, exclude_keys, used_sources, merged_models,
                          d1_query_func, scorer, batch_history=()):
    """남은 슬롯을 일반 뉴스(무료 태그 없음)로 채운다 — AIK24-PIPE-12 (a)→(b) 순서.

    (a) LLM 도움 점수 ≥ SCORE_MIN 인 후보를 점수순으로, (b) 그래도 모자라면 점수
    무관 최신순(pub_date DESC)으로 채운다. 제외 조건은 무료 풀과 동일하다:

      - SQL 1차: 프로바이더·공고 소스·[제외]·briefing_items 전체 이력
        (get_general_fallback_news)
      - 2차: filter_duplicates — D1 3일 히스토리 + local 30일 이력. 같은 사건을
        다른 매체가 쓴 기사도 semantic 중복으로 걸린다 (어제 Reddit r/opensource 사건).
      - 3차: 배치 내부 — 이번 브리핑에 이미 고른 항목(kept·폴백분)과
        is_duplicate_article_strict 로 대조 (batch_history)
      - 출처당 1건(used_sources)·모델 통합(merged_models)·선정/탈락분 제외(exclude_keys)

    used_sources·merged_models 는 채택분을 반영해 **제자리에서 갱신**된다.
    반환: 채택한 기사 리스트 (부족하면 있는 만큼만 — 발행 전 실패 알림은 호출자 몫).
    """
    if needed <= 0:
        return []
    if d1_query_func is None:
        d1_query_func = d1_query
    scorer = scorer or score_helpfulness
    # briefing_dedup 은 auto_news_selector 를 import 하므로 순환 → 지연 import.
    from briefing_dedup import filter_duplicates, is_duplicate_article_strict

    pool = get_general_fallback_news(d1_query_func)
    if not pool:
        log("  [폴백] 일반 뉴스 풀 없음")
        return []
    pool = [dict(a) for a in pool]
    fresh, blocked = filter_duplicates(pool, d1_query_func)
    if blocked:
        log(f"  [폴백] 중복 제외 {len(blocked)}건: "
            + ", ".join(reason for _, reason in blocked))

    batch_all = [dict(a) for a in (batch_history or []) if isinstance(a, dict)]
    exclude_keys = set(exclude_keys or ())
    used_sources = set(used_sources or ())
    merged_models = set(merged_models or ())

    def _usable(art):
        """SQL 1차 방어선 다음의 2차 방어 — 출처·제목·모델 키 재검증."""
        src = art.get("source")
        if _is_announcement_source(src) or src in PROVIDER_SOURCES:
            return False
        if _is_excluded_notice(art):
            return False
        # AIK24-BRIEF-17: 인사·주가/실적·거시경제 단신은 일반 뉴스 폴백에도 들이지 않는다.
        if _is_briefing_misfit(art):
            log(f"  [폴백] 부적합 단신(인사·비AI) 제외: {(art.get('title') or '')[:50]}")
            return False
        mkey = _model_key(art)
        if mkey and mkey in merged_models:
            return False
        # AIK24-PIPE-16: 실행 불가 오픈 웨이트(>32B)는 폴백에서도 제외.
        if _is_nonrunnable_open_weight(art):
            log(f"  [폴백] 실행 불가 오픈 웨이트 제외: {(art.get('title') or '')[:50]}")
            return False
        return True

    candidates = [a for a in fresh
                  if _usable(a) and _article_key(a) not in exclude_keys]

    # 채점 전 출처 제외 — kept(published 슬롯)·폴백 앞 단계에서 이미 쓴 출처는
    # 출처당 1건 때문에 선정될 수 없다. LLM 채점 낭비를 막고 (a) 단계 상한
    # FALLBACK_SCORE_LIMIT 이 살아있는 후보를 넓게 보게 하기 위해 여기서 걷어낸다.
    # (a)/(b) 루프의 used_sources 재검사는 방어선으로 그대로 둔다.
    blocked_by_source = [a for a in candidates if a.get("source") in used_sources]
    if blocked_by_source:
        log(f"  [폴백] 출처 이미 사용 ({len(blocked_by_source)}건 채점 제외): "
            + ", ".join(sorted({a.get("source") for a in blocked_by_source})))
    candidates = [a for a in candidates if a.get("source") not in used_sources]

    # 2026-11-06: 1차 상한(40)에서 잘린 뒤 dedup·_usable·출처 필터로 실후보가 급감한 사례
    # (실측: 40건 → 중복 31건 → 사용가능 2건 → 브리핑 3건 미달로 발행 중단).
    # 부족하면 상한을 키워 한 번 더 조회한다(이미 본 id 는 제외, 재조회분도 2차 dedup 통과).
    if len(candidates) < needed:
        seen_ids = {str(a.get("id")) for a in pool if a.get("id") is not None}
        wide = get_general_fallback_news(d1_query_func, limit=FALLBACK_POOL_LIMIT_WIDE)
        extra = [dict(a) for a in wide if str(a.get("id")) not in seen_ids]
        if extra:
            fresh2, blocked2 = filter_duplicates(extra, d1_query_func)
            blocked += blocked2
            usable2 = [a for a in fresh2
                       if _usable(a) and _article_key(a) not in exclude_keys]
            blocked_by_source += [a for a in usable2 if a.get("source") in used_sources]
            more = [a for a in usable2 if a.get("source") not in used_sources]
            log(f"  [폴백] 실후보 부족({len(candidates)}<{needed}) → 넓게 재조회 "
                f"{len(extra)}건 중 사용가능 {len(more)}건")
            candidates = candidates + more

    # (a) 점수 평가 — 최신 FALLBACK_SCORE_LIMIT 건만. 실제 score_helpfulness 는
    # art['_score'] 를 직접 기록한다 (호출 규약 유지 — 반환값으로 덮어쓰지 않는다).
    to_score = [a for a in candidates if a.get("_score") is None][:FALLBACK_SCORE_LIMIT]
    for i, art in enumerate(to_score, 1):
        s = scorer(art)
        log(f"  [폴백 후보 {i}/{len(to_score)}] {s}점 {(art.get('title') or '')[:50]}")
        if i < len(to_score):
            time.sleep(2)

    picked, taken_keys = [], set()

    def _try_take(art, tier):
        """3차 방어선(배치 내부 중복) 통과 시 채택 — 제약 상태를 갱신한다."""
        dup, reason = is_duplicate_article_strict(art, batch_all + picked)
        if dup:
            log(f"  [폴백] 배치 중복 제외 [{reason}] {(art.get('title') or '')[:50]}")
            return False
        picked.append(art)
        taken_keys.add(_article_key(art))
        src = art.get("source")
        if src:
            used_sources.add(src)
        mkey = _model_key(art)
        if mkey:
            merged_models.add(mkey)
        log(f"  [폴백 {tier}] [{art.get('_score', 0)}점] {(art.get('title') or '')[:55]} "
            f"({art.get('source')} · {art.get('pub_date')})")
        return True

    # (a) LLM 도움 점수 ≥ SCORE_MIN — 종합 점수순 (AI 관련성·최신성 가점 포함, 동점은 최신순)
    for art in sorted([a for a in candidates if (a.get("_score") or 0) >= SCORE_MIN],
                      key=lambda a: (-_rank_score(a), -_pub_ts(a))):
        if len(picked) >= needed:
            break
        if art.get("source") in used_sources:
            continue
        _try_take(art, "a 점수순")

    # (b) 점수 무관 — AI 관련성 우선, 같은 관련성 안에서는 최신순 (pub_date DESC).
    #     AIK24-BRIEF-17: 예전에는 최신순만 보아 인사·설비 단신이 앞자리를 차지했다.
    #     무관 기사도 후보에 남아 있으므로 AI 후보가 모자라면 맨 뒤에서 채운다.
    if len(picked) < needed:
        for art in sorted([a for a in candidates if _article_key(a) not in taken_keys],
                          key=_relevance_first_key):
            if len(picked) >= needed:
                break
            if art.get("source") in used_sources:
                continue
            _try_take(art, "b 관련성·최신순")

    # (c) 출처 제약 완화 — (a)(b)로도 부족하면 이미 쓴 출처에서 추가 선정.
    # 2026-11-02 실측: 9개 후보 중 7개가 이미 쓴 2개 출처라 전부 제외돼 2건에서
    # 멈춤. 빈 브리핑(0건)보다는 같은 출처 2건이 낫다.
    if len(picked) < needed and blocked_by_source:
        for art in sorted([a for a in blocked_by_source
                           if _article_key(a) not in taken_keys],
                          key=lambda a: (-(a.get("_score") or 0), -_ai_relevance(a),
                                         -_pub_ts(a))):
            if len(picked) >= needed:
                break
            _try_take(art, "c 출처완화")

    if picked:
        log(f"  [폴백] 일반 뉴스 {len(picked)}건으로 슬롯 충원")
    return picked


# ---------------------------------------------------------------------------
# AIK24-PIPE-04 — 중복 제거 후 재충원
#
# 실측(2026-10-17 07:00 실행): selector 는 3건을 선정했는데 auto_briefing 의 Phase 2
# 중복 제거가 2건(local_semantic · local_exact_id)을 탈락시켜 브리핑이 1건으로 발행됐다.
# 그 원인은 selector 의 3.5단계 dedup 과 Phase 2 의 dedup **기준 불일치**였다 —
# 3.5단계는 D1 이력만 보고 local history(briefing_dedup.json)를 보지 않아,
# local 히스토리 중복이 선정 이후에야 드러났다 → 빈 슬롯을 다시 채우는
# 로직이 없으면 그대로 빈 채 발행된다. 여기서 그 슬롯을 계단식으로 채운다.
#
# AIK24-PIPE-08(2026-10-21): 기준 불일치를 없앴다 — 3.5단계가 Phase 2 와 **같은**
# filter_duplicates(D1 이력 + local 이력)를 쓰므로 이제 "선정→Phase 2 탈락"은
# 구조적으로 발생하지 않는다(오늘의 56206 케이스). 재충원 풀도 넓혔다(A-5).
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

    AIK24-PIPE-08: 재충원 전용 상한(refill=True)으로 만든다 — 선정 풀과 같은 9행이면
    후보가 고갈됐을 때 재충원이 무의미하다(2026-10-21 실측: 재충원 9/9 탈락).
    """
    pool, _ = interleave_candidates(REFILL_POOL_LIMIT, refill=True)
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
      4) 일반 뉴스 폴백 (AIK24-PIPE-12) — 무료 태그 없는 일반 뉴스로 남은 슬롯을 채운다

    - 이미 선정된 항목(kept)과 중복 제거로 탈락한 항목(dropped)은 후보에서 제외한다.
    - 재충원 후보도 중복 검사(2차 방어)를 다시 통과한 것만 쓴다.
    - 그래도 부족하면 남은 슬롯은 발행 전 실패 알림으로 처리된다 (호출자
      auto_briefing.main 의 <3 가드) — 빈 브리핑을 저장하지 않는다.
    - 모델 행은 merge_same_models 와 같은 키(original_title)로 중복 통합을 방어한다.
    - AIK24-PIPE-08: 슬롯을 **풀별로 분리**한다(기회 상한·Zen 상한). 한 풀이 슬롯을
      독식해 다른 풀을 막지 않게 한다. 남는 슬롯은 일반 뉴스가 채운다.
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

    # 1) 무료 기회 최신순 — AIK24-PIPE-08: 기회 슬롯 상한(1)으로 분리한다.
    opp = sorted([a for a in fresh if a.get("v2_tag") == "free-opportunity"
                  and a.get("source") not in PROVIDER_SOURCES], key=_date_key)
    picked += take(opp, min(needed - len(picked), REFILL_OPP_SLOT_CAP), "1 기회")

    # 2) Zen 변경 최신순 — select_top_articles 와 같은 슬롯 상한(1건)을 지킨다.
    # (2026-10-18: 재충원 단계에서도 제공 중단 알림이 슬롯을 먹던 경로를 막는다)
    # AIK24-PIPE-08: Zen 슬롯 상한을 기회 슬롯과 **분리**한다 — 기회가 슬롯을 독식해
    # Zen 이 못 받는 상황을 없앤다(값 1 은 2026-10-18 사고 방어를 위해 유지).
    if len(picked) < needed:
        zen = sorted([a for a in fresh if a.get("source") == "OpenCode Zen"
                      and a.get("v2_tag") == "free-llm"
                      and not _is_excluded_notice(a)], key=_date_key)
        picked += take(zen, min(needed - len(picked), REFILL_ZEN_SLOT_CAP), "2 Zen")

    # 3) 일반 뉴스 — LLM 평가 점수 상위순 (동점은 최신순). 3단계까지 왔을 때만 평가한다.
    if len(picked) < needed:
        rest = [a for a in fresh
                if a.get("source") not in PROVIDER_SOURCES
                and a.get("v2_tag") != "free-opportunity"
                and not _is_briefing_misfit(a)          # AIK24-BRIEF-17: 인사·비AI 단신 제외
                and _article_key(a) not in excluded
                and not (_model_key(a) and _model_key(a) in merged_models)]
        _score_candidates([a for a in rest if a.get("_score") is None],
                          scorer or score_helpfulness)
        rest = [a for a in rest if (a.get("_score") or 0) >= SCORE_MIN]
        rest.sort(key=_rank_key)
        picked += take(rest, needed - len(picked), "3 뉴스")

    # 4) 일반 뉴스 폴백 (AIK24-PIPE-12) — 무료 태그 없는 일반 뉴스로 남은 슬롯을 채운다.
    #    폴백 풀은 선정·재충원 풀(v2_pass=1)과 다른 조회라 여기서 처음 나온다.
    #    배치 내부 중복은 kept + 지금까지 picked 를 batch_history 로 넘겨 막는다.
    if len(picked) < needed:
        picked += fallback_fill_general(
            needed - len(picked), excluded,
            {a.get("source") for a in kept + picked if a.get("source")},
            merged_models, d1_query_func, scorer, batch_history=kept + picked)

    if picked:
        log(f"  재충원 {len(picked)}건 완료 (빈 슬롯 {needed}개 중 {len(picked)}개 충원)")
    if len(picked) < needed:
        log(f"  ⚠️ 폴백 후에도 후보 부족 — 슬롯 {needed - len(picked)}개 미충원 "
            "(발행 전 실패 알림으로 처리)")
    return kept + picked


def count_fresh_candidates(d1_query_func, pool=None):
    """LLM 채점 전, 최종 dedup 기준(D1+local)으로 살아남는 후보 수.

    pool 이 None 이면 기존 후보 풀 빌더로 생성한다.
    채점(Score)·저장 등 어떤 부작용도 없어야 한다.

    AIK24-PIPE-08 §B-2 계약 — run_pipeline 의 "후보 풀 깊이 게이트"(조기 경보)가
    이 함수를 호출한다. 계약:
      - 판정 기준은 **3.5단계와 동일한** filter_duplicates(D1 이력 + local 이력)다.
      - 반환값은 int (살아남는 후보 수).
      - 부작용 없음: LLM 호출 없음, 파일 쓰기 없음, 저장 없음.
        D1 조회는 **주입된 d1_query_func 로만** 수행한다(자체 네트워크 호출 없음).
    """
    from briefing_dedup import filter_duplicates  # 순환 import → 지연 import
    if pool is None:
        pool, _ = interleave_candidates(CANDIDATE_LIMIT)
    kept, _removed = filter_duplicates(list(pool), d1_query_func)
    return len(kept)


def main(dedup=True, d1_query_func=None):
    """선정 진입점 — 항상 **최대 MAX_COUNT(3)건**을 반환하려 시도한다 (AIK24-PIPE-12/14).

    d1_query_func 는 테스트·재사용용 주입점이다 (기본값 None → 모듈 d1_query).
    AIK24-PIPE-14: 4단계 폴백(일반 뉴스)이 이 함수 안에서 실제로 **도달 가능**해야
    하므로, 폴백이 쓰는 D1 조회를 여기서 명시적으로 넘긴다.
    """
    _ = dedup  # v1의 브리핑 중복 제거는 briefing_dedup.filter_duplicates가 담당
    d1q = d1_query_func or d1_query
    pool, tag_counts = interleave_candidates(CANDIDATE_LIMIT)
    log(f"v2_pass=1 후보: {len(pool)}건 (기회={tag_counts['opportunity']}, zen={tag_counts['zen']}, " +
        ", ".join(f"{t}={tag_counts[t]}" for t in TAG_ORDER) + ") — LLM 도움 점수 평가 시작")
    if not pool:
        # AIK24-PIPE-14 판단: **수집 자체가 0건**인 경우는 폴백으로 덮지 않는다.
        # 폴백 풀(72h 일반 뉴스)까지 비어 있을 가능성이 높고, 수집기 장애를 72시간 지난
        # 일반 뉴스로 가리는 쪽이 더 위험하다 (AIK24-PIPE-08 B-2 조기 경보가 이 상황을
        # 이미 알린다). 폴백은 "무료 풀은 있는데 dedup 으로 전부 빠진" 경우를 담당한다.
        log("선정 대상 없음(수집 0건) — 브리핑 건너뜀 (B-2 조기 경보 확인)")
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
    # AIK24-PIPE-14 (2026-11-01 사고): 여기서 리턴하지 않는다. 점수 미달로 통과 0건이어도
    # 슬롯 4(일반 뉴스 폴백)로 흘려보낸다 — 예전에는 이 조기 리턴이 폴백을 우회해
    # 브리핑이 0건으로 끝났다 (수집 105건 → v2 4건 전멸 → "브리핑 건너뜀").
    if not passed:
        log("통과 후보 없음 — 슬롯 4(일반 뉴스 폴백)로 이어간다")

    # 3.5 이미 브리핑된 기사 제거 — 슬롯 배정 전에 해야 한다 (AIK24-PIPE-DEDUP-01).
    # v1은 슬롯을 채운 뒤 auto_briefing 이 dedup 해서 슬롯이 빈 채로 끝났다
    # (2026-10-15 실측: 상위 4건 전부 과거 브리핑분 → "선정된 기사 없음",
    #  신선한 4건은 슬롯 밖으로 밀려남). 같은 판정 함수를 여기서 재사용한다.
    #
    # AIK24-PIPE-08: **Phase 2 와 동일한 기준**으로 거른다.
    #   이전에는 D1 이력(3일)만 보고 local 이력(30일)은 보지 않아, 선정 단계에서는
    #   살아남은 기사가 Phase 2(auto_briefing.filter_duplicates)에서 탈락했다
    #   ("선정→탈락", 2026-10-21 실측: 56206 이 local_exact_id 로 탈락 → 브리핑 0건).
    #   이제 양쪽이 같은 filter_duplicates(D1 이력 + local 이력)를 쓰므로
    #   선정에서 통과한 기사는 Phase 2 에서 추가 탈락하지 않는다.
    # briefing_dedup 은 auto_news_selector 를 import 하므로 순환 → 지연 import.
    from briefing_dedup import filter_duplicates
    passed, removed = filter_duplicates(passed, d1q)
    if removed:
        log(f"이미 브리핑됨 {len(removed)}건 제외 → 신선 후보 {len(passed)}건")
        for art, reason in removed:
            log(f"    [{reason}] {(art.get('title') or '')[:50]}")
    # AIK24-PIPE-14: dedup 전멸(2026-11-01 실측 — v2 4건이 전부 "이미 브리핑됨")도
    # 조기 리턴하지 않는다. 폴백(일반 뉴스: v2_tag 없음 · 72h · 미브리핑)이 남은
    # 슬롯을 채운다 — 폴백에서도 0건일 때만 브리핑을 건너뛴다.
    if not passed:
        log("신선 후보 없음 — 슬롯 4(일반 뉴스 폴백)로 이어간다")

    # 4. 기회 1 + Zen 변경 + 점수순 일반 뉴스 + (슬롯 4) 일반 뉴스 폴백
    #    AIK24-PIPE-14: allow_fallback=True — v2 풀이 일부만 있어도 남은 슬롯을 일반
    #    뉴스로 채운다. 폴백분 점수는 fallback_fill_general 내부 규칙((a) 점수 ≥
    #    SCORE_MIN 점수순 → (b) 점수 무관 최신순)을 그대로 따르며 재평가는 하지 않는다.
    #    d1_query_func·scorer 를 **명시적으로 주입**한다 — 폴백이 쓰는 D1 조회를
    #    호출자(main 파라미터)가 통제할 수 있어야 테스트가 오프라인으로 돈다
    #    (select_top_articles docstring 의 "④를 켜는 테스트는 주입한다" 계약).
    selected = select_top_articles(
        {"v2": passed}, MAX_COUNT,
        allow_fallback=True,
        d1_query_func=d1q,
        scorer=score_helpfulness,
    )

    if not selected:
        log("폴백(일반 뉴스) 포함 신선 후보 없음 — 브리핑 건너뜀")
        return []

    log(f"선정 {len(selected)}건" + ("" if len(selected) == MAX_COUNT
                                    else f" (요청 {MAX_COUNT}건, 무료 풀·폴백 부족 — "
                                         "재충원에서 추가 충원 시도)"))
    for art in selected:
        log(f"  [{art.get('_score', 0)}점 {art.get('_detail')}] [{art.get('v2_tag')}] "
            f"{(art.get('title') or '')[:60]} ({art.get('source')} · {art.get('pub_date')})")
    return selected


if __name__ == "__main__":
    main()