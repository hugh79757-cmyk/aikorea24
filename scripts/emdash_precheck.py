#!/usr/bin/env python3
"""EmDash 발행 전 게이트 — 규칙 준수를 사람/모델에 맡기지 않고 코드로 막는다.

실패하면 exit 3 (발행 금지). 검사 대상은 라이브 HTML 이 아니라 **발행할 마크다운 본문**.

사용:
    python3 scripts/emdash_precheck.py /tmp/my-post.md
    python3 scripts/emdash_precheck.py /tmp/my-post.md --publish <slug> "<제목>" ["<excerpt>"]
    python3 scripts/emdash_precheck.py --selftest
"""
import re
import sys

MIN_CHARS = 3000      # 사실 밀도 하한 (groq 재작성본 3,447자 / 이전 얇은 판 3,054자 → 표·수치 없으면 못 넘긴다)
MIN_LINKS = 3         # 외부 링크
MIN_TABLES = 1        # 비교·한도·요금은 표로
INTERNAL_TERMS = ["firecrawl", "dev.vars", ".env.common", "launchd"]  # 독자에게 노출 금지 (실제 누출 사례)

# AIK24-BLOG-02 (2026-10-19): 입력이 EmDash PT JSON 이면 이 게이트는 무의미하다.
# 2026-10-18 사고: PT JSON(={"_type":"block",...}) 을 그대로 검사하면 마크다운 문법이 하나도
# 매칭되지 않아 "본문 0자·링크 0개"로만 걸리거나, 역으로 사람이 눈으로 보는 통과와 무관한
# 결과가 나온다. 게이트는 항상 **마크다운 본문**에 대고 돌린다.
_PT_JSON_MARKERS = ('"_type"', '"markDefs"', '"tableCell"', '"portabletext"', '"_key"')


def strip_frontmatter(text: str) -> str:
    """frontmatter(--- 로 감싼 머리말)를 제거한 본문을 돌려준다. 없으면 입력 그대로.

    발행 대기 마크다운(_EMDASH_PENDING[*]["md"])이나 .md 파일을 그대로 check() 에 넘기면
    frontmatter 의 title/description 이 길이에 섞여 통과로 오인된다. 본문만 떼어낸다.
    """
    m = re.match(r"\A---[ \t]*\n.*?\n---[ \t]*\n", text, re.S)
    return text[m.end():] if m else text


def looks_like_pt_json(text: str) -> bool:
    """EmDash Portable Text JSON(또는 그 문자열)인지 판정."""
    s = text.lstrip()
    if not s or s[0] not in "{[":
        return False
    head = s[:600]
    return sum(1 for mk in _PT_JSON_MARKERS if mk in head) >= 1


def check(md: str) -> list:
    issues = []
    if looks_like_pt_json(md):
        return ["입력이 EmDash PT JSON 이다 → 마크다운 본문을 넘겨라 (PT JSON 검사는 통과/실패가 무의미)"]
    if re.search(r"^#\s", md, re.M):
        issues.append("본문에 H1(`# `) 있음 → 제목은 발행 API 의 title 로만 (라이브 <h1> 중복)")
    if not re.search(r"^##\s*마무리", md, re.M):
        issues.append("`## 마무리 — …` 소제목 없음 → 실행 체크리스트로 끝낸다")

    # 마크다운 링크와 생 URL 둘 다 센다 (렌더러가 생 URL 도 자동 링크한다)
    links = set(re.findall(r"\]\((https?://[^)\s]+)\)", md)) | set(re.findall(r"(?<!\()(https?://[^\s)\]]+)", md))
    ext = sorted(l for l in links if "aikorea24.kr" not in l)
    if len(ext) < MIN_LINKS:
        issues.append(f"외부 링크 {len(ext)}개 (최소 {MIN_LINKS}) → 출처·발급·설치 페이지를 링크로")

    tables = len(re.findall(r"^\|\s*-{2,}", md, re.M))
    if tables < MIN_TABLES:
        issues.append(f"표 {tables}개 (최소 {MIN_TABLES}) → 수치·한도·비교는 표로")

    if md.count("```") % 2:
        issues.append("코드펜스 ``` 개수가 홀수 → 블록이 다음 문단을 삼킨다")

    if len(md) < MIN_CHARS:
        issues.append(f"본문 {len(md)}자 (최소 {MIN_CHARS}) → 사실을 더 모아라, 말로 늘리지 말고")

    for term in INTERNAL_TERMS:
        if term.lower() in md.lower():
            issues.append(f"내부 용어 노출: `{term}` → 삭제")

    return issues


def _load(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def selftest():
    good = "## 도입\n" + "가" * 3100 + "\n## 마무리 — 오늘\n| a |\n|---|\n| b |\n" + \
        "](https://a.com) ](https://b.com) https://c.com\n"
    thin = "## 도입\n짧다\n"
    assert not check(good), check(good)
    bad = check(thin)
    assert len(bad) >= 4, bad
    # AIK24-BLOG-02: PT JSON 입력은 무의미한 검사 대신 즉시 차단
    pt = check('{"_type":"block","markDefs":[],"children":[]}')
    assert len(pt) == 1 and "PT JSON" in pt[0], pt
    # frontmatter 는 길이에 섞이지 않아야 한다 (본문만 검사)
    fm = '---\ntitle: "%s"\ndraft: false\n---\n\n%s' % ("가" * 3000, thin)
    assert len(check(strip_frontmatter(fm))) == len(bad), check(strip_frontmatter(fm))
    print("selftest OK —", len(bad), "개 결함 검출:", *bad, sep="\n  ")


def main(argv):
    if "--selftest" in argv:
        selftest()
        return 0
    if len(argv) < 2 or argv[1].startswith("--"):
        print('사용법: emdash_precheck.py <md경로> [--publish <slug> "<제목>" "<excerpt>"] [--selftest]')
        return 2
    path = argv[1]
    md = _load(path)
    issues = check(md)
    if issues:
        print(f"❌ 발행 금지 — {path} 에서 {len(issues)}건:")
        for i in issues:
            print("  -", i)
        return 3
    print(f"✅ 게이트 통과 — {len(md)}자")

    if "--publish" in argv:
        i = argv.index("--publish")
        slug, title = argv[i + 1], argv[i + 2]
        excerpt = argv[i + 3] if len(argv) > i + 3 else None
        sys.path.insert(0, __file__.rsplit("/", 1)[0])
        from emdash_publish import upsert_post
        print("발행:", upsert_post(slug, title, md, excerpt=excerpt))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
