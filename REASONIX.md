# Reasonix project memory

Notes the user pinned via the `#` prompt prefix. The whole file is
loaded into the immutable system prefix every session — keep it terse.

- Task: news_collector.py 해외 RSS 소스 추가 및 AI 키워드 필터링 강화

## 작업 전 필수 확인
1. 현재 `news_collector.py` 전체 코드를 먼저 읽어라
2. 기존 RSS 파싱 방식, 필터링 로직, D1 저장 구조를 파악한 뒤 작업하라
3. 기존 동작 중인 소스들은 절대 건드리지 마라

---

## 작업 1: 신규 RSS 소스 추가

기존 해외 RSS 소스 리스트에 아래 소스들을 추가하라.
기존 소스 목록이 딕셔너리/리스트 형태로 관리되고 있다면 그 구조를 그대로 따라라.

### 추가할 소스 목록

| 매체 | RSS URL | category 값 | 비고 |
|------|---------|-------------|------|
| CNN Technology | http://rss.cnn.com/rss/cnn_tech.rss | global | AI 키워드 필터링 필수 |
| Reuters Technology | https://feeds.reuters.com/reuters/technologyNews | global | AI 키워드 필터링 필수 |
| Business Insider AI | https://feeds.businessinsider.com/custom/all | global | AI 키워드 필터링 필수 |
| NYT Technology | https://rss.nytimes.com/services/xml/rss/nyt/Technology.xml | global | AI 키워드 필터링 필수 |
| NYT AI Spotlight | https://www.nytimes.com/svc/collections/v1/publish/https://www.nytimes.com/spotlight/artificial-intelligence/rss.xml | global | AI 전용 피드, 필터링 완화 가능 |
| Washington Post Technology | https://feeds.washingtonpost.com/rss/business/technology | global | AI 키워드 필터링 필수 |
| The Guardian AI | https://www.theguardian.com/technology/artificialintelligenceai/rss | global | AI 전용 피드, 필터링 완화 가능 |
| BBC Technology | https://feeds.bbci.co.uk/news/technology/rss.xml | global | AI 키워드 필터링 필수 |
| Financial Times AI | https://www.ft.com/artificial-intelligence?format=rss | global | AI 전용 피드, 필터링 완화 가능 |
| Fast Company AI | https://www.fastcompany.com/section/artificial-intelligence/rss | global | AI 전용 피드, 필터링 완화 가능 |

Reuters RSS가 응답 없거나 파싱 실패 시,
아래 Google News 우회 URL로 자동 fallback 처리하라:
https://news.google.com/rss/search?q=site:reuters.com+artificial+intelligence&hl=en&gl=US&ceid=US:en

---

## 작업 2: AI 키워드 필터링 함수 구현 또는 강화

### 요구사항

기존에 필터링 함수가 있으면 아래 기준으로 강화하고,
없으면 신규로 `is_ai_related(title: str, summary: str = "") -> bool` 함수를 만들어라.

### 필터링 기준

**[PASS 조건] 아래 키워드 중 하나라도 title 또는 summary에 포함되면 통과**

1차 키워드 (고신뢰, 단독으로 통과):
- AI, A.I., artificial intelligence
- machine learning, deep learning
- large language model, LLM, LLMs
- ChatGPT, GPT-4, GPT-5, Claude, Gemini, Grok, Llama, Mistral
- OpenAI, Anthropic, DeepMind, Hugging Face
- generative AI, gen AI, genAI
- neural network
- natural language processing, NLP
- computer vision
- autonomous, self-driving (단, 자동차 단독 기사 제외 — 아래 REJECT 참고)

2차 키워드 (복합 조건, 아래 중 2개 이상 포함 시 통과):
- robot, robotics
- automation
- algorithm
- data model, foundation model
- transformer, diffusion model
- prompt, inference, fine-tuning

**[REJECT 조건] 아래 패턴은 1차 키워드가 있어도 제외**
- 제목에 "self-driving car", "autonomous vehicle" 만 있고 AI 언급 없는 순수 자동차 뉴스
- 제목에 "stock", "earnings", "revenue", "profit" 만 있는 순수 주가/실적 뉴스
  (단, "AI stock", "AI earnings" 처럼 AI와 결합된 경우는 통과)

### 함수 적용 범위
- 위 작업 1에서 추가한 "AI 키워드 필터링 필수" 표기 소스 전체에 적용
- "AI 전용 피드, 필터링 완화 가능" 소스는 1차 키워드만으로 필터링 (REJECT 조건은 동일 적용)
- 기존 소스들은 현재 필터링 방식 유지 (변경 금지)

---

## 작업 3: 소스별 에러 핸들링

각 신규 소스에 대해 아래 처리를 적용하라:

1. **타임아웃**: 소스당 fetch timeout = 15초
2. **실패 시 skip**: 특정 소스 fetch/parse 실패해도 전체 스크립트가 멈추지 않도록
   기존 에러 핸들링 패턴이 있으면 그것을 그대로 따라라
3. **Reuters fallback**: 작업 1에서 명시한 fallback URL로 자동 전환
4. **로그**: 실패한 소스는 기존 로깅 방식대로 기록

---

## 작업 4: 중복 제거 확인

기존 코드에 중복 제거 로직(link UNIQUE 기반 또는 별도 dedup 처리)이 있을 것이다.
신규 소스도 동일한 중복 제거 흐름을 타는지 확인하고, 누락되어 있으면 포함시켜라.
중복 제거 로직 자체를 수정하지는 마라.

---

## 작업 5: 검증

코드 수정 완료 후:
1. 신규 소스 10개가 실제로 리스트에 등록되어 있는지 확인
2. `is_ai_related()` 함수(또는 강화된 필터링 함수)가 아래 테스트 케이스를 통과하는지 확인

**통과해야 할 케이스 (is_ai_related = True)**
- "OpenAI releases new GPT-5 model"
- "Google DeepMind achieves breakthrough in protein folding with AI"
- "How companies are using generative AI to cut costs"
- "Claude 3.5 outperforms rivals on new benchmark"
- "Reuters: Anthropic raises $2 billion in funding"

**걸러져야 할 케이스 (is_ai_related = False)**
- "Tesla reports record quarterly revenue"
- "Apple announces new iPhone pricing"
- "Ford recalls 500,000 autonomous vehicles over brake issue"
- "Amazon Q3 earnings beat Wall Street expectations"

테스트 케이스 결과를 코드 아래 주석 또는 출력으로 보여주고 완료 보고하라.

---

## 절대 하지 말 것
- 기존 소스 목록 수정 또는 삭제
- D1 저장 스키마 변경
- 기존 필터링/파싱 로직을 리팩토링 명목으로 변경
- 작업 범위 외 파일 수정 (publish_*.py, auto_publish.py 등)
- 홈페이지 이메일 구독 카드 추가 + 환경변수 문제 해결

## 문제 1: BREVO_API_KEY not set
- Cloudflare Pages 대시보드(aikorea24 프로젝트 > Settings > Environment variables)의 **Production** 환경에 `BREVO_API_KEY`와 `BREVO_LIST_ID`가 등록되어 있는지 확인
- 만약 없으면 `wrangler.toml` `[vars]`에 직접 키 값 복원 후 재배포 안내
- 또는 대시보드에 등록되어 있는데 안 되면, 코드에서 `import.meta.env.BREVO_API_KEY` 접근 방식이 Cloudflare Pages에서 올바르게 동작하는지 확인 (locals.runtime.env.BREVO_API_KEY로 접근해야 함)

## 문제 2: 홈페이지 카드에 이메일 구독 추가

### 할 일
1. `src/pages/index.astro` 파일을 열어 "AI, 지금 바로 시작하세요" 텍스트가 포함된 영역(카드/Call-to-Action 섹션)을 찾는다.
2. 해당 카드 안에 이메일 구독 폼을 추가한다.
3. 폼 디자인은 기존 카드 스타일과 일관되게 유지한다.

### 구독 폼 HTML 예시
```html
<div class="mt-6 pt-6 border-t border-gray-700/50">
  <p class="text-sm text-gray-400 mb-3">📧 매일 아침 AI 브리핑 받아보기</p>
  <form id="home-subscribe" class="flex gap-2">
    <input type="email" placeholder="이메일 주소" required
      class="flex-1 px-4 py-2.5 rounded-lg bg-gray-800 border border-gray-700 text-white text-sm focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none" />
    <button type="submit"
      class="px-5 py-2.5 bg-blue-600 hover:bg-blue-700 text-white font-medium rounded-lg text-sm transition-colors whitespace-nowrap">
      구독
    </button>
  </form>
  <p id="home-subscribe-msg" class="text-xs mt-2 hidden"></p>
</div>
구독 폼 JavaScript (기존 /api/subscribe API 재사용)
Copy<script>
document.getElementById('home-subscribe')?.addEventListener('submit', async (e) => {
  e.preventDefault();
  const input = e.target.querySelector('input[type="email"]');
  const msg = document.getElementById('home-subscribe-msg');
  const btn = e.target.querySelector('button');
  const email = input.value.trim();
  
  btn.disabled = true;
  btn.textContent = '처리 중...';
  msg.classList.add('hidden');
  
  try {
    const res = await fetch('/api/subscribe', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email })
    });
    const data = await res.json();
    
    if (res.ok) {
      msg.className = 'text-xs mt-2 text-green-400';
      msg.textContent = '✅ 구독 완료! 매일 아침 AI 브리핑을 보내드립니다.';
      input.value = '';
    } else {
      msg.className = 'text-xs mt-2 text-red-400';
      msg.textContent = data.error || '오류가 발생했습니다.';
    }
  } catch (err) {
    msg.className = 'text-xs mt-2 text-red-400';
    msg.textContent = '네트워크 오류입니다.';
  } finally {
    btn.disabled = false;
    btn.textContent = '구독';
    msg.classList.remove('hidden');
  }
});
</script>
Copy
중요 조건
기존 카드 레이아웃, 스타일, 다른 버튼(블로그 보기, 커뮤니티 참여)은 절대 수정 금지
카드 내부에 구독 폼 섹션만 추가
/api/subscribe API는 이미 존재하므로 새로 만들지 말고 재사용
다크모드 대응 유지
반응형 디자인 유지
실행 순서
먼저 BREVO_API_KEY 환경변수 문제 원인 파악 및 해결
src/pages/index.astro 수정 (구독 폼 추가)
npm run build로 빌드 테스트
문제 없으면 배포 안내
- Brevo 이메일 발송 시스템 전체 검증

## 검증 항목 (총 8개)

### 1. subscribe.ts 환경변수 접근 방식 검증
- 파일: `src/pages/api/subscribe.ts`
- 확인: `import.meta.env.BREVO_API_KEY` 대신 `locals.runtime.env.BREVO_API_KEY`로 변경되었는가?
- Cloudflare Pages + Astro SSR에서는 `import.meta.env`가 동작하지 않고 `locals.runtime.env`로 접근해야 함
- `import.meta.env.BREVO_API_KEY`가 남아있으면 수정

### 2. send-email.ts 환경변수 접근 방식 검증
- 파일: `src/pages/api/briefing/send-email.ts`
- 확인: `const BREVO_API_KEY = runtime?.env?.BREVO_API_KEY;` 이렇게 접근하는가?
- `import.meta.env`로 접근하는 부분이 없는가?

### 3. wrangler.toml 키 노출 위험 검증
- 파일: `wrangler.toml`
- 확인: `[vars]` 섹션에 실제 `xkeysib-...` 키 값이 평문으로 노출되어 있는가?
- 만약 노출되어 있으면 → `.gitignore`에 `wrangler.toml`이 있는지 확인
- 또는 키 값을 `# 대시보드에서 설정`으로 변경하고 Cloudflare 대시보드에만 키를 유지할 것

### 4. 홈페이지 구독 폼 검증
- 파일: `src/components/home/CtaSection.astro`
- 확인: 구독 폼이 정상적으로 생성되었는가?
- `id="home-subscribe"` form이 존재하는가?
- 버튼 클릭 시 `/api/subscribe`로 POST 요청을 보내는가?
- 성공/실패 메시지가 표시되는가?
- 기존 "블로그 보기", "커뮤니티 참여" 버튼이 그대로 유지되었는가? (삭제 금지)

### 5. admin 페이지 이메일 발송 버튼 검증
- 파일: `src/pages/admin/index.astro`
- 확인: `id="emailBtn"` 버튼이 존재하는가?
- `checkStatus()` 함수에서 오늘 브리핑이 있을 때 버튼이 표시되는가?
- 버튼 클릭 시 `POST /api/briefing/send-email`을 호출하는가?
- 응답에 따라 성공/실패 메시지가 `#msg` 영역에 표시되는가?

### 6. 브리핑 조회 로직 검증
- 파일: `src/pages/api/briefing/send-email.ts`
- 확인: 오늘 날짜 계산이 `Date.now() + 9*3600*1000` (KST 기준)로 되어 있는가?
- 브리핑이 없을 경우 `{ ok: false, error: '오늘 발행된 브리핑이 없습니다.' }`를 반환하는가?
- 브리핑 아이템과 뉴스 테이블 JOIN이 정확한가? (LEFT JOIN, bi.briefing_id = ?)

### 7. Brevo API 호출 검증
- 파일: `src/pages/api/briefing/send-email.ts`
- 확인: Brevo API endpoint가 `https://api.brevo.com/v3/contacts`와 `https://api.brevo.com/v3/smtp/email`로 정확한가?
- `api-key` 헤더에 `BREVO_API_KEY`가 전달되는가?
- 구독자 목록 조회 시 페이지네이션(limit=100, offset)이 구현되어 있는가?
- 이메일 발송 시 100명씩 배치(batch)로 나누어 발송하는가?

### 8. 발신자 이메일 검증
- 파일: `src/pages/api/briefing/send-email.ts`
- 확인: `sender.email`이 `info@aikorea24.kr`로 설정되어 있는가?
- Brevo 대시보드에서 `aikorea24.kr` 도메인이 **Authenticated** 상태인가? (사용자 확인 완료)

## 실행 순서
1. 위 8개 항목을 순서대로 검증
2. 문제 발견 시 수정
3. 최종 결과 요약 (통과/실패)
4. 모든 항목 통과 시 "배포 준비 완료" 메시지 출력
- AI코리아24 툴 수집 소스 확장

## 목표
기존 `tools_collector.py`에 새로운 수집 소스 2개를 추가하여 일일 신규 툴 생산량을 4개 → 12~15개로 증가

## 변경 파일 (총 3개)

### 1) tools_collector.py — 소스 추가

#### 변경 1: 파일 상단에 새 URL 상수 추가
```python
# === 신규 소스 URL ===
FUTUREPEDIA_SITEMAP = "https://www.futurepedia.io/sitemap.xml"
HUGGINGFACE_PAPERS_RSS = "https://huggingface.co/papers"  # RSS 피드
변경 2: collect_futurepedia() 함수 추가
Copydef collect_futurepedia(limit=10):
    """Futurepedia sitemap → 카테고리 페이지 → 툴 정보 추출"""
    tools = []
    
    # 1) sitemap.xml에서 /ai-tools/ 경로만 필터링
    resp = fetch_url(FUTUREPEDIA_SITEMAP)
    if not resp:
        return tools
    
    root = ET.fromstring(resp.encode())
    ns = {'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
    tool_urls = []
    for loc in root.findall('.//ns:loc', ns):
        url = loc.text
        if '/ai-tools/' in url and url.count('/') <= 6:  # 카테고리 페이지만
            tool_urls.append(url)
    
    # 2) 각 카테고리 페이지 방문 (최대 limit개)
    random.shuffle(tool_urls)
    for cat_url in tool_urls[:limit]:
        try:
            html = fetch_url(cat_url, render_js=True)
            if not html:
                continue
            soup = BeautifulSoup(html, 'html.parser')
            # 카드에서 툴 이름, 설명, 링크 추출
            for card in soup.select('[class*="tool"], [class*="card"], article')[:5]:
                name_el = card.select_one('h2, h3, [class*="title"]')
                desc_el = card.select_one('p, [class*="desc"]')
                link_el = card.select_one('a[href*="/tool/"]')
                if not name_el or not link_el:
                    continue
                tools.append({
                    'name': name_el.get_text(strip=True),
                    'description': desc_el.get_text(strip=True) if desc_el else '',
                    'url': link_el['href'] if link_el['href'].startswith('http') else 'https://www.futurepedia.io' + link_el['href'],
                    'price': extract_futurepedia_price(card),
                    'source': 'futurepedia',
                    'pub_date': datetime.now().strftime('%Y-%m-%d')
                })
        except Exception as e:
            print(f"  ⚠️ Futurepedia 오류: {e}")
            continue
    
    return tools[:limit]

def extract_futurepedia_price(card):
    """Futurepedia 카드에서 가격 정보 추출"""
    text = card.get_text()
    if 'Free' in text or '무료' in text:
        return '무료'
    elif 'Freemium' in text:
        return '무료/유료'
    elif '$' in text:
        import re
        prices = re.findall(r'\$\d+', text)
        return prices[0] + '/월' if prices else '유료'
    return '유료'
Copy
변경 3: collect_huggingface_papers() 함수 추가
Copydef collect_huggingface_papers(limit=5):
    """Hugging Face Daily Papers → AI 연구/도구 정보 추출"""
    tools = []
    
    html = fetch_url(HUGGINGFACE_PAPERS_RSS)
    if not html:
        return tools
    
    soup = BeautifulSoup(html, 'html.parser')
    articles = soup.select('article, [class*="paper"], .paper-card')[:limit]
    
    for article in articles:
        title_el = article.select_one('h2, h3, [class*="title"]')
        link_el = article.select_one('a[href*="arxiv"]') or article.select_one('a[href*="hf.co"]') or article.select_one('a[href*="huggingface"]')
        desc_el = article.select_one('p, [class*="desc"], [class*="abstract"]')
        
        if not title_el:
            continue
        
        title = title_el.get_text(strip=True)
        # AI 툴/프로젝트 관련 논문만 필터링
        if not any(kw in title.lower() for kw in ['tool', 'agent', 'model', 'framework', 'llm', 'gpt', 'diffusion', 'transformer']):
            continue
        
        tools.append({
            'name': title[:50],
            'description': desc_el.get_text(strip=True)[:200] if desc_el else title,
            'url': link_el['href'] if link_el else f'https://huggingface.co/papers',
            'price': '무료' if 'open source' in title.lower() else '유료',
            'source': 'huggingface',
            'pub_date': datetime.now().strftime('%Y-%m-%d')
        })
    
    return tools
Copy
변경 4: main() 함수의 collect_tools() 호출 부분 수정
Copy# 기존 코드 찾기:
# ph_tools = collect_ph_tools(limit_per_source)
# gh_tools = collect_github_tools(limit_per_source)

# 아래로 변경:
ph_tools = collect_ph_tools(limit_per_source)
gh_tools = collect_github_tools(limit_per_source)  # 주 1회만 (로직 추가)
fp_tools = collect_futurepedia(limit_per_source)    # 신규
hf_tools = collect_huggingface_papers(5)            # 신규

# 병합
all_tools = ph_tools + gh_tools + fp_tools + hf_tools
변경 5: GitHub 소스 주 1회로 전환
Copydef should_run_github_today():
    """GitHub Awesome AI Tools는 주 1회(월요일)만 실행"""
    return datetime.now().weekday() == 0  # 0 = Monday

# main() 내부:
if should_run_github_today():
    gh_tools = collect_github_tools(limit_per_source)
    print(f"  GitHub Awesome AI Tools: {len(gh_tools)}개 (주간 업데이트)")
else:
    gh_tools = []
    print(f"  GitHub Awesome AI Tools: 오늘 스킵 (주 1회 실행)")
2) tools_collector.py — 임포트 추가
파일 상단에 아래 임포트가 없으면 추가:

Copyimport random  # Futurepedia 무작위 선택용
3) requirements.txt 확인
필요 패키지가 설치되어 있는지 확인:

Copypip install beautifulsoup4 lxml
(이미 설치되어 있어야 함 - news_collector.py에서 사용 중)

실행 순서
tools_collector.py 수정 (위 5개 변경사항 모두 적용)
의존성 확인: pip install beautifulsoup4 lxml
테스트 실행: python tools_collector.py --limit 5 --dry-run
정상 확인 후 전체 실행: python tools_collector.py --collect
배포 확인: git push → Cloudflare 자동 배포
예상 결과
소스	수집	중복 제외	신규 생성
Product Hunt	5개	2~3개	2~3개
GitHub Awesome	0개 (주 1회)	0개	0개
Futurepedia	10개	6~8개	6~8개
HuggingFace	5개	2~3개	2~3개
합계	20개	10~14개	10~14개 🚀
주의사항
Futurepedia HTML 구조가 변경되면 파싱 로직 수정 필요
Hugging Face 페이지 구조 변경 시 동일
--dry-run 옵션으로 먼저 테스트 필수
sitemap.xml 호출 시 너무 빈번하면 차단될 수 있음 (하루 1회만 실행)
- AI코리아24 이메일 템플릿 업그레이드

## 목표
send-email.ts의 이메일 템플릿을 개선하여:
1. 브리핑 아이템 3개만 표시 + 더보기 버튼
2. 아래에 신규 AI 툴 섹션 추가
3. 모든 링크를 aikorea24.kr 내부로 고정 (외부 링크 완전 제거)

## 변경 파일 (1개)
- src/pages/api/briefing/send-email.ts

## DB 선행 확인
아래 명령어로 D1 데이터베이스 이름을 먼저 확인하세요:
```bash
grep -A5 "d1_databases" /Users/twinssn/Projects/aikorea24/wrangler.toml
그 다음 tools 테이블이 있는지 확인:

Copynpx wrangler d1 execute [DB명] --remote --command="SELECT name FROM sqlite_master WHERE type='table' AND name='tools';"
tools 테이블이 없으면 아래 스키마로 생성:

CopyCREATE TABLE IF NOT EXISTS tools (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  slug TEXT NOT NULL UNIQUE,
  tagline TEXT,
  category TEXT,
  price TEXT,
  korean_support INTEGER DEFAULT 0,
  difficulty TEXT,
  url TEXT,
  featured INTEGER DEFAULT 0,
  created_at TEXT DEFAULT (datetime('now')),
  updated_at TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_tools_featured ON tools(featured);
CREATE INDEX IF NOT EXISTS idx_tools_updated ON tools(updated_at);
변경 상세
변경 1: 아이템 3개 제한 + 더보기
Copy// items.results 전체 대신 3개만
const displayItems = (items.results || []).slice(0, 3);
const totalCount = items.results?.length || 0;

// itemsHtml 생성 시 displayItems 사용
for (const item of displayItems) {
  itemsHtml += `...`;
}

// 3개 초과 시 더보기 버튼 추가
if (totalCount > 3) {
  itemsHtml += `
    <tr>
      <td style="padding:16px 0;text-align:center;">
        <a href="https://aikorea24.kr/news/" 
           style="display:inline-block;padding:10px 24px;background:#2563eb;color:#ffffff;border-radius:8px;font-size:14px;font-weight:600;text-decoration:none;">
          👉 오늘의 브리핑 ${totalCount}개 전체 보기 →
        </a>
      </td>
    </tr>`;
}
변경 2: 원문 읽기 링크 → 내부 브리핑 링크로 교체
Copy// 기존 (외부 링크):
// <a href="${item.news_link}" ...>원문 읽기 →</a>

// 변경 (내부 링크):
// 브리핑 페이지 링크
const itemAnchor = item.sort_order ? `#item-${item.sort_order}` : '';
const briefingUrl = `https://aikorea24.kr/news/#${today}${itemAnchor}`;
// ---
// itemsHtml 생성부:
itemsHtml += `
  <tr><td style="padding-top:8px;">
    <a href="${briefingUrl}" style="font-size:12px;color:#2563eb;text-decoration:underline;">
      AI코리아24에서 자세히 보기 →
    </a>
  </td></tr>`;
변경 3: AI 툴 섹션 추가
Copy// 4. 신규 AI 툴 조회 (D1 tools 테이블)
let toolsHtml = '';
try {
  const tools = await db.prepare(
    `SELECT name, slug, tagline, category, price, korean_support, difficulty
     FROM tools
     WHERE featured = 1 OR updated_at > datetime('now', '-7 days')
     ORDER BY updated_at DESC
     LIMIT 6`
  ).all();

  if (tools.results && tools.results.length > 0) {
    toolsHtml = `
      <tr>
        <td style="padding:24px 0 8px 0;">
          <table width="100%" cellpadding="0" cellspacing="0" style="border-top:2px solid #e5e7eb;padding-top:24px;">
            <tr>
              <td style="font-size:16px;font-weight:700;color:#1f2937;padding-bottom:16px;">
                🛠️ 오늘의 신규 AI 도구
              </td>
            </tr>
            ${tools.results.map(t => `
              <tr>
                <td style="padding:8px 0;border-bottom:1px solid #f3f4f6;">
                  <table width="100%" cellpadding="0" cellspacing="0">
                    <tr>
                      <td style="font-size:14px;font-weight:600;color:#111827;">
                        ${t.korean_support ? '🇰🇷 ' : ''}${t.name}
                      </td>
                      <td style="text-align:right;font-size:11px;color:#6b7280;">
                        ${t.price || ''} ${t.category ? '· ' + t.category : ''}
                      </td>
                    </tr>
                    <tr>
                      <td colspan="2" style="font-size:13px;color:#6b7280;padding-top:4px;line-height:1.4;">
                        ${t.tagline || ''}
                      </td>
                    </tr>
                    <tr>
                      <td colspan="2" style="padding-top:6px;">
                        <a href="https://aikorea24.kr/tools/${t.slug}/" 
                           style="font-size:12px;color:#2563eb;text-decoration:underline;">
                          AI코리아24에서 자세히 보기 →
                        </a>
                      </td>
                    </tr>
                  </table>
                </td>
              </tr>
            `).join('')}
            <tr>
              <td style="padding:12px 0;text-align:center;">
                <a href="https://aikorea24.kr/tools/" 
                   style="font-size:13px;color:#2563eb;text-decoration:underline;">
                  🔎 모든 AI 도구 보기 →
                </a>
              </td>
            </tr>
          </table>
        </td>
      </tr>`;
  }
} catch (e) {
  console.error('툴 조회 오류:', e);
}

// 5. htmlContent에 toolsHtml 삽입 (itemsHtml과 footer 사이)
const htmlContent = `
  ...
  ${itemsHtml}
  ${toolsHtml}    // ← itemsHtml 바로 다음에 추가
  ...footer...
`;
Copy
변경 4: 푸터에 구독 해지 링크 유지 (내부)
Copy// 푸터 부분 (기존 유지, 링크만 확인)
<a href="https://aikorea24.kr/unsubscribe" style="color:#9ca3af;text-decoration:underline;">
  구독 해지
</a>
실행 순서
DB 확인 및 tools 테이블 생성
src/pages/api/briefing/send-email.ts 수정 (변경 1~4 적용)
npm run build && npx wrangler pages deploy dist
https://aikorea24.kr/admin 에서 이메일 발송 테스트
주의사항
tools 테이블이 없으면 툴 섹션은 빈 채로 표시되지 않음 (오류 X)
모든 링크는 반드시 https://aikorea24.kr/...로 시작해야 함
item.news_link 사용 금지 (원문 링크는 외부)
- 미션
aikorea24.kr 뉴스 자동 수집 → 소재 점수화 → 쓰레드 글 작성 → Threads API 2시간마다 자동 발행하는 완전 자동화 시스템을 만들어라.

# 프로젝트 환경
- 경로: /Users/twinssn/Projects/aikorea24
- Python 가상환경: .venv 활성화 상태
- .env에 이미 설정된 변수:
  THREADS_APP_ID, THREADS_APP_SECRET, THREADS_REDIRECT_URI,
  THREADS_ACCESS_TOKEN, THREADS_USER_ID, OPENAI_API_KEY

# 사이트 구조
- 오늘 브리핑: https://aikorea24.kr/briefing/YYYY-MM-DD/
- 심층 분석: https://aikorea24.kr/blog/... (각 기사마다 링크 있음)
- RSS 없음. HTML 크롤링으로 수집

# 글쓰기 프롬프트 파일 위치
scripts/threads/prompts/ 폴더 안에 5개 파일이 있음.
글 작성 시 이 파일들을 반드시 읽어서 참고할 것:
- prompt_00_selector.md  → 소재 선별 기준 및 형식 선택
- prompt_A_storytelling.md → 형식 A 탐사형 (인물 행동 있을 때)
- prompt_B_analysis.md   → 형식 B 구조 분석형 (데이터/정책)
- prompt_C_brief.md      → 형식 C X 쓰레드형 (짧은 뉴스)
- prompt_rules.md        → 공통 문체 규칙 + CTA + 출처 표기

# 만들어야 할 파일
scripts/threads/ 안에 아래 파일들을 새로 생성. 기존 파일 절대 수정 금지.

## crawler.py
- 오늘 날짜 브리핑 페이지 크롤링
- 각 기사 제목 + 본문 + URL + 심층분석 링크 수집
- posted.json으로 이미 발행된 기사 중복 방지
- 수집 실패 시 전날 브리핑 페이지로 fallback

## scorer.py
- 아래 기준으로 0~100점 채점 후 높은 순서로 정렬:
  이름 있는 인물의 구체적 행동 기록 (+30점)
  감정/갈등/반전 요소 (+25점)
  구체적 숫자/데이터 (+20점)
  인물 간 대립 구도 (+15점)
  한국 독자 연결점 (+10점)

## writer.py
- OpenAI API (gpt-4o) 사용
- 글 작성 전 scripts/threads/prompts/ 파일 4개 모두 읽어서 system prompt에 포함
- 소재 점수에 따라 형식 A/B/C 자동 선택
- 출력: 카드별로 "---" 구분자로 분리된 텍스트

## publisher.py
- "---" 구분자로 카드 파싱
- 카드 순서대로 Threads API 발행
- 카드 간 간격 3초
- 실패 시 3회 재시도
- 토큰 만료(error code 190) 감지 시 자동 갱신 후 재시도
- 갱신된 토큰 .env 파일에 자동 저장
- 발행 완료 기사 URL을 posted.json에 저장

## main.py
- 실행 순서:
  1. crawler.py로 오늘 기사 수집
  2. scorer.py로 점수화 및 정렬
  3. 상위 1개 기사 선택 (발행 이력 제외)
  4. writer.py로 글 작성
  5. publisher.py로 발행
- 2시간마다 자동 반복 (schedule 라이브러리)
- 매일 자정 posted.json 날짜 체크 후 초기화
- 토큰 만료 30일 전 자동 갱신
- 모든 로그: scripts/threads/logs/YYYY-MM-DD.log 저장

# Threads API 엔드포인트
- 컨테이너 생성: POST https://graph.threads.net/v1.0/{USER_ID}/threads
- 발행: POST https://graph.threads.net/v1.0/{USER_ID}/threads_publish
- 토큰 갱신: GET https://graph.threads.net/refresh_access_token

# 완료 후 테스트 순서
1. python scripts/threads/crawler.py → 기사 수집 확인
2. python scripts/threads/scorer.py → 점수 출력 확인
3. python scripts/threads/writer.py → 글 작성 확인 (발행 안 함)
4. python scripts/threads/publisher.py → 발행 테스트
5. python scripts/threads/main.py → 전체 자동화 확인
- 미션
aikorea24.kr 뉴스 자동 수집 → 소재 점수화 → 쓰레드 글 작성 → Threads API 2시간마다 자동 발행하는 완전 자동화 시스템을 만들어라.

# 프로젝트 환경
- 경로: /Users/twinssn/Projects/aikorea24
- Python 가상환경: .venv 활성화 상태
- .env에 이미 설정된 변수:
  THREADS_APP_ID, THREADS_APP_SECRET, THREADS_REDIRECT_URI,
  THREADS_ACCESS_TOKEN, THREADS_USER_ID, OPENAI_API_KEY

# 사이트 구조
- 오늘 브리핑: https://aikorea24.kr/briefing/YYYY-MM-DD/
- 심층 분석: https://aikorea24.kr/blog/... (각 기사마다 링크 있음)
- RSS 없음. HTML 크롤링으로 수집

# 글쓰기 프롬프트 파일 위치
scripts/threads/prompts/ 폴더 안에 5개 파일이 있음.
글 작성 시 이 파일들을 반드시 읽어서 참고할 것:
- prompt_00_selector.md  → 소재 선별 기준 및 형식 선택
- prompt_A_storytelling.md → 형식 A 탐사형 (인물 행동 있을 때)
- prompt_B_analysis.md   → 형식 B 구조 분석형 (데이터/정책)
- prompt_C_brief.md      → 형식 C X 쓰레드형 (짧은 뉴스)
- prompt_rules.md        → 공통 문체 규칙 + CTA + 출처 표기

# 만들어야 할 파일
scripts/threads/ 안에 아래 파일들을 새로 생성. 기존 파일 절대 수정 금지.

## crawler.py
- 오늘 날짜 브리핑 페이지 크롤링
- 각 기사 제목 + 본문 + URL + 심층분석 링크 수집
- posted.json으로 이미 발행된 기사 중복 방지
- 수집 실패 시 전날 브리핑 페이지로 fallback

## scorer.py
- 아래 기준으로 0~100점 채점 후 높은 순서로 정렬:
  이름 있는 인물의 구체적 행동 기록 (+30점)
  감정/갈등/반전 요소 (+25점)
  구체적 숫자/데이터 (+20점)
  인물 간 대립 구도 (+15점)
  한국 독자 연결점 (+10점)

## writer.py
- OpenAI API (gpt-4o) 사용
- 글 작성 전 scripts/threads/prompts/ 파일 4개 모두 읽어서 system prompt에 포함
- 소재 점수에 따라 형식 A/B/C 자동 선택
- 출력: 카드별로 "---" 구분자로 분리된 텍스트

## publisher.py
- "---" 구분자로 카드 파싱
- 카드 순서대로 Threads API 발행
- 카드 간 간격 3초
- 실패 시 3회 재시도
- 토큰 만료(error code 190) 감지 시 자동 갱신 후 재시도
- 갱신된 토큰 .env 파일에 자동 저장
- 발행 완료 기사 URL을 posted.json에 저장

## main.py
- 실행 순서:
  1. crawler.py로 오늘 기사 수집
  2. scorer.py로 점수화 및 정렬
  3. 상위 1개 기사 선택 (발행 이력 제외)
  4. writer.py로 글 작성
  5. publisher.py로 발행
- 2시간마다 자동 반복 (schedule 라이브러리)
- 매일 자정 posted.json 날짜 체크 후 초기화
- 토큰 만료 30일 전 자동 갱신
- 모든 로그: scripts/threads/logs/YYYY-MM-DD.log 저장

# Threads API 엔드포인트
- 컨테이너 생성: POST https://graph.threads.net/v1.0/{USER_ID}/threads
- 발행: POST https://graph.threads.net/v1.0/{USER_ID}/threads_publish
- 토큰 갱신: GET https://graph.threads.net/refresh_access_token

# 완료 후 테스트 순서
1. python scripts/threads/crawler.py → 기사 수집 확인
2. python scripts/threads/scorer.py → 점수 출력 확인
3. python scripts/threads/writer.py → 글 작성 확인 (발행 안 함)
4. python scripts/threads/publisher.py → 발행 테스트
5. python scripts/threads/main.py → 전체 자동화 확인
이것도 해줘
- AI코리아24 커뮤니티 구글 색인 최적화 + 시드 데이터 생성

## 목표
커뮤니티 게시글을 구글에 색인되게 하여 검색 유입을 만든다.
총 3가지 변경 + 5개 시드 게시글 등록

---

## 변경 1 — src/pages/community/[id].astro (SEO 메타태그 추가)

파일 상단 `---` 블록 내에 아래 변수들을 추가하세요.

```astro
---
// 기존 import 및 코드 유지
// 아래 변수들을 상단에 추가

// 카테고리 한글 매핑
const categoryNames: Record<string, string> = {
  free: '자유게시판',
  qna: '질문답변',
  news: 'AI 뉴스',
  tip: '꿀팁공유',
  project: '프로젝트'
};
const catName = categoryNames[post.category] || post.category;
const cleanContent = post.content?.replace(/<[^>]*>/g, '').substring(0, 150) || '';
const pageTitle = `${post.title} | AI코리아24 커뮤니티`;
const pageDesc = `[${catName}] ${cleanContent}`;
const pageUrl = `https://aikorea24.kr/community/${post.id}`;

// post가 undefined일 경우 기본값 처리
if (!post) {
  return { notFound: true };
}
---
Copy
그리고 <head> 영역이나 Layout 컴포넌트에 props로 전달하는 부분을 확인하세요. 만약 Layout.astro를 사용 중이라면, 아래 코드를 Layout 호출 부분 위에 추가하거나, 아니면 직접 <head> 내에 추가하세요.

Layout에 전달하는 방식:

Copy---
// Layout 호출 부분 수정
const seoProps = {
  title: pageTitle,
  description: pageDesc,
  ogUrl: pageUrl,
};
---
<Layout title={pageTitle} description={pageDesc}>
또는 직접 <head>에 추가하는 방식 (Layout이 SEO props를 지원하지 않을 경우):

Copy<!-- 기존 Layout 위에 별도 head 추가 불가능하니, 
     Layout 컴포넌트가 title/description props를 받는지 확인 후 수정 -->
중요: src/layouts/Layout.astro 또는 사용 중인 레이아웃 파일을 먼저 확인해서, Props로 title, description을 받고 <title>과 <meta> 태그를 렌더링하는 구조인지 파악하세요. 구조에 맞게 수정해야 합니다.

변경 2 — src/pages/community/index.astro (링크 구조 확인)
게시글 목록에서 각 글로 연결되는 <a> 태그가 다음과 같이 정적 링크인지 확인하세요.

Copy<!-- ✅ 이렇게 되어 있어야 구글이 크롤링 가능 -->
<a href="/community/${post.id}">
  {post.title}
</a>

<!-- ❌ 이렇게 되어 있으면 변경 필요 -->
<div onclick="location.href='/community/${post.id}'">
  {post.title}
</div>
만약 JS 기반 동적 이동으로 되어 있다면 <a> 태그로 변경하세요.

변경 3 — src/pages/api/briefing/send-email.ts (뉴스레터 푸터에 커뮤니티 링크 추가)
푸터 영역(unsubscribe 링크 근처)에 아래 HTML을 추가하세요.

Copy// 푸터 HTML 생성 부분 찾아서 아래 내용 추가
// 구독 해지 링크 앞이나 뒤에 추가

// 추가:
<tr>
  <td style="padding:8px 0 0 0;text-align:center;font-size:12px;color:#9ca3af;">
    💬 <a href="https://aikorea24.kr/community/" style="color:#3b82f6;text-decoration:underline;">커뮤니티</a>에서 오늘의 브리핑에 대한 의견을 나눠보세요
  </td>
</tr>
변경 4 — D1에 시드 게시글 5개 INSERT
아래 SQL을 실행하여 커뮤니티에 5개의 시드 게시글을 등록하세요. (기존 posts 테이블의 컬럼 구조에 맞게 조정 필요)

먼저 posts 테이블 구조를 확인:

CopySELECT sql FROM sqlite_master WHERE name='posts';
그리고 users 테이블에서 관리자 사용자 ID 확인:

CopySELECT id, name, email FROM users LIMIT 5;
관리자 사용자 ID(예: 1)를 확인한 후 아래 SQL 실행:

Copy-- 시드 게시글 5개 INSERT
INSERT INTO posts (title, content, category, user_id, views, created_at) VALUES
(
  'ChatGPT 무료 vs 유료, 실전에서는 얼마나 차이날까?',
  'ChatGPT 무료 버전(GPT-4o mini)과 유료 버전(GPT-4o)을 각각 2주씩 써본 후기입니다.\n\n【번역 품질】\n무료: 간단한 영한 번역은 충분하지만, 전문 용어가 포함된 문서는 맥락을 놓치는 경우가 있음.\n유료: 거의 완벽에 가깝습니다. 특히 계약서나 기술 문서 번역에서 차이가 큼.\n\n【코딩】\n무료: 간단한 스크립트 작성에는 무리 없음.\n유료: 복잡한 리팩토링, 디버깅도 척척 해냅니다.\n\n【이미지 생성】\n무료: 불가능\n유료: DALL-E 3로 바로 생성 가능\n\n여러분은 어떤 요금제 쓰시나요? 의견 나눠봐요!',
  'qna',
  1,
  0,
  datetime('now', '-1 days', '+9 hours')
);

INSERT INTO posts (title, content, category, user_id, views, created_at) VALUES
(
  '2026년 AI 이미지 생성 도구 TOP 5 — 실제 사용해보니',
  '올해 실제로 써본 AI 이미지 생성 도구를 순위로 정리했습니다.\n\n1위: Midjourney V7\n- 장점: 퀄리티 압도적, 구도/조명 표현이 예술 수준\n- 단점: 한글 텍스트 표현 취약, 월 10~30달러\n\n2위: DALL-E 3 (ChatGPT)\n- 장점: 대화하며 수정 가능, 한글 텍스트 잘 씀\n- 단점: 세부 프롬프트 제어 어려움\n\n3위: Stable Diffusion 3.5\n- 장점: 무료+오픈소스, 로컬 구동 가능\n- 단점: 초보자 설정 어려움\n\n4위: Ideogram\n- 장점: 텍스트 표현 최강, 로고 디자인 특화\n- 단점: 스타일 다양성 부족\n\n5위: Adobe Firefly\n- 장점: 상업용 안전, 포토샵 연동\n- 단점: 창의성 제한적\n\n각각 한 달씩 써본 솔직한 후기입니다. 질문 환영!',
  'tip',
  1,
  0,
  datetime('now', '-2 days', '+9 hours')
);

INSERT INTO posts (title, content, category, user_id, views, created_at) VALUES
(
  '오픈AI, 새로운 추론 모델 출시…기존 대비 어떤 점이 개선됐을까',
  '오픈AI가 새로운 추론 모델을 발표했습니다.\n\n주요 개선점:\n1. 추론 능력: 복잡한 수학/논리 문제 정확도 30% 향상\n2. 응답 속도: 이전 모델 대비 2배 빠른 추론\n3. 비용: 토큰당 가격 50% 인하\n\n이번 업데이트로 기업용 AI 도입이 더 가속화될 전망입니다.\n\n출처: OpenAI 공식 블로그\n\n여러분은 어떻게 생각하시나요? 이 변화가 우리나라 AI 업계에 미칠 영향은?',
  'news',
  1,
  0,
  datetime('now', '-3 days', '+9 hours')
);

INSERT INTO posts (title, content, category, user_id, views, created_at) VALUES
(
  'AI로 유튜브 영상 요약하는 가장 쉬운 방법 (초보자용)',
  '유튜브에서 1시간짜리 강의 영상을 보다가 "이거 AI로 요약할 수 없나?" 생각한 적 있으신가요?\n\n가장 쉬운 방법 3가지 알려드립니다.\n\n방법 1: NotebookLM (완전 무료)\n1. https://notebooklm.google.com 접속\n2. + 새 노트북 생성\n3. 소스 → YouTube URL 붙여넣기\n4. "이 영상을 5줄로 요약해줘" 입력\n→ 끝. 30초면 완료.\n\n방법 2: ChatGPT (유료 추천)\n1. YouTube 영상 URL 복사\n2. ChatGPT에 "다음 영상 요약해줘: [URL]" 입력\n3. 필요한 경우 "한국어로 3줄 요약" 추가 지시\n\n방법 3: Chrome 확장프로그램\n- Glasp: 영상 스크립트 추출 + AI 요약\n- Transcript: 자막 다운로드\n\n저는 방법1(NotebookLM)을 가장 추천합니다. 완전 무료에 요약 퀄리티도 좋아요.\n\n다들 어떤 방법 쓰시나요?',
  'tip',
  1,
  0,
  datetime('now', '-4 days', '+9 hours')
);

INSERT INTO posts (title, content, category, user_id, views, created_at) VALUES
(
  'Perplexity vs Google 검색, 일주일 써본 솔직 비교',
  '일주일 동안 검색을 Perplexity로만 해봤습니다.\n\n【정보 검색】\nGoogle: 링크 10개 나열 → 내가 클릭해서 읽음\nPerplexity: 질문에 대한 답변을 출처와 함께 요약\n→ Perplexity 승. 시간 1/3로 단축\n\n【최신 뉴스】\nGoogle: 뉴스탭에서 최신순 정렬\nPerplexity: 실시간 검색 활성화하면 출처 포함 요약\n→ 비슷한데 Perplexity가 맥락 파악 더 쉬움\n\n【쇼핑/맛집】\nGoogle: 지도, 리뷰, 가격 비교 최적화\nPerplexity: 텍스트 기반 답변만\n→ Google 승. 이건 아직 못 따라옴\n\n【개발/기술 질문】\nGoogle: Stack Overflow 링크\nPerplexity: Stack Overflow 내용 요약 + 추가 설명\n→ Perplexity 승. 초보자에게 특히 좋음\n\n결론: 정보 검색/리서치는 Perplexity, 로컬 검색/쇼핑은 Google. 둘 다 쓰는 게 정답!\n\n여러분의 검색 습관은 어떤가요?',
  'free',
  1,
  0,
  datetime('now', '-5 days', '+9 hours')
);
Copy
참고: users 테이블에서 실제 admin 사용자 ID가 1이 아닐 수 있으니, 반드시 먼저 확인 후 user_id 값을 수정하세요.

실행 순서 (총 5단계)
Step 1: DB 테이블 구조 확인
Copynpx wrangler d1 execute [DB명] --remote --command="SELECT sql FROM sqlite_master WHERE name='posts';"
npx wrangler d1 execute [DB명] --remote --command="SELECT id, name, email FROM users LIMIT 5;"
Step 2: posts 테이블에 필요한 컬럼 확인
위 결과에서 title, content, category, user_id, views, created_at 외에 추가 필수 컬럼이 있는지 확인. 예: access_level, price, preview_content 등이 NOT NULL이면 기본값을 추가해야 함.

Step 3: 코드 변경 (변경 1~3)
[id].astro SEO 태그
index.astro 링크 확인
send-email.ts 푸터 추가
Step 4: 시드 데이터 INSERT (변경 4)
확인된 테이블 구조에 맞게 SQL 조정 후 실행

Step 5: 빌드 및 배포
Copynpm run build && npx wrangler pages deploy dist
구글 서치콘솔 등록 (수동, Reasonix 불필요)
배포 완료 후 브라우저에서:

https://search.google.com/search-console 접속
속성: aikorea24.kr 선택
URL 검사에 각 게시글 URL 입력:
https://aikorea24.kr/community/1
https://aikorea24.kr/community/2
https://aikorea24.kr/community/3
https://aikorea24.kr/community/4
https://aikorea24.kr/community/5
각각 "색인 요청" 클릭
최종 확인 사항
 site:aikorea24.kr/community 구글 검색 시 결과 노출
 각 게시글 페이지에 SEO 메타태그 정상 출력
 뉴스레터 하단에 커뮤니티 링크 표시
 시드 게시글 5개 모두 정상 표시
- aikorea24 Threads Engine v3 — Narrative-First Design

## 당신의 역할
당신은 AI 뉴스 큐레이터이자 스토리텔러입니다. 
200개의 건조한 AI 뉴스 기사에서 "사람들이 와!" 하고 말게 할 단 하나의 이야기를 발견하고, 
Threads 플랫폼에 맞게 쓰레드로 풀어내는 시스템을 구축하세요.

---

## 1. Threads가 무엇인가 (가장 중요)

Threads는 **하나의 긴 글을 500자 단위로 자른 것**입니다. 
카드뉴스가 아닙니다. 형식 A/B/C가 없습니다. 그냥 좋은 글일 뿐입니다.

### 쓰레드의 본질
하나의 완결된 이야기 ↓ 각 조각(500자)은 단독으로 읽어도 의미가 있고, ↓ 전체를 연결해서 읽으면 하나의 서사 아크를 이룸 ↓ 첫 조각: 스크롤을 멈춤 마지막 조각: 행동을 유도 (CTA)

Copy
### 좋은 쓰레드의 조건
- 각 조각은 독립적으로 읽혀도 "아, 재미있네" 싶어야 함
- 조각과 조각 사이에는 "다음이 궁금한" 맛이 있어야 함
- 전체를 다 읽으면 "아하!" 하는 깨달음이 있어야 함
- 중간에 반전(근데), 놀라움(헉), 깨달음(아하)이 배치되어야 함

### 나쁜 쓰레드
- "1번=훅, 2번=데이터..." 같은 형식에 내용을 끼워넣은 것
- 뉴스 기사를 그대로 요약한 것
- 각 조각이 독립적이지 않고 앞뒤 맥락이 없으면 읽히지 않음

---

## 2. Narrative Pitcher 접근법 (기존 접근과의 차이)

### 틀린 접근 (하지 말 것)
키워드로 기사 클러스터링 → 점수화 → 형식 A/B/C 선택 → 작성

Copy
### 올바른 접근 (할 것)
200개 기사 전체를 GPT가 스캔 ↓ "이 기사들 사이에 숨은 연결고리는 무엇인가?" ↓ "이 연결고리를 엮으면 어떤 이야기가 되는가?" ↓ "그 이야기의 첫 문장은 무엇인가?" (훅 발견) ↓ "그 이야기를 500자 단위로 풀면?"

Copy
### 핵심 통찰
> 키워드 "데이터센터"와 "물"로는 절대 못 찾는다.
> GPT가 "아, 이 기사(가디언)와 저 기사(아주경제)를 연결하면 
> 'AI 시대의 진짜 병목은 물이다' 라는 이야기가 나오겠구나" 
> 하고 발견해야 한다.

---

## 3. 시스템 아키텍처

main.py (v3) │ ├── 1. get_articles(100개) │ - DB에서 최대 100개 미발행 기사 로드 │ - posted.json에 등록된 기사 포함 (GPT가 전체 그림을 보게) │ - 다만 메인 기사는 미발행 기사여야 함 │ ├── 2. narrative_pitcher.get_pitches(articles) │ ├── 모델: gpt-4o-mini (비용 절감) │ ├── 청크: 50개씩 2개 청크 │ ├── 각 청크 → 2개 피치 → 총 4개 │ ├── 4개 → 최종 TOP 1 선정 │ ├── 출력: │ │ { │ │ "hook": "첫 문장 (15자 이내, 스크롤 멈추게 할 것)", │ │ "narrative": "이 이야기의 핵심 (한 줄)", │ │ "twist": "반전/놀라움 포인트", │ │ "emotion": "충격/불안/자부심/분노/놀라움 중 하나", │ │ "article_ids": [3~5개 관련 기사 ID], │ │ "sources": ["출처 URL 리스트"], │ │ "comparison_unit": "독자가 '와' 할 체감 단위" │ │ } │ └── 실패 시: skip + log + return (발행 안 함) │ ├── 3. writer.write_thread(pitch) │ ├── 모델: gpt-4o (1회) │ ├── 입력: pitcher의 내러티브 + 해당 기사들 │ ├── 규칙: │ │ - 첫 문장은 pitcher의 hook을 반드시 그대로 사용 │ │ - 각 조각은 500자 이내 │ │ - 각 조각 끝에 "다음이 궁금한" 맛을 남길 것 │ │ - 조각 수: 이야기에 맞게 (5~15개, 고정 아님) │ │ - 마지막에서 두 번째 조각에 모든 출처 표기 │ │ - 마지막 조각은 CTA만 (시스템이 하드코딩) │ ├── 출력: ["조각1", "조각2", ..., "조각N"] │ └── 실패 시(검증 불통): 재시도 2회 → 실패 시 skip │ └── 4. publisher.publish_chain(cards) ├── 각 조각을 연속 발행 (reply_to_id 체인) ├── 성공 시 posted.json 업데이트 └── 실패 시 log + 재시도

Copy
---

## 4. 파일 구조

/Users/twinssn/Projects/aikorea24/scripts/threads/v3/ ├── main_v3.py # 진입점 ├── narrative_pitcher.py # GPT가 이야기를 발견 ├── writer_v3.py # GPT가 쓰레드 작성 ├── validator_v3.py # 품질 검증 └── db_reader.py # (기존 파일 재사용, import)

기존 파일: publisher.py, token_refresh.py → 수정 금지, 그대로 사용 db_reader_v2.py, scorer_v2.py, enricher.py, writer_v2.py → 건드리지 말 것

Copy
---

## 5. 구현 상세

### 5.1 narrative_pitcher.py

```python
"""
narrative_pitcher.py — 100개 기사 → 가장 강력한 이야기 발견
- 모델: gpt-4o-mini
- 50개씩 2개 청크 → 각 2개 피치 → 총 4개 → TOP 1
"""
import os, json, re
from datetime import datetime
from openai import OpenAI

SYSTEM_PROMPT = """당신은 AI 뉴스 전문 "스토리 파인더"입니다.

100개의 건조한 AI 뉴스 기사들을 보고, 
단 하나의 "이야기"를 찾아내는 일을 합니다.

"이야기"란 무엇인가:
- 단순한 사실의 나열이 아니다
- 기사들 사이에 숨은 연결고리를 발견하는 것이다
- 그 연결고리를 엮으면 하나의 서사가 된다
- 그 서사에는 반전, 놀라움, 깨달음이 있어야 한다
- 그 서사의 첫 문장은 사람들이 스크롤을 멈추게 만든다

예시:
"미국 데이터센터 809개 중 3분의 2가 가뭄 지역에 있다."
+ "새만금 규제 83% 해제. 담수 5억 3,000만 톤."
+ "삼성 평택 팹, 물 때문에 수년간 갈등."
+ "젠슨 황: 한국은 AI 밸리를 만들고 있다."

→ 발견된 이야기: "AI 시대의 진짜 병목은 반도체가 아니라 물이다. 
   그리고 한국은 이 전쟁에서 역설적 강점을 가졌다."
→ 첫 문장: "AI 질문 한 번에 생수 한 병이 증발한다."

당신이 찾아야 할 것:
1. 기사들 사이의 "숨은 연결고리" — 겉으로는 달라 보이지만, 같은 흐름에 있는 기사들
2. 그 연결고리가 만들어내는 "반전" — 사람들이 모르는 사실
3. 한국 독자의 "일상과 연결되는 지점" — 그래서 내 일이야, 싶게
4. "첫 문장" — 15자 이내, 이걸 보면 나머지가 다 궁금해지는 문장

출력 형식 (반드시 아래 JSON 형식으로만 출력):

PITCH 1:
```json
{
  "hook": "15자 이내 첫 문장",
  "narrative": "이 이야기의 핵심 = 발견된 연결고리 (한 줄)",
  "twist": "반전 포인트 (한 줄)",
  "emotion": "충격/불안/자부심/분노/놀라움 중 하나",
  "article_ids": [관련 기사 ID 리스트, 3~5개],
  "sources": ["출처 URL 리스트"],
  "comparison_unit": "독자가 체감할 비교 단위"
}
PITCH 2: ...

중요:

"AI"라는 키워드로 기사를 묶지 말 것. AI 뉴스니까 당연히 AI가 나온다. 더 구체적인 연결고리를 찾아라.
기사 제목만 보지 말고, 본문 내용까지 봐야 연결고리가 보인다.
"이 기사들과 저 기사들을 같이 쓰면 재미있겠다"는 직감을 믿어라.
첫 문장은 절대 묻히지 않게. 강력해야 한다. """
def get_pitches(articles, max_articles=100): """100개 기사 → 3개 피치""" # 기사 텍스트 변환 articles_text = [] for a in articles[:max_articles]: articles_text.append(f""" 기사 #{a['id']}: 제목: {a.get('title','')} 본문: {a.get('description','')[:500]} 출처: {a.get('source','')} 링크: {a.get('link','')} """)

Copy# 2개 청크로 분할
mid = len(articles_text) // 2
chunks = [
    '\n---\n'.join(articles_text[:mid]),
    '\n---\n'.join(articles_text[mid:])
]

all_pitches = []
client = OpenAI(api_key=os.environ.get('OPENAI_API_KEY'))

for i, chunk in enumerate(chunks):
    resp = client.chat.completions.create(
        model='gpt-4o-mini',
        messages=[
            {'role': 'system', 'content': SYSTEM_PROMPT},
            {'role': 'user', 'content': f"""아래는 {i+1}/2번째 기사 묶음입니다.
이 기사들 중에서 가장 강력한 이야기 2개를 찾아 PITCH JSON 형식으로 출력해주세요.

{chunk}"""} ], temperature=0.9, max_tokens=2000, ) text = resp.choices[0].message.content pitches = parse_pitches_from_text(text) all_pitches.extend(pitches)

Copyif not all_pitches:
    return []

# 최종 TOP 1 선정
final_resp = client.chat.completions.create(
    model='gpt-4o-mini',
    messages=[
        {'role': 'system', 'content': '당신은 피치 평가자입니다. 아래 피치들 중 가장 강력한 1개를 선택하고 이유를 설명하세요. 기준: 1) 첫 문장의 강도 2) 반전의 충격 3) 한국 연결점 4) 이야기의 완결성'},
        {'role': 'user', 'content': json.dumps(all_pitches, ensure_ascii=False)}
    ],
    temperature=0.3,
    max_tokens=800,
)

# TOP 1 파싱
final_text = final_resp.choices[0].message.content
return parse_top_pitch(final_text, all_pitches)
Copy
### 5.2 writer_v3.py

```python
"""
writer_v3.py — 피치 → 쓰레드 작성
- 모델: gpt-4o (1회)
- 입력: pitcher의 내러티브 + 관련 기사
- 출력: ["조각1", "조각2", ...]
"""
import os, json, re
from datetime import datetime
from openai import OpenAI

CTA_FOOTER = """
매일 아침 AI 브리핑, 이메일로 받아보세요.
프로필 링크에서 무료 구독 가능합니다.
aikorea24.kr
"""

WRITER_SYSTEM_PROMPT = """당신은 AI 뉴스를 Threads 쓰레드로 만드는 스토리텔러입니다.

Threads 쓰레드란:
- 하나의 긴 글을 500자 단위로 자른 것입니다.
- 각 조각은 혼자 읽어도 의미가 있어야 합니다.
- 전체를 연결해서 읽으면 하나의 서사 아크가 되어야 합니다.
- 카드뉴스가 아닙니다. 형식에 내용을 끼워넣지 마세요.

글쓰기 원칙:
1. 첫 문장은 반드시 주어진 hook을 그대로 사용하세요. 절대 변경하지 마세요.
2. 각 조각(500자 이내)은 하나의 아이디어만 담으세요.
3. 조각의 끝은 "다음이 궁금한" 느낌으로 마무리하세요. (클리프행어)
4. 조각의 수는 이야기에 맞게 자연스럽게 결정하세요. (5~15개)
5. 각 조각은 독립적으로 읽혀도 이해되어야 합니다.
6. 반전, 놀라움, 깨달음이 쓰레드 전체에 고르게 배치되어야 합니다.
7. "근데", "그런데", "하지만"을 반전 신호로 활용하세요.
8. 숫자는 반드시 독자가 체감할 수 있는 단위로 환산하세요.
   (예: 한강 유량의 3분의 1, 잠실 수영장 40개 분량)
9. 한국 독자의 일상과 연결되는 지점을 반드시 포함하세요.
10. 형용사를 최소화하고, 사실만 진술하세요.
11. 이모지, 볼드, 이탤릭 등 서식을 사용하지 마세요.
12. 직접 인용은 날것 그대로 사용하세요. 절대 각색하지 마세요.
13. 각 조각에 카드 번호("2/8", "5/12" 등 형식)를 붙이세요.
14. 마지막에서 두 번째 조각 끝에 모든 출처 URL을 표기하세요.
    형식: "출처: [URL1] / [URL2] / [URL3]"
15. 마지막 조각은 CTA만 포함하세요. 본문 내용을 넣지 마세요.

조각 형식:
2/10

(내용)

Copy
중요: 규칙을 외우려 하지 마세요. 
"이 이야기를 어떻게 쓰면 사람들이 끝까지 읽을까"만 생각하세요.
"""

def write_thread(pitch, articles):
    """피치 + 관련 기사 → 쓰레드 조각 리스트"""
    client = OpenAI(api_key=os.environ.get('OPENAI_API_KEY'))
    
    # 관련 기사 텍스트
    related_articles = "\n\n".join([
        f"""=== 기사 {a['id']} ===
제목: {a.get('title','')}
본문: {a.get('description','')}
출처: {a.get('source','')}
링크: {a.get('link','')}"""
        for a in articles if a['id'] in pitch['article_ids']
    ])
    
    user_prompt = f"""아래 피치와 기사들을 바탕으로 Threads 쓰레드를 작성해주세요.

=== 피치 ===
첫 문장 (변경 금지): {pitch['hook']}
핵심 이야기: {pitch['narrative']}
반전: {pitch['twist']}
감정: {pitch['emotion']}
체감 단위: {pitch['comparison_unit']}

=== 관련 기사 ===
{related_articles}

=== 요구사항 ===
1. 첫 문장은 반드시 "{pitch['hook']}" 그대로 사용할 것
2. 각 조각 끝에 "다음이 궁금한" 맛을 남길 것
3. 조각 수는 이야기에 맞게 (5~15개)
4. 마지막에서 두 번째 조각에 모든 출처 표기
5. 마지막 조각은 CTA만 (아래 CTA 사용):

{CTA_FOOTER}"""
    
    for attempt in range(3):
        try:
            resp = client.chat.completions.create(
                model='gpt-4o',
                messages=[
                    {'role': 'system', 'content': WRITER_SYSTEM_PROMPT},
                    {'role': 'user', 'content': user_prompt},
                ],
                temperature=0.7,
                max_tokens=3000,
            )
            content = resp.choices[0].message.content.strip()
            
            # 검증
            cards = parse_cards(content)
            if validate_thread(cards, pitch):
                return cards
            
        except Exception as e:
            continue
    
    return []

def parse_cards(text):
    """---로 구분된 조각들을 파싱"""
    cards = [c.strip() for c in text.split('---') if c.strip()]
    return cards

def validate_thread(cards, pitch):
    """검증"""
    if not cards or len(cards) < 3:
        return False
    
    # 첫 문장 확인
    first_line = cards[0].strip().split('\n')[0]
    first_line_clean = re.sub(r'^\d+\s*/\s*\d+\s*\n?', '', first_line).strip()
    if pitch['hook'][:10] not in first_line_clean:
        return False
    
    # CTA 확인
    last_card = cards[-1]
    if '매일 아침 AI 브리핑' not in last_card:
        return False
    
    # 출처 확인
    if '출처:' not in cards[-2]:
        return False
    
    return True


def assemble_final(cards, sources):
    """최종 조립: 8번 CTA 하드코딩"""
    # 마지막에서 두 번째 카드에 출처 추가
    card_7 = cards[-2]
    source_line = f"\n출처: {' / '.join(sources)}"
    if '출처:' not in card_7:
        cards[-2] = card_7 + source_line
    
    # 마지막 카드는 CTA로 교체
    cards[-1] = CTA_FOOTER.strip()
    
    return cards
5.3 main_v3.py
Copy#!/usr/bin/env python3
"""
aikorea24 Threads v3 — Narrative-First Design
"""
import os, sys, json
from datetime import datetime

THREADS_DIR = '/Users/twinssn/Projects/aikorea24/scripts/threads'
sys.path.insert(0, THREADS_DIR)

def log(msg):
    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f'[{ts}] {msg}')
    with open(os.path.join(THREADS_DIR, 'logs', 'v3.log'), 'a', encoding='utf-8') as f:
        f.write(f'[{ts}] {msg}\n')

def run_v3(dry_run=False):
    # 1. 기사 로드
    from db_reader import get_articles
    articles = get_articles()
    if not articles:
        log('기사 없음 → 스킵')
        return
    
    log(f'기사 로드: {len(articles)}개')
    
    # 2. 피치 생성
    from v3.narrative_pitcher import get_pitches
    log('피치 생성 시작...')
    pitches = get_pitches(articles)
    
    if not pitches:
        log('❌ 흥미로운 이야기 발견 실패 → 스킵 (2시간 후 재시도)')
        return
    
    pitch = pitches[0]  # TOP 1
    log(f'✅ 피치 선정: "{pitch["hook"]}" ({pitch["emotion"]})')
    log(f'   관련 기사: {pitch["article_ids"]}')
    
    # 3. 쓰레드 작성
    from v3.writer_v3 import write_thread, assemble_final
    log('쓰레드 작성 시작...')
    cards = write_thread(pitch, articles)
    
    if not cards:
        log('❌ 쓰레드 작성 실패 → 스킵')
        return
    
    cards = assemble_final(cards, pitch['sources'])
    log(f'✅ 쓰레드 작성 완료: {len(cards)}개 조각')
    
    # 4. 초안 저장
    draft_path = os.path.join(THREADS_DIR, 'logs', 'drafts', 
                              f'v3_{datetime.now().strftime("%Y-%m-%d-%H")}.txt')
    with open(draft_path, 'w', encoding='utf-8') as f:
        f.write('\n---\n'.join(cards))
    log(f'💾 초안 저장: {draft_path}')
    
    if dry_run:
        log('[DRY RUN] 발행 생략')
        print('\n' + '='*60)
        print('\n---\n'.join(cards))
        print('\n' + '='*60)
        return
    
    # 5. 발행
    from publisher import publish_thread_chain
    log('발행 시작...')
    result = publish_thread_chain(cards, articles[0])
    if result:
        log(f'✅ 발행 완료: 루트 ID {result}')
    else:
        log(f'❌ 발행 실패')


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--once', action='store_true')
    args = parser.parse_args()
    run_v3(dry_run=args.dry_run or args.once)
Copy
6. 구현 순서
scripts/threads/v3/ 디렉토리 생성
v3/narrative_pitcher.py 작성
v3/writer_v3.py 작성
main_v3.py (루트 디렉토리) 작성
v3/__init__.py (빈 파일) 생성
dry-run 테스트: .venv/bin/python3 scripts/threads/main_v3.py --dry-run
결과 확인 → 수정 → 재테스트
7. 주의사항
기존 파일 절대 수정 금지: publisher.py, token_refresh.py, db_reader.py 등
v2 파일도 유지: fallback용으로 보존
비용 관리: narrative_pitcher는 gpt-4o-mini만 사용 (gpt-4o 금지)
실패 처리: 피치 실패 또는 작성 실패 시 → 그냥 스킵. v1/v2 fallback 금지
첫 문장: 절대 변경 금지. validator가 확인
8번 CTA: 시스템이 하드코딩. GPT가 생성 금지**핵심만 요약하면:**
1. "형식"이라는 개념을 버려라
2. GPT가 100개 기사에서 "이야기"를 발견하게 해라
3. 첫 문장이 모든 것을 결정한다
4. 각 조각은 독립적으로도 재미있어야 한다
5. 전체는 하나의 서사 아크여야 한다
- 작업: narrative_pitcher.py chat_completion 마이그레이션 오류 수정

## 문제
`chat_completion()` 함수는 문자열(str)을 반환하는데, 
코드 어딘가에서 `resp.choices[0].message.content` 처럼 
OpenAI 응답 객체 형식으로 접근하고 있어서 
`'str' object has no attribute 'choices'` 에러가 발생함.

## 수정할 파일
`/Users/twinssn/Projects/aikorea24/scripts/threads/v3/narrative_pitcher.py`

## 수정 방법
1. 파일 내에서 `client.chat.completions.create(` 호출이 남아있는지 찾아서
   모두 `chat_completion(` 호출로 교체할 것.
   
2. `resp = chat_completion(...)` 형태로 받은 응답은 이미 문자열이므로,
   `resp.choices[0].message.content` 같은 속성 접근을 제거하고
   변수 `text`에 직접 할당하는 방식으로 수정할 것.
   
3. `import` 부분에 `from openai import OpenAI`가 남아있으면 제거할 것
   (model_router.chat_completion만 사용).
   
4. `client = OpenAI(...)` 코드가 남아있으면 전부 제거할 것.

## 검증
수정 후 다음 명령어로 dry-run 테스트:
```bash
.venv/bin/python3 /Users/twinssn/Projects/aikorea24/scripts/threads/main_v3.py --dry-run
- 추가 수정: 청크 분할 제거 → 단일 호출로 통합

narrative_pitcher.py의 get_pitches() 함수에서 
청크를 2개로 나누는 로직을 제거하고,
100개 기사를 한 번에 chat_completion()으로 전달하도록 수정할 것.

변경 전:
  chunks = [50개, 50개]
  for each chunk → chat_completion() → 각 2개 피치
  총 4개 피치 → chat_completion() → TOP 1

변경 후:
  전체 100개 → chat_completion() 한 번 → 3개 PITCH
  → parse_pitches_from_text() → 첫 번째 피치 반환
  
  (2단계 평가도 제거. 한 번에 3개 피치 뽑고 첫 번째 선택)

이유:
- DiffusionGemma는 256K 컨텍스트로 100개 기사를 한 번에 처리 가능
- 청크 분할 시 기사 간 연결고리 발견률이 떨어짐
- 단일 호출이 더 빠르고 간단함
드라이런 결과 를 보여줘.
- 추가 수정: 청크 분할 제거 → 단일 호출로 통합

narrative_pitcher.py의 get_pitches() 함수에서 
청크를 2개로 나누는 로직을 제거하고,
100개 기사를 한 번에 chat_completion()으로 전달하도록 수정할 것.

변경 전:
  chunks = [50개, 50개]
  for each chunk → chat_completion() → 각 2개 피치
  총 4개 피치 → chat_completion() → TOP 1

변경 후:
  전체 100개 → chat_completion() 한 번 → 3개 PITCH
  → parse_pitches_from_text() → 첫 번째 피치 반환
  
  (2단계 평가도 제거. 한 번에 3개 피치 뽑고 첫 번째 선택)

이유:
- DiffusionGemma는 256K 컨텍스트로 100개 기사를 한 번에 처리 가능
- 청크 분할 시 기사 간 연결고리 발견률이 떨어짐
- 단일 호출이 더 빠르고 간단함
이 작업 완료하고 드라이런 한 후 결과를 보여줘.

---

# v3 Threads Writer — 2026-06-20 업데이트 내역

## 수정 1: validate_year() 재설계

### 문제
`validate_year()`가 기사 `pub_date`(발행일)의 연도를 쓰레드에 강제했다.
→ GPT-4o가 기사 본문에 없는 "2026년 6월 20일"을 사건 발생일로 지어냄

### 변경
**기존:** `expected_year`(pub_date 추출)가 쓰레드에 없거나 최다 언급이 아니면 실패
**변경:** 쓰레드의 20XX 연도가 기사 본문에도 있는지 확인 (없으면 할루시네이션 → 실패)

```python
# writer_v3.py
def validate_year(cards, article_body_text):
    card_years = set(...)  # 쓰레드에서 20XX 추출
    body_years = set(...)  # 기사 본문에서 20XX 추출
    if not card_years:
        return True        # 연도 미표기 → 통과
    invented = card_years - body_years
    if invented:
        return False       # 본문에 없는 연도 → 실패
    return True
```

### 시스템 프롬프트 연도 원칙
**기존:** "기사에 언급된 연도가 없으면 기사 발행일(YYYY-MM-DD)의 연도를 사용하세요"
**변경:** "기사 본문에 명시된 날짜/연도만 사용하라. 본문에 연도가 없으면 쓰레드에도 연도를 표시하지 마라"

---

## 수정 2: article_ids 타입 안전 처리

### 문제
피치의 `article_ids`가 `['#32698']`(str + #접두사) 형식으로 오면 DB int id(32698)와 매칭 실패
→ `related`가 항상 비어서 → `all_articles[:2]` fallback → 엉뚱한 기사로 내용 오염

### 변경
```python
# writer_v3.py - write_thread()
for aid in article_ids:
    raw = str(aid).lstrip('#').strip()     # '#32698' → '32698'
    article_id_set.add(int(raw))           # int로 변환
    # int 실패 시 str로 fallback
related = [a for a in all_articles if a.get('id') in article_id_set]
```

### fallback 제거 (P1)
**기존:** `if not related: related = all_articles[:2]`
**변경:** `if not related: return []` → 스킵. 다음 주제로 넘어감

---

## 수정 3: 고유명사 영어 원문 표기

### 문제
- GPT가 `Huawei`를 `화웨웨이`로 잘못 음역
- hook은 pitcer 생성 → writer가 변경 불가 → 첫 줄에 `엔비디아` 잔류

### 변경
**pitcher(narrative_pitcher.py) 시스템 프롬프트:**
```
hook: ...
- 고유명사(기업명, 인물명, 제품명)는 영어 원문을 사용하라.
  예: 엔비디아(X) → Nvidia(O), 오픈AI(X) → OpenAI(O)
```

**writer(writer_v3.py) 문체 원칙:**
```
- 고유명사(기업명, 인물명, 제품명)는 영어 원문을 그대로 사용하라.
  예: 화웨이(X) → Huawei(O), 앤트로픽(X) → Anthropic(O), 오픈AI(X) → OpenAI(O)
```

