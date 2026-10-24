#!/usr/bin/env python3
"""AIK24-D1-READ-03 (D-2) — D1 실행계획 회귀 감지.

왜 필요한가 (2026-10-24 실측 사고):
  emdash 홈(`src/pages/index.astro`)이 `orderBy: { publishedAt: "desc" }`(camelCase)를
  넘겨 SQL 이 `ORDER BY "publishedAt" DESC` 가 됐다. 그런 컬럼이 없으므로 SQLite 는
  이를 **문자열 상수**로 취급 → published_at 인덱스를 못 타고 `TEMP B-TREE` 정렬 →
  SELECT 목록의 상관 서브쿼리(terms/bylines)가 1,521행 전체에 평가됨.
  결과: 홈 1회 miss 당 11,312행. 시간당 12회 miss → 3,393,820행/일(계정 한도의 68%).
  노출 순서는 `id DESC` 로 떨어져 우연히 최신순처럼 보였기 때문에 육안으로는 정상이었다.

  즉 "출력은 정상인데 요금만 폭주"하는 유형이라 눈으로는 못 잡는다. 실행계획을 주기적으로
  검사해 `TEMP B-TREE`(정렬 인덱스 미사용)와 전량 스캔을 잡아낸다.

비용: EXPLAIN QUERY PLAN 은 행을 읽지 않는다(0행). 30분마다 호출해도 과금 영향 없음.

사용:
    python3 scripts/d1_plan_guard.py            # 검사 (위반 시 exit 1)
    python3 scripts/d1_plan_guard.py --self-test  # 가드가 실제로 회귀를 잡는지 검증

30분 리포트(`scripts/d1_usage_report.py`)가 매 주기 호출한다.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cfnew  # noqa: E402

# (이름, DB, SQL, 금지 패턴)
#   금지 패턴은 EXPLAIN QUERY PLAN 의 detail 문자열에서 찾는다.
#   "TEMP B-TREE" = ORDER BY/GROUP BY 를 인덱스로 못 받아 전량 정렬.
#   "SCAN ec_posts" = ec_posts 전량 스캔(COVERING INDEX 는 COUNT 용이라 허용).
GUARDS = [
    (
        "emdash.home",
        cfnew.EMDASH_DB,
        "SELECT * FROM ec_posts WHERE deleted_at IS NULL AND status='published' "
        "ORDER BY published_at DESC, id DESC LIMIT 10",
        ["TEMP B-TREE", "SCAN ec_posts"],
    ),
    (
        "emdash.posts.page",
        cfnew.EMDASH_DB,
        "SELECT * FROM ec_posts WHERE deleted_at IS NULL AND status='published' "
        "ORDER BY published_at DESC, id DESC LIMIT 12 OFFSET 12",
        ["TEMP B-TREE", "SCAN ec_posts"],
    ),
    (
        "emdash.sitemap",
        cfnew.EMDASH_DB,
        "SELECT slug, id, updated_at FROM ec_posts WHERE status = 'published' "
        "AND deleted_at IS NULL ORDER BY published_at DESC",
        ["TEMP B-TREE"],
    ),
    (
        "a24.home.briefings",
        cfnew.A24_DB,
        "SELECT * FROM briefings WHERE status = 'published' ORDER BY id DESC LIMIT 1",
        ["TEMP B-TREE"],
    ),
]

# 가드 자기검증용 — 실제 사고를 재현하는 쿼리(반드시 위반으로 잡혀야 한다).
SELF_TEST_CASE = (
    "self-test(camelCase ORDER BY)",
    cfnew.EMDASH_DB,
    "SELECT * FROM ec_posts WHERE deleted_at IS NULL AND status='published' "
    'ORDER BY "publishedAt" DESC, "id" DESC LIMIT 10',
    ["TEMP B-TREE"],
)


def check_case(case):
    """케이스 1건 검사 → 위반 detail 문자열 리스트(빈 리스트 = 통과)."""
    name, db, sql, forbidden = case
    try:
        rows = cfnew.sql("EXPLAIN QUERY PLAN " + sql, database_id=db)
    except Exception as e:  # noqa: BLE001 — 가드 실패가 리포트를 죽이면 안 된다
        return [f"EXPLAIN 실패: {type(e).__name__}: {str(e)[:90]}"]
    details = [str(r.get("detail", "")) for r in rows if isinstance(r, dict)]
    bad = []
    for pat in forbidden:
        for d in details:
            if pat in d and not (pat == "SCAN ec_posts" and "COVERING INDEX" in d):
                bad.append(d[:110])
    return bad


def run(cases=None, verbose=True):
    """전체 검사 → (위반 목록, 검사 건수)."""
    cases = cases if cases is not None else GUARDS
    violations = []
    for case in cases:
        name = case[0]
        bad = check_case(case)
        if bad:
            violations.append((name, bad))
            if verbose:
                print(f"[PLAN-GUARD] ⚠️ {name}: " + " / ".join(bad))
        elif verbose:
            print(f"[PLAN-GUARD] ok {name}")
    return violations, len(cases)


def main():
    if "--self-test" in sys.argv[1:]:
        # 1) 정상 쿼리는 통과해야 한다
        ok_violations, _ = run(cases=[GUARDS[0]], verbose=False)
        # 2) 사고 재현 쿼리는 반드시 잡혀야 한다
        bad_violations, _ = run(cases=[SELF_TEST_CASE], verbose=False)
        passed = (not ok_violations) and bool(bad_violations)
        print(f"[PLAN-GUARD] self-test: 정상쿼리 위반 {len(ok_violations)}건 · "
              f"사고재현 검출 {len(bad_violations)}건 → {'통과' if passed else '실패'}")
        return 0 if passed else 1

    violations, n = run()
    if violations:
        print(f"[PLAN-GUARD] 실행계획 회귀 {len(violations)}건 / 검사 {n}건 — 인덱스 미사용 의심")
        return 1
    print(f"[PLAN-GUARD] 실행계획 정상 — 검사 {n}건, 위반 0건")
    return 0


if __name__ == "__main__":
    sys.exit(main())
