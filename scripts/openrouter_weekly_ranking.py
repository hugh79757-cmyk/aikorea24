#!/Users/twinssn/Projects/aikorea24/.venv/bin/python3
"""AIK24-OR-WEEKLY-01 — OpenRouter 주간 토큰 랭킹 집계 + EmDash 초안 생성.

매주 일요일에 실행된다 (launchd kr.aikorea24.openrouter-weekly, 09:00 ICT).
직전 일요일~토요일 7일간의 OpenRouter rankings-daily 를 집계해
Top 10 모델을 추출하고, EmDash CMS 에 글을 쓴 뒤 **품질 게이트를 통과하면 발행까지** 한다
(2026-11-12 대표님 지시 — 초안만 만들던 것을 자동 발행으로 전환).
게이트 미달이면 초안으로 남기고 사유를 로그에 남긴다.

사용:
  python3 scripts/openrouter_weekly_ranking.py                       # 기본: 직전 완성 주
  python3 scripts/openrouter_weekly_ranking.py --start-date 2026-10-25 --end-date 2026-10-31
  python3 scripts/openrouter_weekly_ranking.py --dry-run             # 집계+JSON만, 글 생성 안 함
  python3 scripts/openrouter_weekly_ranking.py --no-publish          # 초안까지만(자동 발행 끔)
"""
import argparse
import json
import os
import sys
from datetime import date, datetime, timedelta, timezone

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, SCRIPT_DIR)
sys.path.insert(0, PROJECT_ROOT)

ICT = timezone(timedelta(hours=7))

ENV_COMMON = os.path.expanduser("~/.env.common")


def load_env_common():
    """~/.env.common 에서 필요한 키만 로드 (값은 로그에 찍지 않는다)."""
    if not os.path.exists(ENV_COMMON):
        return
    with open(ENV_COMMON, encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = val


load_env_common()

# emdash04_migrate 는 PyYAML 을 요구하며, 시스템 python 에는 없다.
# 어떤 인터프리터로 실행되든 .venv 로 재실행한다 (launchd plist 도 .venv 를 쓴다).
try:
    import yaml  # noqa: F401
except ModuleNotFoundError:
    _venv = os.path.join(PROJECT_ROOT, ".venv", "bin", "python3")
    if os.path.exists(_venv) and os.path.realpath(sys.executable) != os.path.realpath(_venv):
        os.execv(_venv, [_venv] + sys.argv)
    raise

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "").strip()
OPENROUTER_URL = "https://openrouter.ai/api/v1/datasets/rankings-daily"
FREE_MODELS_URL = "https://emdash.aikorea24.kr/posts/free-models"


def _fmt_tokens(n):
    """토큰 수를 한국어 단위로 (예: 45.2조 개)."""
    n = int(n)
    if n >= 1_000_000_000_000:
        return "약 %.1f조 개" % (n / 1_000_000_000_000)
    if n >= 100_000_000:
        return "약 %.1f억 개" % (n / 100_000_000)
    if n >= 10_000:
        return "약 %.1f만 개" % (n / 10_000)
    return "약 %d 개" % n


def week_window(today_ict=None):
    """직전 완성 주(일~토)의 (start, end) date. 오늘이 일요일이면 직전 주."""
    if today_ict is None:
        today_ict = datetime.now(ICT).date()
    # days since Sunday (Mon=0..Sun=6 → Sunday 기준)
    days_since_sunday = (today_ict.weekday() + 1) % 7
    this_sunday = today_ict - timedelta(days=days_since_sunday)
    # 직전 완성 주 = 이전 주 일~토
    prev_sunday = this_sunday - timedelta(days=7)
    prev_saturday = prev_sunday + timedelta(days=6)
    return prev_sunday, prev_saturday


def fetch_rankings(start_date, end_date):
    """OpenRouter rankings-daily 조회. (rows, as_of) 반환."""
    import urllib.request
    import urllib.error

    url = "%s?start_date=%s&end_date=%s" % (OPENROUTER_URL, start_date.isoformat(), end_date.isoformat())
    req = urllib.request.Request(url, headers={"Authorization": "Bearer %s" % OPENROUTER_API_KEY})
    last_err = None
    for attempt in range(1, 6):
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                raw = resp.read().decode("utf-8")
            d = json.loads(raw)
            return d.get("data", []), (d.get("meta") or {}).get("as_of")
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
            last_err = e
            import time
            time.sleep(min(2 ** (attempt - 1), 20))
    raise RuntimeError("OpenRouter rankings-daily 조회 실패: %r" % last_err)


def aggregate(rows):
    """model_permaslug 별 7일 토큰 합산 → Top 10 (other 제외)."""
    totals = {}
    for r in rows:
        slug = r.get("model_permaslug")
        if not slug or slug == "other":
            continue
        try:
            tok = int(r.get("total_tokens", "0"))
        except (ValueError, TypeError):
            continue
        totals[slug] = totals.get(slug, 0) + tok
    ordered = sorted(totals.items(), key=lambda kv: kv[1], reverse=True)
    out = []
    for i, (slug, tok) in enumerate(ordered[:10], start=1):
        out.append({
            "rank": i,
            "model_permaslug": slug,
            "total_tokens": tok,
            "tokens_human": _fmt_tokens(tok),
            "is_free": slug.endswith(":free"),
        })
    return out, len(totals)


def _load_prev_week(week_start):
    """직전 주 집계 JSON. 없으면 None (전주 비교 절을 쓰지 않는다)."""
    log_dir = os.path.join(PROJECT_ROOT, "scripts", "logs")
    try:
        names = sorted(n for n in os.listdir(log_dir)
                       if n.startswith("openrouter_weekly_") and n.endswith(".json"))
    except OSError:
        return None
    prev_path = None
    for n in names:
        d = n[len("openrouter_weekly_"):-len(".json")]
        try:
            dd = datetime.strptime(d, "%Y-%m-%d").date()
        except ValueError:
            continue
        if dd < week_start:
            prev_path = os.path.join(log_dir, n)
    if not prev_path:
        return None
    try:
        with open(prev_path, encoding="utf-8") as f:
            data = json.load(f)
    except Exception:  # noqa: BLE001
        return None
    return data if data.get("top10") else None


def build_markdown(week_start, week_end, top10, n_models, as_of, prev=None):
    """주간 랭킹 글 본문 (2026-11-12 재작성).

    독자 순서로 쓴다 — 이번 주 결론 → 순위표 → 달라진 점 → 무료 모델 관점 → 읽는 법 → 마무리.
    전주 JSON 이 있으면 순위·토큰 변화를 붙이고, 없으면 그 절을 통째로 생략한다(추정 금지).
    """
    prev_rank, prev_tok = {}, {}
    for r in ((prev or {}).get("top10") or []):
        prev_rank[r["model_permaslug"]] = r.get("rank")
        prev_tok[r["model_permaslug"]] = r.get("total_tokens") or 0

    free_count = sum(1 for r in top10 if r["is_free"])
    free_names = [r["model_permaslug"] for r in top10 if r["is_free"]]
    total_top = sum(r["total_tokens"] for r in top10) or 1
    first = top10[0]
    second = top10[1] if len(top10) > 1 else None

    def pct(tok):
        return tok * 100.0 / total_top

    L = []
    # ── 리드: 결론부터
    lead = ("이번 주(%d년 %d월 %d일~%d일) OpenRouter에서 가장 많이 쓰인 모델은 **%s**입니다. "
            "7일 동안 %s 토큰입니다"
            % (week_start.year, week_start.month, week_start.day, week_end.day,
               first["model_permaslug"], first["tokens_human"]))
    if second:
        lead += " — 2위(%s)의 %.1f배입니다" % (second["tokens_human"],
                                             first["total_tokens"] / max(second["total_tokens"], 1))
    lead += "."
    L.append(lead)
    L.append("")
    if prev:
        p1 = prev_rank.get(first["model_permaslug"])
        pt1 = prev_tok.get(first["model_permaslug"])
        delta = ""
        if pt1:
            rate = (first["total_tokens"] - pt1) * 100.0 / pt1
            delta = (" 지난주 같은 모델의 토큰(%.1f조)보다 %.0f%% %s했습니다."
                     % (pt1 / 1e12, abs(rate), "늘어" if rate >= 0 else "줄어"))
        if p1 == 1:
            L.append("1위는 지난주와 같습니다. 2주 연속 정상입니다." + delta)
        elif p1:
            L.append("지난주 %d위였던 모델이 이번 주 1위로 올라왔습니다." % p1)
        else:
            L.append("이 모델은 지난주 상위 10위에 없었습니다. 이번 주에 새로 1위가 됐습니다.")
        L.append("")
    if free_count:
        L.append("상위 10개 중 **%d개**가 무료 모델입니다." % free_count)
    else:
        L.append("상위 10개 중 무료 모델은 없습니다. 이번 주 사용량 상위권은 전부 유료 경로입니다.")
    L.append("")

    # ── 순위표
    L.append("## 이번 주 순위")
    L.append("")
    L.append("OpenRouter가 자사 API를 통과한 요청의 토큰 수를 모델별로 집계해 공개합니다. "
             "아래는 %d월 %d일~%d일(UTC) 7일간 입력·출력 토큰 합산입니다."
             % (week_start.month, week_start.day, week_end.day))
    L.append("")
    if prev:
        L.append("| 순위 | 모델 | 7일간 토큰 | 상위10 비중 | 지난주 |")
        L.append("|---|---|---|---|---|")
    else:
        L.append("| 순위 | 모델 | 7일간 토큰 | 상위10 비중 |")
        L.append("|---|---|---|---|")
    for r in top10:
        name = r["model_permaslug"]
        pr = prev_rank.get(name)
        if prev:
            if pr:
                last = "%d위" % pr
            else:
                last = "신규"
            L.append("| %d | %s | %s | %.1f%% | %s |"
                     % (r["rank"], name, r["tokens_human"], pct(r["total_tokens"]), last))
        else:
            L.append("| %d | %s | %s | %.1f%% |"
                     % (r["rank"], name, r["tokens_human"], pct(r["total_tokens"])))
    L.append("")
    L.append("‘상위10 비중’은 이 표에 들어온 10개 모델의 토큰 합계를 100으로 놓은 비율입니다. "
             "전체 시장 점유율이 아니라 상위권 안에서의 비중입니다.")
    L.append("")
    L.append("집계 방법: OpenRouter Data API(rankings-daily)로 %d월 %d일~%d일(UTC) 일별 상위 모델의 토큰 수를 "
             "합산했습니다. 날짜가 붙은 변형은 OpenRouter 표기를 그대로 따랐고, 상위 50위 밖 모델의 합산 항목(other)은 "
             "순위에서 제외했습니다. 집계 대상은 %d개 모델 변형입니다."
             % (week_start.month, week_start.day, week_end.day, n_models))
    L.append("")

    # ── 달라진 점 (전주 데이터가 있을 때만)
    if prev:
        entrants = [r for r in top10 if r["model_permaslug"] not in prev_rank]
        movers_up = []
        movers_down = []
        for r in top10:
            pr = prev_rank.get(r["model_permaslug"])
            if pr and pr > r["rank"]:
                movers_up.append((r, pr))
            elif pr and pr < r["rank"]:
                movers_down.append((r, pr))
        growth = []
        for r in top10:
            pt = prev_tok.get(r["model_permaslug"])
            if pt:
                rate = (r["total_tokens"] - pt) * 100.0 / pt
                growth.append((rate, r))
        growth.sort(reverse=True)

        L.append("## 이번 주에 달라진 것")
        L.append("")
        if entrants:
            L.append("- **새로 들어온 모델**: " + ", ".join(
                "%s (%d위)" % (r["model_permaslug"], r["rank"]) for r in entrants))
        else:
            L.append("- 이번 주 상위 10개는 지난주와 같은 구성입니다. 순위만 바뀌었습니다.")
        for r, pr in movers_up[:3]:
            L.append("- **상승**: %s %d위 → %d위" % (r["model_permaslug"], pr, r["rank"]))
        for r, pr in movers_down[:3]:
            L.append("- **하락**: %s %d위 → %d위" % (r["model_permaslug"], pr, r["rank"]))
        ups = [(rate, r) for rate, r in growth if rate > 0][:2]
        downs = [(rate, r) for rate, r in growth if rate < 0][-1:] if growth else []
        for rate, r in ups:
            L.append("- **토큰 증가**: %s, 지난주보다 %.0f%% 늘었습니다 (%.1f조 → %.1f조)"
                     % (r["model_permaslug"], rate,
                        prev_tok.get(r["model_permaslug"], 0) / 1e12, r["total_tokens"] / 1e12))
        for rate, r in downs:
            L.append("- **토큰 감소**: %s, 지난주보다 %.0f%% 줄었습니다 (%.1f조 → %.1f조)"
                     % (r["model_permaslug"], abs(rate),
                        prev_tok.get(r["model_permaslug"], 0) / 1e12, r["total_tokens"] / 1e12))
        L.append("")

    # ── 무료 모델 관점
    L.append("## 무료 모델 관점")
    L.append("")
    if free_count:
        L.append("상위 10개 중 무료 모델은 **%d개**입니다: %s"
                 % (free_count, ", ".join(free_names)))
        L.append("")
        L.append("같은 모델이라도 무료 변형(:free)은 별도 항목으로 집계됩니다. "
                 "유료 경로와 무료 경로의 사용량이 나뉘어 보이는 것은 정상입니다.")
    else:
        L.append("이번 주 상위 10개에는 무료 변형(:free)이 하나도 없습니다. "
                 "무료 모델이 ‘덜 쓰인다’는 뜻은 아닙니다 — 무료 티어는 호출 한도가 있어 "
                 "대량 사용이 유료 경로로 몰리는 경향이 있습니다.")
        L.append("")
        L.append("무료로 쓸 수 있는 모델은 따로 정리해 두었습니다. "
                 "[무료 모델 목록](%s)에서 실제 호출로 검증한 목록을 볼 수 있습니다." % FREE_MODELS_URL)
    L.append("")

    # ── 읽는 법
    L.append("## 이 순위를 읽을 때 알아둘 점")
    L.append("")
    L.append("- 토큰 사용량은 \"많이 쓰였다\"는 뜻이지 성능 순위가 아닙니다. OpenRouter도 이 집계가 "
             "정확도나 추론 능력을 재는 것이 아니라고 명시합니다.")
    L.append("- 토큰을 세는 방식(토크나이저)은 제공자마다 다릅니다. 서로 다른 회사 모델끼리의 토큰 수 비교는 "
             "근사치로 봐야 합니다.")
    L.append("- 모델 변형(variant)은 따로 집계합니다. 같은 모델이라도 날짜가 붙은 변형이 나뉘어 보일 수 있습니다.")
    L.append("- 상위 10개 밖 모델은 OpenRouter가 'other'로 묶어 공개하므로, 이 표에는 개별 순위로 나오지 않습니다.")
    L.append("- 이 글의 수치는 OpenRouter 공개 데이터(CC BY 4.0)를 그대로 씁니다. 기준 시각은 %s 입니다."
             % (as_of or "OpenRouter 공개 시점"))
    L.append("")

    # ── 참고 자료
    L.append("## 참고 자료")
    L.append("")
    L.append("- [OpenRouter 랭킹 (원본 집계)](https://openrouter.ai/rankings)")
    L.append("- [AIKOREA24 무료 모델 목록](%s)" % FREE_MODELS_URL)
    L.append("")

    # ── 마무리 (게이트 필수 절)
    L.append("## 마무리 — 이 순위를 내 작업에 쓰는 법")
    L.append("")
    L.append("1. 순위가 아니라 **내 과제**로 고르십시오. 쓰임이 많은 모델은 여러 사람이 검증했다는 뜻이지만, "
             "내 작업에 맞는지는 직접 돌려봐야 압니다.")
    L.append("2. 이번 주 1위 모델을 같은 프롬프트로 한 번, 평소 쓰던 모델로 한 번 돌려 결과를 비교합니다. "
             "토큰 사용량이 많은 모델이 내 작업에서도 나은지는 그때 판단하시면 됩니다.")
    L.append("3. 무료로 시작하려면 [무료 모델 목록](%s)에서 검증된 모델을 고르고, 한도에 걸리는 시점을 함께 기록해 두십시오."
             % FREE_MODELS_URL)
    L.append("")
    L.append("매주 일요일 같은 기준으로 집계해 이 코너에 올립니다.")
    return "\n".join(L)


def main():
    parser = argparse.ArgumentParser(description="OpenRouter 주간 토큰 랭킹 집계")
    parser.add_argument("--start-date", help="집계 시작일 YYYY-MM-DD (UTC)")
    parser.add_argument("--end-date", help="집계 종료일 YYYY-MM-DD (UTC)")
    parser.add_argument("--dry-run", action="store_true", help="집계+JSON만, EmDash draft 생성 안 함")
    parser.add_argument("--no-draft", action="store_true", help="draft 생성 생략")
    parser.add_argument("--no-publish", action="store_true",
                        help="발행 단계 생략(초안만). 기본은 게이트 통과 시 자동 발행")
    args = parser.parse_args()

    if args.start_date and args.end_date:
        week_start = datetime.strptime(args.start_date, "%Y-%m-%d").date()
        week_end = datetime.strptime(args.end_date, "%Y-%m-%d").date()
    else:
        week_start, week_end = week_window()

    if (week_end - week_start).days != 6:
        print("⚠️  집계 구간이 7일이 아닙니다 (%s ~ %s, %d일). 계속 진행합니다."
              % (week_start, week_end, (week_end - week_start).days + 1))

    print("집계 구간: %s ~ %s (UTC)" % (week_start, week_end))

    if not OPENROUTER_API_KEY:
        print("❌ OPENROUTER_API_KEY 가 ~/.env.common 에 없습니다.")
        sys.exit(1)

    rows, as_of = fetch_rankings(week_start, week_end)
    print("조회 행수: %d, as_of: %s" % (len(rows), as_of))

    top10, n_models = aggregate(rows)
    if not top10:
        print("❌ Top 10 추출 실패")
        sys.exit(1)

    # JSON 저장
    log_dir = os.path.join(PROJECT_ROOT, "scripts", "logs")
    os.makedirs(log_dir, exist_ok=True)
    json_path = os.path.join(log_dir, "openrouter_weekly_%s.json" % week_start.isoformat())
    payload = {
        "week_start": week_start.isoformat(),
        "week_end": week_end.isoformat(),
        "as_of": as_of,
        "n_models": n_models,
        "n_rows": len(rows),
        "top10": top10,
    }
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print("JSON 저장: %s" % json_path)

    # 콘솔 요약
    print("\n=== Top 10 ===")
    for r in top10:
        print("  %2d. %-46s %s%s" % (r["rank"], r["model_permaslug"], r["tokens_human"],
                                       "  (free)" if r["is_free"] else ""))

    if args.dry_run:
        print("\n[dry-run] EmDash draft 생성 생략")
        return

    prev = _load_prev_week(week_start)
    if prev:
        print("전주 비교: %s ~ %s (1위 %s)"
              % (prev.get("week_start"), prev.get("week_end"),
                 (prev.get("top10") or [{}])[0].get("model_permaslug")))
    else:
        print("전주 JSON 없음 — 전주 비교 절 없이 쓴다")

    title = "주간 OpenRouter 토큰 랭킹 (%d월 %d일~%d일)" % (week_start.month, week_start.day, week_end.day)
    body_md = build_markdown(week_start, week_end, top10, n_models, as_of, prev=prev)
    free_n = sum(1 for r in top10 if r["is_free"])
    excerpt = ("OpenRouter 실사용 집계: %s~%s 7일간 토큰 사용량 Top 10. 1위 %s. 무료 모델 %d개."
               % (week_start.strftime("%m/%d"), week_end.strftime("%m/%d"),
                  top10[0]["model_permaslug"].split("/")[-1], free_n))

    if args.no_draft:
        print("\n[--no-draft] EmDash draft 생성 생략. 제목: %s" % title)
        return

    # 2026-11-12: 발행 전 품질 게이트. 통과할 때만 공개한다(미달이면 초안 유지).
    import blog_quality_gate as qg
    repaired, _notes = qg.repair_markdown(body_md)
    issues = qg.screen_extended(repaired, verify_links=True, is_eval=True)
    print("\n게이트: %s%s" % ("통과" if not issues else "미달 %d건" % len(issues),
                              "" if not issues else " → " + " / ".join(issues[:3])))

    from emdash_publish import create_draft_post, publish_by_slug
    url = create_draft_post(title, repaired, excerpt=excerpt)
    if not url:
        print("\n❌ EmDash draft 생성 실패")
        sys.exit(2)
    print("\n📝 EmDash draft 생성: %s" % url)

    if args.no_publish:
        print("[--no-publish] 발행 생략 — 초안으로 남깁니다")
        return
    if issues:
        print("⛔️ 게이트 미달 — 발행하지 않습니다(초안 유지). 사유를 확인하세요.")
        sys.exit(3)

    pub = publish_by_slug(url)
    if pub:
        print("✅ 발행 완료: %s" % pub)
    else:
        print("❌ 발행 실패 — 초안으로 남깁니다")
        sys.exit(2)


if __name__ == "__main__":
    main()
