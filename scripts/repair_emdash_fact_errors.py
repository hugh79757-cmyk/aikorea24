#!/usr/bin/env python3
"""2026-11-06 사고 복구 — 발행된 EmDash 글의 날짜 날조 · 광고/제휴 링크 제거.

사고(2026-11-05):
  · 네이버클라우드 국방 AI 글: 원문 "3일 행사" → 생성 글 "2024년 5월 3일 개최된 국방·클라우드
    융합 포럼" (6회). 2년 전 날짜·행사명 날조.
  · AMD(2023년 4분기)·뉴욕증시(2024년 10월 30일, 34,500포인트 등)도 같은 유형.
  · 원문 페이지 템플릿에서 긁힌 쿠팡 제휴 링크(link.coupang.com)와
    windows.microsoft.com/.../internet-explorer/download-ie 가 '인용 링크'로 들어가 있었다.

이 스크립트는 **결정적 치환만** 한다(LLM 미사용). 교정 후 게이트의 날짜 근거·정크 링크
검사를 다시 통과하지 못하면 PUT 하지 않는다.

사용: ../.venv/bin/python3 scripts/repair_emdash_fact_errors.py [--dry-run]
환경: EMDASH_PAT (필수) — ~/.env.common 의 EMDASH_API_TOKEN
"""
import argparse
import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import blog_quality_gate as gate  # noqa: E402
import emdash_publish as ep  # noqa: E402
from emdash13_repair import rest  # noqa: E402

NBSP = "\u00a0"

# 슬러그 → (뉴스 id, 치환 목록, excerpt 치환)
# 치환은 (정규식, 대체문) — 블록 전체 텍스트에 적용한다.
REPAIRS = {
    "네이버클라우드-국방-ai-김유원-네이버클라우드-대표-미래-강군은-ai소버린구독형-전략-발표": {
        "news_id": 58615,
        "drop_text": [r"【\s*Coupang[^】]*】[^.]*\."],
        "replace": [
            (r"2024년[\s\u00a0]*5월[\s\u00a0]*3일[\s\u00a0]*(?:에[\s\u00a0]*)?개최된[\s\u00a0]*"
             r"국방[·ㆍ・]?[\s\u00a0]*클라우드[\s\u00a0]*융합[\s\u00a0]*포럼에서",
             "지난 3일(2026년 11월 3일) 진행된 행사에서"),
            (r"2024년[\s\u00a0]*5월[\s\u00a0]*3일", "2026년 11월 3일"),
        ],
    },
    "amd-데이터센터-매출-2배-폭증-시간외-9-폭등-ai-전략이-만든-반전극": {
        "news_id": 58442,
        "replace": [
            (r"2023년[\s\u00a0]*4분기[\s\u00a0]*실적을[\s\u00a0]*발표하면서",
             "최근 실적을 발표하면서"),
            (r"2023년[\s\u00a0]*4분기", "최근 분기"),
        ],
    },
    "뉴욕증시-정치적-불확실성-해소다우-3sp-158-빅테크-투자-확대로-시장-반등": {
        "news_id": 58617,
        "replace": [
            (r"2024년[\s\u00a0]*10월[\s\u00a0]*30일[\s\u00a0]*장[\s\u00a0]*마감[\s\u00a0]*기준[\s\u00a0]*"
             r"34,?500[\s\u00a0]*포인트[\s\u00a0]*수준에서", ""),
            (r"4,?300[\s\u00a0]*포인트에서", ""),
            (r"2024년[\s\u00a0]*10월[\s\u00a0]*30일,?[\s\u00a0]*", ""),
            (r"2024년[\s\u00a0]*초부터[\s\u00a0]*이어진[\s\u00a0]*", ""),
            (r"2025년[\s\u00a0]*말까지", "향후"),
            (r"2024년[\s\u00a0]*글로벌", "글로벌"),
            (r"2028년까지[\s\u00a0]*연평균", "이후 연평균"),
        ],
    },
    # 보일러플레이트 오염(다른 주제 글에 "2023년 4분기 실적"·"2024년 10월 30일 뉴욕증시"
    # 문장이 복사된 글) — generic_ungrounded_repair 가 해당 문장을 삭제한다.
    "네이버-통합-에이전트-구축-앞당긴다-카카오-배민도-자연어-ai-검색-확대-분석": {
        "news_id": 58585,
        "replace": [],
    },
    "무료-llm-crouton-alpha-free-opencode-zen-무료-티어-활용-가이드": {
        "news_id": 58469,
        "replace": [],
    },
}


def pt_text(block):
    return "".join(c.get("text", "") for c in (block.get("children") or []) if isinstance(c, dict))


def pt_to_md(data):
    """게이트 검사용 마크다운 복원 — span 의 링크 mark 를 `[텍스트](URL)` 로 되살린다."""
    out = []
    for b in data.get("content") or []:
        defs = {m.get("_key"): m.get("href") for m in (b.get("markDefs") or [])
                if isinstance(m, dict) and m.get("href")}
        parts = []
        for c in (b.get("children") or []):
            if not isinstance(c, dict):
                continue
            t = c.get("text", "")
            href = next((defs[k] for k in (c.get("marks") or []) if k in defs), None)
            parts.append("[%s](%s)" % (t, href) if href else t)
        out.append("".join(parts))
    return "\n\n".join(x for x in out if x)


def strip_junk_links(data):
    """광고·제휴·브라우저 안내 링크를 markDefs 와 span marks 에서 제거한다."""
    removed = []
    for b in data.get("content") or []:
        defs = b.get("markDefs") or []
        keep, bad = [], set()
        for m in defs:
            href = (m or {}).get("href") or ""
            if href and gate._JUNK_LINK_PAT.search(href):
                bad.add(m.get("_key"))
                removed.append(href)
            else:
                keep.append(m)
        if bad:
            b["markDefs"] = keep
            for c in b.get("children") or []:
                if isinstance(c, dict) and c.get("marks"):
                    c["marks"] = [k for k in c["marks"] if k not in bad]
    return sorted(set(removed))


# 링크 mark 를 지워도 앵커 텍스트는 남는다(2026-11-06 실측: "【Coupang 구독 서비스 예시】",
# "Microsoft Internet Explorer 다운로드 페이지", "Coupang 구독 서비스 소개 페이지").
_JUNK_TEXT_PAT = re.compile(r"(쿠팡|coupang|인터넷\s*익스플로러|internet\s*explorer)", re.I)


def _collapse_block(b, new_text):
    """블록 텍스트를 새 값으로 교체한다. 링크 mark 는 **살릴 수 있으면 살린다**.

    2026-11-06 사고: 공백만 정리해도 children 을 marks=[] 로 재작성해 'Cbci 뉴스 원문 보기'
    링크가 사라졌다(마크다운에는 있었는데 화면에는 링크 없음). 텍스트가 같고 공백만
    다르면 아예 건드리지 않고, 실제로 바뀐 경우에만 단일 span 으로 합친다.
    """
    old = pt_text(b)
    if new_text == old:
        return False
    kids = b.get("children") or []
    key = (kids[0].get("_key") if kids else None) or "k0"
    b["children"] = [{"_type": "span", "_key": key, "text": new_text, "marks": []}]
    b["markDefs"] = []          # 텍스트를 새로 썼으므로 이전 markDefs 는 쓰이지 않는다
    return True


def restore_dangling_links(data):
    """markDefs 에 링크가 있는데 span 이 참조하지 않는(화면에 링크가 안 뜨는) 블록을 복원한다.

    반환: 복원한 블록 수.
    """
    fixed = 0
    for b in data.get("content") or []:
        defs = [m for m in (b.get("markDefs") or []) if isinstance(m, dict) and m.get("href")]
        if len(defs) != 1:
            continue
        keyk = defs[0].get("_key")
        spans = [c for c in (b.get("children") or []) if isinstance(c, dict)]
        if any(keyk in (c.get("marks") or []) for c in spans):
            continue                      # 이미 적용됨
        if not spans or not pt_text(b).strip():
            continue
        for c in spans:
            c["marks"] = list(c.get("marks") or []) + [keyk]
        fixed += 1
    return fixed


def strip_junk_text(data, extra_patterns=()):
    """정크 텍스트 블록/문장을 제거한다. 블록이 비면 통째로 뺀다."""
    removed, keep_blocks = [], []
    for b in data.get("content") or []:
        t = pt_text(b)
        # ① 블록 전체가 정크(참고 자료의 IE/쿠팡 항목) → 블록 제거
        if t.strip() and _JUNK_TEXT_PAT.search(t) and len(t.strip()) < 80:
            removed.append(t.strip()[:60])
            continue
        new = t
        for pat in extra_patterns:
            new = re.sub(pat, "", new)
        # ② 문장 단위 정크 제거
        if _JUNK_TEXT_PAT.search(new):
            sents = re.split(r"(?<=[.!?])\s+", new)
            kept = [s for s in sents if not _JUNK_TEXT_PAT.search(s)]
            removed.extend(s[:60] for s in sents if _JUNK_TEXT_PAT.search(s))
            new = " ".join(kept)
        new = re.sub(r"[ \u00a0]{2,}", " ", new).strip()
        if t.strip() and not new:
            continue
        # 공백만 다른 경우(실측: 후행 공백)에는 링크 mark 를 보존한다.
        if new.replace(" ", "") != t.replace(" ", ""):
            _collapse_block(b, new)
        keep_blocks.append(b)
    data["content"] = keep_blocks
    return removed


def apply_text_replaces(data, rules):
    """블록 텍스트 전체에 정규식 치환을 적용한다(치환 시 인라인 서식은 평문으로 합친다)."""
    changed = []
    for b in data.get("content") or []:
        t = pt_text(b)
        new = t
        for pat, rep in rules:
            new = re.sub(pat, rep, new)
        if new != t:
            # 치환으로 생긴 이중 공백·공백 앞 구두점 정리
            new = re.sub(r"[ \u00a0]{2,}", " ", new).replace(" .", ".").replace(" ,", ",")
            kids = b.get("children") or []
            key = (kids[0].get("_key") if kids else None) or "k0"
            b["children"] = [{"_type": "span", "_key": key, "text": new, "marks": []}]
            changed.append((t[:40], new[:40]))
    return changed


def fix_excerpt(data, rules):
    ex = data.get("excerpt") or ""
    new = ex
    for pat, rep in rules:
        new = re.sub(pat, rep, new)
    if new != ex:
        data["excerpt"] = new
        return True
    return False


def source_text_for(news_id):
    from pipeline.infra.d1_client import d1_query
    rows = d1_query("SELECT title, original_title, description FROM news WHERE id=%d" % news_id)
    if not rows:
        return ""
    r = rows[0]
    return "\n".join(x for x in (r.get("title"), r.get("original_title"), r.get("description")) if x)


def generic_ungrounded_repair(data, source_text):
    """원문에 없는 연도가 들어간 문장을 삭제한다 (보일러플레이트 오염 자동 복구).

    2026-11-05 실측: 서로 다른 주제 글 4건에 "AMD가 2023년 4분기 실적을…",
    "2024년 10월 30일, 미국 뉴욕증시가…" 문장이 그대로 복사돼 있었다.
    """
    allowed = gate.years_in(source_text) | {time.strftime("%Y")}
    removed = []
    for b in data.get("content") or []:
        t = pt_text(b)
        if not t.strip():
            continue
        sents = re.split(r"(?<=[.!?])\s+", t)
        keep = []
        for s in sents:
            ys = gate.years_in(s)
            if ys and (ys - allowed):
                removed.append(s[:70])
                continue
            keep.append(s)
        if len(keep) == len(sents):
            continue
        new = re.sub(r"[ \u00a0]{2,}", " ", " ".join(keep)).strip()
        if not new:
            b["_drop"] = True
            continue
        kids = b.get("children") or []
        key = (kids[0].get("_key") if kids else None) or "k0"
        b["children"] = [{"_type": "span", "_key": key, "text": new, "marks": []}]
    data["content"] = [b for b in (data.get("content") or []) if not b.get("_drop")]
    return removed


def source_text_by_link(links):
    """본문 링크 중 D1 news.link 와 일치하는 기사의 원문 텍스트를 찾는다."""
    from pipeline.infra.d1_client import d1_query
    for u in links:
        if not u or 'aikorea24.kr' in u:
            continue
        rows = d1_query("SELECT title, original_title, description FROM news WHERE link = '%s' LIMIT 1"
                        % u.replace("'", "''"))
        if rows:
            r = rows[0]
            return "\n".join(x for x in (r.get("title"), r.get("original_title"),
                                         r.get("description")) if x)
    return ""


def all_links(data):
    out = []
    for b in data.get("content") or []:
        for m in b.get("markDefs") or []:
            if isinstance(m, dict) and m.get("href"):
                out.append(m["href"])
    return out


def fix_reference_section(data):
    """'참고 자료' 섹션에서 **링크가 실제로 걸리지 않은** 항목을 삭제한다.

    사용자 규칙(2026-11-06): "링크를 못 넣을 경우 참고자료를 언급하지 말아줘."
    """
    blocks = data.get("content") or []
    start = None
    for i, b in enumerate(blocks):
        if re.match(r"^참고\s*자료$", pt_text(b).strip()) and (b.get("style") or "").startswith("h"):
            start = i
            break
    if start is None:
        return 0
    removed, keep, rest = 0, blocks[:start + 1], blocks[start + 1:]
    idx = 0
    while idx < len(rest):
        b = rest[idx]
        if (b.get("style") or "normal").startswith("h"):
            keep.extend(rest[idx:])          # 섹션 종료 — 이후 블록은 그대로
            break
        text = pt_text(b).strip()
        if text:
            defs = {m.get("_key") for m in (b.get("markDefs") or []) if m.get("href")}
            linked = any(defs & set(c.get("marks") or []) for c in (b.get("children") or []))
            if not linked:
                removed += 1
                idx += 1
                continue
        keep.append(b)
        idx += 1
    data["content"] = keep
    return removed


def repair_one(slug, source_text, rules=(), drop_text=(), dry_run=False, verbose=True):
    """글 1건 교정. 반환: (변경여부, 사유/로그 문자열)."""
    it = ep.get_post(slug)
    item = (it or {}).get("item") or {}
    if not item:
        return False, "글 없음"
    data = json.loads(json.dumps(item.get("data") or {}, ensure_ascii=False))
    before = pt_to_md(data)
    links = strip_junk_links(data)
    txt = strip_junk_text(data, drop_text)
    years = generic_ungrounded_repair(data, source_text) if source_text.strip() else []
    restored = restore_dangling_links(data)
    refs = fix_reference_section(data)
    changed_blocks = apply_text_replaces(data, rules) if rules else []
    ex = fix_excerpt(data, rules) if rules else False
    after = pt_to_md(data)
    if verbose and (links or txt or years or changed_blocks or ex or restored or refs):
        print("   제거링크=%d 제거텍스트=%d 연도문장=%d 링크복원=%d 참고자료정리=%d 치환=%d excerpt=%s"
              % (len(links), len(txt), len(years), restored, refs, len(changed_blocks), ex))
        for y in years[:3]:
            print("     - %s" % y[:80])
    if after == before and not (links or txt or years or changed_blocks or ex or restored or refs):
        return False, "변경 없음"
    remaining = (gate.date_grounding_issues(after, source_text) + gate.junk_link_issues(after)
                 + gate.reference_link_issues(after))
    if remaining:
        return False, "교정 후에도 미달 %d건: %s" % (len(remaining), remaining[0][:80])
    if dry_run:
        return True, "[dry-run] 변경 예정"
    st, body = rest("PUT", "/_emdash/api/content/posts/%s" % item.get("id"),
                    {"collection": "posts", "id": item.get("id"), "data": data,
                     "_rev": it.get("_rev")})
    if st not in (200, 201):
        return False, "PUT 실패 http=%s" % st
    st2, _ = rest("POST", "/_emdash/api/content/posts/%s/publish" % item.get("id"), {})
    return st2 in (200, 201), "PUT %s / publish %s" % (st, st2)


def sweep(limit=40, dry_run=False):
    """최근 글을 원문과 대조해 오염(원문 밖 연도·광고 링크)을 일괄 교정한다.

    최적화: ① 모든 글을 먼저 읽어 '의심'(2026년 외 연도 또는 정크 링크)만 추린 뒤,
    ② 그 글들의 원문 링크를 **D1 한 번**으로 조회해 ③ 해당 글만 교정한다.
    """
    import urllib.request
    base = os.environ.get("EMDASH_BASE", "https://emdash.aikorea24.kr").rstrip("/")
    req = urllib.request.Request(base + "/sitemap.xml", headers={"User-Agent": "Mozilla/5.0"})
    xml = urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "ignore")
    posts = []
    for blk in re.findall(r"<url>(.*?)</url>", xml, re.S):
        loc = re.search(r"<loc>([^<]+)</loc>", blk)
        lm = re.search(r"<lastmod>([^<]+)</lastmod>", blk)
        if loc and "/posts/" in loc.group(1):
            posts.append(((lm.group(1) if lm else ""), loc.group(1)))
    posts.sort(reverse=True)
    slugs = [u.split("/posts/")[-1] for _, u in posts[:limit]]
    print("스윕 대상 %d건 (최신순) — 의심 글 선별 중" % len(slugs))

    suspicious = []
    for s in slugs:
        it = ep.get_post(s)
        item = (it or {}).get("item") or {}
        data = item.get("data") or {}
        md = pt_to_md(data)
        years = gate.years_in(md) - {time.strftime("%Y")}
        junk = gate.junk_link_issues(md)
        refs = gate.reference_link_issues(md)
        if years or junk or refs:
            suspicious.append((s, sorted(years), bool(junk)))
    print("의심 글 %d건: %s" % (len(suspicious), ", ".join(x[0][:24] for x in suspicious[:6])))

    src_map = {}
    if suspicious:
        from pipeline.infra.d1_client import d1_query
        links = []
        metas = {}
        for s, _y, _j in suspicious:
            it = ep.get_post(s)
            ls = all_links(((it or {}).get("item") or {}).get("data") or {})
            metas[s] = ls
            links.extend(u for u in ls if u and 'aikorea24.kr' not in u)
        if links:
            in_sql = ", ".join("'%s'" % u.replace("'", "''") for u in set(links))
            rows = d1_query("SELECT link, title, original_title, description FROM news "
                            "WHERE link IN (%s)" % in_sql)
            by_link = {r["link"]: r for r in rows}
            for s, ls in metas.items():
                for u in ls:
                    r = by_link.get(u)
                    if r:
                        src_map[s] = "\n".join(x for x in (r.get("title"), r.get("original_title"),
                                                           r.get("description")) if x)
                        break

    fixed = skipped = failed = 0
    for s, _years, _junk in suspicious:
        src = src_map.get(s, "")
        if not src.strip():
            skipped += 1
            print("  · %-44s 원문 미매칭 — 건너뜀" % s[:44])
            continue
        changed, note = repair_one(s, src, dry_run=dry_run, verbose=False)
        if changed:
            fixed += 1
            print("  ✅ %-44s %s" % (s[:44], note))
        else:
            failed += 1
            print("  ⛔ %-44s %s" % (s[:44], note[:90]))
    print("\n스윕 결과: 교정 %d / 원문미매칭 %d / 실패·정상 %d (대상 %d)"
          % (fixed, skipped, failed, len(slugs)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--sweep", action="store_true", help="최근 글 일괄 교정(원문 대조)")
    ap.add_argument("--limit", type=int, default=40, help="스윕 대상 글 수")
    args = ap.parse_args()
    if args.sweep:
        sweep(limit=args.limit, dry_run=args.dry_run)
        return

    for slug, spec in REPAIRS.items():
        print("\n=== %s" % slug[:60])
        it = ep.get_post(slug)
        item = (it or {}).get("item") or {}
        if not item:
            print("  ! 글을 찾지 못함 — 건너뜀")
            continue
        data = json.loads(json.dumps(item.get("data") or {}, ensure_ascii=False))
        src = source_text_for(spec["news_id"])

        before_md = pt_to_md(data)
        before = gate.date_grounding_issues(before_md, src) + gate.junk_link_issues(before_md)

        removed = strip_junk_links(data)
        removed_txt = strip_junk_text(data, spec.get("drop_text", ()))
        removed_year = generic_ungrounded_repair(data, src)
        changed = apply_text_replaces(data, spec["replace"])
        ex_fixed = fix_excerpt(data, spec["replace"])

        after_md = pt_to_md(data)
        after = gate.date_grounding_issues(after_md, src) + gate.junk_link_issues(after_md)

        print("  제거 링크: %s" % (", ".join(u[:55] for u in removed) or "없음"))
        print("  제거 텍스트 블록/문장: %s" % (" | ".join(removed_txt[:3]) or "없음"))
        print("  원문 밖 연도 문장 삭제: %d" % len(removed_year))
        print("  치환 블록: %d / excerpt 수정: %s" % (len(changed), ex_fixed))
        for b, a in changed:
            print("    · %r → %r" % (b, a))
        print("  게이트 before=%d after=%d" % (len(before), len(after)))
        for i in after:
            print("    ! 잔여: %s" % i[:100])
        if after:
            print("  ⛔ 교정 후에도 미달 — PUT 하지 않음")
            continue
        if args.dry_run:
            print("  [dry-run] PUT 생략")
            continue

        st, body = rest("PUT", "/_emdash/api/content/posts/%s" % item.get("id"),
                        {"collection": "posts", "id": item.get("id"), "data": data,
                         "_rev": it.get("_rev")})
        if st not in (200, 201):
            print("  ! PUT 실패 http=%s %s" % (st, str(body)[:120]))
            continue
        st2, body2 = rest("POST", "/_emdash/api/content/posts/%s/publish" % item.get("id"), {})
        print("  ✅ PUT %s / publish %s → %s/posts/%s"
              % (st, st2, ep.BASE, item.get("slug") or slug))


if __name__ == "__main__":
    main()
