# AI 도구 수집 스킬

> Product Hunt, GitHub, Futurepedia, HuggingFace, TopAI.tools에서 AI 도구를 자동 수집해서 웹사이트 도구 데이터베이스 구축

---

## 1. 개요

여러 소스에서 신규 AI 도구를 수집 → 중복 제거 → 웹 크롤링으로 메타데이터 보강 → 한국어 설명 생성 → MD 파일 저장 → git commit → 텔레그램 알림 → Cloudflare 배포까지 처리하는 자동화 파이프라인.

**주요 스크립트:** `scripts/tools_collector.py`

**실행 주기:** 매일 새벽 06:00 (launchd `kr.aikorea24.tools-collector`)

**수집 소스:**
| 소스 | 방식 | 빈도 |
|------|------|------|
| Product Hunt | RSS 피드 | 매번 |
| GitHub Awesome AI Tools | 페이지 크롤링 | 주 1회 |
| Futurepedia | 사이트맵 | 매번 |
| Hugging Face Papers | RSS | 매번 |
| TopAI.tools | 웹사이트 크롤링 | 매번 |

---

## 2. 사전 준비

### 2.1 환경변수

```bash
# OpenAI (한국어 메타데이터 생성)
OPENAI_API_KEY=sk-xxx

# DeepSeek (한국어 메타 생성 대체)
DEEPSEEK_API_TOKEN=sk-xxx
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1

# Telegram 알림
TELEGRAM_BOT_TOKEN=xxx
TELEGRAM_CHAT_ID=xxx

# Cloudflare
CLOUDFLARE_ACCOUNT_ID=xxx
CLOUDFLARE_ZONE_ID=xxx

# Brevo (선택)
BREVO_API_KEY=xxx
```

### 2.2 Python 의존성

```bash
pip install requests beautifulsoup4 openai
```

---

## 3. 실행 방법

### 3.1 수동 1회 실행

```bash
cd /Users/twinssn/Projects/aikorea24
python3 scripts/tools_collector.py --collect --batch 5
```

- `--collect`: 수집 모드 실행
- `--batch N`: 소스당 최대 N개 수집 (기본 10)

### 3.2 전체 파이프라인 실행 (launchd)

```bash
launchctl load ~/Library/LaunchAgents/kr.aikorea24.tools-collector.plist
```

---

## 4. 동작 흐름

### 4.1 소스별 수집

**Product Hunt RSS:**
```python
PRODUCT_HUNT_FEED = 'https://www.producthunt.com/feed'
# RSS 파싱 → AI 관련 항목 필터링 → 최대 N개 수집
```

**GitHub Awesome AI Tools:**
```python
# 주 1회 실행 (마지막 실행으로부터 7일 경과 시)
# GitHub 리포지토리 페이지 크롤링 → 도구 목록 추출
```

**Futurepedia:**
```python
FUTUREPEDIA_SITEMAP = "https://www.futurepedia.io/sitemap.xml"
# 사이트맵에서 도구 URL 추출
```

**Hugging Face Papers:**
```python
HUGGINGFACE_PAPERS_RSS = "https://huggingface.co/papers"
# RSS 파싱 → 논문 도구 추출
```

**TopAI.tools:**
```python
TOPAI_TOOLS_URL = "https://topai.tools"
# 웹사이트 크롤링 → 도구 정보 추출
```

### 4.2 중복 제거

```python
# 기존 도구 목록과 비교
existing_slugs = load_existing_slugs()  # src/content/tools/*.md
existing_names = load_existing_names()

for tool in new_tools:
    if tool['slug'] in existing_slugs or tool['name'] in existing_names:
        skip  # 중복 스킵
    else:
        collect  # 신규 수집
```

### 4.3 웹 크롤링으로 메타데이터 보강

각 도구 URL에서 다음을 크롤링:
- **제목**: page title 또는 og:title
- **설명**: meta description 또는 본문 일부
- **카테고리**: 페이지 콘텐츠 기반 추정

```python
def crawl_tool_metadata(url):
    resp = requests.get(url, headers=USER_AGENT, timeout=10)
    soup = BeautifulSoup(resp.text, 'html.parser')
    title = soup.find('meta', {'property': 'og:title'})
    description = soup.find('meta', {'name': 'description'})
    return {
        'title': title['content'] if title else '...',
        'description': description['content'] if description else '...'
    }
```

### 4.4 한국어 메타데이터 생성

OpenAI/DeepSeek API로 한국어 설명 생성:

```python
def generate_korean_metadata(title, description):
    # LLM API 호출 → 한국어 한줄 요약 + 상세 설명 생성
    response = openai.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{
            "role": "user",
            "content": f"다음 AI 도구에 대한 한국어 설명을 작성해줘:\n제목: {title}\n설명: {description}"
        }]
    )
    return response.choices[0].message.content
```

### 4.5 MD 파일 생성

`src/content/tools/{slug}.md` 형식으로 저장:

```markdown
---
name: "도구명"
description: "한줄 설명"
category: "카테고리"
price: "무료/월 $XX"
koreanSupport: true/false
difficulty: "초보자 OK/중급/고급"
url: "https://..."
useCases: ["사용 사례 1", "사용 사례 2"]
tags: ["태그1", "태그2"]
featured: false
order: N
tasks: ["작업1", "작업2"]
updated: "2026-08-07"
---

## 한줄 요약

...

## 핵심 기능

- ...

## 가격 정책

- **무료 플랜**: ...
- **유료 플랜**: ...

## 한국어 지원

...

## 이런 분에게 추천합니다

...

## 실제 활용 예시

- ...

## 유사 툴과 비교

**장점:**
- ...

**단점:**
- ...

**이런 분에게 가장 적합합니다:** ...

## 자주 묻는 질문

**Q. ...**
A. ...
```

### 4.6 git commit + 배포 + 알림

```python
# 1. git commit
subprocess.run(["git", "add", f"src/content/tools/{slug}.md"], cwd=PROJECT_DIR)
subprocess.run(["git", "commit", "-m", f"feat: AI 툴 추가 ({tool_name})"], cwd=PROJECT_DIR)
subprocess.run(["git", "push"], cwd=PROJECT_DIR)

# 2. Cloudflare Pages 배포
subprocess.run(["wrangler", "pages", "deploy", "dist", ...])

# 3. 텔레그램 알림
send_telegram(f"✅ {tool_name} → {slug}.md\n{category} · {price}")
```

---

## 5. 파일 구조

```
scripts/
└── tools_collector.py           # 메인 수집기

src/content/tools/               # 생성된 도구 MD 파일들
├── coloringdaily.md
├── unfox-ai.md
├── pebbles-ai.md
└── ...
```

---

## 6. 설정 파일

### config/pexels_used_ids.json (썸네일용)

도구 수집과는 별도지만 같은 프로젝트 인프라 공유.

---

## 7. 체크리스트

### 최초 설정
- [ ] OpenAI API 키 또는 DeepSeek API 토큰 설정
- [ ] Telegram 봇 토큰 + 채팅 ID 설정
- [ ] `python3 scripts/tools_collector.py --collect --batch 5` 테스트 실행
- [ ] 생성된 MD 파일 품질 확인
- [ ] git push + 배포 확인
- [ ] 텔레그램 알림 수신 확인

### 정기 실행
- [ ] launchd 등록이 되어 있는지 확인
- [ ] 매일 아침 수집 결과 로그 확인
- [ ] 중복 제거 정상 동작 확인
- [ ] 신규 도구 MD 파일이 `src/content/tools/`에 추가되는지 확인

---

## 8. 트러블슈팅

| 증상 | 원인 | 해결 |
|------|------|------|
| 수집 0건 | 소스 일시 장애/변경 | 소스 상태 확인, 수동 재시도 |
| 크롤링 실패 | 대상 사이트 구조 변경 | 크롤링 selector 업데이트 |
| 한국어 메타 품질 저하 | API 키 문제/모델 변경 | API 키 확인, 프롬프트 조정 |
| git push 실패 | 인증/네트워크 | git credential 확인 |
| 배포 실패 | wrangler 인증 | auth profile 확인 |

---

*문서 버전: 1.0 | 생성일: 2026-08-07*
