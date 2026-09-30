#!/usr/bin/env python3
"""본문 유실(mode A/B)된 블로그 글 백필 — 파서 버그(2026-06-08, 7d99557e7)로 본문이 잘린 파일 재생성.

대상: src/content/blog/*.md 중 본문 1000자 미만 (mode C는 본문 정상이라 제외)
사용: python3 scripts/backfill_empty_body.py [--apply]
      (기본 dry-run: D1 대상 기사만 확인, 파일 미변경)
"""
import os
import re
import sys
import glob
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import blog_draft_generator as g  # noqa: E402

BLOG_DIR = os.path.join(g.PROJECT_DIR, "src", "content", "blog")
BACKUP_DIR = os.path.join(g.PROJECT_DIR, "logs")
AUTO_RE = re.compile(r"\A\d{4}-\d{2}-\d{2}-\d{3}-")
BROKEN_MAX = 1000  # 이보다 짧고 ## 소제목이 하나도 없으면 파서 버그로 본문 유실

_LINK_RE = re.compile(r"/briefing/(\d{4}-\d{2}-\d{2})-(\d+)/#item-(\d+)")
_FM_RE = re.compile(r"\A---\n(.*?)\n---\n(.*)\Z", re.S)


def q(s):
    return str(s).replace("'", "''")


def split_md(path):
    raw = open(path, encoding="utf-8").read()
    m = _FM_RE.match(raw)
    if not m:
        return None, None, None
    return m.group(1), m.group(2).strip(), raw


def fm_value(fm, key):
    m = re.search(rf'^{key}:\s*"?([^"\n]*)"?', fm, re.M)
    return m.group(1).strip() if m else ""


def fm_tag0(fm):
    m = re.search(r"^tags:\n\s*-\s*\"?([^\"\n]+)\"?", fm, re.M)
    return m.group(1).strip() if m else ""


def resolve_article(body, keyword, path):
    """deep_dive_url(슬러그) → 브리핑 링크 → news.title 3단계로 D1 기사 복원."""
    slug = os.path.basename(path)[:-3].lower()
    rows = g.query_d1(
        f"SELECT n.id, n.title, n.description, n.source, b.date, bi.sort_order "
        f"FROM briefing_items bi JOIN briefings b ON bi.briefing_id=b.id "
        f"JOIN news n ON bi.news_id=n.id WHERE bi.deep_dive_url='https://aikorea24.kr/blog/{q(slug)}/'"
    )
    if rows:
        r = rows[0]
        return dict(r, _briefing_url=f"https://aikorea24.kr/briefing/{r['date']}/#item-{r['sort_order']}"), "deep_dive_url"
    m = _LINK_RE.search(body)
    if m:
        bdate, item = f"{m.group(1)}-{m.group(2)}", int(m.group(3))
        rows = g.query_d1(
            f"SELECT n.id, n.title, n.description, n.source FROM briefing_items bi "
            f"JOIN briefings b ON bi.briefing_id=b.id JOIN news n ON bi.news_id=n.id "
            f"WHERE b.date={q(bdate)} AND bi.sort_order={item}"
        )
        if rows:
            return dict(rows[0], _briefing_url=f"https://aikorea24.kr/briefing/{bdate}/#item-{item}"), f"link {bdate}#{item}"
        return None, f"link miss {bdate}#{item}"
    rows = g.query_d1(f"SELECT id, title, description, source FROM news WHERE title='{q(keyword)}' LIMIT 1")
    if rows:
        return dict(rows[0]), "tag-title"
    return None, "no d1 row"


def inject_briefing_link(content, art):
    url = art.get("_briefing_url")
    if not url:
        return content
    block = f"\n\n원문기사는 아래의 링크를 통해 확인할 수 있습니다. [기사원문보기]({url})"
    head, sep, tail = content.partition("\n\n")
    return head + block + (sep + tail if sep else "")


def main():
    apply = "--apply" in sys.argv
    targets = []
    for path in sorted(glob.glob(os.path.join(BLOG_DIR, "*.md"))):
        fm, body, _ = split_md(path)
        if fm and AUTO_RE.match(os.path.basename(path)) and len(body) < BROKEN_MAX and "## " not in body:
            targets.append((path, fm, body))
    print(f"백필 대상: {len(targets)}건 (apply={apply})")
    if not targets:
        return

    if apply:
        names = " ".join(f"'{os.path.basename(p)}'" for p, _, _ in targets)
        os.system(f"tar czf '{BACKUP_DIR}/backup_blog_backfill_20260930.tgz' -C '{BLOG_DIR}' {names}")
        print(f"백업 완료: {BACKUP_DIR}/backup_blog_backfill_20260930.tgz ({len(targets)}건)")

    results = []
    for i, (path, fm, body) in enumerate(targets, 1):
        keyword = fm_tag0(fm)
        art, how = resolve_article(body, keyword, path)
        name = os.path.basename(path)
        if not art:
            print(f"[{i}/{len(targets)}] {name} → SKIP ({how})")
            results.append((path, None, how))
            continue
        print(f"[{i}/{len(targets)}] {name} → {how} | {art['title'][:50]}", flush=True)
        if not apply:
            results.append((path, art, how))
            continue
        raw = g.generate_draft(keyword, [art], "A")
        _, content = g._parse_title_body(raw or "")
        content = inject_briefing_link(content, art)
        if "## " not in content or len(content) < 800:
            print(f"    ⚠️ 생성 실패(len={len(content)}, ##={'## ' in content}) — 파일 유지")
            results.append((path, None, "gen-fail"))
            continue
        title = fm_value(fm, "title") or keyword
        desc = g._extract_first_sentence(re.sub(r"^##?\s+[^\n]+\n\s*", "", content), 300).replace('"', "'")
        keep = [ln for ln in fm.split("\n")
                if not re.match(r"^(title|description):", ln)]
        md = ("---\n" + f'title: "{title.replace(chr(34), chr(39))}"\n'
              + "\n".join(keep).strip("\n") + f'\ndescription: "{desc}"\n---\n\n{content}\n')
        open(path, "w", encoding="utf-8").write(md)
        print(f"    ✅ {len(body)}자 → {len(content)}자")
        results.append((path, art, "ok"))
        time.sleep(1)

    if apply:
        ok = sum(1 for _, _, h in results if h == "ok")
        print(f"\n결과: {ok}/{len(targets)} 백필, skip={len(targets)-ok}")
        for p, _, h in results:
            if h != "ok":
                print(f"  SKIP {os.path.basename(p)}: {h}")


if __name__ == "__main__":
    main()