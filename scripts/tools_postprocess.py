#!/Users/twinssn/Projects/aikorea24/.venv/bin/python3
"""도구 상세페이지 자동 후처리 — ① 실제 URL 승격 ② 심화 스키마 v2 ③ 썸네일.

호출 경로
  - `tools_collector.py` main(): 신규 저장분(created)을 git 커밋·배포 **전에** 처리한다.
    → 새 도구가 들어와도 사람이 손대지 않으면 8섹션 스텁/썸네일 없음 상태로 배포되지 않는다.
  - 단독 실행(밀린 항목 따라잡기, 멱등):
      python3 scripts/tools_postprocess.py --sweep 15
      python3 scripts/tools_postprocess.py --slugs pondas --budget 300
      python3 scripts/tools_postprocess.py --slugs pondas --dry-run

안전 규칙(이 프로젝트에서 실측으로 확인된 것만)
  - 봇 챌린지 페이지는 **우회하지 않는다**. 걸리면 그 단계만 건너뛰고 기록한다.
  - URL 승격은 (a) 도메인 라벨 == 도구 이름 정규화, (b) 페이지 제목/og:site_name 이 이름과 일치,
    (c) 설명 문구가 비어있지 않고 도구성 키워드를 포함, (d) 챌린지·판매중 도메인 아님 — 4개를 모두
    만족할 때만 한다. 실측 근거: 후보 30건 중 오탐(주류·거래소·교육·에너지·판매중) 9건을 이 규칙이 전부 걸러냄.
  - 4글자 이하 이름은 도메인 일치만으로 오탐이 난다(sol.com = 주류 브랜드) → MIN_LABEL_LEN 미만 제외.
  - 모든 판정은 `scripts/logs/tools_postprocess.jsonl` 에 남긴다(감사용).
  - 시간 예산을 넘으면 새 작업을 시작하지 않는다(무한 실행 금지). 남은 항목은 다음 실행이 이어받는다.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
TOOLS = ROOT / "src" / "content" / "tools"
LEDGER = SCRIPTS / "logs" / "tools_postprocess.jsonl"

# ── 튜닝 값 (실측 기반) ────────────────────────────────────────────────
PROBE_TIMEOUT = 8
TLDS = (".com", ".ai", ".io", ".app", ".co")
MIN_LABEL_LEN = 5  # 4자 이하 이름은 오탐 위험(실측: sol.com=주류 브랜드)
MAX_URL_CANDIDATES = 12
COOLDOWN_DAYS = 7  # 이 기간 내 실패한 (슬러그·단계)는 스윕 대상에서 제외
AGGREGATOR_HOSTS = ("theresanaiforthat.com", "topai.tools", "producthunt.com",
                    "futurepedia.io", "toolify.ai", "aitools.fyi", "theresanaiforthat")
UA = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}
CHALLENGE = re.compile(r"just a moment|attention required|cf-browser-verification|"
                       r"verifying you are human|enable javascript and cookies", re.I)
PARKED = re.compile(r"domain (is )?for sale|buy this domain|for sale \| spaceship|godaddy\.com|"
                    r"hugedomains|afternic|domain is available|secure checkout and guided transfer", re.I)
TOOLISH = re.compile(r"\b(ai|gpt|llm|tool|app|platform|api|software|assistant|chat\w*|bot|"
                     r"generat\w+|automat\w+|design|video|image|seo|analytic\w*|agent|model|"
                     r"studio|workspace|dashboard|saas|editor|writer|summar\w+|transcri\w+)\b", re.I)
SECTIONS_MARK = "## 사용법"
NEW_SECTION_LIST = ("## 사용법", "## 요금제 자세히", "## 한국어 품질 실측", "## 장단점",
                    "## 주의사항", "## 대안 도구 비교")


# ══════════════════════════════════════════════════════════════════════
# md 입출력 (경계 계약: frontmatter 는 닫는 --- 앞 개행을 포함하지 않는다)
# ══════════════════════════════════════════════════════════════════════
def md_path(slug: str) -> Path:
    return TOOLS / f"{slug}.md"


def read_md(slug: str) -> tuple[str, str] | tuple[None, None]:
    p = md_path(slug)
    if not p.exists():
        return (None, None)
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", p.read_text(encoding="utf-8"), re.S)
    if not m:
        return (None, None)
    return m.group(1), m.group(2)


def write_md(slug: str, fm: str, body: str) -> None:
    md_path(slug).write_text(f"---\n{fm}\n---\n{body}", encoding="utf-8")


def fm_get(fm: str, key: str) -> str:
    m = re.search(rf'^{key}\s*:\s*"?(.*?)"?\s*$', fm, re.M)
    return m.group(1).strip() if m else ""


def set_fm(slug: str, fm: str, body: str, key: str, value: str) -> None:
    line = f'{key}: "{value}"'
    if re.search(rf"^{key}\s*:", fm, re.M):
        fm = re.sub(rf"^{key}\s*:.*$", line, fm, count=1, flags=re.M)
    else:
        fm = fm.rstrip() + "\n" + line
    write_md(slug, fm, body)


def is_aggregator(url: str) -> bool:
    host = urllib.parse.urlparse(url or "").netloc.lower().replace("www.", "")
    return any(h in host for h in AGGREGATOR_HOSTS)


# ══════════════════════════════════════════════════════════════════════
# 감사 로그
# ══════════════════════════════════════════════════════════════════════
def ledger(rec: dict) -> None:
    rec = {"ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), **rec}
    try:
        LEDGER.parent.mkdir(parents=True, exist_ok=True)
        with open(LEDGER, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except Exception as e:
        print(f"  [ledger] 기록 실패: {type(e).__name__}: {e}")


# ══════════════════════════════════════════════════════════════════════
# ① 실제 URL 승격
# ══════════════════════════════════════════════════════════════════════
def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def _labels(name: str, slug: str) -> list[str]:
    """도메인 라벨 후보 — 'VideoWeb | Video Generator' 는 'videoweb' 으로 본다."""
    base = _norm((name or "").split("|")[0])
    out: list[str] = []
    for b in (base, _norm(slug)):
        if MIN_LABEL_LEN <= len(b) <= 30 and b not in out:
            out.append(b)
    return out


def _title_tokens_match(token: str, text: str) -> bool:
    """제목/og:site_name 이 도구 이름과 같은지 — 단일 토큰이거나 연속 토큰 연결이 라벨과 같을 때."""
    words = [w for w in re.split(r"[^A-Za-z0-9]+", text or "") if w]
    low = [w.lower() for w in words]
    if token in low:
        return True
    for i in range(len(low)):
        acc = ""
        for j in range(i, min(i + 5, len(low))):
            acc += low[j]
            if acc == token:
                return True
            if len(acc) > len(token):
                break
    return False


def _probe(label: str, url: str) -> tuple[bool, str]:
    """후보 도메인이 그 도구의 실제 사이트인지 판정한다."""
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA),
                                    timeout=PROBE_TIMEOUT) as r:
            if r.status != 200:
                return False, f"HTTP {r.status}"
            final = r.geturl()
            body = r.read(160_000).decode("utf-8", "ignore")
    except urllib.error.HTTPError as e:
        return False, f"HTTP {e.code}"
    except Exception as e:
        return False, type(e).__name__
    if CHALLENGE.search(body[:4000]):
        return False, "BOT_CHALLENGE"
    if PARKED.search(body[:6000]):
        return False, "PARKED_OR_FORSALE"
    if urllib.parse.urlparse(final).netloc.lower().replace("www.", "").split(".")[0] != label:
        return False, "REDIRECT_OTHER_DOMAIN"

    def meta(pat: str) -> str:
        m = re.search(pat, body, re.I | re.S)
        return m.group(1).strip() if m else ""

    title = meta(r"<title[^>]*>(.*?)</title>")
    ogn = meta(r'property=["\']og:site_name["\'][^>]*content=["\']([^"\']+)')
    desc = meta(r'property=["\']og:description["\'][^>]*content=["\']([^"\']+)') \
        or meta(r'name=["\']description["\'][^>]*content=["\']([^"\']+)')
    if not _title_tokens_match(label, f"{title} {ogn}"):
        return False, f"이름 불일치(title={title[:40]!r})"
    if not desc:
        return False, "설명 없음"
    if not TOOLISH.search(desc):
        return False, "도구성 키워드 없음"
    return True, f"title={title[:44]!r}"


def resolve_real_url(slug: str, name: str) -> tuple[str | None, str]:
    for label in _labels(name, slug):
        for tld in TLDS:
            cand = f"https://{label}{tld}"
            ok, why = _probe(label, cand)
            if ok:
                return cand, why
    return None, "후보 전부 실패"


def ensure_url(slug: str, dry_run: bool = False) -> tuple[str, str]:
    """returns (done|skip|fail, 설명)"""
    fm, body = read_md(slug)
    if fm is None:
        return "fail", "md 없음/형식 이상"
    cur = fm_get(fm, "url")
    if cur and not is_aggregator(cur):
        return "skip", f"이미 실제 도메인 ({urllib.parse.urlparse(cur).netloc})"
    name = fm_get(fm, "name")
    found, why = resolve_real_url(slug, name)
    if not found:
        return "fail", f"실제 도메인 미확인 ({why})"
    if dry_run:
        return "done", f"[dry-run] {cur or '빈값'} → {found} ({why})"
    set_fm(slug, fm, body, "url", found)
    return "done", f"{cur or '빈값'} → {found} ({why})"


# ══════════════════════════════════════════════════════════════════════
# ② 심화 스키마 v2 / ③ 썸네일 (기존 검증된 스크립트 재사용)
# ══════════════════════════════════════════════════════════════════════
def _load_module(name: str, filename: str):
    path = SCRIPTS / filename
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def needs_enrich(slug: str) -> bool:
    _, body = read_md(slug)
    if body is None:
        return False
    return SECTIONS_MARK not in body


def ensure_enrich(slug: str, dry_run: bool = False) -> tuple[str, str]:
    if not needs_enrich(slug):
        return "skip", "이미 적용됨"
    if dry_run:
        return "done", "[dry-run] 심화 스키마 v2 생성 대상"
    te = _load_module("aik24_tools_enrich", "tools_enrich.py")
    r = te.enrich_one(slug, True, False)
    if r.get("ok"):
        return "done", f"+{r.get('new_chars', 0):,}자 (시도 {r.get('rounds', 1)})"
    return "fail", f"게이트 미통과: {r.get('why', '알 수 없음')}"


def _thumb_skip() -> set[str]:
    try:
        return set(_load_module("aik24_btt", "backfill_tool_thumbs.py").SKIP)
    except Exception:
        return {"4-mbti", "link2threads-l2t"}


def needs_thumb(slug: str) -> bool:
    fm, _ = read_md(slug)
    if fm is None or re.search(r"^image\s*:", fm, re.M):
        return False
    return slug not in _thumb_skip()


def ensure_thumb(slug: str, channel: str = "chrome", timeout: int = 300,
                 dry_run: bool = False) -> tuple[str, str]:
    if not needs_thumb(slug):
        return "skip", "이미 있음(또는 D1 대체 이미지)"
    if dry_run:  # dry-run 은 브라우저를 띄우지도, md 를 쓰지도 않는다
        return "done", "[dry-run] 썸네일 캡처 대상"
    base = [sys.executable, str(SCRIPTS / "backfill_tool_thumbs.py"), "--apply",
            "--slugs", slug]
    plans: list[list[str]] = []
    if channel:  # 1차: og → 스크린샷 폴백, 시스템 Chrome
        plans.append(base + ["--route", "auto", "--channel", channel])
    # 2차: 브라우저를 아예 띄우지 않는 og 전용(브라우저 미설치·차단 환경용)
    plans.append(base + ["--route", "og"])
    attempts: list[str] = []
    for argv in plans:
        try:
            r = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
            out = (r.stdout or "") + (r.stderr or "")
            line = next((l.strip() for l in out.splitlines() if slug in l and ("✅" in l or "❌" in l)), "")
            if not needs_thumb(slug):
                return "done", line or "캡처 성공"
            attempts.append(line or (out.strip().splitlines()[-1][:70] if out.strip() else f"exit={r.returncode}"))
        except subprocess.TimeoutExpired:
            attempts.append(f"타임아웃 {timeout}s")
        except Exception as e:
            attempts.append(f"{type(e).__name__}: {e}")
    return "fail", " | ".join(attempts)[:160]


# ══════════════════════════════════════════════════════════════════════
# 오케스트레이션
# ══════════════════════════════════════════════════════════════════════
def postprocess_one(slug: str, *, dry_run: bool = False, channel: str = "chrome",
                    do_url: bool = True, do_enrich: bool = True,
                    do_thumb: bool = True) -> dict:
    """한 슬러그를 URL → 심화 → 썸네일 순서로 처리한다.

    URL 을 먼저 바꾸는 이유: 심화 생성기가 md url 을 크롤해 본문 재료로 쓰기 때문에,
    집계 사이트 URL 이면 집계 사이트 문구를 재료로 쓰게 된다.
    """
    done: list[str] = []
    skipped: list[str] = []
    failed: list[str] = []
    for label, enabled, fn in (("url", do_url, ensure_url),
                               ("enrich", do_enrich, ensure_enrich),
                               ("thumb", do_thumb, ensure_thumb)):
        if not enabled:
            continue
        try:
            if label == "thumb":
                state, msg = fn(slug, channel=channel, dry_run=dry_run)
            else:
                state, msg = fn(slug, dry_run=dry_run)
        except Exception as e:  # 한 단계 실패가 나머지 단계·파이프라인을 막지 않는다
            state, msg = "fail", f"예외 {type(e).__name__}: {e}"
        icon = {"done": "✅", "skip": "·", "fail": "⚠️"}[state]
        print(f"    [{label}] {icon} {slug} — {msg}", flush=True)
        {"done": done, "skip": skipped, "fail": failed}[state].append(f"{label}:{msg}")
        # dry-run 은 아무것도 바꾸지 않으므로 원장에도 남기지 않는다(쿨다운·감사 오염 방지).
        # 실패도 원인 추적을 위해 기록한다.
        if state in ("done", "fail") and not dry_run:
            ledger({"slug": slug, "step": label, "result": state, "detail": msg,
                    "dry_run": False})
    return {"slug": slug, "done": done, "skipped": skipped, "failed": failed,
            "changed": bool(done) and not dry_run}


def postprocess(slugs, *, budget: int = 900, dry_run: bool = False, channel: str = "chrome",
                do_url: bool = True, do_enrich: bool = True, do_thumb: bool = True) -> dict:
    """여러 슬러그를 시간 예산 안에서 처리한다. 실패해도 예외를 올리지 않는다."""
    slugs = [s for s in dict.fromkeys(slugs or [])]
    t0 = time.time()
    summary = {"target": len(slugs), "changed": [], "skipped": [], "failed": [],
               "timeout": [], "elapsed": 0.0, "dry_run": dry_run,
               "failed_detail": {}}
    if not slugs:
        return summary
    print(f"[후처리] 대상 {len(slugs)}건 · 예산 {budget}s · dry_run={dry_run}")
    for slug in slugs:
        if time.time() - t0 > budget:
            summary["timeout"] = slugs[slugs.index(slug):]
            print(f"  ⏱ 시간 예산 초과 — 남은 {len(summary['timeout'])}건은 다음 실행에서 처리(멱등)")
            break
        r = postprocess_one(slug, dry_run=dry_run, channel=channel, do_url=do_url,
                            do_enrich=do_enrich, do_thumb=do_thumb)
        if r["failed"]:
            summary["failed"].append(slug)
            summary["failed_detail"][slug] = r["failed"]
        if r["done"] or r["failed"]:
            (summary["changed"] if not dry_run else summary.setdefault("would_change", [])).append(slug)
        if not (r["done"] or r["failed"]):
            summary["skipped"].append(slug)
    summary["elapsed"] = round(time.time() - t0, 1)
    print(f"[후처리] 변경 {len(summary['changed'])}건 / 무변경 {len(summary['skipped'])}건 "
          f"/ 실패 {len(summary['failed'])}건 / 미처리 {len(summary['timeout'])}건 · "
          f"{summary['elapsed']}초")
    if summary["failed_detail"]:
        for s, det in list(summary["failed_detail"].items())[:10]:
            print(f"    ⚠️ {s}: {'; '.join(det)[:150]}")
    return summary


def _recent_failures(days: int = COOLDOWN_DAYS) -> dict[tuple[str, str], str]:
    """최근 N일 내 실패한 (slug, step) — 스윕이 같은 항목을 매일 재시도하지 않게 한다."""
    out: dict[tuple[str, str], str] = {}
    if not LEDGER.exists():
        return out
    cut = datetime.now() - timedelta(days=days)
    for line in LEDGER.read_text(encoding="utf-8").splitlines():
        try:
            r = json.loads(line)
            if r.get("result") != "fail":
                continue
            ts = datetime.strptime(r.get("ts", "")[:19], "%Y-%m-%d %H:%M:%S")
        except Exception:
            continue
        if ts >= cut:
            out[(r.get("slug", ""), r.get("step", ""))] = r["ts"]
    return out


def sweep_targets(limit: int = 0, cooldown_days: int = COOLDOWN_DAYS) -> list[str]:
    """미완료 항목(심화 미적용·썸네일 없음·집계 URL)을 모아 부족한 개수가 많은 순으로 돌려준다.

    최근 cooldown_days 안에 실패한 (슬러그·단계)는 대상에서 뺀다 — 실패 원인이 구조적인
    항목(예: 도메인 미확보·봇 차단)을 매일 다시 긁지 않기 위함이다. 새로 들어온 도구는
    원장에 기록이 없으므로 항상 대상에 포함된다.
    """
    fails = _recent_failures(cooldown_days) if cooldown_days else {}
    out: list[tuple[int, str]] = []
    for p in sorted(TOOLS.glob("*.md")):
        slug = p.stem
        fm, body = read_md(slug)
        if fm is None:
            continue
        missing = 0
        if needs_enrich(slug) and (slug, "enrich") not in fails:
            missing += 3  # 본문이 가장 중요하므로 가중치를 준다
        if needs_thumb(slug) and (slug, "thumb") not in fails:
            missing += 1
        cur = fm_get(fm, "url")
        if (not cur or is_aggregator(cur)) and (slug, "url") not in fails:
            missing += 1
        if missing:
            out.append((missing, slug))
    out.sort(key=lambda x: (-x[0], x[1]))
    slugs = [s for _, s in out]
    return slugs[:limit] if limit else slugs


def main() -> int:
    ap = argparse.ArgumentParser(description="도구 상세페이지 자동 후처리(URL 승격·심화 v2·썸네일)")
    ap.add_argument("--slugs", default="", help="쉼표 구분 슬러그")
    ap.add_argument("--sweep", type=int, default=0, help="미완료 항목에서 앞 N건 자동 선택")
    ap.add_argument("--budget", type=int, default=900, help="최대 실행 시간(초)")
    ap.add_argument("--dry-run", action="store_true", help="변경 없이 대상·판정만 확인")
    ap.add_argument("--channel", default="chrome", help="썸네일 브라우저 채널(빈 값=기본 chromium)")
    ap.add_argument("--no-url", action="store_true", help="URL 승격 건너뛰기")
    ap.add_argument("--no-enrich", action="store_true", help="심화 생성 건너뛰기")
    ap.add_argument("--no-thumb", action="store_true", help="썸네일 건너뛰기")
    ap.add_argument("--list", action="store_true", help="대상 목록만 출력")
    ap.add_argument("--no-cooldown", action="store_true",
                    help="스윕 실패 쿨다운 무시(수동 재시도용)")
    args = ap.parse_args()

    sys.path.insert(0, str(SCRIPTS))
    try:  # 파이프라인과 같은 환경 로딩(프로젝트 .env + ~/.env.common)
        import _config  # type: ignore
        _config.load_to_environ()
    except Exception:
        pass

    if args.slugs:
        slugs = [s.strip() for s in args.slugs.split(",") if s.strip()]
    else:
        slugs = sweep_targets(args.sweep, 0 if args.no_cooldown else COOLDOWN_DAYS)

    if args.list:
        print(f"대상 {len(slugs)}건")
        for s in slugs:
            fm, body = read_md(s)
            marks = []
            if needs_enrich(s):
                marks.append("심화")
            if needs_thumb(s):
                marks.append("썸네일")
            cur = fm_get(fm or "", "url")
            if not cur or is_aggregator(cur):
                marks.append("URL")
            print(f"  {s:40s} {','.join(marks) or '완료'}")
        return 0

    postprocess(slugs, budget=args.budget, dry_run=args.dry_run, channel=args.channel,
                do_url=not args.no_url, do_enrich=not args.no_enrich,
                do_thumb=not args.no_thumb)
    return 0


if __name__ == "__main__":
    sys.exit(main())
