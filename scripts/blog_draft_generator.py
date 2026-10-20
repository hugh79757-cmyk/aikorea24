#!/usr/bin/env python3
"""
aikorea24 블로그 초안 자동 생성기
- D1 DB에서 오늘 수집된 뉴스 중 고단가 키워드 포함 기사 조회
- 키워드별 기사 그룹핑 → OpenAI 블로그 초안 생성
- EmDash 단독 발행 (AIK24-EMDASH-03: src/content/blog/ 저장 없음 — Astro 는 source of truth 아님)
- scripts/emdash_publish.py 로 EmDash 즉시 발행. 실패 시 폴백 없음, 로그만 남기고 다음 글로 진행
- 텔레그램 알림
"""
# launchd 환경 방어: 가장 먼저 sys.path 설정 (모든 import보다 앞)
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import os, re, json, glob, time
from datetime import datetime, date, timezone, timedelta

# launchd 환경: sys.path 미설정 상태이므로 __file__ 기반으로 추가
_script_dir = os.path.dirname(os.path.abspath(__file__))
_PROJECT_DIR = os.path.dirname(_script_dir)
sys.path.insert(0, _PROJECT_DIR)
sys.path.insert(0, _script_dir)
sys.path.insert(0, os.path.join(_PROJECT_DIR, 'scripts', 'threads', 'v3'))

from pipeline.infra.env_loader import EnvConfig
_config = EnvConfig()
_config.load_to_environ()

from pipeline.infra.logger import get_scrubbed_logger
logger = get_scrubbed_logger(__name__)
from pipeline.infra import project_root; PROJECT_DIR = project_root()

KST = timezone(timedelta(hours=9))

def remove_chinese(text):
    """CJK 통합 한자 블록(U+4E00–U+9FFF, U+3400–U+4DBF) 제거"""
    return re.sub(r'[\u4e00-\u9fff\u3400-\u4dbf]', '', text)

# 대표님 지시(2026-10-13): 블로그 본문 이모티콘 금지. 프롬프트로 막혀도 LLM이
# 종종 섞어 쓰므로 저장 직전 한 번 더 긁어낸다(remove_chinese와 같은 안전망).
_EMOJI_RE = re.compile(
    '[\U0001F000-\U0001FAFF⌀-⏿①-⓿■-➿⬀-⯿️‍\U000020E3]'
)

def remove_emoji(text):
    """이모티콘/이모지 블록 제거"""
    return _EMOJI_RE.sub('', text)

# ============================================
# 고단가 키워드 테이블 (deprecated: 브리핑 기사 직접 사용)
# ============================================

# ============================================
# model_router (threads/v3)
# ============================================
from model_router import chat_completion
from auto_thumbnail import process_thumbnail, check_thumbnail_duplicates, validate_thumbnail_quality, is_placeholder_copy, DEEPSEEK_POOL
# AIK24-BLOG-02 (2026-10-19): 발행 게이트 배선. 게이트(emdash_precheck.check)를 실제 발행 경로에
# 연결하는 얇은 계층 — 미달이면 교정 재생성 1회 → 그래도 미달이면 발행 보류(초안 보존 + 알림).
import blog_quality_gate as _quality_gate

# ============================================
# 글쓰기 규칙 주입 (AIK24-BLOG-01, 2026-10-17 대표님 지시)
# ============================================
# 스킬(aik24-blog-writing) 규칙 파일을 읽어 글 생성 system_prompt 앞에 붙인다.
# 어떤 LLM이 글을 쓰더라도 같은 규칙이 적용되게 하는 것이 목적 — 아래 3개 생성 경로 모두에 적용한다.
# 파일이 없으면 빈 문자열을 돌려주고 기존 동작 그대로(폴백) 진행한다.
def _load_blog_rules():
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "blog_writing_rules.md")
    try:
        with open(p, encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return ""


_BLOG_RULES = _load_blog_rules()

# AIK24-BLOG-02 (2026-10-19): 프롬프트의 분량 요구가 게이트 하한과 달라 통과율이 20%였다.
# 프롬프트는 "1,500자/2,000자 이상", 게이트는 3,000자 — 모델은 프롬프트의 숫자를 따른다.
# 숫자를 한 곳(게이트)에서 가져와 두 기준이 어긋날 수 없게 한다.
MIN_BODY_CHARS = _quality_gate.MIN_CHARS


ENV_PATH = os.path.join(PROJECT_DIR, ".env")
DB_ID = "3f4cedde-eabc-4d7c-b459-f6abe8733767"

# ============================================
# 로깅
# ============================================
# Strangler Fig: replace with logger.info() in Phase 3
def log(msg):
    ts = datetime.now(KST).strftime("%H:%M:%S")
    print(f"[{ts}] {msg}")

# ============================================
# 환경변수 로딩
# ============================================
def load_env():
    # 공통 환경변수 먼저 로드 (~/.env.common)
    common = os.path.expanduser('~/.env.common')
    if os.path.exists(common):
        with open(common) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') \
                   and '=' in line and not line.startswith('source'):
                    k, v = line.split('=', 1)
                    os.environ.setdefault(k.strip(),
                                         v.strip().strip('"').strip("'"))

    if not os.path.exists(ENV_PATH):
        log(f"[WARN] .env 파일 없음: {ENV_PATH}")
        return
    with open(ENV_PATH) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ[k.strip()] = v.strip().strip('"').strip("'")

# ============================================
# D1 쿼리 (wrangler CLI — OAuth profile 사용)
# ============================================
_WRANGLER = "/opt/homebrew/bin/wrangler"
_DB = "aikorea24-db"

def _d1_run(sql):
    """wrangler d1 execute 실행, results 반환."""
    import cfnew
    cfnew.check_quota(threshold=0.8)  # [D1-GUARD] 읽기 한도 80% 초과 시 중단
    import subprocess, json, re
    cmd = [_WRANGLER, "d1", "execute", _DB, "--remote", "--command", sql]
    env = dict(os.environ)
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=30, env=env, cwd=PROJECT_DIR)
        if r.returncode != 0:
            stderr = r.stderr.strip()
            # 인증 오류 진단
            if "7403" in stderr:
                log(f"  ⚠️ D1 인증 실패 [7403]: CLOUDFLARE_ACCOUNT_ID와 OAuth 프로필 충돌 의심")
                log(f"  ⚠️ 원인: env에 CLOUDFLARE_ACCOUNT_ID가 설정되어 있으면 안 됨")
            elif "10000" in stderr:
                log(f"  ⚠️ D1 인증 실패 [10000]: CLOUDFLARE_API_TOKEN env var 충돌 의심")
                log(f"  ⚠️ 원인: env에서 CLOUDFLARE_API_TOKEN/CLOUDFLARE_ACCOUNT_ID 해제 필요")
            log(f"  wrangler 오류 (rc={r.returncode}): {stderr[:300]}")
            return None
        m = re.search(r'"results"\s*:\s*(\[.*?\])\s*,\s*"success"', r.stdout, re.DOTALL)
        return json.loads(m.group(1)) if m else []
    except Exception as e:
        log(f"  wrangler 예외: {e}")
        return None

def query_d1(sql):
    """D1 SELECT 실행, 결과 리스트 반환."""
    results = _d1_run(sql)
    if results is None:
        raise RuntimeError("D1 query failed")
    return results

def execute_d1(sql):
    """D1 UPDATE/INSERT 실행. 성공 여부 반환."""
    results = _d1_run(sql)
    return results is not None

def append_comment_link(news_id, blog_url):
    """무료 LLM 코멘트에 '👉 자세한 분석' 링크를 덧붙인다 (중복 삽입 방지).

    09:00 브리핑 시점에는 블로그가 아직 없어 링크를 넣을 수 없다.
    글이 생성된 지금(09:30) D1 코멘트를 한 번 갱신한다.
    """
    if not news_id or not blog_url:
        return False
    briefing_id = get_today_briefing_id()
    if not briefing_id:
        log("  ⚠️ 오늘 브리핑 없음, 코멘트 링크 추가 불가")
        return False
    sql = (
        f"UPDATE briefing_items SET comment = comment || char(10) || "  # char(10)=줄바꿈, SQLite는 \n을 해석 안 한다
        f"'👉 자세한 분석: {blog_url}' "
        f"WHERE briefing_id = {briefing_id} AND news_id = {news_id} "
        f"AND comment NOT LIKE '%👉 자세한 분석%'"
    )
    ok = execute_d1(sql)
    log(f"  🔗 코멘트 분석 링크 추가: {'ok' if ok else '실패'} (news_id={news_id})")
    return bool(ok)


def get_today_briefing_id():
    """오늘 발행된 브리핑 ID 조회 (없으면 None)."""
    today = datetime.now(KST).strftime("%Y-%m-%d")
    try:
        rows = query_d1(
            f"SELECT id FROM briefings WHERE date LIKE '{today}%' AND status = 'published' ORDER BY date DESC LIMIT 1"
        )
        return rows[0]["id"] if rows else None
    except Exception as e:
        log(f"  브리핑 조회 실패 (D1 오류, 빈 브리핑 아님): {e}")
        raise

def update_deep_dive_url(news_id, blog_url):
    """briefing_items의 deep_dive_url을 블로그 URL로 업데이트."""
    if not news_id or not blog_url:
        return False
    briefing_id = get_today_briefing_id()
    if not briefing_id:
        log(f"  ⚠️ 오늘 브리핑 없음, deep_dive_url 연결 불가 (news_id={news_id})")
        return False
    sql = (
        f"UPDATE briefing_items SET deep_dive_url = '{blog_url}' "
        f"WHERE briefing_id = {briefing_id} AND news_id = {news_id}"
    )
    if execute_d1(sql):
        log(f"  🔗 deep_dive_url 연결: {blog_url} (news_id={news_id})")
        return True
    else:
        log(f"  ⚠️ deep_dive_url 연결 실패 (news_id={news_id})")
        return False

# ============================================
# 오늘 뉴스 조회
# ============================================
def get_briefing_articles():
    """오늘 브리핑에 포함된 기사 목록 조회."""
    briefing_id = get_today_briefing_id()
    if not briefing_id:
        log("  오늘 발행된 브리핑 없음")
        return []
    sql = f"""
        SELECT n.id, n.title, n.description, n.source, n.category, n.link,
               n.v2_tag, bi.sort_order, bi.comment, bi.deep_dive_url
        FROM briefing_items bi
        JOIN news n ON bi.news_id = n.id
        WHERE bi.briefing_id = {briefing_id}
        ORDER BY bi.sort_order
    """
    rows = query_d1(sql)
    log(f"오늘 브리핑 기사: {len(rows)}건 (briefing_id={briefing_id})")
    return rows

# ============================================
# AIK24-BLOG-02 (2026-10-19): 발행 게이트 3중 방어
# ============================================
# 교정 라운드별 모델 순서. 교정은 '이미 미달 판정을 받은 초안을 고치는' 마지막 관문이라
# 모델을 지정해 쓴다(1차 생성은 기존 무료 체인 순수 회전 그대로).
_GATE_FIX_ORDERS = (
    ("groq1-gpt120b", "groq2-gpt120b", "zhipu-glm", "gemini-3.5-flash"),
    ("zhipu-glm", "gemini-3.5-flash", "groq3-gpt120b", "groq4-gpt120b"),
)


def _gate_and_fix(title, art, filepath, seo_title, file_num, today_str):
    """1차 방어 — 게이트 검사 후 미달이면 '초안 수정' 교정을 최대 2회 수행한다.

    처음부터 다시 쓰게 하면 같은 모델은 더 짧게 돌아온다(2026-10-19 실측 3,128→2,902자).
    그래서 교정은 초안을 살려 고치는 방식(revision_note) + 모델 지정(strong_completion)이다.

    Returns: (채택_fp, 제목, 사용한_file_num_수, None, None)        — 통과
             (None, None, 사용한_file_num_수, issues, 마지막_fp)   — 교정 후에도 미달(호출측이 보류 처리)
    """
    def _body(fp):
        return _quality_gate.body_of((_EMDASH_PENDING.get(fp) or {}).get("md", ""))

    def _repair(fp):
        """결정적 수리(표 구분선·앞머리 H1). 내용은 바꾸지 않는다."""
        cur = (_EMDASH_PENDING.get(fp) or {}).get("md", "")
        fixed, fixes = _quality_gate.repair_pending(cur)
        if fixes:
            _EMDASH_PENDING[fp]["md"] = fixed
            log("    🛠 자동 수리 — " + ", ".join(fixes))
        return fixes

    _repair(filepath)
    issues = _quality_gate.screen_extended(_body(filepath))
    if not issues:
        log("    ✅ 게이트 통과 — 본문 %d자 / 인용 링크 %d개"
            % (len(_body(filepath)), len(_quality_gate.citation_links(_body(filepath)))))
        return filepath, seo_title, 1, None, None

    log(f"    ⚠️ 게이트 미달 {len(issues)}건 — 초안 수정 교정 {len(_GATE_FIX_ORDERS)}회 시도")
    for it in issues:
        log(f"       · {it}")

    created = [filepath]          # 이 함수가 만든 모든 초안 — 채택본 외에는 pending 에서 제거한다
    best_fp, best_issues, consumed = filepath, issues, 1

    def _drop_except(keep):
        """미달·미사용 초안이 발행 대기에 남지 않게 한다(남으면 검사를 우회해 발행된다)."""
        for _f in created:
            if _f != keep:
                _EMDASH_PENDING.pop(_f, None)

    for attempt, order in enumerate(_GATE_FIX_ORDERS, 1):
        log(f"    🔧 교정 {attempt}/{len(_GATE_FIX_ORDERS)} (모델 {order[0]} 우선)")
        out = generate_draft(title, [art], "A",
                             fix_note=_quality_gate.revision_note(_body(best_fp), best_issues),
                             corrective=True, model_order=order)
        if not out:
            log("       ↳ 교정 생성 실패(빈 응답)")
            continue
        fp2, t2 = save_draft(out, title, file_num + consumed, today_str, articles=[art])
        consumed += 1
        if not fp2:
            log("       ↳ 교정본이 저장 단계에서 거부됨")
            continue
        created.append(fp2)
        _repair(fp2)
        issues2 = _quality_gate.screen_extended(_body(fp2))
        if not issues2:
            _drop_except(fp2)
            log("    ✅ 교정 %d회차에서 게이트 통과 — 채택 (본문 %d자 / 인용 링크 %d개)"
                % (attempt, len(_body(fp2)), len(_quality_gate.citation_links(_body(fp2)))))
            return fp2, t2, consumed, None, None
        log("       ↳ 교정 %d회차도 미달: %s" % (
            attempt, " / ".join(re.split(r"[→(]", i)[0].strip()[:34] for i in issues2)))
        best_fp, best_issues = fp2, issues2

    _drop_except(best_fp)         # 마지막 초안만 호출측에 넘긴다(보류 기록용)
    return None, None, consumed, best_issues, best_fp


# ============================================
# 블로그 초안 생성 (무료 체인 순수 회전)
# ============================================
def generate_draft(keyword, articles, grade, fix_note=None, link_hint=True,
                   corrective=False, model_order=None):
    is_deep = len(articles) == 1

    # AIK24-BLOG-02 (2026-10-19): 게이트를 '실제로' 통과하려면 근거 링크가 있어야 한다.
    # 기사 원문 + 원문 페이지가 인용한 1차 출처를 모아(HTTP 생존 확인) 프롬프트에 넣는다.
    # 게이트 미달로 재생성할 때는 fix_note(교정 지시)를 프롬프트 끝에 붙인다.
    #
    # corrective=True: 교정 전용 경로. 무료 체인 순수 회전 대신 지정 모델(강한 모델)로 고친다.
    #   근거(2026-10-19 실측): 같은 모델에 같은 프롬프트로 '처음부터 다시' 시키면 길이가 오히려
    #   줄었다(3,128→2,902자). 교정은 '초안 수정' + 모델 지정으로 해야 목표에 도달한다.
    links_str = ""
    if link_hint and articles:
        try:
            links_str = _quality_gate.link_block(_quality_gate.collect_real_links(articles[0]))
        except Exception as e:
            log(f"  ⚠️ 인용 링크 수집 실패: {type(e).__name__}: {e}")
    fix_tail = ("\n\n" + fix_note) if fix_note else ""

    # 무료 LLM 항목은 전용 "모델 심층 분석" 구조로 생성한다 (AIK24-MODELEVAL-01).
    # 호출부를 바꾸지 않고 여기서 판별한다 — 모든 호출이 generate_draft를 거친다.
    # AIK24-BLOG-01 (2026-10-13 대표님 지시): 평가할 OpenRouter 모델이 없는 free-llm
    # 항목(HF Trending GGUF, free-llm로 분류된 일반 뉴스 등)은 뉴스 블로그로 생성한다.
    # routing 규칙 1가지: free-llm + OpenRouter 모델 확인됨 → 모델 평가글, 그 외 → 뉴스글.
    model_id = None
    if is_deep and articles[0].get("v2_tag") == "free-llm":
        try:
            model_id = model_eval.extract_model_id(articles[0])
        except Exception as e:
            log(f"  ⚠️ 모델 ID 판별 예외: {type(e).__name__}: {e}")
        if model_id:
            out = generate_model_eval_draft(keyword, articles[0], model_id,
                                           fix_note=fix_note, links_str=links_str,
                                           corrective=corrective, model_order=model_order)
            if out:
                return out
            log("  ⚠️ 모델 심층 분석 생성 실패 → 뉴스 블로그 경로로 대체")
        else:
            log(f"  ℹ️ OpenRouter 모델 ID 미확인 → 뉴스 블로그 경로: '{keyword[:40]}'")

    # 기사 텍스트 조립
    article_lines = []
    for i, a in enumerate(articles, 1):
        desc = (a.get("description") or "")[:300]
        article_lines.append(f"[기사 {i}]\n"
                             f"제목: {a['title']}\n"
                             f"출처: {a['source']}\n"
                             f"내용: {desc}")
    articles_str = "\n\n".join(article_lines)

    # GPT 프롬프트
    if is_deep:
        system_prompt = (
            "당신은 AI/테크 뉴스를 분석하는 한국어 블로거입니다. "
            "주어진 기사 하나를 깊이 분석하여 블로그 초안을 작성해주세요. "
            "중국어(한자)는 절대 사용하지 말고 순수 한국어로만 작성하세요."
        )
        # AIK24-BLOG-01: 규칙 prepend — 심층(단일 기사) 경로
        system_prompt = (_BLOG_RULES + "\n\n" + system_prompt) if _BLOG_RULES else system_prompt
        user_prompt = (
            f"아래 '{keyword}' 관련 기사를 분석한 블로그 초안을 작성해주세요.\n\n"
            f"## 요구사항\n"
            f"- 제목: '{keyword}' 키워드가 자연스럽게 포함된 SEO 최적화 제목\n"
            f"- 제목에 마크다운 백틱(`) 사용 금지\n"
            f"- 본문: {MIN_BODY_CHARS}자 이상(권장 3,200자), 소제목(##) 5개 이상 포함\n"
            f"- [필수] 마크다운 표 최소 1개. 형식은 정확히 이렇게: `| 항목 | 값 |` 다음 줄에 "
            f"`| --- | --- |` 구분선, 그 다음 데이터 행. 구분선이 없으면 표로 렌더링되지 않는다. "
            f"구체적인 수치·한도·비교를 표로 넣는다. "
            f"제목이 '비교'·'점수'·'순위'를 약속하면 반드시 실제 숫자를 넣을 것. "
            f"숫자가 없으면 해당 표현을 제목에서 빼세요.\n"
            f"- 기사의 배경/의미/전망을 분석, 독자가 쉽게 이해할 수 있도록\n"
            f"- [필수] 마지막 소제목을 문자 그대로 `## 마무리 — (짧은 말)` 로 달고, "
            f"그 아래에 오늘 바로 할 수 있는 실행 3단계를 번호 목록으로 쓴다.\n"
            f"- [필수] 본문 맨 앞에 `# 제목` 을 반복하지 않는다 (제목은 TITLE: 줄에만 1회)\n"
            f"- 순한국어, 전문적이면서도 친근한 ~습니다/~입니다 정중 비즈니스 톤\n"
            f"- [중요] 모든 문장은 '~합니다/~입니다/~했습니다' 체로 통일. 반말('~다/~했다/~임') 절대 금지\n"
            f"- [중요] 중국어(한자) 사용 금지. 반드시 순수 한국어로만 작성할 것\n"
            f"- [중요] **본문 첫 단락(도입단락)에서 '본 포스트에서는...', '이번 글에서는...', '이번 글에서는...', "
            f"'살펴보겠습니다', '알아보겠습니다', '다루겠습니다' 등 메타 성격의 도입문(메타 도입문) 절대 금지.** "
            f"기사의 실질적 핵심 내용(사실, 수치, 인용, 분석 등)으로 바로 시작할 것.\n\n"
            f"{links_str}"
            f"## 출력 형식\n"
            f"TITLE: [SEO에 최적화된 제목]\n"
            f"---\n"
            f"[마크다운 본문]\n\n"
            f"## 기사\n{articles_str}"
            f"{fix_tail}"
        )
    else:
        system_prompt = (
            "당신은 AI/테크 뉴스를 분석하는 한국어 블로거입니다. "
            "여러 기사를 종합하여 트렌드 분석 블로그 초안을 작성해주세요. "
            "중국어(한자)는 절대 사용하지 말고 순수 한국어로만 작성하세요."
        )
        # AIK24-BLOG-01: 규칙 prepend — 트렌드(복수 기사) 경로
        system_prompt = (_BLOG_RULES + "\n\n" + system_prompt) if _BLOG_RULES else system_prompt
        user_prompt = (
            f"아래 '{keyword}' 관련 여러 기사를 종합한 블로그 초안을 작성해주세요.\n\n"
            f"## 요구사항\n"
            f"- 제목: '{keyword}' 관련 트렌드가 드러나는 SEO 최적화 제목\n"
            f"- 본문: {MIN_BODY_CHARS}자 이상(권장 3,200자), 소제목(##) 5개 이상 포함\n"
            f"- [필수] 마크다운 표 최소 1개 (기사별 비교·수치 정리). 형식: `| 항목 | 값 |` 다음 줄에 "
            f"`| --- | --- |` 구분선, 그 다음 데이터 행. 구분선이 없으면 표로 렌더링되지 않는다.\n"
            f"- 각 기사의 핵심 내용을 비교/종합하여 트렌드 분석\n"
            f"- [필수] 마지막 소제목을 문자 그대로 `## 마무리 — (짧은 말)` 로 달고, "
            f"그 아래에 오늘 바로 할 수 있는 실행 3단계를 번호 목록으로 쓴다.\n"
            f"- [필수] 본문 맨 앞에 `# 제목` 을 반복하지 않는다 (제목은 TITLE: 줄에만 1회)\n"
            f"- 순한국어, 전문적이면서도 친근한 ~습니다/~입니다 정중 비즈니스 톤\n"
            f"- [중요] 모든 문장은 '~합니다/~입니다/~했습니다' 체로 통일. 반말('~다/~했다/~임') 절대 금지\n"
            f"- [중요] 중국어(한자) 사용 금지. 반드시 순수 한국어로만 작성할 것\n"
            f"- [중요] **본문 첫 단락(도입단락)에서 '본 포스트에서는...', '이번 글에서는...', '이번 글에서는...', "
            f"'살펴보겠습니다', '알아보겠습니다', '다루겠습니다' 등 메타 성격의 도입문(메타 도입문) 절대 금지.** "
            f"기사의 실질적 핵심 내용(사실, 수치, 인용, 분석 등)으로 바로 시작할 것.\n\n"
            f"{links_str}"
            f"## 출력 형식\n"
            f"TITLE: [SEO에 최적화된 제목]\n"
            f"---\n"
            f"[마크다운 본문]\n\n"
            f"## 기사들\n{articles_str}"
            f"{fix_tail}"
        )

    if corrective:
        # 교정(수정) 단계 — 지정 모델로 고친다. 실패하면 빈 문자열 → 호출측이 다음 시도/보류 판단.
        content = _quality_gate.strong_completion(
            user_prompt, system_prompt=system_prompt, max_tokens=7000, temperature=0.5,
            order=model_order or _quality_gate.STRONG_CANDIDATES)
    else:
        content = chat_completion(
            messages=[{"role": "user", "content": user_prompt}],
            system_prompt=system_prompt,
            # AIK24-BLOG-02: 3,000자 이상 한국어 본문은 3,000 토큰으로는 잘린다(실측: 생성 2,5xx자에서 멈춤).
            max_tokens=6000,
            temperature=0.7,
        )
    if not content:
        log("  ❌ 블로그 초안 생성 실패")
        return ""
    # 중국어 문자 제거 (안전망)
    cleaned = remove_chinese(content)
    if cleaned != content:
        removed = len(content) - len(cleaned)
        log(f"  ⚠️ 중국어 문자 {removed}개 제거됨")
    content = cleaned
    log(f"  생성 완료: {len(content)}자")
    return content

# ============================================
# 모델 심층 분석 생성기 (AIK24-MODELEVAL-01)
# ============================================
def _eval_block(model_id):
    """캐시 우선 모델 평가. 캐시 없으면 지금 평가한다(최대 ~1분).

    AIK24-MODELEVAL-02 1-4: 모든 단계에 명시적 로그를 남긴다.
    - 캐시 히트 / 미스
    - 평가 시작 / 완료 / 실패(실패 이유 포함)
    평가가 조용히 실패하면 "왜 글에 평가 데이터가 없는지" 추적이 불가능하다.
    """
    r = model_eval.cache_get(model_id)
    if r:
        log(f"  📊 모델 평가 캐시 사용: {r.get('label')} "
            f"(score={r.get('score')}/{r.get('max_score')}, failed={r.get('failed')})")
        return r
    log(f"  📊 모델 평가 실행 시작 (캐시 없음): {model_id}")
    try:
        result = model_eval.eval_model_cached(model_id)
        failed = result.get("failed", 0)
        max_score = result.get("max_score", 9)
        if failed >= max_score and max_score > 0:
            log(f"  ❌ 모델 평가 전 문항 실패 → 블로그 생성 생략: {model_id} "
                f"(failed={failed}/{max_score}) — 모델 미존재·접근제한·레이트리밋 가능")
        else:
            log(f"  ✅ 모델 평가 완료: {result.get('label')} "
                f"(failed={failed}/{max_score})")
        return result
    except Exception as e:
        log(f"  ❌ 모델 평가 예외 발생: {model_id} — {type(e).__name__}: {e}")
        return {"failed": 9, "max_score": 9, "label": "평가 실패", "details": []}


# BLOG-03: 응답 실패로 0점 처리된 문항의 source 값들 (호출 자체가 실패한 것)
_FAIL_SOURCES = ("http_error", "exception", "empty", "no_choices")


def _leaderboard_block(model_id):
    """BLOG-03 §2-1: 같은 문항 세트(qv)의 실측 결과만 모아 순위를 만든다.

    추가 API 호출 없이 scripts/logs/model_leaderboard.json 파일만 읽는다.
    같은 모델이 여러 번 평가됐으면 최신 기록 1개만 남긴다(리더보드는 모델 단위).
    """
    rows = []
    try:
        with open(model_eval.LEADERBOARD_PATH, "r", encoding="utf-8") as f:
            rows = json.load(f)
    except Exception:
        rows = []
    latest = {}
    for r in rows if isinstance(rows, list) else []:
        if isinstance(r, dict) and r.get("qv") == model_eval.EVAL_QUESTIONS_VERSION and r.get("model_id"):
            latest[r["model_id"]] = r  # append-only 파일이므로 마지막 쓰기가 최신
    # 분모(측정된 문항 수)가 다를 수 있어 비율로 정렬한다. 측정 결함 문항은 이미 빠졌다.
    ranked = sorted(latest.values(), key=lambda r: -(r.get("score", 0) / max(1, r.get("max_score", 1))))
    mine = [i for i, r in enumerate(ranked, 1) if r["model_id"] == model_id]
    if len(ranked) < 2 or not mine:
        return f"비교 데이터 축적 중 — 단독 평가 (누적 {len(ranked)}개 모델)"
    rank, me = mine[0], ranked[mine[0] - 1]
    lines = [f"누적 {len(ranked)}개 모델 중 이 모델 {rank}위 ({me.get('score')}/{me.get('max_score')})"]
    for i in (rank - 2, rank, rank + 1):  # 바로 위·자신·바로 아래
        if 0 <= i < len(ranked):
            r = ranked[i]
            when = time.strftime("%Y-%m-%d", time.localtime(r.get("ts") or 0))
            lines.append(f"{i + 1}위 {r['model_id']} {r.get('score')}/{r.get('max_score')} (측정일 {when})")
    return "\n".join(lines)


def _cost_block(model_id, ev):
    """BLOG-03 §2-2: 오늘 실측한 토큰 사용량 x OpenRouter 단가. 추정이 아니라 계산.

    '무료' 표현은 free_paths()가 실제로 무료 변형을 확인했을 때만 나온다.
    """
    u = ev.get("token_usage") or {}
    p, c = int(u.get("prompt") or 0), int(u.get("completion") or 0)
    if ev.get("source") == "cli":
        return "CLI 경유 — 토큰 사용량 미측정 (OpenCode Zen 경유, 단가·사용량 모두 집계 불가)"
    if not p and not c:
        return "비용 실측 데이터 없음 (문항별 토큰 사용량 미기록 — 구 캐시)"
    pr = model_eval.pricing(model_id)
    n = ev.get("max_score") or 0
    paths = [f"- 접근 경로: {pth['path']} — {pth['note']}" for pth in model_eval.free_paths(model_id)]
    if not pr:
        lines = [f"- 오늘 실측 문항 {n}개의 토큰 사용량: 입력 {p:,} / 출력 {c:,}",
                 "- OpenRouter 단가를 조회하지 못해 비용을 계산하지 않았습니다"]
        return "\n".join(lines + paths)
    cost = p * pr["prompt"] + c * pr["completion"]
    # 완전 무료면 $0 나열을 반복하지 않고 2줄 요약 + 일일 한도 안내 (2026-10-14 대표님 지시)
    if cost == 0:
        lines = [
            f"- 오늘 실측 문항 {n}개의 토큰 사용량: 입력 {p:,} / 출력 {c:,}",
            "- 비용: 무료 (OpenRouter 무료 티어) — 일일 한도·레이트리밋 확인 필요",
        ]
        return "\n".join(lines + paths)
    lines = [
        f"- 오늘 실측 문항 {n}개의 토큰 사용량: 입력 {p:,} / 출력 {c:,}",
        f"- OpenRouter 단가: 입력 ${pr['prompt'] * 1e6:.6f} / 출력 ${pr['completion'] * 1e6:.6f} (1M토큰당)",
        f"- {n}문항 실측 비용: ${cost:.6f}",
    ]
    if n:
        per = cost / n
        lines.append(f"- 같은 비율로 하루 100문항: ${per * 100:.6f} / 하루 1,000문항: ${per * 1000:.6f}")
    return "\n".join(lines + paths)


def _fail_block(ev):
    """BLOG-03 §2-3: 0점 문항의 모델 원문 전문(최대 2,000자) — 원문 공개용.

    축별 요약의 400자 축약본과 목적이 다르니 별개로 만든다.
    """
    out = []
    for d in ev.get("details", []):
        if d.get("score"):
            continue
        if d.get("judge_failed"):
            kind = "측정 결함 — 판관이 점수를 말하지 못함 (모델 실패 아님)"
        elif d.get("measurement_defect"):
            kind = "측정 결함 — 샌드박스 미실행·채점 불가 (모델 실패 아님)"
        elif d.get("source") in _FAIL_SOURCES:
            kind = f"호출 실패 ({d.get('source')})"
        else:
            kind = "모델 오답"
        out.append(f"--- Q{d['idx']} [{d['axis']}] {kind} / 점수 {d.get('score', 0)} ---")
        out.append((d.get("answer") or "").strip()[:2000] or "(응답 없음)")
    return "\n\n".join(out) or "(0점 문항 없음)"


def generate_model_eval_draft(keyword, article, model_id, fix_note=None, links_str="",
                              corrective=False, model_order=None):
    """무료 LLM 전용 7단 구조 블로그 글 생성(BLOG-03 §2-4). 실패 시 빈 문자열(폴백).

    AIK24-BLOG-02 (2026-10-19): 발행 게이트가 요구하는 두 가지를 이 경로에도 넣는다 —
    ① H2 `## 마무리 — …` 소제목(모델 평가글은 H3 8단으로 끝나 게이트에서 18건 누락됐다),
    ② 실제 링크(원문·공식 문서). 재생성 시에는 fix_note 로 교정 지시가 들어온다.
    """
    ev = _eval_block(model_id)
    # 전 문항 실패 시 블로그 생성 생략 (삭제된 [2a] 경로의 가드 이식)
    if ev.get("failed", 0) >= ev.get("max_score", 9):
        log(f"  전 문항 실패 → 모델 심층 분석 생략: {model_id}")
        return ""
    guide = model_eval.get_access_guide(model_id)
    leaderboard_block = _leaderboard_block(model_id)
    cost_block = _cost_block(model_id, ev)
    fail_block = _fail_block(ev)
    access_block = "\n".join(
        f"- {pth['path']}: {pth['note']}" for pth in model_eval.free_paths(model_id)
    )

    # 우리 테스트 결과 — 축별 원시 결과 + 문항별 실제 답변(LLM이 지어내지 못하게 원문 주입)
    axis_block = {}
    for d in ev.get("details", []):
        ans = (d.get("answer") or "").replace("\n", " ")[:400]
        if d.get("judge_failed"):
            mark = "측정 결함(판관 파싱 실패)"
        elif d.get("measurement_defect"):
            mark = "측정 결함(샌드박스 미실행·채점 불가)"
        elif d["source"] in _FAIL_SOURCES:
            mark = "응답 실패(레이트리밋 등)"
        else:
            mark = "정답" if d["score"] else "오답"
        axis_block.setdefault(d["axis"], []).append(f"Q{d['idx']} {mark} — 답변: {ans or '(응답 없음)'}")
    # BLOG-03 §1-3: 측정 결함 문항은 점수 분모에서도 빠진다. 축 제목 N/M도 같이 뺀다.
    axis_sections = []
    for a, v in axis_block.items():
        graded = [x for x in v if "측정 결함" not in x]
        correct = sum(1 for x in graded if x.split(" — 답변: ")[0].endswith(" 정답"))
        axis_sections.append(
            f"### {model_eval.AXIS_LABELS.get(a, a)} ({model_eval._AXIS_DIFFICULTY.get(a, '')}, "
            f"{correct}/{len(graded)} 정답)\n" + "\n".join(v)
        )
    test_block = "\n".join(axis_sections) or "(평가 결과 없음)"

    # BLOG-03 §2-4: 기존 §3 '남들의 의견'(sig_block)은 §4 '돈'으로 통합했다 — 코드는 삭제.

    # EVAL-03 §4-1 호출 안정성 — 실패를 숨기지 않고 그대로 쓴다. 원인은 로그 문자열 그대로.
    st = model_eval.call_stability(ev)
    reason_line = ", ".join(f"{k} {v}건" for k, v in st["by_reason"].items()) or "없음"
    axis_line = ", ".join(
        f"{model_eval.AXIS_LABELS.get(a, a)} {v}문항" for a, v in st["by_axis"].items()
    ) or "없음"
    st_block = (
        f"- 전체 문항 {st['total']}개 중 실제 실행 {st['ran']}개, 호출 실패 {st['failed']}개 "
        f"(실패율 {st['rate']:.0%})\n"
        f"- 실패 원인: {reason_line}\n"
        f"- 실패가 몰린 축: {axis_line}\n"
        f"- 판정: {st['verdict']}"
    )

    system_prompt = (
        "당신은 AI 모델을 정직하게 평가하는 한국어 테크 블로거입니다. "
        "중국어(한자)는 절대 사용하지 말고 순수 한국어로만 작성하세요."
    )
    # AIK24-BLOG-01: 규칙 prepend — 모델 심층 분석 경로
    system_prompt = (_BLOG_RULES + "\n\n" + system_prompt) if _BLOG_RULES else system_prompt
    user_prompt = (
        f"무료 LLM '{model_id}'에 대한 실무 투입 판단 블로그 글을 작성해주세요.\n\n"
        f"이 글의 독자는 돈을 쓰기 싫어하고, 성능 좋은 무료 코딩 LLM이 뭔지 항상 찾는 사람입니다.\n"
        f"독자가 이 글을 읽고 '그래서 이 모델을 쓸까 말까'를 결정할 수 있게 쓰세요.\n\n"
        f"## 반드시 지킬 구조 (8단, 이 순서 그대로)\n"
        f"### 1. 한 줄 판단 + 순위\n"
        f"- 첫 줄에 결론을 박습니다. 예: '지금 당장 서브에이전트로 투입해도 됩니다' / "
        f"'아직 검증이 부족해 파일럿으로만 쓰세요'.\n"
        f"- 바로 다음 줄에 리더보드 순위를 적습니다. 예: 'AI코리아24 실측 리더보드: 무료 코딩 모델 5개 중 2위'.\n"
        f"- 비교 데이터가 2개 미만이면 순위를 매기지 말고 '비교 데이터 축적 중 — 단독 평가'라고 명시하세요.\n"
        f"- [절대 규칙] 리더보드에 없는 모델(유료 모델 포함)과의 급수 비교 표현(예: '○○급', '○○ 수준')은 쓰지 마세요.\n"
        f"  비교는 아래 리더보드 안의 모델끼리 점수 차이로만 서술합니다.\n"
        f"- [절대 규칙] 6절의 호출 안정성이 나쁘면 반드시 첫 줄 판단에 반영하세요.\n\n"
        f"### 2. 왜 이 순위인가 — 실무 축별 결과 (4축)\n"
        f"- 아래는 AI코리아24가 오늘 직접 API로 실측한 결과입니다. "
        f"**숫자와 모델 답변은 그대로 인용하세요. 해석을 지어내지 마세요.**\n"
        f"- 원시 결과: {ev.get('label', '')}\n"
        f"```\n{test_block}\n```\n"
        f"- 축마다 소제목을 달고 **구체적 관찰 1~2줄**을 쓰세요. [절대 규칙] "
        f"'지시를 잘 따름' 같은 추상 평가는 금지. "
        f"답변 원문의 구체적 사실만 적으세요.\n"
        f"- **오답은 숨기지 말고** 왜 틀렸는지 1~2줄로 적으세요. 실패가 독자에게 가장 쓸모있습니다.\n\n"
        f"### 3. 실패 사례 상세 — 원문 공개\n"
        f"- 점수를 깎은 문항의 **모델 답변 원문을 코드블록으로 그대로** 싣고, 어디서 빗나갔는지 짚으세요.\n"
        f"- 원문은 아래 데이터를 그대로 씁니다. 요약·수정을 하지 마세요.\n"
        f"```\n{fail_block}\n```\n"
        f"- 채점 결함(판관 파싱 실패)으로 0점이 된 문항이 있으면 '모델 실패가 아니라 측정 실패'임을 분명히 하세요.\n\n"
        f"### 4. 비용 — 무료인가, 유료면 얼마인가\n"
        f"- 아래는 오늘 실측으로 확인한 값입니다. **수치를 바꾸지 마세요.**\n"
        f"```\n{cost_block}\n```\n"
        f"- 비용이 $0(무료)이면 '$0.000000' 나열을 반복하지 마세요. 무료 확인 1줄 + 일일 한도·레이트리밋 안내 1줄로 씁니다.\n"
        f"- 유료면 '12문항 실측 비용 $0.00X'를 기준으로 하루 100문항·1,000문항 사용 시 예상 비용을 "
        f"**단순 비례로만** 계산해 적으세요.\n"
        f"  '~정도 들 것 같다'는 추정은 금지. 계산식만 씁니다.\n"
        f"- [절대 규칙] '무료'라는 말은 무료 경로가 실제로 확인될 때만 쓰세요.\n\n"
        f"### 5. 어디서, 어떻게 쓰나\n"
        f"- 무료 경로를 유료보다 먼저 안내하세요. 아래 정보를 그대로 쓰세요.\n"
        f"```\n{access_block}\n```\n"
        f"- 다음 문장을 자연스럽게 포함하세요: {guide}\n"
        f"- OpenCode 설정 한 줄(프로바이더·모델 ID 검색어)을 반드시 포함하세요. 독자는 OpenCode 사용자입니다.\n\n"
        f"### 6. 호출 안정성\n"
        f"- 아래는 오늘 실측 중 실제 실패 기록입니다. **숫자를 고치거나 실패를 숨기지 마세요.**\n"
        f"```\n{st_block}\n```\n"
        f"- 마지막에 독자를 위한 해석 1~2줄: 실제로 쓸 수 있는 조언으로.\n"
        f"- [절대 규칙] 실패율이 25% 이상이면 '성능과 무관하게 현 시점 무료로는 실무 투입이 어렵다'고 "
        f"명확히 쓰세요.\n\n"
        f"### 7. 한계\n"
        f"- 이 글이 답하지 못하는 것을 정직하게 적으세요: 문항 수로 커버하지 못한 영역, 1회 실측의 한계, 측정 결함의 영향.\n"
        f"- 마지막 줄에 이 한 줄을 넣으세요: '이 순위는 리더보드에 새 모델이 들어오면 바뀔 수 있습니다.'\n\n"
        f"### 8. 정리 — 이런 때 쓰세요\n"
        f"- 위 1~7절을 5~6문장으로 요약하세요. 언제 쓰면 좋은지, OpenCode에서 쓸 수 있다는 점을 반드시 포함하세요.\n"
        f"- 마지막 문장은 총평 한 줄: 이 모델이 좋은 모델인지, 아니면 아직인지를 분명히 하세요.\n"
        f"- 제조사의 공개 발표 등 확인할 수 있는 출시·회사 정보가 있으면 1~2문장으로 덧붙이세요. 없으면 쓰지 마세요. 지어내지 마세요.\n\n"
        f"### 9. 마무리 — 오늘 바로 할지 결정하는 3단계 (H2 소제목)\n"
        f"- 8단 뒤에 **H2 소제목**(`##`, `###` 아님)을 정확히 이 형식으로 붙입니다: "
        f"`## 마무리 — 오늘 바로 할지 결정하는 3단계`\n"
        f"- 그 아래에 오늘 30분 안에 할 수 있는 실행 3단계를 번호 목록으로 씁니다. "
        f"1단계는 '무료 경로로 1회 호출해 보기'처럼 바로 실행 가능한 행동이어야 합니다.\n"
        f"- 아래 '인용 가능한 실제 링크' 블록의 `## 참고 자료` 섹션을 이 `## 마무리` **앞에** 둡니다.\n\n"
        f"## 리더보드 (같은 문항세트 v{model_eval.EVAL_QUESTIONS_VERSION}·같은 채점 기준)\n"
        f"```\n{leaderboard_block}\n```\n\n"
        f"## 톤 규칙\n"
        f"- 분량 제한 없음. 필요한 만큼 길게 씁니다.\n"
        f"- 순한국어, ~습니다/~입니다 정중 비즈니스 톤. 반말 절대 금지\n"
        f"- 중국어(한자) 사용 금지, 이모티콘 사용 금지\n"
        f"- **본문 첫 단락에서 '이번 글에서는', '살펴보겠습니다' 등 메타 도입문 절대 금지.** "
        f"한 줄 판단으로 바로 시작할 것\n"
        f"- 순위·비용 숫자는 주입된 데이터 그대로. 리더보드에 없는 모델과의 비교 표현 금지\n"
        f"- [절대 규칙] 본문 맨 앞에 `# 제목`을 반복하지 마세요. 제목은 TITLE: 줄에 한 번만 씁니다. "
        f"본문은 한 줄 판단으로 바로 시작합니다.\n"
        f"- [절대 규칙] 제목에 '[정직한 AI 평가]' 같은 대괄호 수식어를 붙이지 마세요.\n"
        f"- 브랜드명의 'AI'는 '아이'로 음역하지 말고 'AI'로 그대로 씁니다 (예: 인클루전AI).\n"
        f"- 구어체·은어를 쓰지 마세요. '손발 작업' 대신 '서브에이전트'처럼 정확한 역할 용어를 씁니다.\n"
        f"- '돈' 대신 '비용'이라 씁니다.\n\n"
        f"{links_str}"
        f"## 참고 기사\n"
        f"제목: {article.get('title', '')}\n"
        f"출처: {article.get('source', '')}\n"
        f"내용: {(article.get('description') or '')[:400]}\n\n"
        f"## 출력 형식\n"
        f"TITLE: [SEO에 최적화된 제목 — 형식: '{{브랜드 한글명}} {{모델명}}({{영문 모델 ID}}) {{N}}문항 실측 — {{판단 한 줄}}']\n"
        f"---\n"
        f"[마크다운 본문]"
        f"{fix_tail}"
    )

    if corrective:
        content = _quality_gate.strong_completion(
            user_prompt, system_prompt=system_prompt, max_tokens=7000, temperature=0.5,
            order=model_order or _quality_gate.STRONG_CANDIDATES)
    else:
        content = chat_completion(
            messages=[{"role": "user", "content": user_prompt}],
            system_prompt=system_prompt,
            max_tokens=7000,
            temperature=0.7,
        )
    if not content:
        log("  ❌ 모델 심층 분석 생성 실패")
        return ""
    cleaned = remove_chinese(content)
    if cleaned != content:
        log(f"  ⚠️ 중국어 문자 {len(content) - len(cleaned)}개 제거됨")
    log(f"  생성 완료(모델 심층 분석): {len(cleaned)}자")
    return cleaned


# ============================================
# 파일 번호 결정
# ============================================
def next_file_number(today_str):
    """AIK24-EMDASH-03: Astro 파일을 만들지 않으므로 디스크 스캔이 무의미하다.
    실행 시각(HHMMSS)을 시작번호로 써서 같은 날 재실행해도 썸네일 디렉터리명이 겹치지 않게 한다.
    (호출부가 실행마다 1씩 더하므로 한 실행 안에서는 계속 증가한다)"""
    return int(datetime.now(KST).strftime("%H%M%S"))

# ============================================
# 슬러그 생성
# ============================================
def make_slug(title):
    slug = title.strip()
    slug = re.sub(r"[^\w\s가-힣]", "", slug)
    slug = re.sub(r"\s+", "-", slug)
    slug = slug[:80].rstrip("-")
    return slug.lower()

# ============================================
# EmDash 단독 발행용 인메모리 초안 (AIK24-EMDASH-03)
# ============================================
# Astro 저장 제거로 src/content/blog/ 에 파일이 생기지 않는다. 아래 dict 가 곧 초안이다.
# 키로 쓰는 filepath 문자열(= "{today}-{num}-{slug}.md")은 더 이상 디스크 경로가 아니라
# 썸네일 디렉터리명(=slug) 을 만들어 내기 위한 식별자일 뿐이다.
_EMDASH_PENDING = {}  # filepath -> {"md": str, "links": [(news_id, comment_link)]}

# ============================================
# 블로그 초안 생성
# ============================================
def save_draft(gpt_output, keyword, file_num, today_str, articles=None):
    """GPT 출력 파싱 → EmDash 발행 대기 초안 생성. articles 전달 시 발행 후 D1 연결 목록 등록."""
    # 이모티콘 제거 (대표님 지시) — 저장 직전 유일한 통과 지점이라 여기서 한 번만
    stripped = remove_emoji(gpt_output)
    if stripped != gpt_output:
        log(f"  ✂️ 이모티콘 {len(gpt_output) - len(stripped)}자 제거됨")
        gpt_output = stripped
    # 브리핑 페이지 URL 조회 (체류시간 확보 — 자기 자신 링크 방지)
    if articles:
        for art in articles:
            news_id = art.get("id")
            if news_id:
                rows = query_d1(
                    f"SELECT b.date, bi.sort_order FROM briefing_items bi "
                    f"JOIN briefings b ON bi.briefing_id = b.id "
                    f"WHERE bi.news_id = {news_id} LIMIT 1"
                )
                if rows:
                    briefing_date = rows[0].get("date", "")
                    sort_order = rows[0].get("sort_order", 1)
                    art["_briefing_url"] = f"https://aikorea24.kr/briefing/{briefing_date}/#item-{sort_order}"
    filepath, seo_title = _save_file(gpt_output, keyword, file_num, today_str, articles)
    # deep_dive_url / 무료 LLM 코멘트 링크는 발행 후 실제 EmDash URL 로 연결한다.
    # (AIK24-EMDASH-03: Astro 저장 이 없어 발행 전에는 최종 URL 을 알 수 없다)
    if filepath:
        for art in articles or []:
            news_id = art.get("id")
            if news_id:
                _EMDASH_PENDING[filepath]["links"].append(
                    (news_id, art.get("v2_tag") == "free-llm")
                )
    return filepath, seo_title

# ============================================
# 유틸: 한국어 종결어미 패턴 (공통)
# ============================================
_KOREAN_SENTENCE_ENDINGS = (
    r'(?<!\d)[.!?](?!\d)|'  # 문장 부호 (숫자 사이가 아닌 경우만: 버전/소수점 제외)
    r'(?:'  # 한국어 종결어미들 (명확한 것만)
    r'습니다|입니다|했습니다|'  # 존댓말 과거/현재
    r'합니다|있습니다|였습니다|됩니다|'  # 존댓말 현재
    r'봅니다|듣습니다|옵니다|갑니다|줍니다|삽니다|팝니다|만듭니다|'  # 동사 존댓말
    r'생각합니다|느낍니다|알고 있습니다|모릅니다|'  # 심리/인지
    r'임|음|이다|한다|했다|'  # 명사형/서술형 (확실한 것만)
    r'요|함'  # 해요체/명사형 종결
    r')(?=[\s\.\!\?]|$)'
)

# 컴파일된 정규식 (성능 최적화)
_KOR_END_PATTERN = re.compile(_KOREAN_SENTENCE_ENDINGS)


# ============================================
# 유틸: 문장 경계에서 텍스트 자르기 (한국어 종결어미 고려) — 기존 호환용
# ============================================
def _truncate_at_sentence_boundary(text, max_len):
    """텍스트를 max_len 이하로 자르되, 한국어 문장 종결어미에서 자름."""
    if len(text) <= max_len:
        return text.strip()
    
    # max_len 근처에서 앞쪽으로 검색하며 종결어미 찾기
    search_start = max(0, max_len - 50)  # 여유분 50자
    truncated = text[:max_len]
    
    # max_len 이전의 마지막 종결어미 찾기
    matches = list(_KOR_END_PATTERN.finditer(truncated[search_start:]))
    
    if matches:
        # 가장 마지막 종결어미 위치 계산
        last_match = matches[-1]
        end_pos = search_start + last_match.end()
        return truncated[:end_pos].strip()
    
    # 종결어미 못 찾으면 공백에서 자름
    last_space = truncated.rfind(' ', search_start)
    if last_space > search_start:
        return truncated[:last_space].strip()
    
    # 그것도 안 되면 그냥 자름
    return truncated.strip()


# ============================================
# 유틸: 첫 번째 완전한 문장 추출 (description용)
# ============================================
def _extract_first_sentence(text, max_len=300):
    """텍스트에서 첫 번째 완전한 문장만 추출.
    
    마크다운 헤딩, 링크, 수평선이 포함된 경우, 이를 제거하고 첫 번째 실제 문장(한국어 종결어미 포함)을 추출.
    
    Args:
        text: 입력 텍스트 (마크다운 헤딩, 링크, 수평선 포함 가능)
        max_len: 최대 길이 (첫 문장이 너무 길면 안전장치로 자름)
    
    Returns:
        첫 번째 완전한 문장 (종결어미 포함)
    """
    if not text:
        return ""
    
    # 0. 선행 수평선(---, ***) 제거
    text = re.sub(r"^(\s*[-*]{3,}\s*)+", "", text)
    
    # 마크다운 헤딩, 링크, 강조, 줄바꿈 제거
    # 1. "서론:", "들어가며:", "시작하며:", "개요:" 프리픽스 제거
    text = re.sub(r"^##?\s*(서론|들어가며|시작하며|개요)\s*[:：]?\s*", "", text)
    # 2. 일반 헤딩 제거 (## 텍스트\n 또는 # 텍스트\n, 뒤따르는 공백 포함)
    text = re.sub(r"^##?\s+[^\n]+\n\s*", "", text)
    # 3. 마크다운 링크 제거 (맨 앞의 링크들) - [텍스트](URL) 패턴, 여러 개 연속 처리
    text = re.sub(r"^(\s*\[.*?\]\([^)]+\)\s*)+", "", text)
    # 4. 남은 마크다운 문법 제거
    text = re.sub(r"[#*>\n\s]+", " ", text).strip()
    
    if not text:
        return ""
    
    # 전체 텍스트에서 첫 번째 종결어미 찾기 (처음부터 검색)
    m = _KOR_END_PATTERN.search(text)
    if m:
        end_pos = m.end()
        # 첫 번째 종결어미 위치에서 문장 추출
        sentence_text = text[:end_pos]
        # 문장 시작점 찾기: 종결어미 앞쪽으로 역추적하여 문장 경계 찾기
        # 한국어 문장은 보통 ". ", "! ", "? ", "\n", 또는 종결어미+공백 뒤부터 시작
        last_boundary = -1
        for pattern in ['. ', '! ', '? ', '\n']:
            idx = sentence_text.rfind(pattern)
            if idx > last_boundary:
                last_boundary = idx
        # 한국어 종결어미 뒤 공백도 체크
        for ending in ['다 ', '요 ', '함 ', '습니다 ', '입니다 ', '했습니다 ', '합니다 ', '있습니다 ', '였습니다 ', '됩니다 ']:
            idx = sentence_text.rfind(ending)
            if idx > last_boundary:
                last_boundary = idx + len(ending) - 1
        
        if last_boundary > 0:
            start = last_boundary + 1
        else:
            start = 0
        
        first_sentence = sentence_text[start:end_pos].strip()
        # 너무 짧으면 (헤딩만 남은 경우) 전체에서 첫 종결어미까지
        if len(first_sentence) < 10:
            m2 = _KOR_END_PATTERN.search(text)
            if m2:
                return text[:m2.end()].strip()
        # 길이 제한 적용
        if len(first_sentence) > max_len:
            return first_sentence[:max_len].strip()
        return first_sentence
    
    # 종결어미 못 찾으면 max_len에서 공백 기준 자름
    last_space = text.rfind(' ', 0, max_len)
    if last_space > 0:
        return text[:last_space].strip()
    
    return text[:max_len].strip()


def _parse_title_body(gpt_output):
    """LLM 출력에서 TITLE 라인(및 바로 뒤 구분선)만 제거 → (title, content).

    주의: LLM이 본문 중간에 `---` 구분선을 넣는 경우가 있어 split("---")로
    자르면 본문 전체가 유실된다. TITLE 라인만 정규식으로 제거한다.
    """
    parts = gpt_output.split("TITLE:", 1)
    title = parts[1].split("\n", 1)[0].strip() if len(parts) > 1 else ""
    # 제목의 마크다운 백틱 제거 (제목에 `code` 형식 노출 방지)
    title = re.sub(r"`([^`]+)`", r"\1", title)
    body = re.sub(
        r"\ATITLE:[^\n]*\n(?:[ \t]*-{3,}[ \t]*\n)?", "", gpt_output, count=1
    ).strip()
    # BLOG-04 작업 2: EmDash가 title 필드를 별도 H1로 렌더링하므로 본문 H1은 중복이다.
    # 프롬프트에도 금지 규칙이 있지만 LLM이 습관적으로 붙이는 경우를 막는 안전망.
    body = re.sub(r"\A#\s+[^\n]*\n", "", body, count=1).strip()
    return title, body


def _save_file(gpt_output, keyword, file_num, today_str, articles=None):
    """GPT 출력 파싱 → EmDash 발행 대기 마크다운 생성 (디스크 저장 없음, 내부)."""
    # TITLE: ... / --- / 본문
    seo_title = keyword
    content = gpt_output
    if "TITLE:" in gpt_output:
        title_line, content = _parse_title_body(gpt_output)
        if title_line:
            seo_title = title_line
        # 본문 길이 검증: 1000자 미만이면 저장 거부 (품질 게이트)
        if len(content) < 1000:
            logger.warning(f"본문 짧음: {len(content)}자 (title={seo_title[:40]}) — 발행 거부")
            return None, None

    # AIK24-RENEWAL-01 C-2: 브리핑 원문 링크 주입 제거.
    # 브리핑 페이지(D-1 폐기)가 더 이상 생성되지 않아 /briefing/{date}/ 가 302로 죽는다.
    # 577개 기존 글은 대상 페이지가 살아 있어 유지하고, 새 글에는 주입하지 않는다.

    # title에서 따옴표 이스케이프 (YAML frontmatter 안전성)
    seo_title_escaped = seo_title.replace('"', "'")

    slug = make_slug(seo_title)
    filename = f"{today_str}-{file_num:03d}-{slug}.md"
    filepath = os.path.join(PROJECT_DIR, "src", "content", "blog", filename)

# description: "서론:", "들어가며:", "시작하며:", "개요:" 프리픽스 제거 + TITLE/--- 제거 + 일반 헤딩 제거 + 첫 번째 완전한 문장 추출
    # 1. TITLE: ... 제거 (content에 TITLE이 섞여있을 수 있음)
    desc_raw = re.sub(r"^TITLE:\s*[^\n]+\n", "", content)
    # 2. --- 구분자 이전 내용 제거
    desc_raw = re.sub(r"^---+\s*\n", "", desc_raw)
    # 3. "서론:", "들어가며:", "시작하며:", "개요:" 프리픽스 제거 (##?, #? 선택적)
    desc_raw = re.sub(r"^##?\s*(서론|들어가며|시작하며|개요)\s*[:：]?\s*|^(서론|들어가며|시작하며|개요)\s*[:：]?\s*", "", desc_raw)
    # 4. 일반 마크다운 헤딩 제거 (## 텍스트\n 또는 # 텍스트\n, 뒤따르는 공백 포함)
    desc_raw = re.sub(r"^##?\s+[^\n]+\n\s*", "", desc_raw)
    # 4b. 모델 평가글 삼중 중복 방지 (2026-10-14 대표님 지시): 제목이 "... N문항 실측 — 판단 한 줄"
    # 형식이고 본문 첫 줄도 같은 판단이라 description이 세 번째 중복이 된다. 첫 줄을 제외하고 추출한다.
    if "문항 실측 —" in seo_title:
        desc_raw = re.sub(r"^[^\n]+\n\s*", "", desc_raw, count=1)
    # 5. 남은 마크다운 문법 제거
    desc_raw = re.sub(r"[#*>\n\s]+", " ", desc_raw).strip()
    # 6. 첫 번째 완전한 문장 추출
    desc_raw = _extract_first_sentence(desc_raw, 300)
    desc_escaped = desc_raw.replace('"', "'")  # YAML frontmatter 안전성 (큰따옴표 이스케이프)

    now_kst = datetime.now(KST)
    date_str = now_kst.strftime("%Y-%m-%dT%H:%M:%S+09:00")

    thumbnail_file = os.path.join(PROJECT_DIR, "public", "images", slug, "thumbnail.webp")
    image_line = f'image: "/images/{slug}/thumbnail.webp"\n' if os.path.exists(thumbnail_file) else ""

    md = f"""---
title: "{seo_title_escaped}"
description: "{desc_escaped}"
date: {date_str}
category: "뉴스"
tags:
  - "{keyword.replace('"', "'")}"
draft: false
{image_line}
---

{content}
"""
    _EMDASH_PENDING[filepath] = {"md": md, "links": []}
    log(f"  EmDash 발행 대기: {filename}")
    return filepath, seo_title

# ============================================
# 썸네일 삽입 (frontmatter image 필드)
# ============================================
def _add_image_to_frontmatter(filepath, image_rel_path):
    """발행 대기 마크다운의 frontmatter 에 image: 주입 (디스크 쓰기 없음)."""
    if not filepath or not image_rel_path:
        return
    # placeholder 사본 검출: news-keyword-og.webp의 복사본이면 image: 필드 주입 안 함
    # (기본 OG 이미지가 그대로 노출되는 사고 방지, og:image도 비움)
    full_path = os.path.join(PROJECT_DIR, "public", image_rel_path.lstrip("/"))
    if is_placeholder_copy(full_path):
        log(f"  ⚠️ placeholder 사본 검출(MD5 일치), image 필드 생략: {image_rel_path}")
        return
    draft = _EMDASH_PENDING.get(filepath)
    if not draft:
        log(f"  ⚠️ image 필드 삽입 실패 (발행 대기 초안 없음): {image_rel_path}")
        return
    content = draft["md"]
    if re.search(r'^image:', content, re.MULTILINE):
        return
    # 모든 frontmatter 구조 대응: 첫 번째 --- 내부, 두 번째 --- 앞에 image: 필드 삽입
    # (draft: false 위치/존재 여부와 무관)
    parts = content.split('---', 2)
    if len(parts) < 2:
        log(f"  ⚠️ image 필드 삽입 실패 (frontmatter --- 구분자 없음)")
        return
    # parts[0] = before first --- (empty or whitespace)
    # parts[1] = frontmatter content (between the two ---)
    # parts[2] = body content (after the second ---)
    image_line = f'image: "{image_rel_path}"'
    # Insert image: right before the closing --- (inside frontmatter)
    draft["md"] = f"---{parts[1]}{image_line}\n---{parts[2] if len(parts) > 2 else ''}"
    log(f"  🖼️ image 필드 추가: {image_rel_path}")

from pipeline.infra.telegram import send_telegram
import model_eval

# ============================================
# EmDash 발행 (AIK24-EMDASH-01 단독화 — AIK24-EMDASH-03)
# ============================================
def _link_d1(url, links):
    """발행 성공 후 브리핑 deep_dive_url / 무료 LLM 코멘트 링크를 EmDash URL 로 연결."""
    for news_id, want_comment in links:
        # retry: 일시적 D1 네트워크 오류 대응 (2회 재시도)
        for attempt in range(3):
            if update_deep_dive_url(news_id, url):
                break
            if attempt < 2:
                log(f"  🔄 deep_dive_url 재시도 {attempt+1}/2...")
                time.sleep(2)
        else:
            log(f"  ⚠️ deep_dive_url 연결 최종 실패 (news_id={news_id}, 3회 모두 실패)")
        if want_comment:
            append_comment_link(news_id, url)


def _publish_generated_to_emdash(generated):
    """생성된 초안을 EmDash 에 publish. Astro 저장 이 없어 폴백이 없다 —
    실패한 글은 로그에만 남고 다음 글로 진행한다."""
    import yaml
    from emdash_publish import publish_post
    ok = 0
    for fp, title, _so, _ in generated:
        draft = _EMDASH_PENDING.get(fp)
        if not draft:
            log(f"  ⚠️ EmDash 발행 skip (초안 없음): {os.path.basename(fp)}")
            continue
        try:
            _, fm, body = draft["md"].split("---", 2)
            meta = yaml.safe_load(fm) or {}
        except Exception as e:
            log(f"  ⚠️ EmDash 발행 skip ({os.path.basename(fp)}): {e}")
            continue

        # AIK24-BLOG-02 2차 방어: 발행 직전 재검사. 1차(생성 직후)를 우회해 도착한 글을 여기서 막는다.
        # 검사 전에 결정적 수리(표 구분선·앞머리 H1)를 한 번 더 적용한다 — 발행되는 본문이 곧 수리본이 된다.
        body = body.strip()
        body, _fixes2 = _quality_gate.repair_markdown(body)
        if _fixes2:
            log("  🛠 자동 수리(2차): " + ", ".join(_fixes2))
        gate_issues = _quality_gate.screen_extended(body)
        if gate_issues:
            _quality_gate.hold(draft["md"], meta.get("title") or title, gate_issues,
                               reason="2차 게이트(발행 직전) 미달")
            continue

        url = publish_post(
            meta.get("title") or title, body,
            excerpt=meta.get("description"),
            featured_image=meta.get("image"),
            published_at=meta.get("date"),
        )
        if url:
            ok += 1
            log(f"  🚀 EmDash 발행: {url}")
            _link_d1(url, draft["links"])
            # AIK24-BLOG-02 3차 방어: 발행본 읽기 검증.
            # 발행 API 가 200 을 돌려줘도 동시 편집자가 낡은 사본을 저장하면 공개본이 되돌아간다
            # (2026-10-18 실측: 54블록으로 발행 → 6분 뒤 24블록으로 회귀). 그 사고를 감지해 알린다.
            try:
                _quality_gate.verify_published(url, expected_body=body, title=meta.get("title") or title)
            except Exception as _ve:
                log(f"  ⚠️ 발행본 검증 예외: {type(_ve).__name__}: {_ve}")
        else:
            log(f"  ❌ EmDash 발행 실패 (글 유실 — 폴백 없음): {os.path.basename(fp)}")
    log(f"  EmDash 발행 결과: 성공 {ok} / 전체 {len(generated)}")

# ============================================
# 메인
# ============================================
def main():
    load_env()
    today_str = datetime.now(KST).strftime("%Y-%m-%d")
    log(f"블로그 초안 생성 시작 ({today_str})")
    print()

    # 1. 오늘 브리핑 기사 조회
    log("[1/4] 브리핑 기사 조회 중...")
    try:
        articles = get_briefing_articles()
    except Exception as e:
        log(f"  브리핑 조회 실패: {e}")
        send_telegram(f"❌ [{today_str}] 블로그 초안 생성 실패: 브리핑 조회 오류")
        sys.exit(1)

    if not articles:
        log("  오늘 브리핑 없음, 종료")
        send_telegram(f"📭 [{today_str}] 블로그 초안 생성 스킵: 브리핑 없음")
        return
    print()

    # 2. 무료 모델 블로그 글 생성 (브리핑의 free-llm 항목만)
    log("[2/4] 무료 모델 블로그 초안 생성 중...")
    file_num = next_file_number(today_str)
    created = []

    for i, art in enumerate(articles, 1):
        art_id = art.get("id")
        title = art.get("title", "")
        link = art.get("link", "")
        deep_dive = art.get("deep_dive_url")
        sort_order = art.get("sort_order", i)

        # AIK24-BLOG-01 (2026-10-13 대표님 지시): v2_tag 스킵 제거.
        # 브리핑에 담긴 모든 항목이 블로그 후보 — free-llm + OpenRouter 모델 확인됨은
        # generate_draft()가 모델 평가글, 나머지는 뉴스글로 라우팅한다.

        if deep_dive:
            log(f"  [{i}/{len(articles)}] '{title[:50]}...' — 이미 연결됨, 스킵")
            created.append((None, title, sort_order, 0))
            continue

        log(f"  [{i}/{len(articles)}] '{title[:50]}...' 생성 중...")
        try:
            gpt_output = generate_draft(title, [art], "A")
            if not gpt_output:
                log(f"    ❌ 생성 실패")
                continue

            filepath, seo_title = save_draft(gpt_output, title, file_num, today_str, articles=[art])
            if not filepath:
                log(f"    ❌ 품질 미달로 발행 거부: '{title[:40]}'")
                continue

            # AIK24-BLOG-02 1차 방어 (2026-10-19): 발행 게이트 + 초안 수정 교정 최대 2회.
            # 배경: 게이트(emdash_precheck.check)가 어떤 스크립트에서도 호출되지 않아
            # 최근 발행 30건 중 기준 통과가 6건(20%)이었다 — 외부 링크 0개 22건, 마무리 없음 18건.
            # 미달이면 그대로 발행하지 않는다. 교정 2회 후에도 미달이면 이 글만 보류한다
            # (파이프라인은 다음 글로 계속 진행 — 볼륨이 0 이 되지 않게 하는 원칙).
            filepath, seo_title, _consumed, _gate_issues, _best_fp = _gate_and_fix(
                title, art, filepath, seo_title, file_num, today_str)
            if filepath is None:
                _quality_gate.hold(
                    (_EMDASH_PENDING.get(_best_fp) or {}).get("md", ""), title, _gate_issues or [],
                    reason="1차 게이트 미달(교정 2회 후에도 미달)")
                if _best_fp:
                    _EMDASH_PENDING.pop(_best_fp, None)
                continue
            file_num += _consumed

            created.append((filepath, seo_title or title, sort_order, 1))

            # 썸네일 생성 (Pexels)
            try:
                slug = os.path.basename(filepath).replace('.md', '').lower()
                thumb_rel = process_thumbnail(
                    link, slug,
                    title=title,
                    description=art.get("description", "")
                )
                if thumb_rel:
                    _add_image_to_frontmatter(filepath, thumb_rel)
            except Exception as thumb_e:
                log(f"  ⚠️ '{title[:40]}' 썸네일 생성 실패: {thumb_e}")
        except Exception as e:
            log(f"    ❌ '{title[:40]}' 생성 실패: {e}")

    # generated/skipped 분류 (thumbnail 검증에 필요하므로 여기서 미리 정의)
    generated = [c for c in created if c[0] is not None]
    skipped = [c for c in created if c[0] is None]

    # 썸네일 중복 검증 게이트 (Plan 28-02)
    log("[검증] 썸네일 중복 검사 중...")
    thumb_paths = []
    for fp, title, sort_order, _ in generated:
        slug = os.path.basename(fp).replace('.md', '').lower()
        thumb_path = os.path.join(PROJECT_DIR, "public", "images", slug, "thumbnail.webp")
        if os.path.exists(thumb_path):
            thumb_paths.append(thumb_path)
    
    dup_result = check_thumbnail_duplicates(thumb_paths)
    dup_count = len(dup_result["duplicates"])
    retry_count = 0  # Initialize here for scope
    
    if dup_count > 0:
        log(f"  ⚠️ 썸네일 중복 감지: {dup_count}개 쌍 (고유 {dup_result['unique_count']}/{len(thumb_paths)})")
        for p1, p2, h in dup_result["duplicates"]:
            log(f"    중복: {os.path.basename(os.path.dirname(p1))} = {os.path.basename(os.path.dirname(p2))} (MD5: {h[:8]}...)")
        
        # 중복된 포스트 재시도 (최대 2회, 다른 키워드 강제)
        # generated 리스트에서 중복된 파일 찾아 재생성
        duplicate_slugs = set()
        for p1, p2, _ in dup_result["duplicates"]:
            duplicate_slugs.add(os.path.basename(os.path.dirname(p1)))
            duplicate_slugs.add(os.path.basename(os.path.dirname(p2)))
        
        for fp, title, sort_order, _ in generated:
            slug = os.path.basename(fp).replace('.md', '').lower()
            if slug in duplicate_slugs and retry_count < 2:
                log(f"  🔄 중복 썸네일 재시도: {slug}")
                # 강제로 다른 키워드 사용 (DEEPSEEK_POOL에서 랜덤)
                try:
                    import random
                    forced_keyword = random.choice([k for k in DEEPSEEK_POOL if k != "abstract technology"])
                    # 재생성 시도 (실제로는 process_thumbnail이 내부에서 랜덤 선택하므로 그냥 재호출)
                    # 원본 article 정보 필요 - generated에는 filepath, title, sort_order만 있음
                    # article 링크/설명은 별도 저장 필요하므로 생략 (process_thumbnail이 내부에서 랜덤 fallback 처리)
                    thumb_rel = process_thumbnail(
                        "",  # link - not easily available here
                        slug,
                        title=title,
                        description=""
                    )
                    if thumb_rel:
                        _add_image_to_frontmatter(fp, thumb_rel)
                        retry_count += 1
                        log(f"    재생성 완료: {thumb_rel}")
                except Exception as retry_e:
                    log(f"    재시도 실패: {retry_e}")
        
        # 재검증
        thumb_paths = []
        for fp, title, sort_order, _ in generated:
            slug = os.path.basename(fp).replace('.md', '').lower()
            thumb_path = os.path.join(PROJECT_DIR, "public", "images", slug, "thumbnail.webp")
            if os.path.exists(thumb_path):
                thumb_paths.append(thumb_path)
        dup_result = check_thumbnail_duplicates(thumb_paths)
        dup_count = len(dup_result["duplicates"])
        if dup_count == 0:
            log(f"  ✅ 재시도 후 중복 해소: 고유 {dup_result['unique_count']}/{len(thumb_paths)}")
        else:
            log(f"  ⚠️ 재시도 후에도 중복 잔존: {dup_count}개 쌍")
    else:
        log(f"  ✅ 썸네일 중복 검증 통과: 고유 {dup_result['unique_count']}/{len(thumb_paths)}")

    # deep_dive_url이 없는 항목은 update_deep_dive_url이 save_draft 내에서 호출됨
    # (save_draft → articles 파라미터로 전달된 기사들의 id로 deep_dive_url 업데이트)
    print()

    # 3. 텔레그램 알림
    log("[3/4] 텔레그램 알림...")
    if generated:
        msg_lines = [f"🤖 <b>[{today_str}] 블로그 발행 완료</b>"]
        msg_lines.append(f"\n📝 생성: {len(generated)}건")
        for fp, title, sort_order, _ in generated:
            fname = os.path.basename(fp)
            msg_lines.append(f"\n  #{sort_order} {title[:60]} → {fname}")
        msg_lines.append(f"\n🔗 딥링크 연결 완료")
        if dup_count > 0:
            msg_lines.append(f"\n⚠️ 썸네일 중복: {dup_count}쌍 감지 (재시도 {retry_count}건)")
        else:
            msg_lines.append(f"\n✅ 썸네일 중복 검증 통과")
        if skipped:
            msg_lines.append(f"\n⏭ 이미 연결됨: {len(skipped)}건")
        send_telegram("\n".join(msg_lines))
    # elif skipped or not generated:
    #     알림 생략: 생성된 글 없을 때만 로그만 남김 (텔레그램 알림 불필요)
    else:
        log(f"  📭 생성된 글 없음 (skipped: {len(skipped)}건) — 텔레그램 알림 생략")
    print()

    # 4. 완료
    log(f"[4/5] 완료! 생성: {len(generated)}건, 스킵(이미연결): {len(skipped)}건")
    for fp, title, sort_order, _ in generated:
        log(f"  ✅ #{sort_order} {title[:60]}")
    for _, title, sort_order, _ in skipped:
        log(f"  ⏭ #{sort_order} {title[:60]} (이미 연결됨)")

    # 5. 사후 검증 (중복 ID, frontmatter 정합성)
    log("[5] 블로그 포스트 검증 중...")
    try:
        import validate_blog_posts as vbp
        if not vbp.validate_all():
            log("  ⚠️ 블로그 포스트 검증 경고 발생 (계속 진행)")
        else:
            log("  ✅ 검증 통과")
    except Exception as e:
        log(f"  ⚠️ 검증 예외: {e}")

    # 5b. 발행 전 품질 체크리스트 (Plan 28-03)
    log("[5b] 발행 전 썸네일 품질 체크리스트...")
    quality_issues = []
    quality_passed = 0
    for fp, title, sort_order, _ in generated:
        slug = os.path.basename(fp).replace('.md', '').lower()
        thumb_path = os.path.join(PROJECT_DIR, "public", "images", slug, "thumbnail.webp")
        if os.path.exists(thumb_path):
            is_valid, reason = validate_thumbnail_quality(thumb_path)
            file_size = os.path.getsize(thumb_path)
            if is_valid:
                # placeholder 사본 검출: 품질은 OK지만 image 필드에서 제외했으므로 이슈로 카운트
                if is_placeholder_copy(thumb_path):
                    log(f"  ⚠️ {slug}: placeholder 사본 (image 필드 생략됨, {file_size:,} bytes)")
                    quality_issues.append((slug, "placeholder 사본 (image 필드 생략)"))
                else:
                    log(f"  ✅ {slug}: {file_size:,} bytes, 800x800, WebP")
                    quality_passed += 1
            else:
                log(f"  ❌ {slug}: {reason} ({file_size:,} bytes)")
                quality_issues.append((slug, reason))
        else:
            log(f"  ⚠️ {slug}: 썸네일 파일 없음")
            quality_issues.append((slug, "파일 없음"))
    
    log(f"  품질 체크리스트: {quality_passed}/{len(generated)} 통과, {len(quality_issues)} 이슈")
    if quality_issues:
        log(f"  ⚠️ 품질 이슈: {quality_issues}")

    # 모든 썸네일 실패 시 배포 차단 (Task 28.1-02)
    if quality_passed == 0 and len(quality_issues) > 0 and len(generated) > 0:
        log("  ❌ 모든 썸네일 품질 검증 실패 — 배포 차단")
        send_telegram(f"❌ [{today_str}] 썸네일 전면 실패: {len(quality_issues)}건 — 배포 차단됨")
        return

    # 5c. EmDash 단독 발행 (AIK24-EMDASH-03). Astro 저장 이 없으므로 여기서 실패한 글은
    # 유실된다 — 실패는 로그로만 남기고 다음 글로 진행한다(파이프라인은 계속된다).
    if generated:
        log("[5c] EmDash 발행 중...")
        _publish_generated_to_emdash(generated)
        _gate_summary = _quality_gate.summary_line()
        if _gate_summary:
            log("  " + _gate_summary)

    # 5e. AIK24-PIPE-05 §3-3: 무료 모델 중 "글이 없는" 모델의 초안 자동 작성.
    # 지시서 §5 — **자동 발행 금지.** 상태는 draft 고정이고 검수 주체(시니어 2/대표님)를 기다린다.
    # 브리핑에 실린 모델만 대상으로 한다(독자가 본 모델에 글이 없는 경우를 메우는 것이 목적).
    try:
        import blog_link_resolver
        log("[5e] 무료 모델 글 필요 큐 처리 (draft 자동 작성)...")
        _d = blog_link_resolver.create_drafts(limit=3, only_in_briefing=True)
        log(f"  draft 생성: {_d.get('created', 0)}건 / 스킵 {_d.get('skipped', 0)}건")
    except Exception as e:
        log(f"  ⚠️ 글 필요 큐 처리 실패(무시하고 계속): {type(e).__name__}: {str(e)[:160]}")

    # 5d. 보류 글 복구 (AIK24-BLOG-02): 게이트가 보류한 글은 scripts/logs/rejected/ 에 남는다.
    # 보류 사유의 대부분은 '표 0개' 하나다. 같은 실행 안에서 표만 추가해 복구하면 볼륨이 죽지 않는다
    # (2026-10-19 실측: 09:30 실행 보류 2건 모두 표 결함 → 표 교정으로 3,700자/3,200자로 복구·발행).
    try:
        import republish_held
        log("[5d] 보류 글 복구 시도...")
        _rec = republish_held.recover_since(today_str, do_publish=True, limit=5)
        # 복구 발행분은 deep_dive_url 을 **반드시** 연결한다. 연결하지 않으면 다음 실행이 같은
        # 기사를 후보로 다시 잡아 중복 발행된다(2026-10-19 실측: 복구 2건이 D1 에서 NULL 로 남았다).
        for _t, _u in _rec.get("urls", []):
            _want = republish_held.norm_title(_t)
            for _a in articles:
                _have = republish_held.norm_title(_a.get("title") or "")
                if not _want or not _have:
                    continue
                if _want == _have or _want in _have or _have in _want:
                    if not _a.get("deep_dive_url"):
                        _link_d1(_u, [(_a.get("id"), bool(_a.get("comment")))])
                    break
    except Exception as e:
        log(f"  ⚠️ 보류 글 복구 실패(무시하고 계속): {type(e).__name__}: {e}")

    # 6. 자동 배포 (새 블로그 포스트가 생성되었거나 미커밋 파일이 있으면)
    # AIK24-EFFICIENCY-02: 파이프라인 경로에서는 run_pipeline.py 의 Step 6(deploy.sh)이
    # 1분 뒤에 배포한다. 여기서 또 배포해 62초를 중복으로 썼다. standalone 실행은 그대로.
    if os.environ.get("PIPELINE_MODE") == "1":
        log("[6] Cloudflare 배포 스킵 (파이프라인 모드 — Step 6에서 1회 배포)")
        return

    # 미커밋 블로그 파일 감지 (git status --porcelain)
    untracked_blog_files = []
    try:
        import subprocess
        git_status = subprocess.run(
            ["git", "status", "--porcelain", "src/content/blog/"],
            capture_output=True, text=True, timeout=10, cwd=PROJECT_DIR
        )
        if git_status.returncode == 0:
            for line in git_status.stdout.strip().split('\n'):
                if line and (line.startswith('??') or line.startswith('A ')):
                    untracked_blog_files.append(line[3:].strip())
    except Exception as e:
        log(f"  ⚠️ git status 확인 실패: {e}")

    if generated or untracked_blog_files:
        log("[6] Cloudflare 배포 중...")
        if untracked_blog_files:
            log(f"  📦 미커밋 블로그 파일 {len(untracked_blog_files)}개 감지 → 배포 실행")
            for f in untracked_blog_files[:5]:  # 최대 5개만 로그
                log(f"    - {f}")
            if len(untracked_blog_files) > 5:
                log(f"    ... 외 {len(untracked_blog_files) - 5}개")
        import subprocess
        try:
            # AIK24-BLOG-01: Pages → Workers 이전으로 wrangler pages deploy 대상이 사라졌다
            # (실측 오류: The Pages project "aikorea24" does not exist).
            # scripts/deploy.sh = 빌드 + Workers 배포 + sitemap ping 가 유일한 배포 경로.
            deploy_env = dict(os.environ)
            deploy_result = subprocess.run(
                ["npm", "run", "deploy"], capture_output=True, text=True,
                timeout=900, cwd=PROJECT_DIR, env=deploy_env
            )
            if deploy_result.returncode == 0:
                log("  ✅ 배포 완료: https://aikorea24.kr")
                # 실제로 생성된 글이 있을 때만 배포 완료 알림 (미커밋 재배포 시 중복 방지)
                if generated:
                    send_telegram(f"🚀 [{today_str}] 블로그 {len(generated)}건 배포 완료")
                else:
                    log("  ℹ️ 신규 생성 글 없음 → 배포 알림 생략 (미커밋 파일 재배포)")
            else:
                log(f"  ❌ 배포 실패: {deploy_result.stderr[:200]}")
                send_telegram(f"❌ [{today_str}] 블로그 배포 실패")
        except Exception as deploy_e:
            log(f"  ⚠️ 배포 예외: {deploy_e}")
            send_telegram(f"⚠️ [{today_str}] 블로그 배포 예외: {str(deploy_e)[:100]}")


if __name__ == "__main__":
    main()
