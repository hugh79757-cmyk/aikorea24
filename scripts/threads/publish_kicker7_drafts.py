#!/usr/bin/env python3
"""publish_kicker7_drafts.py — kicker7 드래프트 → Threads 발행 (비동기).

kicker7_selector/*.txt 를 글로브 → 파싱(6카드) → 루브릭 게이트 → publish_thread_chain.
멱등: 발행 성공 시 published/ 이동 + posted_ids.json 기록. 미달 시 hold/ 이동.

주: publish_thread_chain 은 5 콘텐츠카드 + 링크별도발행 구조.
     카드6(출처)은 발행 카드에서 제외하고 link_url 로 따로 붙임.
"""
import sys, os, re, json, pathlib, glob, shutil, datetime, argparse

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT))

from pipeline.threads.contrast.kicker7_writer import _parse_kicker7_cards  # noqa
from main_v3 import validate_final_cards  # noqa
from publisher import publish_thread_chain  # noqa

DRAFT_DIR = HERE / "logs" / "drafts" / "kicker7_selector"
HOLD_DIR = DRAFT_DIR / "hold"
PUBLISHED_DIR = DRAFT_DIR / "published"
POSTED_JSON = DRAFT_DIR / "posted_ids.json"
V3_POSTED = HERE / "posted.json"  # v3(main_v3) 발행기와 공유 — 이중 발행 방지

_NAME_RE = re.compile(r"[가-힣]{1,4}\s[가-힣]{2,8}|[A-Za-z]+\s[A-Za-z]+")
_ROLE_RE = re.compile(r"해커|주민|시민|CEO|대표|교수|위원|장관|의원|사장|회장|기자|연구원|의사|변호사|활동가|노조|관계자")
_FACT_RE = re.compile(r"\d|[\"「“]|" + _ROLE_RE.pattern)


def load_posted() -> set:
    if POSTED_JSON.exists():
        try:
            return set(json.loads(POSTED_JSON.read_text(encoding="utf-8")))
        except Exception:
            return set()
    return set()


def save_posted(ids: set):
    POSTED_JSON.write_text(json.dumps(sorted(ids), ensure_ascii=False, indent=2), encoding="utf-8")


def _v3_posted_links() -> set:
    """v3 발행기(posted.json)가 이미 발행한 기사 링크 집합. 이중 발행 방지 공유 dedup."""
    if not V3_POSTED.exists():
        return set()
    try:
        data = json.loads(V3_POSTED.read_text(encoding="utf-8"))
    except Exception:
        return set()
    links = set(data.get("posted_links", []) if isinstance(data, dict) else [])
    for h in (data.get("history", []) if isinstance(data, dict) else []):
        if isinstance(h, dict) and h.get("link"):
            links.add(h["link"])
    return links


def _record_v3_posted(link: str, fid: str):
    """k7 발행 성공을 v3 posted.json에도 기록 — v3가 같은 기사 재발행하지 않게."""
    if not V3_POSTED.exists() or not link:
        return
    try:
        data = json.loads(V3_POSTED.read_text(encoding="utf-8"))
    except Exception:
        return
    if not isinstance(data, dict):
        return
    if link not in data.get("posted_links", []):
        data.setdefault("posted_links", []).append(link)
    data.setdefault("history", []).append({
        "link": link, "source": "kicker7", "id": fid,
        "posted_at": datetime.datetime.now().isoformat(timespec="seconds"),
    })
    V3_POSTED.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _clean_card(s: str) -> str:
    lines = s.split("\n")
    while lines and lines[0].strip() in ("", "---"):
        lines.pop(0)
    while lines and lines[-1].strip() in ("", "---"):
        lines.pop()
    return "\n".join(lines).strip()


def parse_draft(path: pathlib.Path):
    """returns (dict, None) or (None, reason).

    카드1~5는 모델이 '--- 카드 N ---' 헤더 없이 '---' 로만 구분.
    카드6(출처)는 '--- 카드 6 ---' 헤더. 카드간 구분은 '---' 만 사용.
    """
    text = path.read_text(encoding="utf-8")
    # 카드6(출처) 분리
    m = re.search(r"---\s*카드\s*6\s*---(.*?)$", text, re.DOTALL)
    if m:
        card6 = _clean_card("--- 카드 6 ---" + m.group(1))
        body = text[:m.start()]
    else:
        m2 = re.search(r"(출처:.*?원문:\s*\S+.*)$", text, re.DOTALL)
        if not m2:
            return None, "출처카드없음"
        card6 = _clean_card(m2.group(1))
        body = text[:m2.start()]
    # 본문(카드1~5) 분리: '---' 만 카드간 구분 (카드 내부 절구분 \n\n 는 보존)
    chunks = [_clean_card(c) for c in re.split(r"\n\s*---\s*\n", body) if c.strip()]
    if len(chunks) != 5:
        return None, f"카드수부족({len(chunks)})"
    src = re.search(r"출처:\s*(.+)", card6)
    url = re.search(r"원문:\s*(\S+)", card6)
    if not src or not url:
        return None, "출처카드형식오류"
    return {"content": chunks, "source": src.group(1).strip(),
            "link": url.group(1).strip(), "card6": card6}, None


def rubric_pass(content, card6, path) -> tuple[bool, str]:
    # 1) 무근거 0: 카드1~5 각각 사실토큰 ≥1
    for i, c in enumerate(content, 1):
        if not _FACT_RE.search(c):
            return False, f"무근거 카드{i}"
    # 2) 화자실명: 카드4(현장목소리) 이름+직함
    if not (_NAME_RE.search(content[3]) and _ROLE_RE.search(content[3])):
        return False, "화자실명누락(카드4)"
    # 3) 출처카드 존재
    if "출처:" not in card6 or "원문:" not in card6:
        return False, "출처카드누락"
    # 4) 기존 검증 재사용 (카드1~5만)
    ok, issues = validate_final_cards(content)
    if not ok:
        return False, f"validate_final_cards:{issues}"
    return True, "OK"


def move_to(src: pathlib.Path, dst_dir: pathlib.Path, suffix: str = ""):
    dst_dir.mkdir(parents=True, exist_ok=True)
    dst = dst_dir / (src.stem + suffix + src.suffix)
    shutil.move(str(src), str(dst))
    return dst


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="검증+로그만, 발행/이동 안 함")
    args = ap.parse_args()
    dry = args.dry_run

    HOLD_DIR.mkdir(parents=True, exist_ok=True)
    PUBLISHED_DIR.mkdir(parents=True, exist_ok=True)
    posted = load_posted()
    v3_links = _v3_posted_links()

    files = sorted(glob.glob(str(DRAFT_DIR / "k7_*.txt")))
    print(f"[k7-publish] drafts={len(files)} dry_run={dry}")
    if not files:
        return

    for f in files:
        p = pathlib.Path(f)
        fid = p.stem
        if fid in posted:
            print(f"  [SKIP] 이미 발행됨 {fid}")
            continue
        parsed = parse_draft(p)
        if parsed[0] is None:
            print(f"  [HOLD] {fid} — {parsed[1]}")
            if not dry:
                move_to(p, HOLD_DIR, f"_{parsed[1]}")
            continue
        d = parsed[0]
        if d["link"] in v3_links:
            print(f"  [SKIP] v3 이미 발행한 기사 — {fid} link={d['link']}")
            if not dry:
                move_to(p, HOLD_DIR, "_v3_dedup")
            continue
        passed, reason = rubric_pass(d["content"], d["card6"], p)
        if not passed:
            print(f"  [HOLD] {fid} — 루브릭미달:{reason}")
            if not dry:
                move_to(p, HOLD_DIR, f"_rubric_{reason}")
            continue
        print(f"  [PASS] {fid} — source={d['source']} link={d['link']}")
        if dry:
            continue
        article = {"link": d["link"], "title": d["content"][0].splitlines()[0][:60] if d["content"] else fid,
                   "source": d["source"], "id": fid}
        # publish_thread_chain 은 5 콘텐츠카드 + link 별도발행 → 카드6 제외
        root = publish_thread_chain(d["content"], article, link_url=d["link"])
        if root:
            posted.add(fid)
            save_posted(posted)
            _record_v3_posted(d["link"], fid)
            move_to(p, PUBLISHED_DIR)
            print(f"    [PUBLISHED] {fid} → root={root}")
        else:
            print(f"    [FAIL] {fid} — publish_thread_chain None (토큰/인증/쿼터 확인)")
            # 실패 시 이동 안 함 → 다음 사이클 재시도


if __name__ == "__main__":
    main()
