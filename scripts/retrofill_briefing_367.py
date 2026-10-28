#!/usr/bin/env python3
"""AIK24-PIPE-12 소급 채우기 — 브리핑 id=367 (2026-10-28-1) 1건 → 3건.

지시서: /Users/twinssn/Desktop/메모 Hugh-v2/SSOT/프로젝트/aikorea24/지시서/
        2026-10-28-0946-AIK24-PIPE-12-브리핑-항상3건-일반뉴스-폴백.md §소급 채우기
(대표님 2026-10-28 12:21 결정).

- 기존 1건(57426, 인공지능신문 엔타이어)의 순서·내용은 바꾸지 않는다.
- 추가 2건은 2순위 폴백 규칙 그대로: fallback_fill_general
  (a) LLM 도움 점수 ≥6 순 → (b) 부족하면 점수 무관 pub_date DESC.
  제외 조건(이미 브리핑된 기사 — 어제 Reddit 2건 포함, [제외], 프로바이더 4종,
  지원사업 공고, 출처당 1건)은 본 경로와 동일하게 적용된다.
- 코멘트는 기존 브리핑 코멘트 생성 경로(generate_comment + cli_free_block)와 동일.
- 이메일 재발송 금지 — 웹은 SSR(D1 직독)이라 이 INSERT 만으로 페이지가 갱신된다.
- 완료 후 briefing_dedup.json 에 2건을 기록해 내일 dedup 이 재사용하지 않게 한다.

실행 (세션 주입 토큰은 무권한 — 반드시 해제하고 OAuth 기본 프로필로):
  env -u CLOUDFLARE_API_TOKEN -u CLOUDFLARE_ACCOUNT_ID \
      python3 scripts/retrofill_briefing_367.py
"""
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
for p in (str(_HERE), str(_HERE.parent), str(_HERE / "threads" / "v3")):
    if p not in sys.path:
        sys.path.insert(0, p)

import auto_news_selector as sel  # noqa: E402
import auto_briefing  # noqa: E402
import briefing_dedup  # noqa: E402

BRIEFING_ID = 367


def log(msg):
    print(f"[retrofill] {msg}", flush=True)


def main():
    log("=== 소급 채우기: 브리핑 id=367 ===")

    # 0. 현재 상태 확인 — 반드시 기존 1건짜리여야 한다 (두 번 실행 방지).
    head = sel.d1_query(
        f"SELECT id, date, status, intro FROM briefings WHERE id = {BRIEFING_ID}")
    if not head:
        log(f"브리핑 {BRIEFING_ID} 없음 — 종료")
        return 1
    cur = sel.d1_query(
        "SELECT bi.news_id, bi.sort_order, bi.comment, n.title, n.source "
        f"FROM briefing_items bi JOIN news n ON n.id = bi.news_id "
        f"WHERE bi.briefing_id = {BRIEFING_ID} ORDER BY bi.sort_order")
    log(f"현재 등기: {len(cur)}건")
    if len(cur) != 1:
        log(f"기대와 다른 상태(기존 1건이어야 함) — 중단. 실제: {[c['news_id'] for c in cur]}")
        return 1
    existing_id = int(cur[0]["news_id"])
    existing_src = cur[0]["source"]
    log(f"기존 1건: {existing_id} 《{cur[0]['title'][:45]}》 ({existing_src}, sort={cur[0]['sort_order']})")

    # 1. 폴백 선정 (실제 LLM 도움 점수). SQL 이 briefing_items 전체 이력을 제외하고,
    #    filter_duplicates(D1 3일 + local 30일)가 어제 Reddit 재보도 등을 막는다.
    existing = sel.d1_query(
        "SELECT %s FROM news WHERE id = %d" % (sel._COLS, existing_id))
    picked = sel.fallback_fill_general(
        2,
        {"id:" + str(existing_id)},
        {existing_src},
        set(),
        sel.d1_query,
        sel.score_helpfulness,
        batch_history=existing,
    )
    if len(picked) < 2:
        log(f"폴백 후보 부족 ({len(picked)}/2) — 중단 (임의 채움 금지)")
        return 1

    # 2. 코멘트 생성 — 기존 브리핑 저장 경로와 동일한 조합.
    for art in picked:
        title = (art.get("title") or "")[:50]
        log(f"  코멘트 생성: {title}")
        comment = auto_briefing.generate_comment(art)
        block = auto_briefing.cli_free_block(art)
        if block:
            comment = f"{comment}\n\n{block}".strip()
        art["_comment"] = (comment or "").strip()

    # 3. D1 기록 — 기존 sort_order 는 그대로 (1), 새 건은 뒤에 (2, 3).
    for i, art in enumerate(picked, start=len(cur) + 1):
        comment_escaped = art["_comment"].replace("'", "''")
        sql = (f"INSERT INTO briefing_items (briefing_id, news_id, sort_order, comment) "
               f"VALUES ({BRIEFING_ID}, {int(art['id'])}, {i}, '{comment_escaped}')")
        if not auto_briefing.d1_execute(sql):
            log(f"  INSERT 실패: news_id={art['id']} — 중단 (D1 상태 수동 확인 필요)")
            return 1
        log(f"  INSERT 완료: sort={i} news_id={art['id']} 《{(art.get('title') or '')[:45]}》")

    # 4. intro 갱신 — 1건 → 3건 (형식은 build_briefing 과 동일 유지).
    new_intro = (head[0]["intro"] or "").replace(
        "AI 소식 1건을 정리했습니다.", "AI 소식 3건을 정리했습니다.")
    if "AI 소식 3건을 정리했습니다." not in new_intro:
        log("intro 치환 실패 — 형식이 기대와 다름, intro 유지 (확인 필요)")
    elif not auto_briefing.d1_execute(
            f"UPDATE briefings SET intro = '{new_intro.replace(chr(39), chr(39) * 2)}' "
            f"WHERE id = {BRIEFING_ID}"):
        log("intro UPDATE 실패 — 아이템은 저장됨, intro만 수동 확인 필요")
    else:
        log("intro 갱신 완료: AI 소식 3건을 정리했습니다.")

    # 5. local 이력 기록 — record_briefing 은 data['articles'] 에 쌓고 30일 초과를
    #    정리한다 (아침 실행과 동일 경로). 내일 dedup 이 재사용하지 않게 하는 목적.
    briefing_dedup.record_briefing(BRIEFING_ID, picked, sel.d1_query)
    log(f"briefing_dedup.json 에 {len(picked)}건 기록 완료")

    # 6. 결과 확인
    final = sel.d1_query(
        "SELECT bi.sort_order, bi.news_id, n.source, n.title "
        f"FROM briefing_items bi JOIN news n ON n.id = bi.news_id "
        f"WHERE bi.briefing_id = {BRIEFING_ID} ORDER BY bi.sort_order")
    log(f"=== 최종 {len(final)}건 ===")
    for r in final:
        log(f"  sort={r['sort_order']} [{r['source']}] 《{r['title'][:45]}》")
    return 0


if __name__ == "__main__":
    sys.exit(main())
