#!/usr/bin/env python3
"""Compass 2-pass 드라이런 — 실제 LLM으로 compass + body 생성.

사용법:
  python3 scripts/threads/compass_dryrun.py <url>
  python3 scripts/threads/compass_dryrun.py <url> --tone fan_friendly
  python3 scripts/threads/compass_dryrun.py <url> --skip-g4
  python3 scripts/threads/compass_dryrun.py --all-tones

흐름: URL → crawl → compass Pass1 → G4 gate → Pass2 body → 저장 (발행 없음)
"""
import sys, json, pathlib, datetime, argparse, traceback

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts" / "threads"))

OUT = pathlib.Path("/tmp")
POSTED_JSON = ROOT / "pipeline" / "posted.json"


def _backup_compass_counters():
    with open(POSTED_JSON, "r") as f:
        data = json.load(f)
    return {
        "compass_intro_rotation": data.get("compass_intro_rotation", 0),
        "compass_h2_rotation": data.get("compass_h2_rotation", 0),
    }


def _restore_compass_counters(backup):
    with open(POSTED_JSON, "r") as f:
        data = json.load(f)
    data["compass_intro_rotation"] = backup["compass_intro_rotation"]
    data["compass_h2_rotation"] = backup["compass_h2_rotation"]
    with open(POSTED_JSON, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _pick_latest_article():
    """DB에서 최신 기사 1건 선택."""
    import db_reader
    arts = db_reader.get_articles()
    if not arts:
        return None
    def _dt(a):
        s = a.get("pub_date", "")
        try:
            return datetime.datetime.strptime(s[:19], "%Y-%m-%d %H:%M:%S")
        except Exception:
            return datetime.datetime.min
    arts.sort(key=_dt, reverse=True)
    return arts[0]


def _crawl(url, source, title):
    from pipeline.threads.crawler import fetch_article_body
    body = fetch_article_body(url, source, title)
    if not body or len(body) < 300:
        print(f"크롤링 실패: {url}")
        sys.exit(1)
    return body


def _detect_summary_format(body):
    """본문에서 사용된 요약 형식 감지."""
    last_md = body.rfind("📌")
    if last_md < 0:
        return "unknown"
    tail = body[last_md:]
    if tail.startswith("📌 **요약**"):
        return "bullet"
    elif tail.startswith("📌 요약."):
        return "narrative"
    elif tail.startswith("📌 핵심 질문."):
        return "key_question"
    elif tail.startswith("📌 마무리."):
        return "natural_close"
    return "unknown"


def _extract_summary_block(body):
    """본문에서 마지막 📌 섹션(요약 블록) 추출."""
    last_md = body.rfind("📌")
    if last_md < 0:
        return "(요약 블록 없음)"
    return body[last_md:]


def _run_single(url, tone, skip_g4, restore=True):
    """단일 드라이런 실행. 결과 dict 반환.

    restore=False이면 posted.json 카운터를 백업/복원하지 않음
    (--all-tones 모드에서 외부에서 한 번만 복원).
    """
    # ── 기사 선택 및 크롤링 ──
    if ":" in url and not url.startswith("http"):
        pass

    from pipeline.threads.crawler import fetch_article_body

    # URL 모드 vs DB 모드 구분: http 로드 시도
    if url.startswith("http"):
        body = _crawl(url, "manual", "")
        title = body[:80].split("\n")[0]
        seed = {
            "id": "manual", "title": title, "link": url, "url": url,
            "crawled_body": body, "pub_date": datetime.datetime.now().strftime("%Y-%m-%d"),
            "source": "manual", "description": body[:200],
        }
        all_articles = [seed]
        source_url = url
    else:
        a = _pick_latest_article()
        if not a:
            print("[FAIL] DB에 기사 없음")
            sys.exit(1)
        link = a.get("link") or a.get("url", "")
        if not link:
            print(f"크롤링 실패: {url}")
            sys.exit(1)
        body = _crawl(link, a.get("source", ""), a.get("title", ""))
        aid = a.get("id")
        title = a.get("title", "")
        seed = {
            "id": aid, "title": title, "link": link, "url": link,
            "crawled_body": body,
            "pub_date": a.get("pub_date", ""),
            "source": a.get("source", ""),
            "description": a.get("description", "") or body[:200],
        }
        all_articles = [seed]
        source_url = link

    print(f"[INFO] 기사: {title[:60]}")
    print(f"[INFO] 본문: {len(body)}자")
    print(f"[INFO] 톤: {tone}")
    print(f"[INFO] G4 fact-gate {'SKIP' if skip_g4 else 'ON'}")
    print()

    # ── posted.json 카운터 백업 ──
    if restore:
        backup = _backup_compass_counters()

    try:
        # ── Compass pipeline ──
        from pipeline.threads.compass import write_compass_article

        print(f"[PASS 1] Compass JSON 생성 중... (mode=blog, tone={tone})")
        result = write_compass_article(
            seed, all_articles,
            output_target="naver",
            skip_g4=skip_g4,
            mode="blog",
            tone=tone,
        )

        if result is None:
            print("[FAIL] Compass pipeline 실패 (Pass 1 또는 G4 차단)")
            return None

        compass, output = result
        body_pass2 = output.get("body", "")

        if len(body_pass2) < 500:
            print(f"[FAIL] Pass 2 본문 너무 짧음 ({len(body_pass2)}자)")
            return None

        # ── 파일 저장 ──
        ts = datetime.datetime.now().strftime("%H%M%S")
        filepath = OUT / f"compass_dryrun_{ts}_{tone}.md"

        intro_style = compass.get("intro_style", "?")
        h2_flow = compass.get("h2_flow", "?")
        summary_format = _detect_summary_format(body_pass2)
        fact_gate_passed = "Skipped" if skip_g4 else "True"
        summary_block = _extract_summary_block(body_pass2)

        content = f"""# Compass Dryrun Result
- timestamp: {datetime.datetime.now().isoformat()}
- tone: {tone}
- mode: blog
- skip_g4: {skip_g4}
- source_url: {source_url}

## Compass JSON (Pass 1)
```json
{json.dumps(compass, ensure_ascii=False, indent=2)}
```

## Body (Pass 2)
{body_pass2}

## Summary Block
{summary_block}

## Meta
intro_style: {intro_style}
h2_flow: {h2_flow}
summary_format: {summary_format}
fact_gate_passed: {fact_gate_passed}
"""
        filepath.write_text(content, encoding="utf-8")

        print(f"[SAVED] → {filepath}")
        return {"filepath": filepath, "compass": compass, "body": body_pass2}

    except Exception as e:
        traceback.print_exc()
        return None

    finally:
        if restore:
            _restore_compass_counters(backup)


def main():
    parser = argparse.ArgumentParser(description="Compass 2-pass dryrun")
    parser.add_argument("url", nargs="?", default=None, help="기사 URL (생략 시 DB 최신 기사)")
    parser.add_argument("--tone", default="neutral_careful",
                        choices=["neutral_careful", "fan_friendly", "analytical"],
                        help="톤 (기본값: neutral_careful)")
    parser.add_argument("--skip-g4", action="store_true", help="G4 fact-gate 건너뛰기")
    parser.add_argument("--all-tones", action="store_true", help="3개 톤 연속 실행")
    args = parser.parse_args()

    if args.all_tones:
        if not args.url:
            print("[FAIL] --all-tones 모드에서는 URL 필요: python3 scripts/threads/compass_dryrun.py <url> --all-tones")
            sys.exit(1)
        backup = _backup_compass_counters()
        try:
            for tone in ["neutral_careful", "fan_friendly", "analytical"]:
                print(f"\n{'=' * 60}")
                print(f"[ALL-TONES] tone={tone}")
                print(f"{'=' * 60}")
                result = _run_single(args.url, tone, args.skip_g4, restore=False)
                if result is None:
                    print(f"[FAIL] tone={tone} 실패, 중단")
                    sys.exit(1)
        finally:
            _restore_compass_counters(backup)
    else:
        if not args.url:
            print("사용법: python3 scripts/threads/compass_dryrun.py <url> [--tone X] [--skip-g4]")
            sys.exit(1)
        result = _run_single(args.url, args.tone, args.skip_g4)
        if result is None:
            sys.exit(1)


if __name__ == "__main__":
    main()
