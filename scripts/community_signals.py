#!/usr/bin/env python3
"""OpenCode 커뮤니티 검증 신호 (AIK24-PIPE-03 §4-2).

커뮤니티는 **선정 소스가 아니라 검증용**이다. 무료 모델 후보마다 "실사용자가
이 모델을 무료로 썼다고 언급했는가"만 확인해 가산점으로 준다.

2026-10-13 실측 상태:
  GitHub : sst/opencode 은 301 로 `anomalyco/opencode`(별 21.3만)로 이전했다.
           Discussions 는 미사용(has_discussions=false) → 이슈만 수집한다.
           무인증 검색 API는 분당 10회 한도라 issues REST 를 직접 쓴다.
  Reddit : r/opencodeCLI/.json 은 이 IP 에서 403 차단. /.rss 는 200 이나
           재요청 시 429 가 난다. → 실패해도 브리핑은 계속 돌아야 하므로
           예외를 밖으로 흘리지 않는다.
           수집(제목·링크)은 유지하되 가산점은 GitHub 이슈 언급(+2)만 준다.
"""

import json
import urllib.request
from xml.etree import ElementTree as ET

UA = {"User-Agent": "aikorea24-briefing/1.0"}
GH_REPO = "anomalyco/opencode"
GH_ISSUES = (
    f"https://api.github.com/repos/{GH_REPO}/issues"
    "?state=all&per_page=50&sort=created&direction=desc"
)
REDDIT_RSS = "https://www.reddit.com/r/opencodeCLI/.rss"
ATOM = "{http://www.w3.org/2005/Atom}"

GH_BONUS = 2  # GitHub 이슈 1건 이상 언급 (유일한 가산점)


def _get(url, timeout=25):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def github_posts(limit=50):
    """최근 이슈 본문. PR 은 제외한다. 실패 시 빈 리스트."""
    try:
        data = json.loads(_get(GH_ISSUES))
        if not isinstance(data, list):
            return []
    except Exception as e:  # noqa: BLE001 — 커뮤니티 실패가 브리핑을 막지 않게
        print(f"  [warn] GitHub 수집 실패: {e}")
        return []
    out = []
    for it in data[:limit]:
        if not isinstance(it, dict) or "pull_request" in it:
            continue
        out.append({
            "title": it.get("title") or "",
            "body": (it.get("body") or "")[:1500],
            "url": it.get("html_url") or "",
        })
    return out


def reddit_posts():
    """r/opencodeCLI 최근 글 제목. 실패 시 빈 리스트."""
    try:
        root = ET.fromstring(_get(REDDIT_RSS))
    except Exception as e:  # noqa: BLE001
        print(f"  [warn] Reddit 수집 실패: {e}")
        return []
    out = []
    for entry in root.findall(f"{ATOM}entry"):
        title = (entry.findtext(f"{ATOM}title") or "").strip()
        if not title:
            continue
        url = ""
        for link in entry.findall(f"{ATOM}link"):
            if link.get("rel") == "alternate":
                url = link.get("href") or ""
        out.append({"title": title, "url": url})
    return out


def build_signal_map(model_ids):
    """{모델id.lower(): {"gh": n, "rd": n}} — 언급 있는 것만 반환."""
    keys = {str(m).lower() for m in model_ids if m}
    if not keys:
        return {}
    gh, rd = github_posts(), reddit_posts()
    print(f"  [community] GitHub 이슈 {len(gh)}건 · Reddit 글 {len(rd)}건 · 검사 모델 {len(keys)}개")
    sig = {k: {"gh": 0, "rd": 0, "gh_url": "", "rd_url": ""} for k in keys}
    for k in sig:
        for p in gh:
            if k in (p["title"] + " " + p["body"]).lower():
                sig[k]["gh"] += 1
                sig[k]["gh_url"] = sig[k]["gh_url"] or p["url"]
        for p in rd:
            if k in p["title"].lower():
                sig[k]["rd"] += 1
                sig[k]["rd_url"] = sig[k]["rd_url"] or p["url"]
    return {k: v for k, v in sig.items() if v["gh"] or v["rd"]}


def bonus(sig):
    """신호 dict → 가산점."""
    if not sig:
        return 0
    return GH_BONUS if sig.get("gh") else 0


def quote_line(sig):
    """브리핑 코멘트에 붙는 커뮤니티 한 줄."""
    if not sig:
        return ""
    parts = []
    if sig.get("gh"):
        parts.append(f"💬 GitHub {GH_REPO} 이슈 {sig['gh']}건 언급 — 실사용 검증")
    if sig.get("rd"):
        parts.append(f"💬 r/opencodeCLI {sig['rd']}건 언급")
    return " · ".join(parts)


if __name__ == "__main__":
    import sys
    sig = build_signal_map(sys.argv[1:] or ["ling-3.1-flash-free", "glm-5.3-flash"])
    print(json.dumps(sig, ensure_ascii=False, indent=2))
    print("가산점:", {k: bonus(v) for k, v in sig.items()})