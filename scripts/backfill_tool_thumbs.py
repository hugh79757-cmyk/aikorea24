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
import re
import sys
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


async def capture(browser, url: str, out: Path) -> tuple[bool, str]:
    from PIL import Image

    page = await browser.new_page(viewport=VIEWPORT)
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=TIMEOUT_MS)
        await page.wait_for_timeout(SETTLE_MS)
        if await is_challenge(page):
            return False, "BOT_CHALLENGE"
        # 병렬 실행 시 공유 tmp 충돌 방지 — slug 로 고유화
        tmp = ROOT / "scripts" / f".thumb_tmp_{out.stem}.jpg"
        await page.screenshot(path=str(tmp), type="jpeg", quality=90)
        with Image.open(tmp) as im:
            im = im.convert("RGB").resize((TARGET_W, TARGET_H), Image.LANCZOS)
            out.parent.mkdir(parents=True, exist_ok=True)
            im.save(out, "WEBP", quality=75)
        return True, f"{out.stat().st_size // 1024}KB"
    except Exception as e:
        return False, type(e).__name__ + ": " + str(e).split("\n")[0][:90]
    finally:
        await page.close()


def write_image_field(path: Path, rel: str) -> None:
    text = path.read_text(encoding="utf-8")
    fm, body, closing = split_frontmatter(text)
    if fm == "\x00":
        raise RuntimeError(f"frontmatter 없음: {path.name}")
    line = f'image: "{rel}"\n'
    path.write_text(f"---\n{fm.rstrip()}\n{line}---{body}", encoding="utf-8")


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="실제로 캡쳐 + md 수정")
    ap.add_argument("--limit", type=int, default=0, help="앞 N 개만")
    args = ap.parse_args()

    jobs = []
    for p in sorted(TOOLS_DIR.glob("*.md")):
        fm, _, _ = split_frontmatter(p.read_text(encoding="utf-8"))
        if fm == "\x00" or re.search(r"^image\s*:", fm, re.M):
            continue
        if p.stem in SKIP:
            print(f"  [skip] {p.stem} — D1 스크린샷 보유")
            continue
        u = target_url(fm)
        if not u:
            print(f"  [skip] {p.stem} — url 없음")
            continue
        jobs.append((p, u))

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
        browser = await pw.chromium.launch(headless=True)

        async def worker(p, u):
            async with sem:
                rel = f"/images/tools/{p.stem}.webp"
                good, msg = await capture(browser, u, ROOT / "public" / rel.lstrip("/"))
                if good:
                    write_image_field(p, rel)
                    ok.append(p.stem)
                    print(f"  ✅ {p.stem} {msg}", flush=True)
                else:
                    fail.append((p.stem, msg))
                    print(f"  ❌ {p.stem} {msg}", flush=True)

        await asyncio.gather(*(worker(p, u) for p, u in jobs))
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