#!/usr/bin/env python3
"""AIK24-BLOG-02 (2026-10-19) — 보류 초안 복구 도구.

배경
----
1차/2차 게이트가 발행을 보류한 초안은 `scripts/logs/rejected/` 에 남는다. 보류 사유를 보면
대부분이 '표 0개' 처럼 **국소 결함 하나**다(2026-10-19 09:30 실행 보류 2건 모두 그러했다).
글 전체를 다시 쓰지 않고 그 결함만 고쳐서 발행하면 볼륨이 죽지 않는다.

동작 (초안 1건당)
----------------
1. 결정적 수리(표 구분선·앞머리 H1) 후 게이트 재검사 → 통과하면 발행.
2. 잔여 결함이 **표뿐**이면 → '본문에 이미 있는 수치만 모아 표 1개 추가' 교정 1회 → 재검사 → 통과 시 발행.
   (새 사실·수치를 만들지 않는다. 본문을 지우지도 않는다.)
3. 그 외(본문 분량 미달·링크 부족 등)는 손대지 않고 사유만 보고한다 — 사실을 지어내지 않기 위해서다.

안전장치
--------
- 기본은 **드라이런**이다. 실제 발행은 `--publish` 를 줘야 한다.
- EmDash 라이브 제목과 대조해 이미 발행된 글은 건너뛴다(중복 발행 방지).
- 발행 후 3차 검증(라이브 본문 대조)까지 수행한다.

사용
----
    python3 scripts/republish_held.py                 # 오늘 보류건 드라이런
    python3 scripts/republish_held.py --publish       # 실제 발행
    python3 scripts/republish_held.py --since 2026-10-18 --limit 5 --publish
"""
from __future__ import annotations

import argparse
import datetime
import glob
import json
import os
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import blog_quality_gate as g  # noqa: E402

REJECTED_DIR = os.path.join(_HERE, "logs", "rejected")

# hold() 는 파이프라인의 today_str 과 달리 머신 로컬 시각(datetime.now())으로 파일명 스탬프를
# 찍는다. 이 머신은 +07, 파이프라인 기준은 KST(+09) 라서 두 값의 날짜가 2시간 창에서 어긋난다
# (2026-10-19 실측: 스탬프 093045 는 KST 11:30). 복구 대상 판정은 KST 날짜로 정규화한다 —
# 그러지 않으면 예약 시각이 아닌 실행에서 보류 글이 조용히 복구되지 않는다.
KST = datetime.timezone(datetime.timedelta(hours=9))
_STAMP_RE = re.compile(r"(\d{8})-(\d{6})")


def _kst_date_of(stem: str) -> str:
    """보류 파일명 스탬프(YYYYMMDD-HHMMSS, 머신 로컬) → KST 날짜(YYYY-MM-DD).

    파싱 실패 시 "" 를 돌려주고 호출측은 그 항목을 제외하지 않는다(복구 시도 우선).
    """
    m = _STAMP_RE.match(stem or "")
    if not m:
        return ""
    try:
        dt = datetime.datetime.strptime(m.group(1) + m.group(2), "%Y%m%d%H%M%S")
    except ValueError:
        return ""
    return dt.astimezone(KST).strftime("%Y-%m-%d")

_TABLE_FIX_PROMPT = """아래는 한국어 기술 블로그 글이다. 발행 검사에서 **표가 없다**는 이유로 미달됐다.

할 일: 본문에 **이미 들어 있는 수치·요금·한도·비교**만 모아서 마크다운 표 1개를 글 중간에 추가하라.

절대 규칙:
- 새로운 사실·수치·출처를 만들어내지 마라. 본문에 없는 숫자를 쓰면 안 된다.
- 기존 문장을 삭제하거나 줄이지 마라. 표는 **추가**만 한다.
- 표 형식: `| 항목 | 값 |` 다음 줄에 `| --- | --- |` 구분선, 그 다음 데이터 행들.
- 본문에 숫자가 정말 하나도 없으면, '무엇을 비교할 수 있는지'를 정리한 항목 표를 만들되 값 칸에는 본문의 서술을 그대로 요약해 넣어라.
- 그 외 결함(없음)은 건드리지 마라.

출력: `TITLE: 제목` 한 줄 + `---` + **고친 마크다운 본문 전체**(일부만 보내지 말 것).

[본문]
"""


def _parse_title_body(text: str):
    m = re.match(r"\s*(?:TITLE|제목)\s*[:：]\s*(.+?)\s*\n+[-=]{3,}\s*\n", text or "")
    if m:
        return m.group(1).strip().strip('"'), text[m.end():].strip()
    return "", (text or "").strip()


def _split_md(md: str):
    m = g._FM_RE.match(md or "")
    if not m:
        return {}, (md or "")
    import yaml
    try:
        meta = yaml.safe_load(m.group(0).replace("---", "", 2)) or {}
    except Exception:
        meta = {}
    return meta, (md or "")[m.end():]


def norm_title(t: str) -> str:
    """제목 비교용 정규화 — 공백·구두점·대소문자 차이를 없앤다."""
    return re.sub(r"[^0-9a-z가-힣]", "", (t or "").casefold())


def _live_titles(max_pages: int = 40):
    """EmDash 라이브 글 제목 집합. **조회 실패 시 None** 을 돌려준다(중복 검사 불가 = 발행 금지).

    2026-10-19 함정: `?limit=200` 은 http=400 인데 `api()` 가 예외를 던지지 않아 조용히
    빈 목록이 됐고, 그 상태로 발행하면 이미 있는 글과 중복된 글이 생길 수 있었다.
    그래서 ① 100건씩 커서 페이지네이션 ② 실패·0건이면 None(fail-closed) 로 바꿨다.
    """
    try:
        import emdash_publish as ep
        os.environ["EMDASH_PAT"] = ep.get_pat() or ""
        from emdash04_migrate import api
        out, cursor, pages = set(), "", 0
        while pages < max_pages:
            q = "/_emdash/api/content/posts?limit=100" + ("&cursor=%s" % cursor if cursor else "")
            st, d = api(q, "GET")
            if st != 200:
                print("  ⚠️ EmDash 목록 조회 실패 http=%s — 중복 검사 불가" % st)
                return None
            data = (d or {}).get("data") or {}
            items = data.get("items") or []
            for i in items:
                t = ((i.get("data") or {}).get("title") or "").strip()
                if t:
                    out.add(t)
            cursor = data.get("nextCursor") or ""
            pages += 1
            if not cursor or not items:
                break
        if not out:
            print("  ⚠️ EmDash 목록이 0건 — 중복 검사 불가")
            return None
        print("  EmDash 라이브 글 %d건 확인" % len(out))
        return out
    except Exception as e:
        print("  ⚠️ EmDash 목록 조회 예외: %s: %s — 중복 검사 불가" % (type(e).__name__, e))
        return None


def _is_duplicate(title: str, live_titles) -> str:
    """이미 발행된 글인가. 정규화 제목의 포함관계까지 본다(제목 뒤에 수식이 붙은 경우)."""
    if not live_titles:
        return ""
    want = norm_title(title)
    if not want:
        return ""
    for lt in live_titles:
        have = norm_title(lt)
        if not have:
            continue
        if want == have:
            return lt
        if len(want) >= 12 and len(have) >= 12 and (want in have or have in want):
            return lt
    return ""


def _publish(title: str, body: str, meta: dict, dump_dir: str = "") -> str:
    import emdash_publish as ep
    if dump_dir:
        try:
            os.makedirs(dump_dir, exist_ok=True)
            safe = re.sub(r"[^\w가-힣.-]+", "-", title)[:60].strip("-")
            with open(os.path.join(dump_dir, "%s.md" % safe), "w", encoding="utf-8") as f:
                f.write(body)
            print("     저장: %s/%s.md" % (dump_dir, safe))
        except Exception as e:
            print("     ⚠️ 덤프 저장 실패: %s" % e)
    url = ep.publish_post(
        title, body,
        excerpt=meta.get("description"),
        featured_image=meta.get("image"),
        published_at=meta.get("date"),
    )
    if not url:
        return ""
    try:
        g.verify_published(url, expected_body=body, title=title)
    except Exception as e:
        print("  ⚠️ 3차 검증 예외: %s: %s" % (type(e).__name__, e))
    return url


def _only_table_issues(issues: list) -> bool:
    return bool(issues) and all(i.startswith("표 ") for i in issues)


def _preserved(old_body: str, new_body: str):
    """원문 문단이 새 본문에 남아 있는 비율. 표 추가 교정이 본문을 갈아엎었는지 본다."""
    paras = [p.strip() for p in (old_body or "").split("\n")
             if len(p.strip()) >= 30 and not p.strip().startswith("|") and not p.strip().startswith("#")]
    if not paras:
        return 1.0, []
    missing = [p for p in paras if p not in new_body]
    return (len(paras) - len(missing)) / len(paras), missing


def _try_candidate(path: str, title: str, live_titles, do_publish: bool, force: bool = False,
                   dump_dir: str = ""):
    """초안 1건 복구 시도. Returns: ("published"|"clean"|"fixed"|"skip", 설명, url)"""
    dup = "" if force else _is_duplicate(title, live_titles)
    if dup:
        # 이미 발행된 글 → LLM 호출 없이 즉시 종료 (2026-10-19: 재실행 시 낭비 방지)
        return "skip", "이미 발행된 글(중복) — %s" % dup[:40], ""

    md = open(path, encoding="utf-8").read()
    meta, _ = _split_md(md)
    fixed_md, fixes = g.repair_pending(md)
    body = g.body_of(fixed_md)
    if fixes:
        print("     🛠 수리: %s" % ", ".join(fixes))

    issues = g.screen_extended(body)
    if not issues:
        line = "%d자 / 인용 %d개" % (len(body), len(g.citation_links(body)))
        if dup:
            return "skip", "이미 발행된 글(중복) — %s (%s)" % (dup[:40], line), ""
        if not do_publish:
            return "clean", "드라이런 — 발행 가능 (%s)" % line, ""
        url = _publish(title, body, meta, dump_dir)
        return ("published" if url else "skip"), ("발행됨" if url else "발행 실패"), url

    if _only_table_issues(issues):
        print("     🔧 표 추가 교정 1회 (사실 추가 없이 재구성)")
        out = g.strong_completion(_TABLE_FIX_PROMPT + body, max_tokens=7000, temperature=0.4)
        _t, new_body = _parse_title_body(out or "")
        if not new_body:
            return "skip", "표 교정 생성 실패(빈 응답)", ""
        new_md, _fx = g.repair_markdown(new_body)
        ratio, missing = _preserved(body, new_md)
        print("     ↳ 본문 보존율 %.0f%% (누락 문단 %d개)" % (ratio * 100, len(missing)))
        if ratio < 0.9:
            # 본문을 갈아엎었다 = 사실이 바뀌었을 수 있다. 복구하지 않고 사람이 볼 수 있게 남긴다.
            return "skip", "표 교정이 본문을 갈아엎음(보존율 %.0f%%) → 수동 확인 필요" % (ratio * 100), ""
        issues2 = g.screen_extended(new_md)
        if issues2:
            return "skip", "표 교정 후에도 미달: %s" % " / ".join(
                i.split("→")[0].strip()[:32] for i in issues2), ""
        if dup:
            return "skip", "이미 발행된 글(중복) — %s" % dup[:40], ""
        if not do_publish:
            return "fixed", "드라이런 — 표 교정 후 발행 가능 (%d자 / 인용 %d개)" % (
                len(new_md), len(g.citation_links(new_md))), ""
        url = _publish(title, new_md, meta, dump_dir)
        return ("published" if url else "skip"), ("표 교정 후 발행됨" if url else "발행 실패"), url

    return "skip", "자동 복구 불가: %s" % " / ".join(
        i.split("→")[0].strip()[:32] for i in issues), ""


def recover_since(since: str, do_publish: bool = True, limit: int = 5, dump_dir: str = "",
                  force: bool = False) -> dict:
    """`since`(YYYY-MM-DD) 이후 보류건을 복구한다. 파이프라인에서도 호출한다.

    Returns: {"published": n, "clean": n, "fixed": n, "skip": n, "urls": [(제목, 발행URL), ...]}
    `urls` 는 호출측이 D1 `deep_dive_url` 을 연결하는 데 쓴다(연결하지 않으면 다음 실행이
    같은 기사를 다시 생성해 **중복 발행**된다 — 2026-10-19 실측).
    """
    metas = sorted(glob.glob(os.path.join(REJECTED_DIR, "*.json")))
    done = {"published": 0, "clean": 0, "fixed": 0, "skip": 0, "urls": []}
    if not metas:
        return done
    print("모드=%s" % ("PUBLISH" if do_publish else "DRY-RUN"))
    live = _live_titles()
    if live is None and do_publish and not force:
        print("⛔ 중복 검사(EmDash 목록)를 못 해서 발행을 중단한다. 원인 해결 후 다시 실행하거나 "
              "(정말 필요하면) --force 를 쓴다.")
        return done

    for jp in metas:
        rec = json.load(open(jp, encoding="utf-8"))
        kst_date = _kst_date_of(os.path.basename(jp))
        if kst_date and kst_date < since:
            continue
        if sum(done[k] for k in ("published", "clean", "fixed", "skip")) >= limit:
            break
        title = (rec.get("title") or "").strip()
        base = jp[:-5]
        cands = [p for p in (base + ".md", base + "-retry.md") if os.path.exists(p)]
        if not cands:
            continue
        print("· %s" % title[:66])
        print("   보류 사유: %s" % (rec.get("reason") or ""))
        result = ("skip", "후보 없음", "")
        for p in cands:
            kind, why, url = _try_candidate(p, title, live, do_publish, force, dump_dir)
            print("   [%s] %s → %s" % (
                "재시도본" if p.endswith("-retry.md") else "1차초안",
                why, url or "-"))
            result = (kind, why, url)
            if kind in ("published", "clean", "fixed"):
                break
        done[result[0]] = done.get(result[0], 0) + 1
        if result[2]:
            live.add(title)
            done["urls"].append((title, result[2]))
            with open(os.path.join(REJECTED_DIR, "_recovered.jsonl"), "a", encoding="utf-8") as f:
                f.write(json.dumps({"title": title, "url": result[2],
                                    "at": datetime.datetime.now().isoformat(timespec="seconds")},
                                   ensure_ascii=False) + "\n")
        print()
    print("=== 복구 결과: 발행 %d / 발행가능(드라이런) %d / 교정후가능 %d / 복구불가 %d ==="
          % (done["published"], done["clean"], done["fixed"], done["skip"]))
    if done["urls"]:
        print("주의: 복구 발행분은 D1 briefing_items.deep_dive_url 연결이 필요하다(미연결 시 다음 실행이 "
              "같은 기사를 다시 생성해 중복 발행). 파이프라인 5d 경로는 자동 연결하지만, 수동 실행 시에는 "
              "연결 여부를 확인할 것.")
    return done


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", default=datetime.datetime.now(KST).date().isoformat(),
                    help="이 날짜 이후 보류건만 (KST 기준)")
    ap.add_argument("--limit", type=int, default=10)
    ap.add_argument("--publish", action="store_true", help="실제 발행 (기본은 드라이런)")
    ap.add_argument("--force", action="store_true", help="중복 검사 무시 (권장하지 않음)")
    ap.add_argument("--dump-dir", default="", help="발행한 본문을 이 폴더에 저장(감사용)")
    args = ap.parse_args()
    recover_since(args.since, args.publish, args.limit, args.dump_dir, args.force)


if __name__ == "__main__":
    main()
