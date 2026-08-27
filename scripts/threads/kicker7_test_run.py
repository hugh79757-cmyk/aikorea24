#!/usr/bin/env python3
"""kicker7 v3 테스트 러너 v2 — 정보수집 복원 버전.

흐름: URL → crawl → orchestrator 컬렉션(다각도+배경, cross5+bg3)
      → write_kicker7_thread(SYSTEM_KICKER7_V3 + 🔗 마지막 카드 후처리).
운영 코드 미변경 (orchestrator.writer_fn 주입만 사용). 격리된 테스트 전용.
"""
import sys, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts" / "threads"))

OUT_PATH = pathlib.Path("/tmp/kicker7_v3_output.txt")


def main():
    if len(sys.argv) < 2:
        print("usage: kicker7_test_run.py <url>")
        sys.exit(1)
    url = sys.argv[1]

    # 1. crawl
    import standalone_extractor as se
    body, title, pub_date = se.crawl(url)
    if not body or len(body) < 300:
        print(f"[FAIL] crawl 실패/본문 부족 ({len(body or '')}자)")
        sys.exit(1)
    print(f"[CRAWL] {len(body)}자 / 제목: {title} / 발행일: {pub_date}")

    # 2. seed dict
    from urllib.parse import urlparse
    domain = urlparse(url).netloc
    seed = {
        "id": "kicker7-test",
        "title": title or url,
        "link": url,
        "url": url,
        "crawled_body": body,
        "body": body,
        "pub_date": pub_date or "",
        "source": domain,
        "description": body[:200],
    }

    # 3. orchestrator 컬렉션 + kicker7 writer
    from pipeline.threads.contrast.orchestrator import run_contrast_thread
    from pipeline.threads.contrast.kicker7_writer import write_kicker7_thread

    result = run_contrast_thread(seed, [seed], writer_fn=write_kicker7_thread)
    if not result or not result.get("cards"):
        print("[FAIL] 생성 실패 (orchestrator drop 또는 writer None)")
        sys.exit(1)

    cards = result["cards"]
    meta = result.get("search_meta") or {}
    OUT_PATH.write_text("\n\n---\n\n".join(cards), encoding="utf-8")
    print(f"[OK] {len(cards)}카드 (cross={meta.get('cross_n')} bg={meta.get('bg_n')}) "
          f"→ {OUT_PATH}")
    print("=" * 60)
    print("\n\n".join(cards))


if __name__ == "__main__":
    main()
