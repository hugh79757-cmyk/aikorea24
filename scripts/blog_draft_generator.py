#!/usr/bin/env python3
"""
aikorea24 블로그 초안 자동 생성기
- D1 DB에서 오늘 수집된 뉴스 중 고단가 키워드 포함 기사 조회
- 키워드별 기사 그룹핑 → OpenAI 블로그 초안 생성
- src/content/blog/ 에 마크다운 파일 저장
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

# ============================================
# 고단가 키워드 테이블 (deprecated: 브리핑 기사 직접 사용)
# ============================================

# ============================================
# model_router (threads/v3)
# ============================================
from model_router import chat_completion
from auto_thumbnail import process_thumbnail, check_thumbnail_duplicates, validate_thumbnail_quality, DEEPSEEK_POOL

ENV_PATH = os.path.join(PROJECT_DIR, ".env")
DB_ID = "bec650ce-f732-46bc-87c0-bd76ed17e42a"

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
    import subprocess, json, re
    cmd = [_WRANGLER, "d1", "execute", _DB, "--remote", "--command", sql]
    env = dict(os.environ)
    env.pop("CLOUDFLARE_API_TOKEN", None)  # profile 우선 사용
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=30, env=env, cwd=PROJECT_DIR)
        if r.returncode != 0:
            log(f"  wrangler 오류 (rc={r.returncode}): {r.stderr[:200]}")
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

def get_today_briefing_id():
    """오늘 발행된 브리핑 ID 조회 (없으면 None)."""
    today = date.today().strftime("%Y-%m-%d")
    try:
        rows = query_d1(
            f"SELECT id FROM briefings WHERE date LIKE '{today}%' AND status = 'published' ORDER BY date DESC LIMIT 1"
        )
        return rows[0]["id"] if rows else None
    except Exception as e:
        log(f"  브리핑 조회 실패: {e}")
        return None

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
               bi.sort_order, bi.comment, bi.deep_dive_url
        FROM briefing_items bi
        JOIN news n ON bi.news_id = n.id
        WHERE bi.briefing_id = {briefing_id}
        ORDER BY bi.sort_order
    """
    rows = query_d1(sql)
    log(f"오늘 브리핑 기사: {len(rows)}건 (briefing_id={briefing_id})")
    return rows

# ============================================
# 블로그 초안 생성 (MiMo v2.5 via model_router)
# ============================================
def generate_draft(keyword, articles, grade, retry_count=0):
    is_deep = len(articles) == 1

    # 기사 텍스트 조립 — 원문 URL·출처·발행일 포함 (Task 1)
    article_lines = []
    articles_with_url = []
    for i, a in enumerate(articles, 1):
        desc = (a.get("description") or "")[:300]
        link = a.get("link", "") or ""
        source = a.get("source", "") or ""
        published_at = a.get("published_at", "") or ""
        article_lines.append(
            f"[기사 {i}]\n"
            f"제목: {a['title']}\n"
            f"매체: {source}\n"
            f"원문 URL: {link}\n"
            f"원문 발행일: {published_at}\n"
            f"내용: {desc}"
        )
        if link:
            articles_with_url.append(a)

    articles_str = "\n\n".join(article_lines)

    # 원문 URL이 없는 기사가 있으면 경고 (초안 큐 보관 대상)
    articles_without_url = [a for a in articles if not (a.get("link") or "")]
    if articles_without_url:
        log(f"  ⚠️ 원문 URL 없는 기사 {len(articles_without_url)}건 — 자동 발행 제외 대상")

    # GPT 프롬프트 — 원문 분류·조건 분기·출처 강제·content_type별 섹션 포함 (Task 2)
    prompt_extra = ""
    if articles_without_url:
        prompt_extra += (
            f"\n\n[⚠️ 주의: 아래 {'여러' if not is_deep else '한'} 기사 중 "
            f"원문 URL이 없는 기사가 있습니다. 해당 기사의 수치는 '원문 기준'으로 표기하고, "
            f"가능하면 다른 기사의 원문 URL로 교차 확인하십시오. "
            f"URL을 임의로 생성하지 마십시오.]\n"
        )

    common_rules = f"""
[사전 분석 - 반드시 먼저 수행]
아래 원문을 분석하여 다음 플래그를 판정하라. 결과는 내부적으로만 사용한다.
- has_numeric: 수치 데이터(금액/퍼센트/성능수치/사용자수/날짜별 변화)가 2개 이상 있는가? (Y/N)
- has_comparison: 비교 대상이 2개 이상인가? (기업 vs 기업, 이전 vs 이후, 모델 vs 모델) (Y/N)
- has_source_entity: 특정 출처가 명시돼 있는가? (기업 실적발표, 조사기관 보고서, 논문, SEC 공시 등) (Y/N)
- content_type: [실적/시장] | [제품출시] | [연구/논문] | [사건/논란] | [정책/규제] 중 하나

[조건 분기 — 표 삽입 규칙]
- has_numeric=Y AND has_comparison=Y → 비교표 필수 (항목·값A·값B·변화율 열 포함, 모든 행 값 채워야 함)
- has_numeric=Y AND has_comparison=N → 사실확인표 필수 (지표·수치·기준일·출처 열 포함, 모든 행 값 채워야 함)
- has_numeric=N → 표 대신 핵심 요점 3줄로 대체
- content_type=[연구/논문] → 표 + 방법론 한 줄 명시 필수
- 표를 생성할 경우 모든 셀이 채워져야 한다. 빈 셀이 있으면 초안 reject 대상.

[출처 규칙 — 위반 시 재생성]
- 본문에 등장하는 모든 수치는 출처 각주 또는 인라인 링크를 가져야 한다.
- has_source_entity=Y인 경우: 원문 출처(기관명+보고서명)를 본문에 명시하고, 원문 URL을 [출처] 섹션에 최소 1개 넣는다.
- 출처를 확인할 수 없는 수치는 "~로 알려졌다" 대신 문장에서 삭제하거나 "원문 기준" 표기를 명시한다.
- 추측성 수치를 생성하지 않는다. 원문 URL을 그대로 Markdown 링크로 사용한다.

[content_type별 필수 섹션]
공통(항상): 한 문장 결론(첫 120자 내) → 본문 → [한국 독자 관점] 섹션 → [요약] 섹션
- [실적/시장]: 사실확인표 + "투자/사업 관점 시사점"(단, 투자권유 아님 명시)
- [제품출시]: 스펙/가격표 + "기존 대안과 비교" + "국내 사용 가능 여부"
- [연구/논문]: 방법론/한계 + 원논문 링크
- [사건/논란]: 사실관계 타임라인 + 입장 양측 병기
- [정책/규제]: "한국 현행 제도와 비교" 필수

[제목 규칙]
- 한국어 독자가 검색하는 키워드를 기준으로 제목을 작성한다.
- 영문 원제를 그대로 제목으로 쓰지 않는다. 반드시 한국어로 번역·요약한 제목을 사용한다.
- 제목에 영문이 섞이더라도 한글이 주가 되어야 한다.

[독자 행동·관련 허브]
- 글 마지막에 [관련 문서] 섹션을 넣어 aikorea24 내 관련 글(허브)로 연결한다.
  (정확한 URL이 없으면 글 제목만 링크 텍스트로 표시)
- 독자가 이 글을 읽은 뒤 취할 수 있는 구체적 행동 1~2개를 [액션] 항목 형태로 제시한다.
"""

    if is_deep:
        system_prompt = (
            "당신은 AI/테크 뉴스를 분석하는 한국어 블로거입니다. "
            "주어진 기사 하나를 깊이 분석하여 블로그 초안을 작성해주세요. "
            "중국어(한자)는 절대 사용하지 말고 순수 한국어로만 작성하세요."
        )
        user_prompt = (
            f"아래 '{keyword}' 관련 기사를 분석한 블로그 초안을 작성해주세요.\n\n"
            f"## 요구사항\n"
            f"- 제목: '{keyword}' 키워드가 자연스럽게 포함된 SEO 최적화 제목 (한글 우선)\n"
            f"- 본문: 1500자 이상, 소제목(##) 3개 이상 포함\n"
            f"- 기사의 배경/의미/전망을 분석, 독자가 쉽게 이해할 수 있도록\n"
            f"- 기사 수치·비교 데이터가 있으면 적절한 표를 반드시 포함\n"
            f"- 마지막에 📌 **요약** 섹션 + [한국 독자 관점] 섹션 + [관련 문서] 섹션 포함\n"
            f"- 순한국어, 전문적이면서도 친근한 ~습니다/~입니다 정중 비즈니스 톤\n"
            f"- [중요] 모든 문장은 '~합니다/~입니다/~했습니다' 체로 통일. 반말('~다/~했다/~임') 절대 금지\n"
            f"- [중요] 중국어(한자) 사용 금지. 반드시 순수 한국어로만 작성할 것\n"
            f"- [중요] **본문 첫 단락(도입단락)에서 '본 포스트에서는...', '이번 글에서는...', "
            f"'살펴보겠습니다', '알아보겠습니다', '다루겠습니다' 등 메타 성격의 도입문(메타 도입문) 절대 금지.** "
            f"기사의 실질적 핵심 내용(사실, 수치, 인용, 분석 등)으로 바로 시작할 것.\n"
            f"{common_rules}\n\n"
            f"## 출력 형식\n"
            f"TITLE: [SEO에 최적화된 제목]\n"
            f"---\n"
            f"[마크다운 본문]\n\n"
            f"## 원문 기사\n{articles_str}"
            f"{prompt_extra}"
        )
    else:
        system_prompt = (
            "당신은 AI/테크 뉴스를 분석하는 한국어 블로거입니다. "
            "여러 기사를 종합하여 트렌드 분석 블로그 초안을 작성해주세요. "
            " 중국어(한자)는 절대 사용하지 말고 순수 한국어로만 작성하세요."
        )
        user_prompt = (
            f"아래 '{keyword}' 관련 여러 기사를 종합한 블로그 초안을 작성해주세요.\n\n"
            f"## 요구사항\n"
            f"- 제목: '{keyword}' 관련 트렌드가 드러나는 SEO 최적화 제목 (한글 우선)\n"
            f"- 본문: 2000자 이상, 소제목(##) 3개 이상 포함\n"
            f"- 각 기사의 핵심 내용을 비교/종합하여 트렌드 분석\n"
            f"- 여러 기사에 수치·비교 데이터가 있으면 비교표를 반드시 포함\n"
            f"- 마지막에 📌 **요약** 섹션 + [한국 독자 관점] 섹션 + [관련 문서] 섹션 포함\n"
            f"- 순한국어, 전문적이면서도 친근한 ~습니다/~입니다 정중 비즈니스 톤\n"
            f"- [중요] 모든 문장은 '~합니다/~입니다/~했습니다' 체로 통일. 반말('~다/~했다/~임') 절대 금지\n"
            f"- [중요] 중국어(한자) 사용 금지. 반드시 순수 한국어로만 작성할 것\n"
            f"- [중요] **본문 첫 단락(도입단락)에서 '본 포스트에서는...', '이번 글에서는...', "
            f"'살펴보겠습니다', '알아보겠습니다', '다루겠습니다' 등 메타 성격의 도입문(메타 도입문) 절대 금지.** "
            f"기사의 실질적 핵심 내용(사실, 수치, 인용, 분석 등)으로 바로 시작할 것.\n"
            f"{common_rules}\n\n"
            f"## 출력 형식\n"
            f"TITLE: [SEO에 최적화된 제목]\n"
            f"---\n"
            f"[마크다운 본문]\n\n"
            f"## 원문 기사들\n{articles_str}"
            f"{prompt_extra}"
        )

    content = chat_completion(
        messages=[{"role": "user", "content": user_prompt}],
        system_prompt=system_prompt,
        max_tokens=3000,
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
# 파일 번호 결정
# ============================================
def next_file_number(today_str):
    pattern = os.path.join(PROJECT_DIR, "src", "content", "blog", f"{today_str}-*.md")
    existing = glob.glob(pattern)
    nums = []
    for f in existing:
        m = re.search(r"\d{4}-\d{2}-\d{2}-(\d+)-", f)
        if m:
            nums.append(int(m.group(1)))
    return max(nums) + 1 if nums else 1

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
# 블로그 파일 저장
# ============================================
def save_draft(gpt_output, keyword, file_num, today_str, articles=None):
    """GPT 출력 파싱 → .md 파일 저장. articles 전달 시 deep_dive_url 연결."""
    filepath, seo_title = _save_file(gpt_output, keyword, file_num, today_str)
    # deep_dive_url 연결 (slug 소문자: Astro가 content collection ID를 lowercase로 정규화)
    if articles and filepath:
        slug = filepath.stem if hasattr(filepath, 'stem') else os.path.basename(filepath).replace('.md', '')
        slug = slug.lower()
        blog_url = f"https://aikorea24.kr/blog/{slug}/"
        for art in articles:
            news_id = art.get("id")
            if news_id:
                # retry: 일시적 D1 네트워크 오류 대응 (2회 재시도)
                for attempt in range(3):
                    if update_deep_dive_url(news_id, blog_url):
                        break
                    if attempt < 2:
                        log(f"  🔄 deep_dive_url 재시도 {attempt+1}/2...")
                        time.sleep(2)
                else:
                    log(f"  ⚠️ deep_dive_url 연결 최종 실패 (news_id={news_id}, 3회 모두 실패)")
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
# 유틸: 숫자+단위 추출 정규식 (검수 게이트용)
# ============================================
# 숫자(정수/소수) + 단위(%, 억, 만, 달러, $, 배, 배율, 포인트, 퍼센트, 배)
_NUMERIC_UNIT_PATTERN = re.compile(
    r'(\d+[\.\d]*)\s*(%|억|만|달러|\$|배|배율|포인트|퍼센트)',
    re.IGNORECASE
)
# 보완: 숫자 뒤에 단위가 바로 붙는 경우 (예: "13%", "2배", "100억")
_NUMERIC_DIRECT_PATTERN = re.compile(
    r'(\d+[\.\d]*)(%|달러|\$|억|만|배|포인트|퍼센트)',
    re.IGNORECASE
)
# Markdown 링크 패턴: [텍스트](URL)
_MD_LINK_PATTERN = re.compile(r'\[([^\]]+)\]\(([^)]+)\)')
# 출처 엔티티 힌트: 기관명/보고서명 등이 포함된 단어 (대략적)
_SOURCE_ENTITY_HINTS = re.compile(
    r'(보고서|조사|발표|공시|데이터|통계|연구|논문|조사결과|분석|자료|기준|원문)',
    re.IGNORECASE
)

# 결론 신호어 패턴 (첫 120자 내 결론 판정용)
_CONCLUSION_SIGNAL_PATTERN = re.compile(
    r'(이다|로 나타났다|로 확인됐다|라는 결과다|것으로 나타났다|으로 나타났다|'
    r'로 조사됐다|로 밝혀졌다|로 드러났다|것으로 확인됐다|것으로 조사됐다|'
    r'것이다|라는 점이다|라는 것이다|수준이다|기록했다|증가했다|감소했다|'
    r'올랐다|내렸다|상승했다|하락했다|돌파했다|넘어섰다|보였다|보여줬다|'
    r'시작됐다|주목했다|확인됐다|밝혀졌다|드러났다|나타났다|조사됐다|기록됐다|'
    r'발표했다|공개했다|도입했다|출시했다|확대했다|축소했다|개선했다|하락세|상승세)',
    re.IGNORECASE
)

# 영문 비율 계산용 (한글/한자 제외 순수 영문 글자)
_LETTER_PATTERN = re.compile(r'[A-Za-z]')
_HANGUL_PATTERN = re.compile(r'[가-힣]')

# Markdown 표 파서
def _parse_markdown_tables(text):
    """텍스트에서 Markdown 표를 파싱하여 (헤더행, 데이터행들) 리스트 반환.
    각 행은 셀 문자열 리스트. 구분선 행(|---|...)은 무시.
    """
    tables = []
    lines = text.split('\n')
    in_table = False
    header = None
    rows = []

    for line in lines:
        stripped = line.strip()
        if not stripped.startswith('|') or not stripped.endswith('|'):
            if in_table:
                # 표 종료
                if header is not None and rows:
                    tables.append((header, rows))
                in_table = False
                header = None
                rows = []
            continue

        # 셀 분할
        cells = [c.strip() for c in stripped.split('|')[1:-1]]
        # 구분선 행 체크 (| --- | --- | 등)
        if all(re.match(r'^[-: ]+$', c) for c in cells):
            if in_table and header is not None:
                # 구분선 발견 → 기존 헤더 유지, 새로운 데이터 행수집 시작
                pass
            continue

        if not in_table:
            in_table = True
            header = cells
            rows = []
        else:
            rows.append(cells)

    if in_table and header is not None and rows:
        tables.append((header, rows))

    return tables

def _check_table_integrity(draft_text):
    """표 무결성 검수: 빈 셀(값이 비어있는 셀)이 있는지 확인.
    반환: (passed: bool, empty_cells: int, table_count: int)
    """
    tables = _parse_markdown_tables(draft_text)
    if not tables:
        return (True, 0, 0)  # 표가 없으면 통과 (표 강제는 프롬프트에서 처리)

    total_empty = 0
    table_count = len(tables)
    for header, rows in tables:
        all_cells = [header] + rows
        for row in all_cells:
            for cell in row:
                if cell == '':
                    total_empty += 1

    passed = total_empty == 0
    return (passed, total_empty, table_count)

def _check_title_language(title):
    """제목 언어 일관성 검수: 영문 비율이 40% 초과면 fail.
    title은 '#'이나 'TITLE:' 접두사가 제거된 순수 제목 문자열로 전달 필요.
    반환: (passed: bool, en_ratio: float)
    """
    if not title:
        return (True, 0.0)

    letters = _LETTER_PATTERN.findall(title)
    hanguls = _HANGUL_PATTERN.findall(title)
    total_letters = len(letters) + len(hanguls)

    if total_letters == 0:
        # 숫자·기호뿐이면 통과
        return (True, 0.0)

    en_ratio = len(letters) / total_letters
    passed = en_ratio <= 0.40
    return (passed, en_ratio)

def _check_first_120chars_conclusion(draft_text):
    """첫 120자 내 결론 신호어 포함 여부 검정.
    반환: (passed: bool, has_signal: bool, first_120: str)
    """
    if not draft_text:
        return (False, False, "")

    first_120 = draft_text[:120]
    has_signal = bool(_CONCLUSION_SIGNAL_PATTERN.search(first_120))
    passed = has_signal
    return (passed, has_signal, first_120)

def _find_numbers_without_source(draft_text):
    """출처 없는 숫자 검출 (heuristic).
    숫자+단위 패턴을 모두 찾고, 해당 문단에 링크 또는 출처 엔티티 힌트가 있는지 확인.
    반환: [(number_str, 문단_index, has_source: bool), ...]
    """
    if not draft_text:
        return []

    paragraphs = re.split(r'\n\n+', draft_text)
    results = []

    for pi, para in enumerate(paragraphs):
        # 문단에서 숫자+단위 패턴 모두 찾기
        # 직접 붙는 패턴 우선
        for m in _NUMERIC_DIRECT_PATTERN.finditer(para):
            num_str = m.group(0)
            # 같은 문단에 Markdown 링크나 출처 힌트가 있는지
            has_link = bool(_MD_LINK_PATTERN.search(para))
            has_source_hint = bool(_SOURCE_ENTITY_HINTS.search(para))
            has_source = has_link or has_source_hint
            results.append((num_str, pi, has_source))

        # 공백이 있는 패턴 (예: "13 %", "350 억")
        for m in _NUMERIC_UNIT_PATTERN.finditer(para):
            num_str = m.group(0)
            has_link = bool(_MD_LINK_PATTERN.search(para))
            has_source_hint = bool(_SOURCE_ENTITY_HINTS.search(para))
            has_source = has_link or has_source_hint
            # 중복 체크: 이미 direct 패턴에서 잡혔으면 skip
            if num_str not in [r[0] for r in results if r[1] == pi]:
                results.append((num_str, pi, has_source))

    return results

def _judge_generalness_llm(paragraphs, max_paragraphs=5):
    """LLM 일반론 판정: 각 문단이 특정 사실 없이 일반적으로 성립하는지 판정.
    비용 고려로 최대 max_paragraphs개만 검사.
    반환: {'general_count': int, 'total_checked': int, 'general_ratio': float, 'details': list}
    모델 호출이 불가능하면 {'error': '모델 호출 불가'} 반환.
    """
    if not paragraphs:
        return {'general_count': 0, 'total_checked': 0, 'general_ratio': 0.0, 'details': []}

    # 샘플 문단 선택 (앞에서부터 최대 max_paragraphs개)
    sample = paragraphs[:max_paragraphs]
    total_checked = len(sample)

    prompt_items = []
    for i, p in enumerate(sample, 1):
        # 빈 문단/너무 짧은 문단 스킵
        if len(p.strip()) < 20:
            continue
        prompt_items.append(f"문단 {i}:\n{p.strip()}\n\n")

    if not prompt_items:
        return {'general_count': 0, 'total_checked': 0, 'general_ratio': 0.0, 'details': []}

    # model_router.chat_completion 호출
    try:
        from model_router import chat_completion
        prompt_text = (
            "다음 각 문단이 특정 사실·수치·사건·인용 없이 일반적으로 성립하는 문장인지 판정하라. "
            "각 문단마다 'Y'(일반론) 또는 'N'(특정 사실 있음)으로만 줄마다 답하라. "
            "다른 말은 하지 마라.\n\n"
            + "".join(prompt_items)
        )
        response = chat_completion(
            messages=[{"role": "user", "content": prompt_text}],
            system_prompt="당신은 텍스트 분석 전문가다. 객관적으로 판정하라.",
            max_tokens=200,
            temperature=0.0,
        )
        if not response:
            return {'error': 'LLM 응답 없음'}

        lines = [l.strip() for l in response.strip().split('\n') if l.strip()]
        general_count = sum(1 for l in lines if l.upper() == 'Y')
        actual_checked = len(lines)

        return {
            'general_count': general_count,
            'total_checked': actual_checked,
            'general_ratio': general_count / actual_checked if actual_checked > 0 else 0.0,
            'details': lines,
        }
    except Exception as e:
        logger.warning(f"  ⚠️ LLM 일반론 판정 실패: {e}")
        return {'error': str(e)}


def validate_draft_quality(draft_text, articles):
    """발행 전 자동 검수 게이트 (heuristic 4 + LLM 1).
    반환: {
        'passed': bool,  # 전체 통과 여부
        'checks': {      # 항목별 결과
            'numbers_without_source': {'passed': bool, 'unmatched_count': int},
            'first_120_conclusion': {'passed': bool, 'has_signal': bool},
            'table_integrity': {'passed': bool, 'empty_cells': int, 'table_count': int},
            'title_language': {'passed': bool, 'en_ratio': float},
            'generalness': {'passed': bool, 'general_ratio': float, 'error': str|None},
        },
        'reasons': [str],  # 실패 사유 목록
    }
    """
    reasons = []
    checks = {}

    # 1. 출처 없는 숫자 (heuristic)
    num_results = _find_numbers_without_source(draft_text)
    unmatched = [r for r in num_results if not r[2]]
    checks['numbers_without_source'] = {
        'passed': len(unmatched) == 0,
        'unmatched_count': len(unmatched),
    }
    if unmatched:
        sample = unmatched[:3]
        reasons.append(
            f"출처 없는 숫자 {len(unmatched)}건 검출: {', '.join(r[0] for r in sample)}"
        )

    # 2. 첫 120자 결론 (heuristic)
    concl_passed, has_signal, first_120 = _check_first_120chars_conclusion(draft_text)
    checks['first_120_conclusion'] = {
        'passed': concl_passed,
        'has_signal': has_signal,
    }
    if not concl_passed:
        reasons.append(
            f"첫 120자에 결론 신호어 없음 (앞부분: '{first_120[:60]}...')"
        )

    # 3. 표 무결성 (heuristic)
    tbl_passed, empty_cells, table_count = _check_table_integrity(draft_text)
    checks['table_integrity'] = {
        'passed': tbl_passed,
        'empty_cells': empty_cells,
        'table_count': table_count,
    }
    if not tbl_passed:
        reasons.append(f"표에 빈 셀 {empty_cells}개 존재 (표 {table_count}개)")

    # 4. 제목 언어 일관성 (heuristic) — 제목 추출 필요
    # TITLE: ... 줄에서 제목 추출
    title = ""
    if "TITLE:" in draft_text:
        parts = draft_text.split("TITLE:", 1)
        title_line = parts[1].split("\n", 1)[0].strip()
        title = title_line
    elif draft_text.startswith("# "):
        title = draft_text.split("\n", 1)[0].strip("# ").strip()

    lang_passed, en_ratio = _check_title_language(title)
    checks['title_language'] = {
        'passed': lang_passed,
        'en_ratio': en_ratio,
    }
    if not lang_passed:
        reasons.append(f"제목 영문 비율 {en_ratio:.0%}로 40% 초과 (제목: '{title[:50]}')")

    # 5. 일반론 과다 (LLM) — 별도 호출
    paragraphs = [p.strip() for p in re.split(r'\n\n+', draft_text) if p.strip()]
    # 소제목(##) 라인 필터링: 순수 본문 문단만
    body_paras = [p for p in paragraphs if not p.startswith('##') and not p.startswith('TITLE')]
    generalness = _judge_generalness_llm(body_paras, max_paragraphs=5)
    if 'error' in generalness:
        # LLM 실패 시 경고만 하고 통과 처리 (과도한 발행 차단 방지)
        checks['generalness'] = {
            'passed': True,
            'general_ratio': 0.0,
            'error': generalness['error'],
        }
        reasons.append(f"일반론 판정 LLM 실패 (경고): {generalness['error']}")
    else:
        gen_ratio = generalness['general_ratio']
        gen_passed = gen_ratio <= 0.30
        checks['generalness'] = {
            'passed': gen_passed,
            'general_ratio': gen_ratio,
            'error': None,
        }
        if not gen_passed:
            reasons.append(f"일반론 문단 비율 {gen_ratio:.0%}로 30% 초과 (LLM 판정)")

    all_passed = all(c['passed'] for c in checks.values())
    return {
        'passed': all_passed,
        'checks': checks,
        'reasons': reasons,
    }


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


def _save_file(gpt_output, keyword, file_num, today_str):
    """GPT 출력 파싱 → .md 파일 저장 (내부)."""
    # TITLE: ... / --- / 본문
    seo_title = keyword
    content = gpt_output
    if "TITLE:" in gpt_output:
        parts = gpt_output.split("TITLE:", 1)
        title_line = parts[1].split("\n", 1)[0].strip()
        if title_line:
            seo_title = title_line
        if "---" in gpt_output:
            body_parts = gpt_output.split("---", 1)
            if len(body_parts) > 1:
                content = body_parts[1].strip()

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
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(md)
    log(f"  저장: {filename}")
    return filepath, seo_title

# ============================================
# 썸네일 삽입 (frontmatter image 필드)
# ============================================
def _add_image_to_frontmatter(filepath, image_rel_path):
    if not filepath or not image_rel_path:
        return
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()
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
    fm_content = parts[1]
    image_line = f'image: "{image_rel_path}"'
    # Insert image: right before the closing --- (inside frontmatter)
    updated = f"---{fm_content}{image_line}\n---{parts[2] if len(parts) > 2 else ''}"
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(updated)
        log(f"  🖼️ image 필드 추가: {image_rel_path}")
    except Exception as e:
        log(f"  ⚠️ image 필드 저장 실패: {e}")

from pipeline.infra.telegram import send_telegram


# ============================================
# 메인
# ============================================
def main():
    load_env()
    today_str = date.today().strftime("%Y-%m-%d")
    log(f"블로그 초안 생성 시작 ({today_str})")
    print()

    # 1. 오늘 브리핑 기사 조회
    log("[1/5] 브리핑 기사 조회 중...")
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

    # 2. 블로그 글 생성 (브리핑 기사별 1개씩)
    log("[2/5] 블로그 초안 생성 중...")
    file_num = next_file_number(today_str)
    created = []

    for i, art in enumerate(articles, 1):
        art_id = art.get("id")
        title = art.get("title", "")
        link = art.get("link", "")
        deep_dive = art.get("deep_dive_url")
        sort_order = art.get("sort_order", i)

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

            # 발행 전 검수 게이트 (Task 3)
            quality = validate_draft_quality(gpt_output, [art])
            if not quality['passed']:
                log(f"    ⚠️ 검수 실패 — 초안 큐 보관:")
                for reason in quality['reasons']:
                    log(f"      - {reason}")
                log(f"    (검수 상세: {quality['checks']})")
                continue

            filepath, seo_title = save_draft(gpt_output, title, file_num, today_str, articles=[art])
            # article 링크/설명도 함께 저장 (썸네일 중복 재시도 시 사용)
            created.append((filepath, seo_title or title, sort_order, 1, link, art.get("description", "")))
            file_num += 1

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
    # created 튜플: (filepath, title, sort_order, count, article_link, article_description)
    generated = [c for c in created if c[0] is not None]
    skipped = [c for c in created if c[0] is None]

    # article 링크/설명을 빠르게 조회할 수 있는 매핑 (slug → (link, description))
    article_info_by_slug = {}
    for fp, title, sort_order, count, art_link, art_desc in generated:
        slug = os.path.basename(fp).replace('.md', '').lower()
        article_info_by_slug[slug] = (art_link, art_desc)

    # 썸네일 중복 검증 게이트 (Plan 28-02)
    log("[검증] 썸네일 중복 검사 중...")
    thumb_paths = []
    for fp, title, sort_order, _, _, _ in generated:
        slug = os.path.basename(fp).replace('.md', '').lower()
        thumb_path = os.path.join(PROJECT_DIR, "public", "images", slug, "thumbnail.webp")
        if os.path.exists(thumb_path):
            thumb_paths.append(thumb_path)
    
    dup_result = check_thumbnail_duplicates(thumb_paths)
    dup_count = len(dup_result["duplicates"])
    
    if dup_count > 0:
        log(f"  ⚠️ 썸네일 중복 감지: {dup_count}개 쌍 (고유 {dup_result['unique_count']}/{len(thumb_paths)})")
        for p1, p2, h in dup_result["duplicates"]:
            log(f"    중복: {os.path.basename(os.path.dirname(p1))} = {os.path.basename(os.path.dirname(p2))} (MD5: {h[:8]}...)")
        
        # 중복된 포스트 재시도 (슬러그별 최대 2회, 다른 키워드 강제)
        duplicate_slugs = set()
        for p1, p2, _ in dup_result["duplicates"]:
            duplicate_slugs.add(os.path.basename(os.path.dirname(p1)))
            duplicate_slugs.add(os.path.basename(os.path.dirname(p2)))
        
        # slug별 재시도 횟수 추적
        retry_count_by_slug = {}
        total_retries = 0
        
        for fp, title, sort_order, _, _, _ in generated:
            slug = os.path.basename(fp).replace('.md', '').lower()
            if slug not in duplicate_slugs:
                continue
            
            # 이 슬러그의 현재 재시도 횟수 확인
            current_retries = retry_count_by_slug.get(slug, 0)
            if current_retries >= 2:
                log(f"  ⏭ {slug} 재시도 한도(2회) 도달, 스킵")
                continue
            
            log(f"  🔄 중복 썸네일 재시도 ({current_retries+1}/2): {slug}")
            art_link, art_desc = article_info_by_slug.get(slug, ("", ""))
            
            try:
                # 원본 article의 링크/설명을 사용하여 Pexels 검색 품질 향상
                thumb_rel = process_thumbnail(
                    art_link or "",
                    slug,
                    title=title,
                    description=art_desc or ""
                )
                if thumb_rel:
                    _add_image_to_frontmatter(fp, thumb_rel)
                    retry_count_by_slug[slug] = current_retries + 1
                    total_retries += 1
                    log(f"    재생성 완료: {thumb_rel}")
                else:
                    log(f"    재시도 실패: 썸네일 생성 결과 없음")
            except Exception as retry_e:
                log(f"    재시도 실패: {retry_e}")
        
        # 재검증
        thumb_paths = []
        for fp, title, sort_order, _, _, _ in generated:
            slug = os.path.basename(fp).replace('.md', '').lower()
            thumb_path = os.path.join(PROJECT_DIR, "public", "images", slug, "thumbnail.webp")
            if os.path.exists(thumb_path):
                thumb_paths.append(thumb_path)
        dup_result = check_thumbnail_duplicates(thumb_paths)
        dup_count = len(dup_result["duplicates"])
        retry_count = total_retries  # 텔레그램 알림용
        if dup_count == 0:
            log(f"  ✅ 재시도 후 중복 해소: 고유 {dup_result['unique_count']}/{len(thumb_paths)}")
        else:
            log(f"  ⚠️ 재시도 후에도 중복 잔존: {dup_count}개 쌍")
    else:
        log(f"  ✅ 썸네일 중복 검증 통과: 고유 {dup_result['unique_count']}/{len(thumb_paths)}")
        retry_count = 0  # 텔레그램 알림용

    # deep_dive_url이 없는 항목은 update_deep_dive_url이 save_draft 내에서 호출됨
    # (save_draft → articles 파라미터로 전달된 기사들의 id로 deep_dive_url 업데이트)
    print()

    # 3. 텔레그램 알림
    log("[3/5] 텔레그램 알림...")
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

    # 6. 자동 배포 (새 블로그 포스트가 생성되었거나 미커밋 파일이 있으면)
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
        log("[6] Cloudflare Pages 배포 중...")
        if untracked_blog_files:
            log(f"  📦 미커밋 블로그 파일 {len(untracked_blog_files)}개 감지 → 배포 실행")
            for f in untracked_blog_files[:5]:  # 최대 5개만 로그
                log(f"    - {f}")
            if len(untracked_blog_files) > 5:
                log(f"    ... 외 {len(untracked_blog_files) - 5}개")
        import subprocess
        try:
            # npm run build
            build_result = subprocess.run(
                ["npm", "run", "build"],
                capture_output=True, text=True, timeout=300, cwd=PROJECT_DIR
            )
            if build_result.returncode != 0:
                log(f"  ❌ 빌드 실패: {build_result.stderr[:200]}")
                send_telegram(f"❌ [{today_str}] 블로그 빌드 실패")
            else:
                log("  ✅ 빌드 완료")

                # wrangler pages deploy (auth profile 사용)
                wrangler = "/opt/homebrew/bin/wrangler"
                if not os.path.exists(wrangler):
                    wrangler = "npx"
                    cmd = [wrangler, "pages", "deploy", "dist",
                           "--project-name", "aikorea24", "--branch", "main", "--commit-dirty=true"]
                else:
                    cmd = [wrangler, "pages", "deploy", "dist",
                           "--project-name", "aikorea24", "--branch", "main", "--commit-dirty=true"]

                deploy_env = dict(os.environ)
                deploy_env.pop("CLOUDFLARE_API_TOKEN", None)  # auth profile 우선

                deploy_result = subprocess.run(
                    cmd, capture_output=True, text=True, timeout=180,
                    cwd=PROJECT_DIR, env=deploy_env
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
