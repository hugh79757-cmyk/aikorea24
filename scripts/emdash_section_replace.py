#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""EmDash 글의 **구간(블록 범위)만** 마크다운으로 갈아끼우는 도구.

AIK24-BLOG-02 (2026-10-17). 배경: 기존 발행 글의 "사용법" 구간이 에이전트용
명령줄 호출 중심으로 쓰여 있어, 사람이 화면에서 하는 경로(모델 선택 창)로
바꿔야 했다. 글 전체를 다시 쓰면 실측 표·이미지·표까지 흔들리므로, 문제 구간만
블록 단위로 교체한다.

동작
----
1. `--dump`               : 현재 본문을 블록 인덱스 + 스타일 + 텍스트로 출력한다(편집 지점 탐색).
2. `--anchor A`            : 가시 텍스트에 A 를 포함하는 블록 1개를 찾는다(중복이면 중단).
   `--to-anchor B`         : A 블록 이후 B 를 포함하는 첫 블록 **직전까지** 를 범위로 잡는다.
                            B 를 생략하면 다음 제목(h2/h3) 직전까지.
   `--index N` / `--index N:M` : 인덱스로 직접 지정(M 은 미포함).
3. `--md 파일`             : 범위를 이 마크다운으로 교체한다(md_to_pt 로 변환 후 삽입).
4. 기본은 dry-run. `--apply` 를 줘야 PUT + publish 한다.

안전장치
--------
- 교체 대상 블록의 `_key` 는 건드리지 않는다. **새로 삽입하는 블록만** 키를 재발급해
  기존 키와 충돌하지 않게 한다(키 충돌은 CMS 가 같은 블록으로 보는 원인).
- `data` 전체를 PUT 하므로 featured_image·excerpt·title 은 그대로 유지된다.
- 적용 전 백업(JSON)을 scripts/logs/ 에 남기고, 적용 후 재조회로
  ① 새 문구 존재 ② 옛 문구 부재 ③ slug·publishedAt 불변 을 검증한다.
"""

import argparse
import datetime as _dt
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import emdash_publish as ep  # noqa: E402
from emdash_text_replace import visible_strings  # noqa: E402

LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
KEY_RE = re.compile(r"^k[0-9a-f]+$")


def block_text(b):
    """블록 1개의 가시 텍스트(표·이미지 포함)."""
    out = []
    if b.get("_type") == "block":
        return "".join(s.get("text", "") for s in b.get("children", []))
    if b.get("_type") in ("code",):
        return b.get("code", "")
    if b.get("_type") == "image":
        return b.get("alt", "") or b.get("asset", {}).get("url", "")
    if b.get("_type") == "table":
        rows = []
        for r in b.get("rows", []):
            cells = ["".join(s.get("text", "") for s in c.get("content", []))
                     for c in r.get("cells", [])]
            rows.append(" | ".join(cells))
        return " / ".join(rows)
    visible_strings([b], out)
    return " ".join(out)


def rekey(blocks, prefix):
    """삽입 블록의 _key / marks 값을 새 접두사로 재발급(기존 문서와 충돌 방지)."""
    counter = [0]

    def walk(node):
        if isinstance(node, list):
            for v in node:
                walk(v)
            return
        if not isinstance(node, dict):
            return
        for name, val in list(node.items()):
            if name == "_key" and isinstance(val, str) and KEY_RE.match(val):
                counter[0] += 1
                node[name] = "%s%04d" % (prefix, counter[0])
            elif name in ("marks", "markDefs") and isinstance(val, list):
                for i, v in enumerate(val):
                    if isinstance(v, str) and KEY_RE.match(v):
                        counter[0] += 1
                        val[i] = "%s%04d" % (prefix, counter[0])
                    elif isinstance(v, dict):
                        walk(v)
            elif isinstance(val, (dict, list)):
                walk(val)

    for b in blocks:
        walk(b)
    return blocks


def resolve_range(content, args):
    """(start, end) 블록 범위를 정한다. end 는 미포함."""
    if getattr(args, "section", None):
        heads = [i for i, b in enumerate(content)
                 if b.get("_type") == "block" and b.get("style") in ("h2", "h3")
                 and args.section in block_text(b)]
        if len(heads) != 1:
            raise SystemExit("--section %r 에 해당하는 제목이 %d개입니다: %s"
                             % (args.section, len(heads), heads[:8]))
        start = heads[0] + 1
        end = len(content)
        for i in range(start, len(content)):
            if content[i].get("_type") == "block" and content[i].get("style") in ("h2", "h3"):
                end = i
                break
        print("제목 [%d] %s — 본문 구간 [%d, %d)" % (heads[0], block_text(content[heads[0]]), start, end))
        return start, end
    if args.index:
        if ":" in args.index:
            a, b = args.index.split(":", 1)
            return int(a), int(b)
        i = int(args.index)
        return i, i + 1
    hits = [i for i, b in enumerate(content) if args.anchor in block_text(b)]
    if not hits:
        raise SystemExit("앵커 문구를 찾지 못했습니다: %r" % args.anchor)
    if len(hits) > 1:
        raise SystemExit("앵커가 %d개 블록에 걸립니다(더 길게 잡으세요): %s"
                         % (len(hits), hits[:8]))
    start = hits[0]
    if args.to_anchor:
        tail = [i for i in range(start + 1, len(content))
                if args.to_anchor in block_text(content[i])]
        if not tail:
            raise SystemExit("종료 앵커를 찾지 못했습니다: %r" % args.to_anchor)
        return start, tail[0]
    end = len(content)
    for i in range(start + 1, len(content)):
        if content[i].get("_type") == "block" and content[i].get("style") in ("h2", "h3"):
            end = i
            break
    return start, end


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--slug", required=True)
    ap.add_argument("--dump", action="store_true", help="현재 블록 구조를 출력")
    ap.add_argument("--anchor", default=None, help="범위 시작 — 가시 텍스트에 포함될 문구")
    ap.add_argument("--to-anchor", default=None, help="범위 끝(미포함) 문구. 없으면 다음 제목까지")
    ap.add_argument("--index", default=None, help="N 또는 N:M 으로 직접 지정")
    ap.add_argument("--section", default=None,
                    help="제목(h2/h3)에 이 문구가 든 섹션의 본문 전체 — 제목은 그대로 두고 본문만 교체")
    ap.add_argument("--md", default=None, help="교체할 마크다운 파일")
    ap.add_argument("--apply", action="store_true", help="실제 PUT + publish (기본 dry-run)")
    a = ap.parse_args(argv)

    it = ep.get_post(a.slug) or {}
    item = it.get("item") or {}
    data = item.get("data") or {}
    content = data.get("content")
    pw = (item.get("data") or {}).get("title") or data.get("title")
    if not isinstance(content, list):
        raise SystemExit("본문 조회 실패: %s" % a.slug)

    if a.dump or not a.md:
        print("글: %s" % (item.get("slug") or a.slug))
        print("제목: %s" % pw)
        print("블록 %d개 | publishedAt %s" % (len(content), item.get("publishedAt")))
        print()
        for i, b in enumerate(content):
            t = block_text(b).replace("\n", " ⏎ ")
            style = b.get("style") or b.get("_type")
            if b.get("listItem"):
                style += ":" + b["listItem"]
            print("[%3d] %-14s %s" % (i, style, t[:150]))
        if not a.md:
            return 0

    new_md = open(a.md, encoding="utf-8").read()
    from emdash04_migrate import md_to_pt

    start, end = resolve_range(content, a)
    print("범위: [%d, %d) — 블록 %d개" % (start, end, end - start))
    for i in range(start, end):
        print("   - [%d] %s" % (i, block_text(content[i])[:110]))
    new_blocks = md_to_pt(new_md)
    stamp = _dt.datetime.now().strftime("%Y%m%d%H%M%S%f")
    rekey(new_blocks, "n%s" % stamp[-6:])
    print("삽입 블록 %d개 (새 키 접두사 n%s)" % (len(new_blocks), stamp[-6:]))
    print()
    print("--- 삽입될 첫 블록 ---")
    print(block_text(new_blocks[0])[:300])

    if not a.apply:
        print()
        print("DRY-RUN — 쓰지 않았습니다. 적용하려면 --apply")
        return 0

    os.makedirs(LOG_DIR, exist_ok=True)
    bpath = os.path.join(LOG_DIR, "backup_section_%s_%s.json" % (stamp, item.get("id") or "x"))
    with open(bpath, "w", encoding="utf-8") as f:
        json.dump({"id": item.get("id"), "slug": item.get("slug"),
                   "published_at": item.get("publishedAt"), "data": data},
                  f, ensure_ascii=False)
    print("백업: %s (%d bytes)" % (bpath, os.path.getsize(bpath)))

    new_content = content[:start] + new_blocks + content[end:]
    new_data = dict(data)
    new_data["content"] = new_content
    from emdash04_migrate import api

    st, d = api("/_emdash/api/content/posts/%s" % (item.get("id") or a.slug), "PUT",
                {"collection": "posts", "id": item.get("id") or a.slug,
                 "data": new_data, "_rev": it.get("_rev")})
    if st not in (200, 201):
        print("! PUT 실패 http=%s %s" % (st, json.dumps(d, ensure_ascii=False)[:200]))
        return 1
    st2, d2 = api("/_emdash/api/content/posts/%s/publish" % (item.get("id") or a.slug), "POST", {})
    if st2 not in (200, 201):
        print("! publish 실패 http=%s %s" % (st2, json.dumps(d2, ensure_ascii=False)[:200]))
        return 1
    print("PUT+publish 완료")

    # 재조회 검증
    after = (ep.get_post(item.get("id")) or {}).get("item") or {}
    d2b = after.get("data") or {}
    c2 = d2b.get("content") or []
    # 검증은 **블록 단위 텍스트**로 한다. visible_strings 는 스팬(조각) 단위라
    # 여러 스팬에 걸친 문구를 찾지 못해 "미반영"으로 잘못 판정한다(2026-10-17 실측).
    txt_all = "\n".join(block_text(b) for b in c2)
    probe = block_text(new_blocks[0])[:40]
    ok_probe = probe in txt_all
    old_gone = all(block_text(b) not in txt_all for b in content[start:end] if block_text(b).strip())
    print("  · 블록수 %d → %d" % (len(content), len(c2)))
    print("  · 새 문구 반영: %s | 옛 블록 텍스트 제거: %s" % (ok_probe, old_gone))
    print("  · slug 불변: %s | publishedAt 불변: %s"
          % (after.get("slug") == item.get("slug"),
             after.get("publishedAt") == item.get("publishedAt")))
    print("  · 제목 유지: %s" % (d2b.get("title") == pw))
    if not ok_probe:
        print("  ! 새 문구가 재조회에서 확인되지 않았습니다 — 백업으로 복구하세요: %s" % bpath)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
