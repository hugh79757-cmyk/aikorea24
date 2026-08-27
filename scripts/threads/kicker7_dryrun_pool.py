#!/usr/bin/env python3
"""kicker7 풀 드라이런 (발행 금지). 주니어 위임용.

흐름: get_articles() → 48h 필터 cap30 → crawl → person_gate → 통과분 orchestrator(kicker7)
결과: /tmp/kicker7_dryrun_*.txt, failed_crawls.json, person_gate 표, 탈락분포.
"""
import sys, json, pathlib, datetime, re

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts/threads"))
sys.path.insert(0, str(ROOT))

import db_reader  # noqa
from pipeline.threads.crawler import fetch_article_body  # noqa
from pipeline.threads.person_gate import person_gate  # noqa
from pipeline.threads.contrast.orchestrator import run_contrast_thread  # noqa
from pipeline.threads.contrast.kicker7_writer import write_kicker7_thread  # noqa

WINDOW_H = 48
CAP = 30
OUT = pathlib.Path("/tmp")
FAILED_CRAWLS = OUT / "failed_crawls.json"


def _parse_dt(s):
    if not s:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.datetime.strptime(s[:19] if "T" in s else s[:19], fmt)
        except ValueError:
            continue
    m = re.match(r"(\d{4}-\d{2}-\d{2})", s or "")
    return datetime.datetime.strptime(m.group(1), "%Y-%m-%d") if m else None


def load_pool():
    arts = db_reader.get_articles()
    now = datetime.datetime.now()
    recent = []
    for a in arts:
        dt = _parse_dt(a.get("pub_date", ""))
        if dt and (now - dt).total_seconds() <= WINDOW_H * 3600:
            recent.append(a)
    recent.sort(key=lambda a: _parse_dt(a.get("pub_date", "")) or now, reverse=True)
    return recent[:CAP]


def classify_drop(reason: str) -> str:
    r = (reason or "").lower()
    if "person" in r and ("none" in r or "부재" in r or "없" in r):
        return "(가)비관료당사자부재"
    if "인용" in r or "quote" in r:
        return "(나)직접인용부재"
    if "대가" in r or "cost" in r or "피해" in r or "해고" in r:
        return "(다)대가부재"
    # fallback: person None → 가
    return "(가)비관료당사자부재"


_ROLE_RE = re.compile(r"해커|주민|시민|CEO|대표|교수|의원|장관|위원|연구원|소장|감독|총장|사장|회장|박사|부장|이사")
_NAME_RE = re.compile(r"[A-Z][a-z]+ [A-Z][a-z]+|[가-힣]{1,4}\s[가-힣]{2,8}")


def rubric(cards, person):
    rows = []
    n = len(cards)
    for i, c in enumerate(cards):
        is_source = c.strip().startswith("--- 카드 6") or c.strip().startswith("출처:")
        has_quote = bool(re.search(r'[「"“]', c))
        has_num = bool(re.search(r"\d", c))
        who_pays = bool(re.search(r"해고|실직|피해|손해|소송|감원|처벌|형사|비용|일자리|오남용|스토킹", c))
        # 출처 카드(카드6)는 화자실명/인용/대가 검출 대상에서 제외
        if is_source:
            role = "출처"
            named = False
        else:
            # 화자실명: 외국인명(영문) 또는 한글 음차명+직함 병합 검출 (카드1~5만)
            named = bool(_NAME_RE.search(c) and _ROLE_RE.search(c)) \
                or bool(re.search(r"[A-Z][a-z]+ [A-Z][a-z]+", c)) \
                or bool(person and person in c)
            if i == n - 2:
                role = "카드5(대가)"
            else:
                role = f"카드{i+1}"
        rows.append({
            "card": role,
            "화자실명": "-" if is_source else ("O" if named else "X"),
            "인용/수치": "-" if is_source else ("O" if (has_quote or has_num) else "X"),
            "대가귀결": "-" if is_source else (
                "O" if (role == "카드5(대가)" and who_pays) else ("X" if role == "카드5(대가)" else "-")),
        })
    return rows


def main():
    pool = load_pool()
    print(f"[POOL] 기준: get_articles() 7일 풀 → pub_date >= now-{WINDOW_H}h 필터 → DESC → cap {CAP}. 조회 {len(pool)}건")
    table, crawled, failed = [], [], []
    failed_crawls = []

    for a in pool:
        aid, title, link = a.get("id"), a.get("title", ""), a.get("link") or a.get("url", "")
        body = fetch_article_body(link, a.get("source", ""), title) if link else ""
        if not body:
            failed_crawls.append({"id": aid, "title": title, "link": link, "reason": "crawl_empty"})
            table.append((title, "X", "-", "-", "크롤실패"))
            continue
        g = person_gate(title, body)
        person = g.get("person")
        gate_label = "gate통과" if g.get("pass") else "gate신호만"
        crawled.append((a, body, person, g.get("pass")))
        table.append((title, "O", gate_label, person or "-", (g.get("reason") or "")[:60]))

    print("\n=== person_gate 표 (신호용 — 생성은 전량) ===")
    print(f"{'제목':<40} {'크롤':<4} {'게이트':<8} {'person':<18} reason")
    for t in table:
        print(f"{str(t[0])[:38]:<40} {t[1]:<4} {t[2]:<8} {str(t[3])[:16]:<18} {t[4][:40]}")

    print(f"\n[결과] 총 {len(pool)}건 / 크롤실패 {len(failed_crawls)} / 생성대상 {len(crawled)}")
    if failed_crawls:
        FAILED_CRAWLS.write_text(json.dumps(failed_crawls, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[기록] {FAILED_CRAWLS}")

    print("\n=== 전량 스레드 생성 (게이트 무관) ===")
    for a, body, person, gp in crawled:
        seed = {"id": a.get("id"), "title": a.get("title"), "link": a.get("link") or a.get("url"),
                "pub_date": a.get("pub_date"), "source": a.get("source"), "crawled_body": body,
                "description": a.get("description", "")}
        res = run_contrast_thread(seed, [seed], writer_fn=write_kicker7_thread)
        if not res or not res.get("cards"):
            print(f"  [DROP] {a.get('title')[:40]} — kicker7 생성 실패")
            continue
        cards = res["cards"]
        path = OUT / f"kicker7_dryrun_{a.get('id')}.txt"
        path.write_text("\n\n".join(cards), encoding="utf-8")
        print(f"  [OK] {a.get('title')[:40]} → {path} ({len(cards)}카드)")
        for r in rubric(cards, person):
            print(f"    {r['card']:<9} 화자실명 {r['화자실명']} 인용/수치 {r['인용/수치']} 대가귀결 {r['대가귀결']}")


if __name__ == "__main__":
    main()
