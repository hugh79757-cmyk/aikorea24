# 썸네일 자동 생성 스킬

> Pexels API로 뉴스 기반 이미지를 검색 → DeepSeek 키워드 추출 → 800x800 WebP 썸네일 생성 + 품질 검증 + 중복 방지

---

## 1. 개요

뉴스 기사 제목/설명을 기반으로 Pexels에서 관련 이미지를 찾아 800x800 WebP 썸네일을 생성하는 파이프라인.

**주요 스크립트:** `scripts/auto_thumbnail.py`

**사용 API:**
- Pexels API (이미지 검색/다운로드)
- DeepSeek API (키워드 추출)

**출력:** `public/images/{slug}/thumbnail.webp`

---

## 2. 사전 준비

### 2.1 환경변수

```bash
# Pexels API
PEXELS_API_KEY=xxx  # ~/.env.common 에 설정

# DeepSeek (키워드 추출)
DEEPSEEK_API_TOKEN=sk-xxx  # ~/.env.common 에 설정

# 프로젝트 설정
PROJECT_DIR=/Users/twinssn/Projects/aikorea24
```

### 2.2 Python 의존성

```bash
pip install requests beautifulsoup4 pillow openai
```

### 2.3 Pexels API 키 발급

1. [Pexels API 가입](https://www.pexels.com/api/)
2. API Key 발급
3. `~/.env.common`에 `PEXELS_API_KEY=xxx` 추가

---

## 3. 실행 방법

### 3.1 파이프라인 통합 실행

```bash
cd /Users/twinssn/Projects/aikorea24
python3 scripts/run_pipeline.py  # 기본 포함됨
```

### 3.2 단독 실행

```bash
cd /Users/twinssn/Projects/aikorea24
python3 scripts/auto_thumbnail.py <URL> <slug> --title "제목" --description "설명"
```

예시:
```bash
python3 scripts/auto_thumbnail.py \
  "https://techcrunch.com/2026/08/07/openai-new-model" \
  "openai-new-model-released" \
  --title "OpenAI 새 모델 출시" \
  --description "OpenAI가 차세대 AI 모델을 공개했다"
```

### 3.3 프로그램matic 호출

```python
import auto_thumbnail

rel_path = auto_thumbnail.process_thumbnail(
    url="https://example.com/article",
    slug="article-slug",
    title="기사 제목",
    description="기사 설명"
)
print(f"썸네일 경로: {rel_path}")
# 출력: /images/article-slug/thumbnail.webp
```

---

## 4. 동작 흐름

### 4.1 DeepSeek 키워드 추출 (`_extract_deepseek_keyword()`)

기사 제목/설명을 DeepSeek에 보내 Pexels 검색용 키워드 추출:

```python
# 시스템 프롬프트
"Pick the best stock photo keyword for this news from: {DEEPSEEK_POOL}.
 Or create a 1-2 word similar visual keyword. Return ONLY the keyword, lowercase, max 3 words."

# 사용자 입력
description[:400]
```

**DEEPSEEK_POOL** (40개 기본 키워드):
`abstract technology`, `artificial intelligence`, `big data`, `binary code`, `brain neuron`, `business meeting`, `chatbot`, `circuit board`, `cloud computing`, `code programming`, `cyber security`, `data center`, `deep learning`, `digital brain`, `digital transformation`, `factory automation`, `fiber optics`, `global network`, `hand robot`, `internet things`, `machine learning`, `mobile device`, `network server`, `office technology`, `robot arm`, `saas`, `semiconductor`, `server room`, `smart city`, `social media`, `software code`, `startup`, `stock market`, `technology abstract`, `virtual reality`, `ai chip`, `blockchain`, `cloud server`, `computer science`

**폴백 체인:**
1. DeepSeek API 호출 (최대 3회 재시도, exponential backoff)
2. 실패 시 DEEPSEEK_POOL에서 랜덤 선택

### 4.2 Pexels 검색 (`search_pexels()`)

```python
# 페이지네이션: 최대 3페이지 × 15장 = 최대 45개 후보
for page in range(1, max_pages + 1):
    resp = requests.get(
        "https://api.pexels.com/v1/search",
        headers={"Authorization": api_key},
        params={"query": keyword, "per_page": 15, "page": page},
        timeout=15
    )
```

### 4.3 미사용 사진 선택 (`_pick_unused_photo()`)

`config/pexels_used_ids.json`에 기록된 used_ids와 비교하여 미사용 사진 선택.

### 4.4 대체 쿼리 폴백

미사용 사진이 없으면 DEEPSEEK_POOL의 다른 키워드로 최대 5회 재시도.

### 4.5 이미지 다운로드 + 썸네일 생성

```python
# 1. large 소스 URL 가져오기 (없으면 medium)
img_url = chosen["src"]["large"] or chosen["src"]["medium"]

# 2. 다운로드
image_data = download_image(img_url)

# 3. 썸네일 생성
create_thumbnail(image_data, output_path)
# → 중앙 크로핑(정사각형) → 800x800 리사이즈(LANCZOS) → WebP 품질 85
```

### 4.6 품질 검증 (`validate_thumbnail_quality()`)

```python
is_valid, reason = validate_thumbnail_quality(output_path)
# 체크 항목:
# - 파일 존재
# - 파일 크기 ≥ 15KB
# - 유효한 이미지 (PIL verify)
# - 해상도 800x800
# - 포맷 WEBP
```

**품질 재시도:** 실패 시 다른 키워드로 최대 2회 재시도 → 모두 실패 시 placeholder 사용.

### 4.7 Used ID 저장

```python
_save_used_id(pixel_id)  # config/pexels_used_ids.json 에 추가
```

---

## 5. 파일 구조

```
scripts/
└── auto_thumbnail.py              # 썸네일 생성기

config/
└── pexels_used_ids.json           # 사용된 Pexels 사진 ID 기록

public/images/
├── {slug}/
│   └── thumbnail.webp             # 생성된 썸네일
├── news-keyword-og.webp           # placeholder (기본값)
└── ...
```

---

## 6. Thumbnail 품질 검증 기준

| 항목 | 기준 |
|------|------|
| 파일 존재 | 필수 |
| 파일 크기 | ≥ 15KB |
| 해상도 | 800×800px |
| 포맷 | WEBP |
| 무결성 | PIL verify 통과 |

---

## 7. 체크리스트

### 최초 설정
- [ ] Pexels API 키 발급 + `~/.env.common`에 설정
- [ ] DeepSeek API 토큰 설정 (키워드 추출용, 없으면 랜덤 폴백)
- [ ] 기본 placeholder 이미지 `public/images/news-keyword-og.webp` 존재 확인
- [ ] `python3 scripts/auto_thumbnail.py` 단독 테스트 실행
- [ ] 생성된 썸네일 품질 확인 (해상도/포맷/크기)

### 파이프라인 통합
- [ ] `run_pipeline.py` 실행 시 썸네일 생성 포함 확인
- [ ] 생성된 썸네일 경로가 블로그 frontmatter의 `image:` 필드에 자동 주입되는지 확인
- [ ] 동일 Pexels 사진 중복 사용 방지 확인 (used_ids.json)

---

## 8. 트러블슈팅

| 증상 | 원인 | 해결 |
|------|------|------|
| Pexels 검색 0건 | 키워드 부적합/API 키 | 키워드 확인, API 키 확인 |
| DeepSeek 키워드 추출 실패 | API 키/네트워크 | 폴백으로 랜덤 키워드 사용 (로그에 기록) |
| 이미지 다운로드 실패 | URL 만료/차단 | Pexels photo ID 재사용 방지 확인 |
| 품질 검증 실패 | 이미지 크기/해상도 | 품질 재시도 (최대 2회) → placeholder |
| WebP 변환 오류 | Pillow 설치 문제 | `pip install pillow` 재설치 |

---

*문서 버전: 1.0 | 생성일: 2026-08-07*
