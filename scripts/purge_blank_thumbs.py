"""백필 썸네일 품질 검증 — 평평한 화면(빈 페이지·에러 페이지)을 찾아 제거한다.

stddev 가 낮은 이미지만 후보로 삼고, 실제 페이지 텍스트로 확인한 뒤
md frontmatter 의 image: 필드와 webp 파일을 함께 지운다.

사용: .venv/bin/python3 scripts/purge_blank_thumbs.py [--apply] [--stddev 30]
"""

import argparse
import asyncio
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from backfill_tool_thumbs import ROOT, TOOLS_DIR, split_frontmatter, target_url  # noqa: E402

ERROR_MARKERS = (
    "access denied",
    "403 forbidden",
    "404 not found",
    "page not found",
    "just a moment",
    "verify you are human",
    "attention required",
)


def img_stddev(p: Path) -> float:
    from PIL import Image, ImageStat

    with Image.open(p) as im:
        return ImageStat.Stat(im.convert("L").resize((160, 90))).stddev[0]


def strip_image_field(path: Path) -> bool:
    text = path.read_text(encoding="utf-8")
    fm, body, closing = split_frontmatter(text)
    if fm == "\x00":
        return False
    new = re.sub(r'^image\s*:.*$', "", fm, flags=re.M)
    if new == fm:
        return False
    path.write_text(f"---\n{new.rstrip()}\n---{body}", encoding="utf-8")
    return True


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--stddev", type=float, default=30.0)
    ap.add_argument(
        "--blank-stddev",
        type=float,
        default=5.0,
        help="이 값 미만이면 문구 무관하게 빈 화면으로 간주하고 제거",
    )
    args = ap.parse_args()

    from PIL import Image
    from playwright.async_api import async_playwright

    d = ROOT / "public" / "images" / "tools"
    cands = []
    blank = []
    for p in sorted(d.glob("*.webp")):
        s = img_stddev(p)
        if s < args.blank_stddev:
            blank.append(p)  # 거의 평평함 — 빈 화면 확정, 페이지 확인 불필요
        elif s < args.stddev:
            cands.append((s, p))
    for p in blank:
        print(f"  ❌ {p.stem}: 빈 화면 (stddev {img_stddev(p):.2f})", flush=True)
    print(f"후보 {len(cands)}건 (stddev < {args.stddev}) / 빈 화면 {len(blank)}건", flush=True)
    if not cands and not blank:
        return 0

    bad = [(p, "blank") for p in blank]

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        sem = asyncio.Semaphore(6)

        async def check(p: Path) -> None:
            md = TOOLS_DIR / f"{p.stem}.md"
            if not md.exists():
                return
            url = target_url(split_frontmatter(md.read_text(encoding="utf-8"))[0])
            if not url:
                return
            async with sem:
                page = await browser.new_page(viewport={"width": 1280, "height": 720})
                try:
                    await page.goto(url, wait_until="domcontentloaded", timeout=25000)
                    await page.wait_for_timeout(1500)
                    txt = ((await page.inner_text("body", timeout=5000)) or "").lower()
                    hit = next((m for m in ERROR_MARKERS if m in txt), None)
                    if hit:
                        bad.append((p, hit))
                        print(f"  ❌ {p.stem}: '{hit}'", flush=True)
                except Exception:
                    pass
                finally:
                    await page.close()

        await asyncio.gather(*(check(p) for _, p in cands))
        await browser.close()

    print(f"\n제거 대상 {len(bad)}건")
    if args.apply:
        for p, _ in bad:
            strip_image_field(TOOLS_DIR / f"{p.stem}.md")
            p.unlink(missing_ok=True)
        print(f"md image: 필드 + webp 삭제 완료 ({len(bad)}건)")
    else:
        print("dry-run — --apply 없음")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))