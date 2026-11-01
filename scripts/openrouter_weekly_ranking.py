#!/Users/twinssn/Projects/aikorea24/.venv/bin/python3
"""AIK24-OR-WEEKLY-01 — OpenRouter 주간 토큰 랭킹 집계 + EmDash 초안 생성.

매주 일요일에 실행된다 (launchd kr.aikorea24.openrouter-weekly, 09:00 ICT).
직전 일요일~토요일 7일간의 OpenRouter rankings-daily 를 집계해
Top 10 모델을 추출하고, EmDash CMS 에 **draft** 글로 저장한다 (발행은 수동).

사용:
  python3 scripts/openrouter_weekly_ranking.py                       # 기본: 직전 완성 주
  python3 scripts/openrouter_weekly_ranking.py --start-date 2026-10-25 --end-date 2026-10-31
  python3 scripts/openrouter_weekly_ranking.py --dry-run             # 집계+JSON만, draft 생성 안 함
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


def build_markdown(week_start, week_end, top10, n_models, as_of):
    """첫 글(2026-10-23) 포맷을 따르는 마크다운 본문."""
    title_range = "%d월 %d일~%d일" % (week_start.month, week_start.day, week_end.day)
    free_count = sum(1 for r in top10 if r["is_free"])
    free_names = [r["model_permaslug"] for r in top10 if r["is_free"]]

    lines = []
    lines.append("이번 주(%d년 %d월 %d일~%d일) OpenRouter에서 가장 많이 쓰인 모델 순위입니다. "
                 "OpenRouter 가 공개한 실사용 집계(토큰 사용량)를 7일간 합산한 결과입니다."
                 % (week_start.year, week_start.month, week_start.day, week_end.day))
    lines.append("")
    lines.append("## 1. 이번 주 토큰 사용량 순위")
    lines.append("")
    lines.append("OpenRouter 는 자사 API 를 통과한 요청의 토큰 수를 모델별로 집계해 공개합니다. "
                 "아래 순위는 %d년 %d월 %d일부터 %d일까지 7일간의 입력·출력 토큰 합산입니다."
                 % (week_start.year, week_start.month, week_start.day, week_end.day))
    lines.append("")
    lines.append("| 순위 | 모델 | 7일간 토큰 수 |")
    lines.append("|---|---|---|")
    for r in top10:
        name = r["model_permaslug"]
        if r["is_free"]:
            name = name + " :free"
        lines.append("| %d | %s | %s |" % (r["rank"], name, r["tokens_human"]))
    lines.append("")
    if top10:
        first = top10[0]
        lines.append("1위는 %s (%s) 입니다." % (first["model_permaslug"], first["tokens_human"]))
    lines.append("")
    lines.append("## 2. 이 순위를 읽을 때 알아둘 점")
    lines.append("")
    lines.append("- 토큰 사용량은 \"많이 쓰였다\"는 뜻이지 성능 순위가 아닙니다. OpenRouter 도 이 집계가 정확도나 추론 능력을 재는 것이 아니라고 명시합니다.")
    lines.append("- 토큰을 세는 방식(토크나이저)은 제공자마다 다릅니다. 서로 다른 회사 모델끼리의 토큰 수 비교는 근사치로 봐야 합니다.")
    lines.append("- 모델 변형(variant)은 따로 집계합니다. 같은 모델이라도 날짜가 붙은 변형이 나뉘어 보일 수 있습니다.")
    lines.append("- 무료 변형(:free)도 별도 항목으로 집계됩니다. 같은 모델이라도 무료 경로와 유료 경로의 사용량이 나뉘어 보입니다.")
    lines.append("")
    lines.append("## 3. 무료 모델 관점")
    lines.append("")
    if free_count:
        lines.append("상위 10개 중 **%d개**가 무료 모델입니다: %s"
                     % (free_count, ", ".join(free_names)))
    else:
        lines.append("이번 주 상위 10개 중 무료 모델은 없습니다.")
    lines.append("")
    lines.append("무료 모델 목록은 [무료 모델 페이지](%s)에서 확인할 수 있습니다." % FREE_MODELS_URL)
    lines.append("")
    lines.append("## 4. 독자가 직접 해볼 것")
    lines.append("")
    lines.append("- OpenRouter 랭킹 페이지(https://openrouter.ai/rankings)에서 오늘의 순위를 직접 확인합니다. 집계는 매일 갱신됩니다.")
    lines.append("- 상위 무료 모델부터 작은 과제로 써 봅니다. 사용량이 많은 모델은 그만큼 여러 사람이 검증한 셈이지만, 내 작업에 맞는지는 직접 돌려봐야 압니다.")
    lines.append("- 모델을 고를 때는 사용량 순위가 아니라 내 과제의 결과로 판단합니다.")
    lines.append("")
    lines.append("## 참고 자료")
    lines.append("")
    lines.append("- Source: OpenRouter (openrouter.ai/rankings), as of %s. Licensed under CC BY 4.0." % (as_of or ""))
    lines.append("- 집계 방법: OpenRouter Data API(rankings-daily)로 %d년 %d월 %d일~%d일(UTC) 일별 상위 모델의 토큰 수를 합산했습니다. 날짜별 변형은 OpenRouter 표기를 따랐고, 상위 50위 밖 모델의 합산 항목(other)은 순위에서 제외했습니다."
                 % (week_start.year, week_start.month, week_start.day, week_end.day))
    lines.append("- 총 %d개 모델 변형이 집계 대상이었습니다." % n_models)
    lines.append("")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="OpenRouter 주간 토큰 랭킹 집계")
    parser.add_argument("--start-date", help="집계 시작일 YYYY-MM-DD (UTC)")
    parser.add_argument("--end-date", help="집계 종료일 YYYY-MM-DD (UTC)")
    parser.add_argument("--dry-run", action="store_true", help="집계+JSON만, EmDash draft 생성 안 함")
    parser.add_argument("--no-draft", action="store_true", help="draft 생성 생략")
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

    title = "주간 OpenRouter 토큰 랭킹 (%d월 %d일~%d일)" % (week_start.month, week_start.day, week_end.day)
    body_md = build_markdown(week_start, week_end, top10, n_models, as_of)
    excerpt = "OpenRouter 실사용 집계: %s~%s 7일간 토큰 사용량 Top 10. 무료 모델 %d개 포함." % (
        week_start.strftime("%m/%d"), week_end.strftime("%m/%d"), sum(1 for r in top10 if r["is_free"]))

    if args.no_draft:
        print("\n[--no-draft] EmDash draft 생성 생략. 제목: %s" % title)
        return

    from emdash_publish import create_draft_post
    url = create_draft_post(title, body_md, excerpt=excerpt)
    if url:
        print("\n✅ EmDash draft 생성: %s" % url)
    else:
        print("\n❌ EmDash draft 생성 실패")
        sys.exit(2)


if __name__ == "__main__":
    main()
