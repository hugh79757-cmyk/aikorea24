# 심층글(Deep Article) 생성 스킬

> 뉴스 URL 크롤링 → AI 심층 분석 프롬프트 → 블로그 마크다운 생성 → frontmatter 정규화 → 저장

---

## 1. 개요

뉴스 기사 URL을 받아 원문을 크롤링하고, MiMo API로 심층 분석 블로그 글을 생성한 후 Astro 콘텐츠 컬렉션 형식으로 저장하는 파이프라인.

**주요 스크립트:** `scripts/auto_deep_article.py`

**사용 API:** MiMo (xiaomimimo.com) — 모델: `mimo-v2.5`

**출력:** `src/content/blog/YYYY-MM-DD-슬러그.md`

---

## 2. 사전 준비

### 2.1 환경변수

```bash
# MIMO API
MIMO_API_KEY=xxx  # ~/.env.common 에 설정

# 프로젝트 설정
PROJECT_DIR=/Users/twinssn/Projects/aikorea24
```

`~/.env.common`:
```bash
MIMO_API_KEY=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

### 2.2 Python 의존성

```bash
pip install requests beautifulsoup4
```

---

## 3. 실행 방법

### 3.1 파이프라인 통합 실행

```bash
cd /Users/twinssn/Projects/aikorea24
python3 scripts/run_pipeline.py
```

※ 심층글(deep article) 기능은 2026-07-12 Phase 26에서 비활성화되었으며, 2026-08-13 기준 auto_deep_article.py는 제거되었습니다. 현재 블로그 글 생성은 blog_draft_generator.py의 generate_draft()를 통해 이루어집니다.

### 3.2 단독 테스트 실행

```bash
cd /Users/twinssn/Projects/aikorea24
python3 scripts/auto_deep_article.py
```

※ 스크립트 내 main()에 테스트 기사가 하드코딩되어 있어, 단독 실행 시 테스트 기사로 동작합니다.

### 3.3 프로그램matic 호출

```python
import auto_deep_article

# 1. 원문 크롤링
content = auto_deep_article.crawl_article("https://example.com/article")

# 2. 심층분석 글 생성
article_md = auto_deep_article.generate_deep_article(title, content, url)

# 3. 파일 저장 (frontmatter 정규화 + image: 자동 주입)
filepath = auto_deep_article.save_article(article_md, title)
print(f"저장 완료: {filepath}")
```

---

## 4. 동작 흐름

### 4.1 원문 크롤링 (`crawl_article()`)

**크롤링 selector 체인 (우선순위 순):**
1. `article`
2. `main`
3. `.post-content`, `.article-content`, `.entry-content`
4. `#content`, `.content`
5. `.ArticleBody-articleBody`, `.article-body`
6. `.story-body`, `.story-text`
7. `[class*="articleBody" i]`
8. 최후의 fallback: `body` 전체

**크롤링 후 처리:**
- `script`, `style`, `nav`, `footer`, `.ad`, `.advertisement` 태그 제거
- 텍스트 추출 (strip + newline separator)
- 500자 이상만 유효로 간주
- 최대 5000자까지 추출

### 4.2 심층분석 글 생성 (`generate_deep_article()`)

**프롬프트 구성:**
```
[55줄 DEEP_ANALYSIS_PROMPT]  ← 상세 규칙 포함
+ 원문 뉴스 제목/URL
+ 원문 내용 (최대 3000자)
+ "위 뉴스를 바탕으로 심층분석 블로그 포스팅을 작성해줘"
```

**MiMo API 호출:**
```python
requests.post(
    f"{MIMO_BASE_URL}/chat/completions",
    headers={"Authorization": f"Bearer {_mimo_key}", "Content-Type": "application/json"},
    json={
        "model": "mimo-v2.5",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 4000,
        "temperature": 0.5,
    },
    timeout=60
)
```

### 4.3 Frontmatter 정규화 (`normalize_frontmatter()`)

AI가 생성한 마크다운의 frontmatter를 강제로 정규화:

1. **코드 펜스 제거**: 시작/끝 ``` 제거
2. **Frontmatter 파싱**: `---` 사이 필드 추출
3. **필수 필드 보장** (없으면 기본값):
   - `title`: 기사 제목
   - `description`: 빈 문자열
   - `date`: 오늘 날짜
   - `draft`: false
   - `tags`: `["AI", "뉴스"]`
   - `category`: `뉴스`
4. **따옴표 보장**: title/description에 따옴표 없으면 추가

### 4.4 Image 필드 자동 주입 (`inject_frontmatter_image()`)

```python
# 썸네일 파일이 존재하면 frontmatter에 image: 필드 추가
thumbnail_file = PROJECT_DIR / "public" / "images" / slug / "thumbnail.webp"
if thumbnail_file.exists():
    markdown_content = inject_frontmatter_image(markdown_content, thumbnail_path)
```

- `draft:` 값이 깨진 경우(`\x01` 등) `false`로 보정
- `image:` 필드가 이미 있으면 건너뛰기

### 4.5 파일 저장 (`save_article()`)

- 파일명: `YYYY-MM-DD-슬러그.md`
- 슬러그 생성: 제목을 소문자 영문/한글 외 문자 → `-`로 치환, 최대 60자
- 저장 위치: `src/content/blog/`

---

## 5. 심층분석 프롬프트 (DEEP_ANALYSIS_PROMPT)

핵심 규칙 요약:

**문체:**
- 모든 문장 `~합니다/~입니다/~했습니다` 체
- 반말(`~다/~했다/~임`) 절대 금지

**SEO:**
- title 앞 30자 안에 핵심 검색 키워드 배치
- description 앞 80자 안에 키워드와 글의 가치 포함

**내용 구조:**
- 서론/본론/마무리 항목 각각 소제목만 사용
- 마무리 항목만 `## 마무리:` 접두사

**금지:**
- 표 사용 금지
- 이모티콘 사용 금지
- 중국어(한자) 사용 금지

**권장:**
- 전문 용어에 괄호 설명 병기
- 배경, 맥락, 영향 다룸
- 경쟁사/유사 사례 비교 포함
- 한국 사용자에게 미치는 영향 다룸
- 기술적 내용은 비유/일상적 예시로 설명

---

## 6. 파일 구조

```
scripts/
└── auto_deep_article.py          # 심층글 생성기

src/content/blog/                 # 생성된 블로그 포스트
├── 2026-08-07-그라인드-ai-지출-효과...
├── 2026-08-07-구글-픽셀-ai-잠금화면...
└── ...
```

---

## 7. 체크리스트

### 최초 설정
- [ ] `~/.env.common`에 `MIMO_API_KEY` 설정
- [ ] `python3 scripts/auto_deep_article.py` 테스트 실행
- [ ] 생성된 MD 파일 확인 (frontmatter + 내용 품질)
- [ ] `python3 scripts/validate_blog_posts.py` 검증 통과 확인

### 파이프라인 통합
- [ ] `run_pipeline.py` 실행 확인 (기본 실행)
- [ ] 브리핑 아이템의 `deep_dive_url`이 생성된 블로그 URL로 연결되는지 확인
- [ ] 썸네일과 blog post의 image: 필드 연결 확인

---

## 8. 트러블슈팅

| 증상 | 원인 | 해결 |
|------|------|------|
| 크롤링 실패 (None 반환) | URL 접근 불가/차단 | User-Agent 확인, URL 접근 테스트 |
| API 오류 (401/403) | MIMO API 키 문제 | 키 재발급/확인 |
| 중국어 문자 포함 | 프롬프트 지시 무시 | remove_chinese() 안전망으로 제거됨 (경고 로그) |
| frontmatter 누락 | AI 출력 이상 | normalize_frontmatter()가 기본값 채움 |
| image: 필드 없음 | 썸네일 미생성 | auto_thumbnail.py 먼저 실행 또는 placeholder 확인 |

---

*문서 버전: 1.0 | 생성일: 2026-08-07*
