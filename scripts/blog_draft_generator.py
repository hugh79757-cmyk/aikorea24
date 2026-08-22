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
def generate_draft(keyword, articles, grade):
    is_deep = len(articles) == 1

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
        user_prompt = (
            f"아래 '{keyword}' 관련 기사를 분석한 블로그 초안을 작성해주세요.\n\n"
            f"## 요구사항\n"
            f"- 제목: '{keyword}' 키워드가 자연스럽게 포함된 SEO 최적화 제목\n"
            f"- 본문: 1500자 이상, 소제목(##) 3개 이상 포함\n"
            f"- 기사의 배경/의미/전망을 분석, 독자가 쉽게 이해할 수 있도록\n"
            f"- 마지막에 📌 **요약** 섹션 포함\n"
            f"- 순한국어, 전문적이면서도 친근한 ~습니다/~입니다 정중 비즈니스 톤\n"
            f"- [중요] 모든 문장은 '~합니다/~입니다/~했습니다' 체로 통일. 반말('~다/~했다/~임') 절대 금지\n"
            f"- [중요] 중국어(한자) 사용 금지. 반드시 순수 한국어로만 작성할 것\n"
            f"- [중요] **본문 첫 단락(도입단락)에서 '본 포스트에서는...', '이번 글에서는...', '이번 글에서는...', "
            f"'살펴보겠습니다', '알아보겠습니다', '다루겠습니다' 등 메타 성격의 도입문(메타 도입문) 절대 금지.** "
            f"기사의 실질적 핵심 내용(사실, 수치, 인용, 분석 등)으로 바로 시작할 것.\n\n"
            f"## 출력 형식\n"
            f"TITLE: [SEO에 최적화된 제목]\n"
            f"---\n"
            f"[마크다운 본문]\n\n"
            f"## 기사\n{articles_str}"
        )
    else:
        system_prompt = (
            "당신은 AI/테크 뉴스를 분석하는 한국어 블로거입니다. "
            "여러 기사를 종합하여 트렌드 분석 블로그 초안을 작성해주세요. "
            "중국어(한자)는 절대 사용하지 말고 순수 한국어로만 작성하세요."
        )
        user_prompt = (
            f"아래 '{keyword}' 관련 여러 기사를 종합한 블로그 초안을 작성해주세요.\n\n"
            f"## 요구사항\n"
            f"- 제목: '{keyword}' 관련 트렌드가 드러나는 SEO 최적화 제목\n"
            f"- 본문: 2000자 이상, 소제목(##) 3개 이상 포함\n"
            f"- 각 기사의 핵심 내용을 비교/종합하여 트렌드 분석\n"
            f"- 마지막에 📌 **요약** 섹션 포함\n"
            f"- 순한국어, 전문적이면서도 친근한 ~습니다/~입니다 정중 비즈니스 톤\n"
            f"- [중요] 모든 문장은 '~합니다/~입니다/~했습니다' 체로 통일. 반말('~다/~했다/~임') 절대 금지\n"
            f"- [중요] 중국어(한자) 사용 금지. 반드시 순수 한국어로만 작성할 것\n"
            f"- [중요] **본문 첫 단락(도입단락)에서 '본 포스트에서는...', '이번 글에서는...', '이번 글에서는...', "
            f"'살펴보겠습니다', '알아보겠습니다', '다루겠습니다' 등 메타 성격의 도입문(메타 도입문) 절대 금지.** "
            f"기사의 실질적 핵심 내용(사실, 수치, 인용, 분석 등)으로 바로 시작할 것.\n\n"
            f"## 출력 형식\n"
            f"TITLE: [SEO에 최적화된 제목]\n"
            f"---\n"
            f"[마크다운 본문]\n\n"
            f"## 기사들\n{articles_str}"
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


def _save_file(gpt_output, keyword, file_num, today_str, articles=None):
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
        else:
            # --- 구분자 없으면 TITLE: 라인만 본문에서 제거
            content = re.sub(r"^TITLE:\s*[^\n]+\n*", "", content).strip()

    # 브리핑 페이지 링크 주입 (첫 문단 뒤) — 체류시간 확보
    if articles:
        briefing_urls = []
        for art in articles:
            briefing_url = art.get("_briefing_url", "")
            if briefing_url:
                briefing_urls.append(briefing_url)
        if briefing_urls:
            source_url = briefing_urls[0]
            source_block = f"\n\n원문기사는 아래의 링크를 통해 확인할 수 있습니다. [기사원문보기]({source_url})"
            # 첫 문단 뒤에 삽입 (빈 줄 기준 분리)
            parts = content.split("\n\n", 1)
            if len(parts) > 1:
                content = parts[0] + source_block + "\n\n" + parts[1]
            else:
                content = content + source_block

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

            filepath, seo_title = save_draft(gpt_output, title, file_num, today_str, articles=[art])
            created.append((filepath, seo_title or title, sort_order, 1))
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
