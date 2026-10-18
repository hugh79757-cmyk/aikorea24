#!/usr/bin/env python3
"""도구 썸네일 백필 — md 에 image: 가 없는 도구의 홈페이지를 Playwright 로 캡쳐한다.

기존 auto_thumbnail.py 는 Pexels/Unsplash 스톡 사진을 쓰므로 사용하지 않는다.
여기는 해당 서비스의 첫 화면(16:9 viewport)을 그대로 캡쳐한다.

  --apply 없으면 dry-run(캡쳐 없이 대상 목록만 출력).
  --limit N  파일럿 실행.
"""
from __future__ import annotations

import argparse
import asyncio
import io
import os
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOOLS_DIR = ROOT / "src" / "content" / "tools"
OUT_DIR = ROOT / "public" / "images" / "tools"

# D1 tool_submissions 에 스크린샷이 이미 있는 슬러그 — 덮어쓰지 않는다.
SKIP = {"4-mbti", "link2threads-l2t"}

VIEWPORT = {"width": 1280, "height": 720}
TARGET_W, TARGET_H = 800, 450
TIMEOUT_MS = 25000
SETTLE_MS = 1500
CONCURRENCY = 6

# 봇 챌린지 페이지 마커 — 우회하지 않고 건너뛴다(우회는 프로젝트 규칙상 금지).
CHALLENGE_MARKERS = (
    "just a moment",
    "verify you are human",
    "performing security verification",
    "attention required",
    "enable javascript and cookies",
    "checking your browser",
    "checking if the site connection is secure",
    # 봇 통과를 오인하는 서버 에러/차단 페이지 (썸네일로 쓸 수 없음)
    "access denied",
    "403 forbidden",
    "404 not found",
    "page not found",
)


def validate_thumb(path: Path) -> tuple[bool, str]:
    """빈 화면·로고 수준 결과를 걸러낸다. 0~1KB webp = 흰 페이지 스크린샷(실측)."""
    from PIL import Image, ImageStat

    try:
        size = path.stat().st_size
        if size < MIN_THUMB_BYTES:
            return False, f"SMALL_{size}B"
        with Image.open(path) as im:
            std = ImageStat.Stat(im.convert("L")).stddev[0]
        if std < MIN_THUMB_STD:
            return False, f"BLANK_std{std:.1f}"
        return True, f"{size // 1024}KB"
    except Exception as e:
        return False, "VERIFY_" + type(e).__name__


async def is_challenge(page) -> bool:
    try:
        title = (await page.title() or "").lower()
        body = (await page.inner_text("body", timeout=3000) or "")[:800].lower()
    except Exception:
        return False
    return any(m in title or m in body for m in CHALLENGE_MARKERS)


def split_frontmatter(text: str) -> tuple[str, str, str]:
    """(frontmatter, body, closing) 로 분리. frontmatter 없으면 ('\x00', '', '')."""
    if not text.startswith("---"):
        return "\x00", text, ""
    end = text.find("\n---", 3)
    if end == -1:
        return "\x00", text, ""
    return text[3:end], text[end + 4 :], text[end : end + 4]


def target_url(fm: str) -> str | None:
    m = re.search(r'^url\s*:\s*["\']?(https?://[^"\'\n]+)', fm, re.M)
    return m.group(1).strip() if m else None


async def og_from_page(page, out: Path) -> tuple[bool, str]:
    """브라우저 세션 안에서 og:image 를 읽어 내려받는다(핫링크·403 우회 아님 — 세션 쿠키 사용)."""
    from PIL import Image, ImageOps

    try:
        img_url = await page.evaluate(
            "() => { const m = document.querySelector('meta[property=\"og:image\"]');"
            " return m ? m.content : null; }"
        )
        if not img_url:
            return False, "NO_OG_IMAGE"
        if any(k in img_url for k in GENERIC_OG_MARKERS):
            return False, "OG_GENERIC"
        resp = await page.request.get(img_url)
        if not resp.ok:
            return False, f"OG_HTTP_{resp.status}"
        with Image.open(io.BytesIO(await resp.body())) as im:
            if im.size[0] < MIN_OG_W or im.size[1] < MIN_OG_H:
                return False, f"OG_SMALL_{im.size[0]}x{im.size[1]}"
            fitted = ImageOps.fit(im.convert("RGB"), (TARGET_W, TARGET_H), Image.LANCZOS)
            out.parent.mkdir(parents=True, exist_ok=True)
            fitted.save(out, "WEBP", quality=75)
        ok, why = validate_thumb(out)
        return (True, f"og {why}") if ok else (False, "OG_" + why)
    except Exception as e:
        return False, "BR_OG_" + type(e).__name__


async def capture(browser, url: str, out: Path) -> tuple[bool, str]:
    from PIL import Image

    page = await browser.new_page(viewport=VIEWPORT)
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=TIMEOUT_MS)
        await page.wait_for_timeout(SETTLE_MS)
        if await is_challenge(page):
            good, msg = await og_from_page(page, out)
            return (True, "br-og " + msg) if good else (False, f"BOT_CHALLENGE | {msg}")
        # 병렬 실행 시 공유 tmp 충돌 방지 — slug 로 고유화
        tmp = ROOT / "scripts" / f".thumb_tmp_{out.stem}.jpg"
        await page.screenshot(path=str(tmp), type="jpeg", quality=90)
        with Image.open(tmp) as im:
            im = im.convert("RGB").resize((TARGET_W, TARGET_H), Image.LANCZOS)
            out.parent.mkdir(parents=True, exist_ok=True)
            im.save(out, "WEBP", quality=75)
        ok, why = validate_thumb(out)
        if ok:
            return True, why
        # 흰 화면(JS 미렌더 등) → 같은 세션에서 og:image 로 대체 시도
        out.unlink(missing_ok=True)
        good, msg = await og_from_page(page, out)
        return (True, "br-og " + msg) if good else (False, f"BLANK({why}) | {msg}")
    except Exception as e:
        return False, type(e).__name__ + ": " + str(e).split("\n")[0][:90]
    finally:
        await page.close()


async def browser_og_capture(browser, url: str, out: Path) -> tuple[bool, str]:
    """브라우저로 페이지만 열고 og:image 만 받아온다(--route browser-og)."""
    page = await browser.new_page(viewport=VIEWPORT)
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=TIMEOUT_MS)
        await page.wait_for_timeout(SETTLE_MS)
        return await og_from_page(page, out)
    except Exception as e:
        return False, "BR_" + type(e).__name__ + ": " + str(e).split("\n")[0][:70]
    finally:
        await page.close()


# ── og:image 폴백 (2026-10-18 추가) ────────────────────────────────────────
# 집계 사이트(topai.tools 등)는 브라우저 캡처가 봇 챌린지로 막히지만, 일반 HTTP
# 요청에는 원본 사용화면(1920×1080)을 og:image 로 내려준다(실측 12/12 성공).
UA_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36",
}
AGGREGATOR_HOSTS = ("topai.tools", "theresanaiforthat.com", "futurepedia.io", "producthunt.com")
# 사이트 자체 홍보 이미지(툴 화면이 아님) — 썸네일로 쓰면 오해를 준다.
GENERIC_OG_MARKERS = ("/assets/img/splash", "/img/favicon", "apple-touch-icon", "/default-og")
MIN_OG_W, MIN_OG_H = 600, 300  # 로고 수준의 작은 이미지는 거부
MIN_THUMB_BYTES = 4096         # 0~1KB webp = 흰 화면 스크린샷
MIN_THUMB_STD = 8.0            # 휘도 표준편차 — 단색에 가까우면 빈 화면


def is_aggregator(url: str) -> bool:
    host = urllib.parse.urlparse(url).netloc.lower().replace("www.", "")
    return any(h in host for h in AGGREGATOR_HOSTS)


def _http_get(url: str, timeout: int = 20) -> bytes:
    req = urllib.request.Request(url, headers=UA_HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def og_page_candidates(md_url: str, slug: str) -> list[str]:
    """집계 사이트 URL 이면 슬러그 기반 툴 페이지를 먼저 시도(`topai.tools#` 같은 깨진 URL 대응)."""
    cands: list[str] = []
    if "topai.tools" in md_url:
        cands.append(f"https://topai.tools/t/{slug}")
    cands.append(md_url)
    seen, uniq = set(), []
    for u in cands:
        if u and u not in seen:
            seen.add(u)
            uniq.append(u)
    return uniq


def _unescape_url_entities(s: str) -> str:
    """URL 안에 남은 HTML 엔티티를 푼다(&amp; 등). 모듈 html 과 이름 충돌을 피해 별도 함수로 둔다."""
    for ent, ch in (("&amp;", "&"), ("&#38;", "&"), ("&#x26;", "&"), ("&#x2F;", "/"),
                    ("&quot;", '"'), ("&#39;", "'")):
        s = s.replace(ent, ch)
    return s


def og_capture(md_url: str, slug: str, out: Path) -> tuple[bool, str]:
    """og:image 를 내려받아 16:9 썸네일로 저장한다(브라우저 불필요)."""
    from PIL import Image, ImageOps

    last = "NO_OG_IMAGE"
    for page_url in og_page_candidates(md_url, slug):
        try:
            html = _http_get(page_url).decode("utf-8", "ignore")
        except Exception as e:
            last = "OG_PAGE_" + type(e).__name__
            continue
        m = re.search(r'property=["\']og:image["\'][^>]*?content=["\']([^"\']+)', html) \
            or re.search(r'content=["\']([^"\']+)["\'][^>]*?property=["\']og:image', html)
        if not m:
            last = "NO_OG_IMAGE"
            continue
        # 2026-10-18: og:image URL 이 &amp; 로 HTML 이스케이프된 사이트(openai.com 등)는
        # 그대로 요청하면 CDN 이 거부한다(HTTPError). 엔티티를 풀어서 요청한다.
        img_url = urllib.parse.urljoin(page_url, _unescape_url_entities(m.group(1)))
        if any(k in img_url for k in GENERIC_OG_MARKERS):
            last = "OG_GENERIC"
            continue
        try:
            data = _http_get(img_url, timeout=30)
        except Exception as e:
            last = "OG_IMG_" + type(e).__name__
            continue
        try:
            with Image.open(io.BytesIO(data)) as im:
                if im.size[0] < MIN_OG_W or im.size[1] < MIN_OG_H:
                    last = f"OG_SMALL_{im.size[0]}x{im.size[1]}"
                    continue
                fitted = ImageOps.fit(im.convert("RGB"), (TARGET_W, TARGET_H), Image.LANCZOS)
                out.parent.mkdir(parents=True, exist_ok=True)
                fitted.save(out, "WEBP", quality=75)
            ok, why = validate_thumb(out)
            if ok:
                return True, f"og {why}"
            out.unlink(missing_ok=True)
            last = "OG_" + why
            continue
        except Exception as e:
            last = "OG_DECODE_" + type(e).__name__
            continue
    return False, last


def write_image_field(path: Path, rel: str) -> None:
    text = path.read_text(encoding="utf-8")
    fm, body, closing = split_frontmatter(text)
    if fm == "\x00":
        raise RuntimeError(f"frontmatter 없음: {path.name}")
    line = f'image: "{rel}"'
    if re.search(r"^image\s*:", fm, re.M):
        # 재캡처(품질 교체) — 기존 줄을 교체해 중복 image: 를 만들지 않는다.
        fm = re.sub(r"^image\s*:.*$", line, fm, count=1, flags=re.M)
        path.write_text(f"---{fm}---{body}", encoding="utf-8")
        return
    path.write_text(f"---\n{fm.rstrip()}\n{line}\n---{body}", encoding="utf-8")


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="실제로 캡쳐 + md 수정")
    ap.add_argument("--limit", type=int, default=0, help="앞 N 개만")
    ap.add_argument("--route", choices=("auto", "screenshot", "og", "browser-og"), default="auto",
                    help="auto=스크린샷→og:image 폴백(기본), screenshot=브라우저만, og=og:image만, "
                         "browser-og=브라우저 세션으로 og:image 만 수집")
    ap.add_argument("--channel", default="", help="브라우저 채널 (chrome = 시스템 Chrome 사용)")
    ap.add_argument("--slugs", default="", help="쉼표로 지정한 슬러그만 처리(실패분 재시도용)")
    ap.add_argument("--url-map", default="",
                    help="슬러그→URL 오버라이드 TSV(집계 사이트 대신 도구 자체 사이트로 캡처)")
    args = ap.parse_args()

    # 2026-10-18 추가: 집계 사이트 URL 밖에 없던 항목의 도구 실제 사이트를 별도로 확보한 경우,
    # md 의 url 은 건드리지 않고 캡처 대상 URL 만 바꾼다.
    url_map: dict[str, str] = {}
    if args.url_map:
        for line in Path(args.url_map).read_text(encoding="utf-8").splitlines():
            parts = line.split("\t")
            if len(parts) >= 2 and parts[0].strip() and parts[1].strip():
                url_map[parts[0].strip()] = parts[1].strip()
        print(f"URL 오버라이드 {len(url_map)}건 로드: {args.url_map}")

    jobs = []
    want = {s.strip() for s in args.slugs.split(",") if s.strip()} if args.slugs else set()
    for p in sorted(TOOLS_DIR.glob("*.md")):
        fm, _, _ = split_frontmatter(p.read_text(encoding="utf-8"))
        if fm != "\x00" and re.search(r"^image\s*:", fm, re.M) and p.stem not in want:
            continue
        if fm == "\x00":
            continue
        if p.stem in SKIP:
            print(f"  [skip] {p.stem} — D1 스크린샷 보유")
            continue
        u = url_map.get(p.stem) or target_url(fm)
        if not u:
            print(f"  [skip] {p.stem} — url 없음")
            continue
        jobs.append((p, u))

    if args.slugs:
        jobs = [(p, u) for p, u in jobs if p.stem in want]

    if args.limit:
        jobs = jobs[: args.limit]
    print(f"백필 대상 {len(jobs)}건  (mode={'apply' if args.apply else 'dry-run'})")
    if not args.apply:
        for p, u in jobs[:20]:
            print(f"  {p.stem:40s} {u}")
        return 0

    from playwright.async_api import async_playwright

    ok, fail = [], []
    sem = asyncio.Semaphore(CONCURRENCY)
    async with async_playwright() as pw:
        # 2026-10-18: 로컬 캐시에 1228 이 없고 1234 만 있는 환경 대응.
        # 기존 동작 보존 — AIK24_CHROMIUM_PATH 미설정 시 이전과 동일하게 기본 실행파일을 쓴다.
        exe = os.environ.get("AIK24_CHROMIUM_PATH") or None
        channel = args.channel or os.environ.get("AIK24_CHROME_CHANNEL") or None
        # 2026-10-18: --route og 는 브라우저를 쓰지 않는다. 로컬 Chromium 미설치 환경에서
        # og 경로만 돌릴 때 브라우저 실행 단계에서 죽던 문제 방지(동작 변화 없음).
        browser = None
        if args.route != "og":
            if channel:
                # 시스템 Chrome — 번들 headless shell 이 봇 차단에 걸리는 사이트 대응(2026-10-18 실측)
                browser = await pw.chromium.launch(headless=True, channel=channel)
            elif exe:
                browser = await pw.chromium.launch(headless=True, executable_path=exe)
            else:
                browser = await pw.chromium.launch(headless=True)

        async def worker(p, u):
            async with sem:
                rel = f"/images/tools/{p.stem}.webp"
                dest = ROOT / "public" / rel.lstrip("/")
                if args.route == "browser-og":
                    good, msg = await browser_og_capture(browser, u, dest)
                elif args.route == "og" or (args.route == "auto" and is_aggregator(u)):
                    good, msg = await asyncio.to_thread(og_capture, u, p.stem, dest)
                else:
                    good, msg = await capture(browser, u, dest)
                    if not good and args.route == "auto":
                        good2, msg2 = await asyncio.to_thread(og_capture, u, p.stem, dest)
                        good, msg = (True, f"{msg}→{msg2}") if good2 else (False, f"{msg} | {msg2}")
                if good:
                    write_image_field(p, rel)
                    ok.append(p.stem)
                    print(f"  ✅ {p.stem} {msg}", flush=True)
                else:
                    fail.append((p.stem, msg))
                    print(f"  ❌ {p.stem} {msg}", flush=True)

        await asyncio.gather(*(worker(p, u) for p, u in jobs))
        if browser:
            await browser.close()

    for f in (ROOT / "scripts").glob(".thumb_tmp_*.jpg"):
        f.unlink(missing_ok=True)
    print(f"\n완료: 성공 {len(ok)} / 실패 {len(fail)} / 총 {len(jobs)}")
    if fail:
        print("실패 목록:")
        for s, m in fail:
            print(f"  {s}: {m}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))