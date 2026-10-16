#!/usr/bin/env python3
"""aikorea24 주간 무료 기회 수집 (AIK24-PIPE-03 §작업7)

대표님이 매주 월요일 직접 큐레이션한 scripts/logs/weekly_opportunities.json 을 읽어
news 테이블에 INSERT 한다. 선정기(auto_news_selector)의 슬롯 1 이 이 행(v2_tag='free-opportunity')
을 최신 1건 집어 브리핑에 싣는다.

  - access='unverified' 는 넣지 않는다 (미검증 정보를 실으면 신뢰가 깎인다).
  - expires 가 지난 항목은 넣지 않는다.
  - 접근성 표기를 description 끝에 자동 부착한다 — (a) 바로 선택 / (b) 커스텀 프로바이더 /
    로컬 브리지. (b)를 (a)처럼 표현하지 않는다 (지시서 §11).

사용:
  python3 scripts/weekly_opportunity.py --dry-run   # D1 쓰기 없이 선별 결과만
  python3 scripts/weekly_opportunity.py             # D1 INSERT
"""
import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cfnew  # noqa: E402

INPUT_PATH = Path(__file__).resolve().parent / "logs" / "weekly_opportunities.json"
KST = timezone(timedelta(hours=9))
SOURCE = "무료 기회"
CATEGORIES = ("provider_credit", "event_promo", "government", "hackathon", "cloud_compute", "student")
REQUIRED = ("title", "description", "link", "category", "access", "expires")
ACCESS_LABEL = {
    "direct": "(a) OpenCode에서 바로 선택 가능",
    "custom": "(b) 커스텀 프로바이더 설정 후 연결 가능",
    "local": "로컬 브리지(Ollama 등) 필요",
}


def log(msg):
    print(f"[{datetime.now(KST).strftime('%H:%M:%S')}] [opportunity] {msg}")


def load_entries(path=None):
    p = Path(path or INPUT_PATH)
    if not p.exists():
        log(f"입력 파일 없음: {p} — 이번 주 큐레이션 없음으로 처리")
        return []
    data = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError(f"입력은 배열이어야 합니다: {type(data).__name__}")
    return data


def select_entries(entries, today=None):
    """INSERT 대상 선별 (순수 함수 — D1 호출 없음). (선별, 제외사유목록) 반환."""
    today = today or datetime.now(KST).strftime("%Y-%m-%d")
    out, skipped = [], []
    for e in entries or []:
        if not isinstance(e, dict):
            skipped.append(("<non-dict>", f"형식 오류: {type(e).__name__}"))
            continue
        title = (e.get("title") or "").strip() or "<제목 없음>"
        missing = [k for k in REQUIRED if not str(e.get(k) or "").strip()]
        if missing:
            skipped.append((title, "필수 필드 누락: " + ",".join(missing)))
            continue
        if e["category"] not in CATEGORIES:
            skipped.append((title, f"알 수 없는 category={e['category']}"))
            continue
        if e["access"] == "unverified":
            skipped.append((title, "access=unverified (미검증)"))
            continue
        if e["access"] not in ACCESS_LABEL:
            skipped.append((title, f"알 수 없는 access={e['access']}"))
            continue
        if str(e["expires"]) < today:
            skipped.append((title, f"만료 {e['expires']}"))
            continue
        out.append(e)
    return out, skipped


def describe(entry):
    """브리핑에 실릴 description — 접근성 표기 자동 부착."""
    return f"{str(entry['description']).strip()} · {ACCESS_LABEL[entry['access']]}"


def build_inserts(entries, now=None):
    """news INSERT 문 생성 (순수 함수). 컬럼·이스케이프는 news_collector_v2.save() 와 동일."""
    ts = (now or datetime.now(KST)).strftime("%Y-%m-%d %H:%M:%S")

    def lit(v):
        return "'" + str(v or "").replace("'", "''")[:500] + "'"

    stmts = []
    for e in entries:
        stmts.append(
            "INSERT OR IGNORE INTO news "
            "(title, link, description, source, category, pub_date, source_url, original_title, country, v2_pass, v2_tag) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s);"
            % (
                lit(e["title"][:200]), lit(e["link"]), lit(describe(e)),
                lit(SOURCE), lit("benefit"), lit(ts),
                lit(e["link"]), lit(e["title"]), lit("kr"),
                1, lit("free-opportunity"),
            )
        )
    return stmts


def existing_titles():
    rows = cfnew.sql("SELECT title FROM news WHERE source = '%s';" % SOURCE,
                     database_id=cfnew.A24_DB) or []
    return {r.get("title") for r in rows if isinstance(r, dict)}


def main():
    ap = argparse.ArgumentParser(description="주간 무료 기회 → news INSERT (v2_tag=free-opportunity)")
    ap.add_argument("--dry-run", action="store_true", help="D1 쓰기 없이 선별 결과만 출력")
    ap.add_argument("--path", default=str(INPUT_PATH), help="입력 JSON 경로")
    args = ap.parse_args()

    try:
        entries = load_entries(Path(args.path))
    except Exception as e:  # noqa: BLE001
        log(f"입력 로드 실패: {type(e).__name__}: {e}")
        return 1

    selected, skipped = select_entries(entries)
    for title, why in skipped:
        log(f"  제외: {title} — {why}")
    log(f"선별 {len(selected)}건 / 입력 {len(entries)}건")

    if args.dry_run:
        for e in selected:
            log(f"  [INSERT 예정] {e['title']} ({e['category']}/{e['access']}) — {describe(e)}")
        return 0
    if not selected:
        return 0

    try:
        cfnew.check_quota()  # 지시서 §작업7 — 쓰기 전 가드
        known = existing_titles()
        todo = [e for e in selected if e["title"] not in known]
        if len(todo) != len(selected):
            log(f"이미 등록됨 {len(selected) - len(todo)}건 스킵")
        if not todo:
            log("신규 없음")
            return 0
        res = cfnew.sql(";\n".join(build_inserts(todo)), database_id=cfnew.A24_DB)
        log(f"INSERT {len(todo)}건 전송 (ok={isinstance(res, list)})")
    except Exception as e:  # noqa: BLE001 — 실패를 조용히 넘기지 않는다
        log(f"D1 쓰기 실패: {type(e).__name__}: {e}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
