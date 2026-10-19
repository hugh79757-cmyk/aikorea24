#!/usr/bin/env python3
"""AIK24-BLOG-02 (2026-10-19) — 자동 발행 파이프라인용 품질 게이트 (3중 방어).

배경
----
`emdash_precheck.py` 는 2026-10-17 에 만들어졌지만 **아무도 호출하지 않았다.** 그래서
`blog_draft_generator.py` 는 게이트 없이 EmDash 로 바로 발행했고, 대표님이 지적한
`workbuddy에서-deepseek-v41-flash-무료로-쓰는-방법` 같은 글이 그대로 나갔다.
실측(2026-10-18): 최근 발행 30건 중 게이트 통과 6건(20%). 결함은 `외부 링크 0개`(22건),
``## 마무리`` 없음(18건), 3,000자 미만(14건)에 집중 — 사람 눈이 아니라 **배선**의 문제였다.

3중 방어 (AIK24-BLOG-02 2026-10-19 실측으로 형태가 굳었다)
-------------------------------------------------------
- 0차 (결정적 수리, `repair_markdown`): 모델이 **구분선 없이 쓴 표**를 실제 표로 고치고 본문 앞머리
  H1 을 제거한다. LLM 재호출 없이 '렌더링 불가' 결함을 없앤다. (실측: glm 이 13줄 표를 썼지만
  구분선이 없어 게이트가 0개로 세었고, 그 결함 하나로 오늘 발행 2건이 보류됐다)
- 1차 (생성 직후, `blog_draft_generator._gate_and_fix`): 수리 후 검사. 미달이면 **초안을 살려 고치는**
  교정을 최대 2회(지정 모델) 수행하고, 그래도 미달이면 그 글만 보류한다(파이프라인은 다음 글로 계속).
  근거: 같은 모델에 '처음부터 다시' 시키면 길이가 오히려 줄었고(2,211→2,381자), 초안 수정 + 모델
  지정으로는 3,417~4,026자까지 올라 통과했다.
- 2차 (발행 직전, `_publish_generated_to_emdash` 안): 수리 + 재검사. 미달이면 그 글만 보류.
- 3차 (발행 직후): 라이브 HTML 을 읽어 본문·제목이 실제로 반영됐는지 검증한다.
  동시 편집자가 낡은 사본을 저장해 발행본을 되돌리는 사고(2026-10-18 실측)를 잡기 위한 것.

게이트 기준은 `emdash_precheck.check()` **하나만** 쓴다(사본을 만들지 않는다).
"""
from __future__ import annotations

import datetime
import json
import os
import re
import subprocess
import urllib.error
import urllib.parse
import urllib.request

sys_path_added = False
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
    sys_path_added = True

from emdash_precheck import check, strip_frontmatter, MIN_CHARS, MIN_LINKS, MIN_TABLES  # noqa: E402

REJECTED_DIR = os.path.join(_HERE, "logs", "rejected")
_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/155.0.0.0 Safari/537.36")

# 인용 우선순위 (1차 출처·공식 문서). 여기 없어도 아래 차단 목록만 아니면 후보에 넣는다.
_PREFERRED = (
    "openai.com", "anthropic.com", "claude.com", "deepmind.google", "blog.google", "ai.meta.com",
    "huggingface.co", "github.com", "gitlab.com", "nvidia.com", "microsoft.com", "azure.microsoft.com",
    "cloud.google.com", "mistral.ai", "x.ai", "cohere.com", "groq.com", "openrouter.ai", "deepseek.com",
    "api-docs.deepseek.com", "opencode.ai", "sst.dev", "ollama.com", "together.ai", "fireworks.ai",
    "cerebras.ai", "perplexity.ai", "qwen.ai", "moonshot.ai", "z.ai", "zhipuai.cn", "alibabacloud.com",
    "aws.amazon.com", "arxiv.org", "nature.com", "science.org", "ieee.org", "acm.org",
    "techcrunch.com", "theverge.com", "reuters.com", "venturebeat.com", "zdnet.com", "wired.com",
    "arstechnica.com", "theinformation.com", "nikkei.com", "bloomberg.com", "wsj.com", "cnbc.com",
)
# 후보에서 제외 (SNS·공유·단축·집계·광고)
_BLOCKED = (
    "aikorea24.kr", "facebook.com", "instagram.com", "pinterest.", "linkedin.com", "t.co/", "bit.ly",
    "naver.me", "band.us", "kakao.com", "news.google.com", "google.com/url", "google.com/search",
    "doubleclick.net", "googlesyndication.com", "adservice.google", "taboola", "outbrain",
    "twitter.com/intent", "x.com/intent", "facebook.com/sharer", "plus.google.com", "line.me",
    "utm_source=", "utm_medium=", "fbclid=", "gclid=", "javascript:", "mailto:",
    # 2026-10-19 실측(수율 측정): 사이트푸터·광고망·프로필 링크가 후보로 올라와 품질을 떨어뜨렸다.
    "dianomi.com", "cdn-uploads.", "discuss.", "jobs.", "support.", "trust.", "advertise.",
    "apps.apple.com", "play.google.com", "itunes.apple.com", "google.com/preferences", "accounts.google",
    # 자사 계열 (외부 링크로 세지 않는다)
    "rotcha.kr", "informationhot.kr", "techpawz.com",
)

# 경로에 이 문자열이 있으면 인용 가치가 없다 (약관·개인정보·채용·구독 안내)
_PATH_BLOCK = (
    "/privacy", "/terms", "/legal", "/cookie", "/tos", "/policy", "/about", "/contact", "/jobs",
    "/careers", "/press", "/advertise", "/subscribe", "/newsletter", "/rss", "/feed", "/sitemap",
    "/login", "/signup", "/signin", "/signup", "/search", "/tag/", "/category/", "/author/",
    "/user/", "/profile", "/cdn-cgi", "/preferences", "/store/apps", "/npm/", "?share=", "&share=",
)
# 정적 자산 확장자 (마지막 경로 조각 기준) — 페이지가 아니라 번들/이미지
_ASSET_EXT = (".js", ".mjs", ".css", ".json", ".map", ".xml", ".svg", ".woff", ".woff2", ".txt",
              ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".mp4", ".pdf.zip")

_listing_cache: dict = {}

# 실행 1회 동안 보류된 글 수 (main 이 끝날 때 요약 로그로 쓴다)
HOLD_COUNT = 0
HOLDED_TITLES: list = []


# ---------------------------------------------------------------- 결정적 수리
# LLM 초안의 '렌더링 불가' 결함을 내용 변경 없이 고친다. 교정 LLM 호출을 아끼고,
# 교정으로도 안 고쳐지는 습관적 결함(구분선 없는 표)을 확실히 없앤다.
_FM_RE = re.compile(r"\A---[ \t]*\n.*?\n---[ \t]*\n", re.S)


def _pipe_cols(line: str) -> int:
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|"):
        s = s[:-1]
    return len(s.split("|"))


def _is_pipe_row(line: str) -> bool:
    s = line.strip()
    return s.startswith("|") and s.endswith("|") and len(s) > 2


def repair_markdown(body: str) -> tuple:
    """렌더링 불가 결함을 결정적으로 고친다 (문장·수치·사실은 건드리지 않는다).

    ① 구분선 없는 표 → 첫 행 뒤에 `| --- | --- |` 를 넣어 **실제 표로** 만든다.
       (2026-10-19 실측: glm-4.5-flash 가 13줄짜리 표를 썼지만 구분선이 없어 게이트가 0개로 셌고,
        EmDash 렌더러에서도 표가 아니라 문단으로 나온다)
    ② 본문 맨 앞 H1(`# 제목`) 제거 — 제목은 발행 API 의 title 로만 쓴다.
    ③ 코드펜스 안은 건드리지 않는다.

    Returns: (고친 본문, 고친 항목 설명 리스트)
    """
    fixes = []
    body = body or ""

    # ② 앞머리 H1 제거 (문서 맨 앞의 것만 — 본문 중간 H1 은 사람이 판단할 문제)
    m = re.match(r"\A\s*(#\s+[^\n]+\n+)+", body)
    if m:
        body = body[m.end():]
        fixes.append("앞머리 H1 제거")

    # ① 구분선 없는 표 보수 (코드펜스 밖만)
    segs = re.split(r"(```.*?```)", body, flags=re.S)
    n_fixed = 0
    for si, seg in enumerate(segs):
        if seg.startswith("```"):
            continue
        lines = seg.split("\n")
        out, i = [], 0
        while i < len(lines):
            if not _is_pipe_row(lines[i]):
                out.append(lines[i])
                i += 1
                continue
            j = i
            while j < len(lines) and _is_pipe_row(lines[j]):
                j += 1
            block = lines[i:j]
            cols = _pipe_cols(block[0])
            has_sep = any(re.fullmatch(r"\|[\s:|-]*-{2,}[\s:|-]*\|?", b.strip()) for b in block)
            same_cols = cols >= 2 and all(_pipe_cols(b) == cols for b in block)
            if not has_sep and len(block) >= 2 and same_cols:
                out.append(block[0])
                out.append("| " + " | ".join(["---"] * cols) + " |")
                out.extend(block[1:])
                n_fixed += 1
            else:
                out.extend(block)
            i = j
        segs[si] = "\n".join(out)
    if n_fixed:
        fixes.append("표 구분선 %d개 삽입" % n_fixed)
    return "".join(segs), fixes


def repair_pending(md: str) -> tuple:
    """frontmatter + 본문 md 를 받아 본문만 수리한다. Returns: (md, 고친 항목)."""
    m = _FM_RE.match(md or "")
    fm, body = (m.group(0), (md or "")[m.end():]) if m else ("", md or "")
    nb, fixes = repair_markdown(body)
    return fm + nb, fixes


# ---------------------------------------------------------------- 검사
def body_of(pending_md: str) -> str:
    """발행 대기 md(= frontmatter + 본문) 또는 순수 본문 → 검사용 본문."""
    return strip_frontmatter(pending_md or "").strip()


def screen(text: str) -> list:
    """본문(또는 frontmatter 포함 md)을 게이트에 통과시켜 결함 목록을 돌려준다."""
    return check(body_of(text))


def is_clean(text: str) -> bool:
    return not screen(text)


_URL_TRIM = ".,;:!?)]}\"'’”»`>"


def links_in(md: str) -> list:
    """본문에서 외부 링크(자사 제외)를 뽑는다. 게이트와 같은 규칙.

    2026-10-19 통합 테스트에서 잡힌 두 함정을 반영한다.
    ① 꼬리에 따옴표가 붙은 채 추출되면(`curl …/chat/completions"`) 살아있는 URL 도
       죽은 링크로 오판한다 → URL 끝 문자를 잘라낸다.
    ② HTML 엔티티(`&amp;`)는 실제 URL 과 달라 404 를 유발한다 → 되돌린다.
    """
    links = set(re.findall(r"\]\((https?://[^)\s]+)\)", md)) | \
        set(re.findall(r"(?<!\()(https?://[^\s)\]]+)", md))
    out = []
    for l in sorted(links):
        l = l.replace("&amp;", "&").strip().rstrip(_URL_TRIM)
        low = l.lower()
        if any(b in low for b in ("aikorea24.kr", "rotcha.kr", "informationhot.kr", "techpawz.com")):
            continue
        if l:
            out.append(l)
    return out


def citation_links(md: str) -> list:
    """코드블록·인라인 코드 **밖**의 외부 링크 = 실제 인용.

    curl 예시(`https://api.deepseek.com/v1/chat/completions`)나 환경변수 안내처럼
    코드로 보여주는 URL 은 '출처'가 아니다. 게이트는 문자열 기준으로 세지만(수동 경로
    호환), 자동 경로의 품질 검사는 실제 인용만 센다.
    """
    md2 = re.sub(r"```.*?```", " ", md, flags=re.S)
    md2 = re.sub(r"~~~.*?~~~", " ", md2, flags=re.S)
    md2 = re.sub(r"`[^`\n]*`", " ", md2)       # 인라인 코드(예시 URL 포함) 제거
    return links_in(md2)


def dead_links(md: str, limit: int = 8, timeout: float = 8.0) -> list:
    """본문 링크가 실제로 열리는지 확인한다 → 죽은 링크 목록.

    LLM 이 '공식 문서'라고 자신 있게 적은 URL 이 404 인 사고를 막는다. 살아있는 링크만
    실린 글은 그 자체로 검증 가능한 글이 된다. (병렬 확인: 8개 기준 ~6초)

    검사 대상은 **코드블록 밖 인용 링크**다. curl 예시의 API 엔드포인트(405/404)는
    '출처'가 아니므로 여기서 세면 정상 초안이 계속 걸린다(2026-10-19 통합 테스트 실증).
    """
    urls = citation_links(md)[:limit] or links_in(md)[:limit]
    res = _verify_many(urls, timeout=min(timeout, 6.0))
    return [u for u in urls if not res.get(u)]


def screen_extended(text: str, verify_links: bool = True) -> list:
    """게이트 + 링크 생존 검증(자동 파이프라인 전용).

    `emdash_precheck.check()` 는 순수 문자열 검사로 남겨두고(수동 글쓰기 경로와 공유),
    네트워크·구조 검사는 여기서만 한다.
    """
    md = body_of(text)
    issues = check(md)
    cit = citation_links(md)
    # 게이트의 링크 검사는 코드블록 안 URL 도 세므로, 인용이 부족한 글은 여기서 한 번 더 막는다.
    if not any("외부 링크" in i for i in issues) and len(cit) < MIN_LINKS:
        issues.append("실제 인용 링크(코드블록 밖) %d개 (최소 %d) → 원문·공식 문서를 본문/`## 참고 자료`에 넣어라"
                      % (len(cit), MIN_LINKS))
    if verify_links:
        dead = dead_links(md)
        if dead:
            issues.append("끊긴 링크 %d개 (%s) → 살아있는 URL 로 교체"
                          % (len(dead), ", ".join(u[:60] for u in dead[:3])))
    return issues


# ---------------------------------------------------------------- 교정 지시
_FIX_HINTS = (
    ("PT JSON", "- 이전 출력이 JSON 이었다. 마크다운 본문 텍스트로 다시 써라."),
    ("본문에 H1", "- 본문 맨 앞에 `# 제목` 을 넣지 마라. 제목은 TITLE: 줄에만 한 번 쓴다."),
    ("`## 마무리", "- 마지막 소제목을 **문자 그대로** `## 마무리 — (내용을 요약한 짧은 말)` 로 달아라. "
                   "그 아래에 오늘 바로 할 수 있는 실행 3단계를 번호 목록으로 쓴다."),
    ("외부 링크", "- 본문에 실제 URL 을 인라인 링크로 최소 3개 넣어라. 이 프롬프트의 '인용 가능한 실제 링크' "
                 "목록에 있는 URL 을 그대로 쓰고, 목록에 없는 URL 은 지어내지 마라."),
    ("끊긴 링크", "- 아래 링크는 실제로 열리지 않는다(404 등). 다른 URL 로 교체하거나 지워라. "
                 "이 프롬프트의 '인용 가능한 실제 링크' 목록에서 골라라."),
    ("인용 링크", "- 코드블록(curl 예시) 안의 URL 은 출처로 세지 않는다. 본문 문장이나 "
                 "`## 참고 자료` 섹션에 클릭 가능한 링크를 최소 3개 넣어라."),
    ("표 ", "- 수치·한도·요금·비교는 문장이 아니라 마크다운 표로 넣어라. 형식은 정확히 이렇게:\n"
            "  `| 항목 | 값 |` 다음 줄에 `| --- | --- |` 구분선, 그 다음 데이터 행. "
            "**구분선이 없으면 표로 렌더링되지 않아 검사에서 0개로 센다.**"),
    ("코드펜스", "- 코드펜스(```)를 열었으면 반드시 닫아라. 홀수면 발행 금지다."),
    ("내부 용어", "- 파이프라인 내부 용어(firecrawl, dev.vars, .env.common, launchd)를 본문에서 모두 지워라. "
                 "독자용 표현으로 바꿔라."),
    ("본문 ", "- 분량이 부족하다. 추측으로 늘리지 말고, 기사에 있는 사실·수치·인용을 더 세밀하게 풀어써라. "
              "부족하면 기사에서 확인 가능한 배경과 구체적 사용 절차를 단계로 쪼개 적어라."),
)


def fix_note(issues: list) -> str:
    """게이트 결함 → LLM 교정 지시문(재생성 프롬프트에 붙인다)."""
    lines = ["", "[교정 지시] 방금 쓴 초안은 아래 검사에서 미달했다. 같은 주제로 **처음부터 다시** 써라.",
             "미달 항목:"]
    for it in issues:
        lines.append("  - " + it)
    lines.append("")
    lines.append("반드시 지킬 것:")
    seen = set()
    for key, hint in _FIX_HINTS:
        if any(key in it for it in issues) and hint not in seen:
            lines.append(hint)
            seen.add(hint)
    lines.append(f"- 분량 하한은 {MIN_CHARS}자(공백 포함), 외부 링크 {MIN_LINKS}개 이상, 표 {MIN_TABLES}개 이상이다.")
    lines.append("- 위 수치를 채우려고 문장을 늘리거나 반복하지 마라. 사실 밀도로 채운다.")
    return "\n".join(lines)


def revision_note(draft_body: str, issues: list) -> str:
    """교정 지시문 — **처음부터 다시 쓰지 말고 초안을 고치게** 한다 (AIK24-BLOG-02 실측).

    2026-10-19 A/B 실측: 같은 모델에게 같은 프롬프트로 '처음부터 다시' 시키면 길이가 오히려 줄었다
    (3,128→2,902자 / 2,211→2,381자). 반면 결함만 지적해 초안을 살려 고치게 하면 통과율이 올라간다.
    부족한 분량은 추측이 아니라 기사에 있는 사실을 더 세밀하게 풀어 채우게 한다.
    """
    short = [re.split(r"[→(]", i)[0].strip() for i in issues]
    lines = ["", "[교정 지시] 아래 초안은 발행 검사에서 미달했다. **처음부터 새로 쓰지 말고 이 초안을 고쳐라.**",
             "미달 항목:"] + ["  - " + s for s in short] + ["", "반드시 지킬 것:"]
    seen = set()
    for key, hint in _FIX_HINTS:
        if any(key in it for it in issues) and hint not in seen:
            lines.append(hint)
            seen.add(hint)
    lines += [
        f"- 분량 하한은 {MIN_CHARS}자(공백 포함, 현재 {len(draft_body)}자). "
        f"늘릴 때는 문장을 반복하거나 추측을 넣지 말고, 기사에 있는 사실·수치·인용을 더 세밀하게 풀어 쓴다.",
        f"- 외부 링크 {MIN_LINKS}개 이상, 마크다운 표 {MIN_TABLES}개 이상.",
        "",
        "[이미 잘 쓴 부분은 그대로 유지한다. 좋은 문장을 지우고 새로 쓰면 분량과 밀도가 떨어진다.]",
        "",
        "[직전 초안]",
        draft_body.strip(),
        "",
        "[출력] TITLE: 줄 하나 + `---` + 고친 **마크다운 본문 전체**(일부만 보내지 말 것).",
    ]
    return "\n".join(lines)


# ------------------------------------------------- 교정 전용 강한 모델 호출
# 교정(수정) 단계는 품질이 걸린 마지막 관문이라 모델을 지정해 쓴다.
# 1차 생성은 기존 무료 체인(순수 회전)을 그대로 두고, 여기서만 지정 모델을 쓴다.
_STRONG_CANDIDATES = ("groq1-gpt120b", "groq2-gpt120b", "zhipu-glm", "gemini-3.5-flash")
STRONG_CANDIDATES = _STRONG_CANDIDATES   # 공개 별칭 (생성기가 순서를 지정할 때 사용)
_MODELS_YAML = os.path.join(os.path.dirname(_HERE), "config", "models.yaml")


def _load_chain_config() -> dict:
    try:
        import yaml
        with open(_MODELS_YAML, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception as e:
        print("  ⚠️ models.yaml 로드 실패: %s" % e)
        return {}


def strong_completion(prompt: str, system_prompt: str = None, max_tokens: int = 7000,
                      temperature: float = 0.5, order=_STRONG_CANDIDATES,
                      timeout: float = 180.0) -> str:
    """지정 모델로 1회 생성 (교정 전용). 실패하면 다음 후보 → 전부 실패 시 ''.

    무료 체인의 순수 회전 규약은 1차 생성 경로에서 그대로 유지된다. 이 함수는
    '이미 미달 판정을 받은 초안을 고치는' 용도로만 쓴다(교정 실패 = 발행 보류).
    """
    cfg = _load_chain_config()
    models = cfg.get("models") or {}
    providers = cfg.get("providers") or {}
    for key in order:
        t = models.get(key)
        if not t:
            continue
        prov = providers.get(t.get("provider")) or {}
        api_key = os.environ.get(prov.get("api_key_env", ""), "")
        if not api_key:
            continue
        try:
            from openai import OpenAI
            client = OpenAI(base_url=prov.get("base_url"), api_key=api_key, timeout=timeout)
            msgs = ([{"role": "system", "content": system_prompt}] if system_prompt else []) + \
                   [{"role": "user", "content": prompt}]
            print("  [교정모델] %s (%s)" % (t.get("model"), t.get("provider")))
            resp = client.chat.completions.create(
                model=t.get("model"), messages=msgs, temperature=temperature, max_tokens=max_tokens)
            text = (resp.choices[0].message.content or "").strip() if resp.choices else ""
            if text:
                return text
            print("  ⚠️ %s 빈 응답 → 다음 후보" % key)
        except Exception as e:
            print("  ⚠️ %s 실패: %s: %s" % (key, type(e).__name__, str(e)[:120]))
    return ""



# ---------------------------------------------------------------- 실제 링크 수집
# 401/403/405/406/429 = 접근 제한·봇 차단·메서드 불일치. 링크 자체는 존재하므로 살아있는 것으로 본다.
# (실측: 유료 매체·API 엔드포인트가 403/405 를 돌려주는데 이를 '끊긴 링크'로 세면 정상 인용이 걸린다)
_SOFT_OK_CODES = (401, 403, 405, 406, 429)


def _http_ok(url: str, timeout: float = 8.0) -> bool:
    for method in ("HEAD", "GET"):
        try:
            req = urllib.request.Request(url, method=method, headers={"User-Agent": _UA})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                if 200 <= r.status < 400:
                    return True
        except urllib.error.HTTPError as e:
            if 200 <= e.code < 400 or e.code in _SOFT_OK_CODES:
                return True
        except Exception:
            pass
    # urllib 은 TLS 지문 때문에 봇 차단(Akamai 등)에 걸리는 경우가 있다.
    # 실측(2026-10-19): https://azure.microsoft.com/... 은 curl 로 200 인데 urllib 은 실패 →
    # 정상 인용이 '끊긴 링크'로 오판됐다. curl 로 한 번 더 확인한다(있으면).
    return _http_ok_curl(url, timeout)


def _http_ok_curl(url: str, timeout: float = 6.0) -> bool:
    try:
        p = subprocess.run(
            ["curl", "-sL", "-o", "/dev/null", "-w", "%{http_code}",
             "--max-time", str(max(int(timeout), 3)), "-A", _UA, url],
            capture_output=True, text=True, timeout=timeout + 3)
        code = (p.stdout or "").strip()
        if not code.isdigit():
            return False
        c = int(code)
        return 200 <= c < 400 or c in _SOFT_OK_CODES
    except Exception:
        return False


def _verify_many(urls, timeout: float = 6.0, workers: int = 6) -> dict:
    """여러 URL 을 병렬로 생존 확인한다 (직렬 8개 × 2회 시도 = 최대 1분 → 병렬 ~6초)."""
    urls = list(dict.fromkeys(urls))
    if not urls:
        return {}
    try:
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=min(workers, len(urls))) as ex:
            ok = list(ex.map(lambda u: _http_ok(u, timeout=timeout), urls))
        return dict(zip(urls, ok))
    except Exception:
        return {u: _http_ok(u, timeout=timeout) for u in urls}


def _fetch(url: str, timeout: float = 10.0) -> str:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": _UA})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read(600_000)
        return raw.decode("utf-8", "ignore")
    except Exception:
        return ""


def _domain(url: str) -> str:
    m = re.match(r"https?://([^/]+)", url)
    return (m.group(1) if m else "").lower().lstrip("www.")


def _allowed(url: str, source_domain: str) -> bool:
    low = url.lower()
    if any(b in low for b in _BLOCKED):
        return False
    d = _domain(url)
    if not d or d == source_domain:
        return False
    if d.endswith((".css", ".js", ".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".ico")):
        return False
    if any(p in low for p in _PATH_BLOCK):
        return False
    # 루트/프로필 링크는 인용 가치가 없다 (실측: electrek.co, github.com/huggingface, trust.openrouter.ai)
    segs = [s for s in urllib.parse.urlparse(url).path.split("/") if s]
    if len(segs) < 2:
        return False
    if segs[-1].lower().endswith(_ASSET_EXT):
        return False
    return True


def _rank(url: str) -> int:
    d = _domain(url)
    for i, p in enumerate(_PREFERRED):
        if d == p or d.endswith("." + p) or d.endswith(p):
            return i
    return len(_PREFERRED) + 1


def collect_real_links(article: dict, limit: int = 5, timeout: float = 8.0) -> list:
    """기사에서 **실제로 확인된** 인용 링크를 모은다.

    원문 기사 URL 1건은 항상 맨 앞에 둔다. 그 다음 원문 페이지가 인용한 외부 링크를
    (공식·1차 출처 우선으로) 추출하고 HTTP 로 살아있는지 확인한 뒤 돌려준다.
    지어낸 URL 을 글에 넣지 않기 위한 장치 — 게이트의 `외부 링크 3개` 요구를
    '추측'이 아니라 '실제 근거'로 채우게 한다.

    Returns: [{"url": str, "domain": str, "kind": "원문"|"인용"}, ...]
    """
    link = (article or {}).get("link") or ""
    out, seen = [], set()

    if link.startswith("http"):
        out.append({"url": link, "domain": _domain(link), "kind": "원문"})
        seen.add(link)

    cache_key = (link, limit)
    if cache_key in _listing_cache:
        found = _listing_cache[cache_key]
    else:
        found = []
        if link.startswith("http"):
            html = _fetch(link, timeout=max(timeout, 8.0))
            cands = set()
            for m in re.finditer(r'href=["\'](https?://[^"\'\s>]+)', html or ""):
                u = m.group(1).replace("&amp;", "&").strip().rstrip(_URL_TRIM)
                if _allowed(u, _domain(link)):
                    cands.add(u)
            found = sorted(cands, key=lambda u: (_rank(u), len(u)))[: max(limit * 2, 6)]
        _listing_cache[cache_key] = found

    # 후보 전체를 병렬로 생존 확인한 뒤, 순위대로 상위 limit 개를 채택한다.
    # (직렬로 하나씩 확인하면 후보 12개 × 최대 12초 = 2분까지 걸린다)
    if found:
        ok_map = _verify_many(found, timeout=timeout)
        for u in found:
            if len(out) >= limit:
                break
            if u in seen:
                continue
            if ok_map.get(u):
                out.append({"url": u, "domain": _domain(u), "kind": "인용"})
                seen.add(u)
    return out


def link_block(links: list) -> str:
    """프롬프트에 넣을 '인용 가능한 실제 링크' 블록. 링크가 없으면 지어내지 말라고 명시한다.

    구조 규칙: ① 원문 링크는 본문에서 인라인으로 한 번 이상 인용,
    ② `## 참고 자료` 섹션을 **마무리 앞에** 두고 목록의 링크를 정리,
    ③ 목록 밖 URL 창작 금지. (게이트가 요구하는 외부 링크 3개를 '실제 근거'로 채운다)
    """
    if not links:
        return ("## 인용 가능한 실제 링크\n(없음 — URL 을 지어내지 마라. 지어낸 링크는 발행 전 검사에서 걸린다.)\n")
    lines = [
        "## 인용 가능한 실제 링크 (아래 URL 을 우선 사용)",
        "① 원문 링크는 본문 안에서 인라인 링크로 1회 이상 인용한다.",
        "② `## 참고 자료` 섹션을 **`## 마무리` 앞에** 두고, 사용한 링크를 목록으로 정리한다(제목 + 링크).",
        "③ 아래 목록 밖의 URL 을 쓰려면 **공식 문서·공식 발표 페이지**여야 한다. 실제로 열리지 않는 "
        "URL 은 발행 전 검사에서 걸려 글이 발행되지 않는다 — 확실하지 않으면 쓰지 마라.",
        "④ 본문 전체에 외부 링크가 최소 3개 있어야 한다(원문 1 + 참고 자료 2 이상).",
    ]
    for l in links:
        lines.append(f"- {l['url']}  ({l['kind']}·{l['domain']})")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------- 알림 / 보류 저장
def alert(msg: str) -> None:
    """텔레그램 알림(실패해도 본 흐름을 막지 않는다)."""
    try:
        sys.path.insert(0, os.path.dirname(_HERE))
        from pipeline.infra.telegram import send_telegram  # type: ignore
        send_telegram(msg)
    except Exception as e:  # pragma: no cover
        print("  ⚠️ 텔레그램 알림 실패: %s" % e)


def _slugify(title: str) -> str:
    s = re.sub(r"[^\w\s가-힣-]", "", title or "").strip().replace(" ", "-")
    return (s[:60] or "untitled").lower()


def hold(pending_md: str, title: str, issues: list, retry_md: str = None,
         retry_issues: list = None, reason: str = "1차 게이트 미달") -> str:
    """발행 보류 초안을 디스크에 남기고 알린다. Returns: 저장 경로."""
    os.makedirs(REJECTED_DIR, exist_ok=True)
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    base = "%s-%s" % (stamp, _slugify(title))
    path = os.path.join(REJECTED_DIR, base + ".md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(pending_md or "")
    meta = {
        "title": title,
        "reason": reason,
        "issues": issues or [],
        "retry_issues": retry_issues or [],
        "saved_at": datetime.datetime.now().isoformat(timespec="seconds"),
    }
    if retry_md:
        rpath = os.path.join(REJECTED_DIR, base + "-retry.md")
        with open(rpath, "w", encoding="utf-8") as f:
            f.write(retry_md)
        meta["retry_path"] = rpath
    with open(os.path.join(REJECTED_DIR, base + ".json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=1)

    head = "\n".join("    · " + i for i in (issues or [])[:6])
    global HOLD_COUNT
    HOLD_COUNT += 1
    HOLDED_TITLES.append((title or "")[:60])
    print("  ⛔ 발행 보류 — %s (%s)" % (title[:40], reason))
    print(head)
    print("     저장: %s" % path)
    alert("⛔ [게이트] 발행 보류 — %s\n이슈 %d건: %s\n초안: %s" % (
        (title or "")[:60], len(issues or []),
        " / ".join(re.split(r"[→(]", i)[0].strip() for i in (issues or [])[:4]), path))
    return path


def summary_line() -> str:
    """실행 요약 한 줄 (보류가 없으면 빈 문자열)."""
    if not HOLD_COUNT:
        return ""
    return "게이트 보류 %d건 — %s (초안: scripts/logs/rejected/)" % (
        HOLD_COUNT, ", ".join(HOLDED_TITLES[:3]))


# ---------------------------------------------------------------- 3차: 발행본 읽기 검증
def _plain(text: str) -> str:
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"[`*_>#|]", "", text)
    return re.sub(r"\s+", " ", text).strip()


def verify_published(url: str, expected_body: str = "", title: str = None,
                     timeout: float = 20.0) -> tuple:
    """발행 직후 라이브 HTML 을 읽어 본문이 실제로 반영됐는지 확인한다 (3차 방어).

    잡으려는 사고: 동시 편집자가 낡은 사본을 저장·발행해 공개본이 옛 내용으로 되돌아간 건
    (2026-10-18 `workbuddy…` 글, 24블록으로 회귀). 발행 API 가 200 을 돌려줘도 사고는 난다.

    Returns: (ok: bool, detail: str)
    """
    if not url:
        return False, "url 없음"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": _UA})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            html = r.read().decode("utf-8", "ignore")
            status = r.status
    except Exception as e:
        alert("⚠️ [게이트 3차] 발행본 읽기 실패 — %s (%s)" % (url, e))
        return False, "http 실패: %s" % e
    if status != 200:
        alert("⚠️ [게이트 3차] 발행본 HTTP %s — %s" % (status, url))
        return False, "http %s" % status

    body = re.sub(r"<script.*?</script>|<style.*?</style>", " ", html, flags=re.S)
    body = re.sub(r"<[^>]+>", " ", body)
    body = re.sub(r"\s+", " ", body)

    problems = []
    if title and _plain(title)[:20] and _plain(title)[:20] not in body:
        problems.append("제목 불일치")
    if "마무리" not in body:
        problems.append("`## 마무리` 없음")
    if "emdash-table" not in html:
        problems.append("표 없음")
    if expected_body:
        frag = _plain(expected_body)[:40]
        if frag and frag not in body:
            problems.append("본문 앞부분 불일치(덮어쓰기 의심)")
        exp_chars = len(expected_body)
        live_chars = len(body)
        if exp_chars > 1500 and live_chars < exp_chars * 0.6:
            problems.append("본문 분량 부족(예상 %d / 라이브 %d)" % (exp_chars, live_chars))

    if problems:
        alert("⚠️ [게이트 3차] 발행본 검증 실패 — %s\n%s" % (url, " / ".join(problems)))
        return False, " / ".join(problems)
    print("  ✅ 발행본 검증 OK (3차): %s" % url)
    return True, "ok"


# ---------------------------------------------------------------- CLI (수동 점검용)
def _main(argv):
    if len(argv) < 2 or argv[1].startswith("--"):
        print("사용법: blog_quality_gate.py <md경로> [--links <url>] [--verify <발행URL>]")
        return 2
    path = argv[1]
    with open(path, encoding="utf-8") as f:
        text = f.read()
    issues = screen(text)
    if issues:
        print("❌ 게이트 미달 %d건:" % len(issues))
        for i in issues:
            print("  -", i)
        print()
        print(fix_note(issues))
    else:
        print("✅ 게이트 통과 — 본문 %d자" % len(body_of(text)))
    if "--links" in argv:
        u = argv[argv.index("--links") + 1]
        print(json.dumps(collect_real_links({"link": u}), ensure_ascii=False, indent=1))
    if "--verify" in argv:
        u = argv[argv.index("--verify") + 1]
        print(verify_published(u, expected_body=body_of(text)))
    return 0 if not issues else 3


if __name__ == "__main__":
    sys.exit(_main(sys.argv))
