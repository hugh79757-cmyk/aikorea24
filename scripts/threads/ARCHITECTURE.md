# Threads 자동 발행 파이프라인 — 기술 문서

## 개요

AI 뉴스 기사 100개를 분석하여 5개 카드 Threads 쓰레드로 자동 생성·발행한다.
2시간 간격 스케줄러로 동작하며, 중복 주제를 방지하고 발행 이력을 관리한다.

---

## 파일 구조

```
scripts/threads/
├── main_v3.py              # 진입점 — 스케줄러/dry-run/1회 실행
├── db_reader.py             # D1 데이터베이스 → 기사 풀 로드 + URL 검증 함수
├── publisher.py             # Threads API 연동 발행
├── posted.json              # 발행 이력 저장소
├── logs/                    # 실행 로그 + 초안 보관
│   ├── drafts/              # GPT 생성물 원본 저장
│   └── YYYY-MM-DD.log      # 일별 실행 로그
└── v3/
    ├── model_router.py      # 모델 라우팅 (DiffusionGemma → GPT-4o-mini)
    ├── narrative_pitcher.py # 기사 → 피치 (이야기 발견)
    ├── pitch_evaluator.py   # 피치 품질 평가 게이트
    ├── writer_v3.py         # 피치 → 쓰레드 작성 (핵심)
    └── style_examples.md    # 문체 예시 (3개)
```

---

## 데이터 흐름

```
D1 Database
    │
    ▼
[1] db_reader.get_articles()
    │   기사 풀 (posted.json 기준 중복 제외)
    │   1순위: 오늘 브리핑 → 2순위: 최근 7일 → 3순위: 이전
    │   pub_date RFC 2822 / YYYY-MM-DD 변환 후 필터링
    │
    ▼
[2] narrative_pitcher.get_pitches()
    │   100개 기사 → description 원문 (크롤링 없음)
    │   → DiffusionGemma → 3개 피치 JSON
    │   ↓ hook[:8]+article_ids 중복 검사 (pitch_history 대조)
    │   ↓ pitch_evaluator.filter_pitches() 0~6점 평가 (4개 기준)
    │     (방향 정확성 0점이면 강제 불통과)
    │   ↓ posted.json pitch_history 저장
    │
    ▼
[3] writer_v3.write_thread()
    │   피치 연결 기사 URL → fetch_article_body() 원문 크롤링
    │   ├─ 크롤링 성공 → crawled_urls에 URL 기록
    │   ├─ 크롤링 실패 → description fallback
    │   ├─ 모든 기사 크롤링 실패 → 스킵
    │   build_system_prompt() + user_prompt → 모델 추론
    │   ↑ DiffusionGemma 2회 시도 → 실패 시 GPT-4o-mini 1회
    │   ↓ fix_cards() — GPT-4o-mini로 글자 단위 오류 수정
    │   ↓ validate_cards() + validate_year() + validate_keywords()
    │   ↓ assemble_final(crawled_urls) — 크롤링 성공 URL 중 선택
    │   ↓ save_draft() 로그/초안 저장
    │
    ▼
[4] publisher.publish_thread_chain()
    │   add_line_spacing() — 문장 사이 공백 추가
    │   각 카드 → Threads Graph API 컨테이너 생성
    │   reply_to_id 체인 → 연속 답글 발행
    │   posted.json posted_ids/links 갱신
    │
    ▼
    Threads 게시 완료 (루트 ID 반환)
```

---

## 컴포넌트 상세

### 1. db_reader.py

D1 database에서 기사를 3단계 우선순위로 로드한다.

| 우선순위 | 조건 | 설명 |
|---------|------|------|
| 1순위 | 오늘 briefing_items 포함 news | AI 브리핑에 선정된 핵심 기사 |
| 2순위 | 최근 7일 news (최대 **2000**개) | 브리핑 제외, 발행 이력 제외 |
| 3순위 | 그 이전 (최대 30일) | 풀이 50개 미만일 때만 보충 |

- `posted.json`의 `posted_ids` / `posted_links`와 대조하여 중복 제외
- wrangler D1 execute remote로 SQL 실행

**pub_date 형식 처리 (2026-06-23):**
- DB에 RFC 2822 형식(`Wed, 10 Jun 2026 17:38:24`)과 YYYY-MM-DD 형식(`2026-06-01 18:03:36`)이 혼재
- SQL CASE문으로 두 형식 모두 `YYYY-MM-DD`로 변환 후 `date('now', '-7 days')`와 비교
- 변환 불가능한 형식은 NULL 반환 → 제외 처리

**URL 검증 공유 함수 (writer_v3.py에서 import):**

```python
_VALIDATE_SOURCES = {'TechCrunch', 'TechCrunch AI', 'CNBC Tech', 'BBC Technology', 'BBC', 'Business Insider AI'}

def validate_link(url, timeout=8) -> bool
    """HEAD 요청으로 URL 유효성 확인 (2xx/3xx → True)"""

def find_fallback_url(title, max_title_chars=80) -> str | None
    """Google News RSS로 동일 기사 검색 → 첫 번째 유효 URL 반환"""
```

- `_VALIDATE_SOURCES`: RSS 수집 시 링크가 자주 깨지는 소스 목록
- `validate_link()`: `urllib.request` HEAD 요청, 404/500 등 실패 시 False
- `find_fallback_url()`: 기사 제목으로 Google News RSS 검색 → 정상 URL 획득
- `news_collector.py`의 동일 함수와 동일한 로직으로 일관성 유지

### 2. narrative_pitcher.py

100개 기사에서 '상식과 실제의 충돌'을 발견한다.

**SYSTEM_PROMPT 핵심 설계:**
- "상식적으로 A였어야 하는데 실제로는 B인 상황" 찾기
- hook: 핵심 긴장 한 줄 (길이 제한 없음)
- 2개 이상 연결 가능. 단, 억지로 연결하지 말 것. 기사 하나로도 가능
- `[소스 신뢰도]` 섹션: 주어-동사 방향 보존 지시
- 고유명사는 영어 원문 사용 (Nvidia, OpenAI 등)

**크롤링 정책 (변경 — 2026-06-20):**
- 피치 선별 단계에서는 **크롤링하지 않음**
- DB의 `description` 컬럼을 **500자 제한 없이 전문(全文)** 사용
- 100개 기사를 가볍게 스캔하여 어떤 이야기로 글을 쓸지 선별하는 단계이므로 description으로 충분
- 실제 원문 크롤링은 writer_v3.py에서 선정된 2~3개 기사에 대해서만 수행

**모델:** DiffusionGemma 1순위 → GPT-4o-mini fallback (model_router 경유)
**max_articles:** 500개 (2026-06-21: 100→500)

**중복 방지:**
- `is_duplicate_pitch()`: hook[:8] 또는 narrative[:30] 또는 article_ids 집합 일치 검사
- `save_pitch_to_history()`: 선택된 피치를 `posted.json` `pitch_history`에 저장
- `pitch_history` 최대 30개 유지, 7일 지난 항목 자동 정리

**출력 JSON 형식:**
```json
{
  "hook": "이야기의 핵심 긴장 한 줄",
  "narrative": "상식(A) vs 실제(B)",
  "twist": "A가 아니고 B인 진짜 이유",
  "emotion": "충격/불안/자부심/분노/놀라움",
  "article_ids": [2개 이상],
  "sources": ["URL"]
}
```

### 3. pitch_evaluator.py

피치 품질을 **4가지 기준**으로 0~6점 평가한다.

| 기준 | 배점 | 평가 내용 |
|------|------|---------|
| 상식충돌 | 0~2점 | "어? 몰랐다" 할 충돌 구조 |
| 구체성 | 0~2점 | 숫자/인물/기업명 포함 |
| 연결성 | 0~1점 | 2개 이상 서로 다른 출처 |
| 방향 정확성 | 0~1점 | twist의 주어-동사 방향이 narrative와 일치? |

- **3점 이상**만 통과
- **방향 정확성이 0점이면 총점과 무관하게 강제 불통과** (`direction_ok=false`)
- 평가 모델: **GPT-4o-mini** (DiffusionGemma는 방향 판별에 취약하여 2026-06-20 변경)
- 출력 형식에 `"direction_ok": true/false` 필드 포함
- JSON 파싱 실패 시 fallback: article_ids 2개 이상 + hook 존재 → 통과

### 4. model_router.py

모델 호출을 중앙 라우팅한다.

```
1순위: NVIDIA DiffusionGemma 26B (build.nvidia.com, google/diffusiongemma-26b-a4b-it)
2순위: OpenAI GPT-4o-mini (fallback)

호출 함수: chat_completion(messages, system_prompt, temperature, max_tokens, model_override)
```

- `model_override='openai'` → DiffusionGemma 스킵하고 바로 GPT-4o-mini
- 각 API 키는 `.env`에서 로드

### 5. writer_v3.py — 핵심

피치와 원문 크롤링 데이터를 바탕으로 5개 카드 쓰레드를 생성한다.

**원문 크롤링 (`fetch_article_body(url, title='')` → `(body_text, actual_url)`):**
- `requests` + `BeautifulSoup(lxml)`
- User-Agent 설정, timeout 15초
- 노이즈 태그 제거: script, style, nav, header, footer, aside, iframe
- 7개 CSS selector로 본문 영역 탐색: article, main, [role=main], .article-body, .post-content, .entry-content, .story-body
- 실패 시 description fallback
- **글자 수 제한 없음** — 선정된 2~3개 기사만 크롤링하므로 전문(全文) 전달
  (2026-06-20 변경: 기존 `max_chars=3000` 제거. 방향 정보가 뒷부분에서 잘리는 사고 방지)

**URL 유효성 검사 (2026-06-20 추가):**
- 크롤링 전 `db_reader.validate_link()` 호출 (techcrunch/cnbc/bbc 등 불안정 소스)
- HEAD 요청 실패(404 등) 시 `db_reader.find_fallback_url(title)`로 Google News 검색
- fallback URL 발견 시 해당 URL로 크롤링 + `actual_url` 반환
- fallback 실패 시 크롤링 스킵 (빈 문자열 반환)
- `actual_url`이 `write_thread()`의 `actual_urls[]`에 수집되어 `assemble_final()`에 전달
- 최종 `🔗` URL은 `assemble_final()`에서 `validate_link()`로 재검증 후 추가
- 깨진 URL이 Threads에 발행되는 것을 방지

**프롬프트 구조:**

```
build_system_prompt()
├── [문체 원칙] — 반말체, 한 줄 하나의 정보, 형용사 금지
├── [숫자 원칙] — 기사 숫자 전부 추출, 추상어 금지
├── [카드 구조] — 5개 카드 역할 정의
├── [밀도 기준] — 1번 5~6줄, 2~5번 최소 10줄
└── [참고 문체 예시] — style_examples.md 동적 로드

user_prompt
├── 피치 정보 (hook/narrative/twist 등)
├── 관련 기사 원문 (크롤링 결과)
└── 요구사항 (hook 고정, 반말체, 5카드, 숫자 추출)
```

**추론 실패 처리:**
- DiffusionGemma **2회** 시도 (2026-06-21: 5→2, 첫 글자 드랍 빠른 fallback)
- 전부 실패 시 GPT-4o-mini 1회 fallback
- 각 시도마다 `validate_cards()` + `validate_year()` + `validate_keywords()` 검증 (3단계):
  - 카드 수 5개 이상
  - 첫 번째 카드가 pitch hook[:8] 포함
  - 기사 본문 연도와 쓰레드 연도 일치 (할루시네이션 방지)
  - 기사 핵심 키워드의 음절 잘림/누락 탐지 (2026-06-22 추가)
- 쓰레드 생성 성공 후 **fix_cards() 1-pass**: GPT-4o-mini로 글자 단위 오류 수정
  - DiffusionGemma 대신 GPT-4o-mini 사용 (자기 오류 자기 수정 구조적 문제 해결)
  - 첫 글자/숫자 생략 복구, 한국어 음절 생략 복구 ("데팅→데이팅"), 중복/특수문자 정리
- 실패 시 상세 로그 출력

**출력 포맷팅:**
- `---` 로 카드 구분
- 같은 주제 문장은 붙이고, 시점/장소/인물 전환 시 빈 줄
- 마지막 카드는 선언형 마무리 (여운)
- `assemble_final(cards, related, primary_url, crawled_urls)`: 대표 URL 1개를 `🔗 url` 형식으로 마지막에 추가
  - `crawled_urls` 우선 — 크롤링 성공한 URL에서만 선택 (재검증 불필요)
  - `primary_url`이 `crawled_urls`에 있으면 해당 URL 사용
  - 없으면 `crawled_urls`의 첫 번째 URL 사용
  - `crawled_urls` 없으면 기존 validate_link 로직 fallback

### 6. publisher.py

Threads Graph API v1.0으로 연속 답글 체인을 발행한다.

**발행 프로세스:**
```
1. 각 카드 → add_line_spacing()으로 문장 사이 공백 추가
2. 각 카드 → POST /{user_id}/threads (컨테이너 생성)
   - 첫 카드: 일반 발행
   - 2번째 이후: reply_to_id = 이전 카드 post_id
3. 각 컨테이너 → POST /{user_id}/threads_publish (실제 발행)
4. posted.json 갱신 (posted_ids, posted_links, history)
```

- 3회 재시도, 토큰 만료 시 자동 갱신
- 각 단계 간 **10초** 대기 (2026-06-21: 3→10초, rate limit 대응)

**add_line_spacing() (2026-06-23):**
- 마침표/물음표/느낌표 뒤 공백 기준으로 문장 분리
- 각 문장 사이 `\n\n` (빈 줄) 삽입
- 카드 텍스트가 한 줄에 모든 문장이 이어져 있는 경우에도 정상 동작

### 7. main_v3.py — 진입점

3가지 실행 모드를 제공한다.

| 모드 | 명령 | 설명 |
|------|------|------|
| 1회 발행 | `--once` | 피치→작성→발행 1회 실행 |
| dry-run | `--dry-run` | 발행 없이 글만 생성, posted_ids만 저장 |
| 데몬 | `--daemon` | 2시간 간격 자동 실행, 자정 피치 이력 정리 |

- `--daemon` 모드: `schedule` 라이브러리로 2시간 주기 스케줄링
- dry-run에서도 `posted_ids`/`posted_links` 저장하여 중복 방지

---

## 중복 방지 체계

| 레벨 | 저장 대상 | 저장 시점 | 검사 방식 |
|------|---------|----------|---------|
| 피치 이력 | hook, article_ids, date | 매 run (dry-run 포함) | hook[:8] 또는 narrative[:30] 또는 article_ids 집합 일치 |
| 기사 ID | posted_ids | 실제 발행 + dry-run | id 기준 필터링 |
| 기사 링크 | posted_links | 실제 발행 + dry-run | link 기준 필터링 |

이중 필터링 구조로 동일한 기사/주제가 재발행되지 않는다.

---

## 카드 구조 설계 (5카드)

| 카드 | 줄 수 | 역할 |
|------|-------|------|
| 1 | 5~6줄 | 사건 충돌 — 날짜/장소/인물로 시작. "어?" |
| 2 | 10~12줄 | A면 사실 — 숫자, 인용, 연구 결과 빽빽하게 |
| 3 | 10~12줄 | 반전 — 예상 못 한 제3의 사실 |
| 4 | 10~12줄 | 확장 — 큰 맥락/한국 연결 |
| 5 | 10~12줄 | 여운 — 선언형 마무리 |

---

## 문체 원칙

- **반말체**: "~임", "~했음", "~있음", "~아님". "~합니다" 절대 금지.
- **숫자 우선**: 기사에 있는 모든 숫자 추출. "많은", "대규모", "수십억" 금지.
- **사실만**: 형용사·감탄사·이모지·볼드·이탤릭 전면 금지.
- **서술**: 각 문장 2~3줄로 충분히 서술. 한 줄짜리 축약 금지. 인과관계를 설명할 것.
- **여운**: 마지막 카드 마지막 줄은 선언이나 반전.
- **고유명사**: 영어 원문 사용 (Nvidia, OpenAI, Huawei 등)

---

## 의존성

```
requests          — HTTP 통신 (크롤링, API)
beautifulsoup4    — HTML 파싱
lxml              — HTML 파서 (BeautifulSoup 백엔드)
openai            — OpenAI / NVIDIA API 호환
schedule          — 데몬 스케줄링 (선택, daemon 모드)
```

설치 상태 확인:
```bash
.venv/bin/pip list | grep -E "requests|beautifulsoup|lxml|openai|schedule"
```

---

## 운영

### 실행
```bash
# 1회 발행
.venv/bin/python3 scripts/threads/main_v3.py --once

# dry-run (발행 없음)
.venv/bin/python3 scripts/threads/main_v3.py --dry-run

# 데몬 (2시간 간격)
.venv/bin/python3 scripts/threads/main_v3.py --daemon
```

### 로그 확인
```bash
# 오늘 로그
cat scripts/threads/logs/$(date +%Y-%m-%d).log

# 최신 초안
ls -lt scripts/threads/logs/drafts/ | head -3
```

### posted.json 구조
```json
{
  "posted_ids": [32152, ...],
  "posted_links": ["https://...", ...],
  "history": [{"id": 32152, "title": "...", "posted_at": "..."}],
  "last_reset": "2026-06-19",
  "pitch_history": [{"hook": "...", "article_ids": [...], "date": "2026-06-19"}]
}
```

---

## 변경 이력

| 날짜 | 변경 내용 |
|------|---------|
| 2026-06-18 | v3 최초 구축 — 7카드, GPT-4o, URL+CTA 강제 |
| 2026-06-19 | 7→3카드 전환, URL/CTA 제거, 여운 스타일 |
| 2026-06-19 | 3→5카드 확장, 원문 크롤링 추가 |
| 2026-06-19 | 모델 DiffusionGemma 1순위 전환, fallback GPT-4o-mini |
| 2026-06-19 | 중복 방지 강화 (dry-run posted_ids 저장, 타입 버그 수정) |
| 2026-06-19 | 5회 시도 + GPT-4o-mini fallback, 디버그 로그 |
| 2026-06-19 | 2시간 데몬 모드 활성화 |
| 2026-06-20 | 피치 선별 단계 크롤링 제거 |
| 2026-06-20 | 쓰레드 작성 단계 전문 크롤링 (max_chars 제거) |
| 2026-06-20 | 방향 정확성 평가 추가 (pitch_evaluator direction_ok) |
| 2026-06-20 | twist 키워드 검증 추가 (커버리지 40%) |
| 2026-06-20 | URL 검증 시스템 추가 (validate_link + fallback) |
| 2026-06-21 | **validate_year 재설계** — pub_date 강제→본문 연도 기반 검증, hook 제외, current_year 허용 |
| 2026-06-21 | **article_ids 타입 안전** — str/int/#접두사 혼용 대응 |
| 2026-06-21 | **fallback(all_articles[:2]) 제거** — 매칭 실패 시 스킵 |
| 2026-06-21 | **고유명사 영어 원문 표기** — pitcher+writer 양쪽 규칙 추가 |
| 2026-06-21 | **twist 키워드 검증 제거** — 발행률 저하 원인, hook+연도+카드 수만 유지 |
| 2026-06-21 | **pitch_history 30→6 정리** — dry-run/failed 제거, 실발행만 유지 |
| 2026-06-21 | **db_reader LIMIT 200→1000**, **max_articles 100→500** — 풀 확장 |
| 2026-06-21 | **assemble_final DB 링크 사용** — pitcher sources 제거, validate_link 3xx 거부 |
| 2026-06-21 | **primary_url 우선** — article_ids[0] 링크를 1순위로 |
| 2026-06-21 | **DiffusionGemma 2-pass(fix_cards) 도입** — 생성→글자 오류 수정 |
| 2026-06-21 | **실패 시 5분×3회 재시도** — 단, 쓰레드 생성 성공 시 재시도 중단 (부분 발행 방지) |
| 2026-06-21 | **publish_thread_chain 실제 기사 저장** — articles[0]→article_ids[0], 모든 article_ids/links 저장 |
| 2026-06-21 | **DiffusionGemma→Gemma-3n→DiffusionGemma 복귀** — 프롬프트 순응도 |
| 2026-06-21 | **문장 축약 금지** — "2~3줄 서술, 인과관계 설명"으로 변경 |
| 2026-06-21 | **publisher rate limit 대응** — 카드 간 대기 3→10초, 재시도 간격 2→10초 |
| 2026-06-21 | **fix_cards 금지 규칙 개선** — '단어 교체 금지'→'틀린 글자는 올바른 글자로 교체, 의미 유지' |
| 2026-06-22 | **fix_cards GPT-4o-mini 전환** — DiffusionGemma 자기 오류 자기 수정 구조적 문제 해결, 한국어 음절 오류 패턴 추가 ("데팅→데이팅" 등) |
| 2026-06-22 | **validate_keywords() 추가** — 기사 본문 핵심 키워드(2회 이상 등장 3자+ 한글 단어) vs 쓰레드 대조, 접두사/접미사 잘림 탐지 |
| 2026-06-23 | **pub_date 형식 변환** — RFC 2822와 YYYY-MM-DD 형식 모두 처리, 7일 이내 기사 필터 정확도 개선 |
| 2026-06-23 | **문장 단위 공백 추가** — add_line_spacing()을 마침표 기준 분리 방식으로 변경, 발행 시 각 문장 사이 빈 줄 삽입 |
| 2026-06-23 | **크롤링 성공 URL 발행** — crawled_urls 리스트 도입, assemble_final()에서 크롤링 성공한 URL만 사용하여 링크 미스매치 방지 |
