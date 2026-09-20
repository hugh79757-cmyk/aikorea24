#!/usr/bin/env python3
"""Compass 2-pass 드라이런 — 실제 LLM으로 compass + body 생성.

사용법:
  python3 scripts/threads/compass_dryrun.py <url>
  python3 scripts/threads/compass_dryrun.py  # DB에서 최신 기사 자동 선택

흐름: URL → crawl → compass Pass1 → G4 gate → Pass2 body → 출력 (발행 없음)
"""
import sys, json, pathlib, datetime

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts" / "threads"))

OUT = pathlib.Path("/tmp")


def _pick_latest_article():
    """DB에서 최신 기사 1건 선택."""
    import db_reader
    arts = db_reader.get_articles()
    if not arts:
        return None
    # pub_date 기준 최신
    def _dt(a):
        s = a.get("pub_date", "")
        try:
            return datetime.datetime.strptime(s[:19], "%Y-%m-%d %H:%M:%S")
        except Exception:
            return datetime.datetime.min
    arts.sort(key=_dt, reverse=True)
    return arts[0]


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    url = args[0] if args else None
    skip_g4 = "--skip-g4" in sys.argv

    if url:
        # URL 모드: 직접 크롤
        from pipeline.threads.crawler import fetch_article_body
        body = fetch_article_body(url, "manual", "")
        if not body or len(body) < 300:
            print(f"[FAIL] 크롤 실패/본문 부족 ({len(body or '')}자)")
            sys.exit(1)
        title = body[:80].split("\n")[0]
        aid = "manual"
        source = "manual"
        seed = {
            "id": aid, "title": title, "link": url, "url": url,
            "crawled_body": body, "pub_date": datetime.datetime.now().strftime("%Y-%m-%d"),
            "source": source, "description": body[:200],
        }
        all_articles = [seed]
    else:
        # DB 모드
        a = _pick_latest_article()
        if not a:
            print("[FAIL] DB에 기사 없음")
            sys.exit(1)
        from pipeline.threads.crawler import fetch_article_body
        link = a.get("link") or a.get("url", "")
        body = fetch_article_body(link, a.get("source", ""), a.get("title", ""))
        if not body or len(body) < 300:
            print(f"[FAIL] 크롤 실패/본문 부족 ({len(body or '')}자) — {a.get('title', '')[:40]}")
            sys.exit(1)
        aid = a.get("id")
        title = a.get("title", "")
        source = a.get("source", "")
        seed = {
            "id": aid, "title": title, "link": link, "url": link,
            "crawled_body": body,
            "pub_date": a.get("pub_date", ""),
            "source": source,
            "description": a.get("description", "") or body[:200],
        }
        all_articles = [seed]

    print(f"[INFO] 기사: {title[:60]}")
    print(f"[INFO] 본문: {len(body)}자")
    print(f"[INFO] 소스: {source}")
    if skip_g4:
        print("[INFO] G4 fact-gate SKIP 모드")
    print()

    # ── Compass pipeline ──
    from pipeline.threads.compass import write_compass_article

    print("[PASS 1] Compass JSON 생성 중...")
    result = write_compass_article(seed, all_articles, output_target="naver", skip_g4=skip_g4)

    if result is None:
        print("[FAIL] Compass pipeline 실패 (Pass 1 또는 G4 차단)")
        sys.exit(1)

    compass, output = result

    # ── 출력 ──
    print("\n" + "=" * 60)
    print("COMPASS JSON (Pass 1)")
    print("=" * 60)
    print(json.dumps(compass, ensure_ascii=False, indent=2))

    print("\n" + "=" * 60)
    print("DRAFT BODY (Pass 2)")
    print("=" * 60)
    if isinstance(output, dict) and "cards" in output:
        cards = output["cards"]
        for i, card in enumerate(cards, 1):
            print(f"\n--- 카드 {i} ---")
            print(card)
    else:
        print(output)

    # ── 파일 저장 ──
    ts = datetime.datetime.now().strftime("%H%M%S")
    compass_path = OUT / f"compass_{ts}.json"
    body_path = OUT / f"compass_body_{ts}.txt"

    compass_path.write_text(json.dumps(compass, ensure_ascii=False, indent=2), encoding="utf-8")
    if isinstance(output, dict) and "cards" in output:
        body_path.write_text("\n\n---\n\n".join(output["cards"]), encoding="utf-8")
    else:
        body_path.write_text(str(output), encoding="utf-8")

    print(f"\n[SAVED] compass → {compass_path}")
    print(f"[SAVED] body → {body_path}")


if __name__ == "__main__":
    main()
