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


def _link_list(entries):
    """entries → 중복 제거된 SQL IN 리스트 문자열."""
    links = [str(e.get("link") or "").strip() for e in (entries or [])]
    links = [l for l in links if l]
    uniq = list(dict.fromkeys(links))
    return ",".join("'" + l.replace("'", "''") + "'" for l in uniq)


def link_conflicts(entries):
    """INSERT 전 링크 충돌 사전 점검.

    news.link 는 UNIQUE 라, 다른 source 가 같은 링크를 이미 점유하고 있으면
    `INSERT OR IGNORE` 가 그 행을 **소리 없이** 버린다 (2026-10-16 실측: id=56069 가
    'https://openrouter.ai/models?max_price=0' 을 점유해 8건 중 1건이 로그상
    '8건 전송'인데 실제로는 7건만 남았다). 점유 행을 미리 찾아 명시적으로 건너뛴다.

    반환: {link: {'id':..,'title':..,'source':..}} — 충돌 없으면 빈 dict.
    """
    in_list = _link_list(entries)
    if not in_list:
        return {}
    rows = cfnew.sql("SELECT id, title, source, link FROM news WHERE link IN (%s);" % in_list,
                     database_id=cfnew.A24_DB) or []
    return {str(r.get("link")): r for r in rows if isinstance(r, dict)}


def landed_count(entries):
    """INSERT 후 실제 반영 수 — 전송 수와 다르면 조용히 넘기지 않는다 (fail-silent 금지)."""
    in_list = _link_list(entries)
    if not in_list:
        return 0
    rows = cfnew.sql("SELECT COUNT(*) AS c FROM news WHERE link IN (%s);" % in_list,
                     database_id=cfnew.A24_DB) or []
    return int((rows[0] or {}).get("c") or 0) if isinstance(rows[0], dict) else 0


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

        # 링크 충돌 사전 점검 (2026-10-16: link UNIQUE 점유로 1건이 소리 없이 사라졌다)
        conflicts = link_conflicts(todo)
        if conflicts:
            kept = []
            for e in todo:
                held = conflicts.get(str(e.get("link") or "").strip())
                if held:
                    log(f"  ⚠️ 링크 충돌: '{e['title']}' → 기존 id={held.get('id')} "
                        f"(source={held.get('source')}, '{str(held.get('title'))[:40]}') — 건너뜀")
                    continue
                kept.append(e)
            todo = kept

        if not todo:
            log("신규 없음")
            return 0
        res = cfnew.sql(";\n".join(build_inserts(todo)), database_id=cfnew.A24_DB)
        log(f"INSERT {len(todo)}건 전송 (ok={isinstance(res, list)})")

        # 사후 검증 — 전송 수 ≠ 실제 반영 수면 성공으로 보고하지 않는다
        landed = landed_count(todo)
        if landed != len(todo):
            missing = ", ".join(f"'{e['title']}'" for e in todo)
            log(f"⚠️ 등록 건수 불일치: 전송 {len(todo)} / 확인 {landed} — 확인 대상: {missing}")
            return 1
        log(f"확인: {landed}건 반영됨")
    except Exception as e:  # noqa: BLE001 — 실패를 조용히 넘기지 않는다
        log(f"D1 쓰기 실패: {type(e).__name__}: {e}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
