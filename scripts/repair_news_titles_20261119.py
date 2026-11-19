#!/usr/bin/env python3
"""2026-11-19 사고 복구 — 배치 번역 제목 밀림(news 61933~61940) 교정.

사고: 05:30 수집 회차(무료 LLM 배치 번역)에서 61933~61940 의 제목이 **한 칸씩 밀렸다.**
  · 밀림 시작 61933 — 제목이 61934 원제목("Snapchat … AR Lenses")의 번역으로 바뀌었고
    자기 제목(Palmer Luckey 기사)은 사라졌다.
  · 61939 "The AI Hype Index" 기사가 "냄새 스타트업" 제목을,
    61940 "This smell startup" 기사가 "오픈소스 진영, 젠슨 황의 복귀를 원해" 제목을 가졌다.
  · DESC 는 자기 기사 것이 정확해서 브리핑·뉴스레터·EmDash 심층글에서
    "제목과 내용이 완전히 다른" 상태로 발행됐다.

복구 방법: 검증된 사실만 쓴다.
  · 61934~61940 의 올바른 제목 = 바로 앞 행이 현재 들고 있는 제목(밀림의 역방향).
    근거: 8개 행의 (한국어 제목 ↔ 다음 행 원제목) 짝이 전부 일치함을 실측 확인.
  · 61933 은 사라진 제목이라 원제목을 단건 번역(단건 경로는 밀림 위험이 없다)해 채운다.

원인 코드 수정은 `api_test/news_collector.py` 의 AIK24-TRANSLATE-ALIGN-01
(번호 블록 단위 파싱 + 번호 매핑) 참조.

사용:
  ../.venv/bin/python3 scripts/repair_news_titles_20261119.py --dry-run
  ../.venv/bin/python3 scripts/repair_news_titles_20261119.py --apply
"""
import argparse
import datetime as dt
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cfnew  # noqa: E402

LOGS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")

# 61933 은 번역문이 유실된 행 — 원제목 단건 번역 결과를 고정해 둔다.
PALMER_TITLE = '파머 럭키, "AI 기반 사이버 공격이 방어를 앞지른다… 이제 뛰어야 할 때"'

START_ID = 61933
END_ID = 61940


def fetch_rows():
    sql = (
        "SELECT id, title, original_title FROM news "
        f"WHERE id BETWEEN {START_ID} AND {END_ID} ORDER BY id"
    )
    return cfnew.sql(sql, database_id=cfnew.A24_DB)


def build_plan(rows):
    """{id: new_title} — 앞 행의 현재 제목을 한 칸씩 앞으로 당긴다."""
    assert len(rows) == (END_ID - START_ID + 1), f"예상 {END_ID-START_ID+1}행, 실제 {len(rows)}행"
    plan = {}
    for pos, row in enumerate(rows):
        if pos == 0:
            plan[row["id"]] = PALMER_TITLE
        else:
            plan[row["id"]] = rows[pos - 1]["title"]
    return plan


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    rows = fetch_rows()
    plan = build_plan(rows)

    print(f"대상 {len(rows)}행 (news {START_ID}~{END_ID})")
    for row in rows:
        new = plan[row["id"]]
        mark = "=" if new == row["title"] else "→"
        print(f'{row["id"]} {mark}')
        print(f'   전: {row["title"]}')
        if new != row["title"]:
            print(f'   후: {new}')
            print(f'   원: {row["original_title"][:90]}')

    if not a.apply:
        print("\n[DRY-RUN] 쓰기 없음. 적용하려면 --apply")
        return 0

    os.makedirs(LOGS, exist_ok=True)
    ts = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = os.path.join(LOGS, f"backup_news_titles_{ts}.json")
    with open(backup, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=1)
    print(f"\n백업: {backup}")

    changed = 0
    for row in rows:
        new = plan[row["id"]]
        if new == row["title"]:
            continue
        # 낙관적 동시성: 읽은 제목이 그대로일 때만 바꾼다.
        esc_t = row["title"].replace("'", "''")
        esc_n = new.replace("'", "''")
        stmt = (
            "UPDATE news SET title = '" + esc_n + "' "
            f"WHERE id = {row['id']} AND title = '" + esc_t + "';"
        )
        res = cfnew.sql(stmt, database_id=cfnew.A24_DB)
        print(f'  {row["id"]} UPDATE → {res}')
        changed += 1

    after = fetch_rows()
    bad = [r["id"] for r in after if r["title"] != plan[r["id"]]]
    print(f"\n변경 {changed}행 · 사후검증 불일치 {len(bad)}행 {bad}")
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main())
