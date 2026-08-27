# Threads 자동 발행 파이프라인 기술 문서

> 프로젝트: aikorea24.kr  
> 작성일: 2026-08-14  
> 상태: 운영 중 (v3)  
> 관련 스킬: `thread-auto-pipeline`, `thread-content-writing`, `thread-writing-api`, `thread-scheduling`, `thread-viral-analysis`

---

## 1. 개요

이 시스템은 **D1 뉴스 DB에서 AI 관련 기사를 수집 → LLM으로 "이야기(pitch)"를 발견 → 쓰레디드(Threads) 게시물 6카드 작성 → Threads API로 연속 답글 체인 발행**까지의 전 과정을 자동화한다.

**핵심 설계 철학: Narrative-First**

- GPT-4o-mini(또는 무료 체인)가 100여 개 기사에서 "통념-현실 간 모순·역설"을 발견
- GPT-4o(또는 무료 체인 최상위 모델)가 실제 쓰레드 게시물 작성
- v1/v2와 병행 가능한 Strangler Fig 패턴으로 단계적 마이그레이션 중

---

## 2. 전체 아키텍처

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        Threads 자동 발행 파이프라인                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  [1] D1 DB                        [2] Pitch 생성              [3] Write    │
│  ┌─────────────┐                  ┌──────────────┐           ┌──────────┐  │
│  │ get_articles│                  │ get_pitches  │           │ write_   │  │
│  │  ├─ 1순위   │──► articles ────►│  ├─ SYSTEM_   │──► pitch ──►thread() │  │
│  │  │ 브리핑    │                  │  │ PROMPT     │           │         │  │
│  │  ├─ 2순위   │                  │  ├─ parse_   │           │ 조립·     │  │
│  │  │ 최근3일   │                  │  │ pitches()  │           │ 검증·     │  │
│  │  └─ 3순위   │                  │  ├─ dedup    │           │ assemble │  │
│  │    (최대30일)│               │  └─ save_    │           └─────┬────┘  │
│  └─────────────┘                  │     history   │                 │       │
│       │                           └──────────────┘                 │       │
│       ▼                                  │                         │       │
│  ┌──────────┐                           │                         │       │
│  │ posted   │◄──────────────────────────┘                         │       │
│  │ .json    │  (중복 방지, 이력)                                   │       │
│  └──────────┘                                                      │       │
│                                                                     │       │
│                                      [4] 발행                     │       │
│                                      ┌─────────────┐              │       │
│                                      │ publish_    │◄────────────┘       │
│                                      │ thread_     │  cards             │
│                                      │ chain()     │                     │
│                                      └──────┬──────┘                     │
│                                             ▼                            │
│                                      ┌─────────────┐                     │
│                                      │ Threads API │                     │
│                                      │ graph.threads│                    │
│                                      │ .net/v1.0   │                     │
│                                      └─────────────┘                     │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │ [5] 검증 게이트 (3중 방어)                                           │    │
│  │  1차: pitch.py validate_korean_output() — 언어·프롬프트 릭           │    │
│  │  2차: writer.py validate_cards()/validate_year()/validate_card_      │    │
│  │       structure() — 카드 기본 검증                                   │    │
│  │  3차: validator.py validate_final_output() — 발행 직전 종합         │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │ [6] 모델 라우팅 (LLM 폴백 체인)                                      │    │
│  │  config/models.yaml → 무료 16모델 순차 → 유료 DeepSeek V4 Flash      │    │
│  │  서킷브레이커: 10회 연속 실패 → 5분 개방                             │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. 파일 구조

### 3.1 파이프라인 핵심 모듈 (`pipeline/threads/`)

| 파일 | 역할 | 비고 |
|------|------|------|
| `__init__.py` | 패키지 마커 | Phase 4에서 채워짐 |
| `crawler.py` | 기사 원문 크롤링 (BeautifulSoup + lxml) | 실패 시 `failed_crawls.json` 기록, 2회 재시도 |
| `pitch.py` | 피치 생성·파싱·중복제거·이력관리 | SYSTEM_PROMPT 정의, `validate_korean_output()`, `detect_prompt_leak()`, `is_duplicate_pitch()`, `save_pitch_to_history()` |
| `writer.py` | 쓰레드 카드 조립·휴먼화·최종 검증 | `write_thread()`, `humanize_cards()`, `assemble_final()`, `save_draft()` |
| `validator.py` | 카드/연도/키워드/외국어/최종 출력 검증 | `validate_cards()`, `validate_year()`, `validate_final_output()`, `validate_card_structure()` |

### 3.2 실행 진입점 (`scripts/threads/`)

| 파일 | 역할 | 비고 |
|------|------|------|
| `main_v3.py` | 메인 오케스트레이터 (v3) | `--dry-run` 지원, 5회 재시도, launchd 스케줄러 연동 |
| `db_reader.py` | D1 DB 기사 풀 로드 | 3단계 우선순위 (브리핑 → 최근3일 → 이전), `posted.json` 중복 제외 |
| `publisher.py` | Threads API 연속 답글 체인 발행 | 토큰 자동 갱신, 3회 재시도+지수 백오프, DNS 사전체크 |
| `dedup.py` | 언어 통합 중복 탐지 엔진 | EN-EN/KO-KO/Mixed 3가지 모드, Jaccard + entity overlap |
| `failed_articles.py` | 크롤링/작성 실패 기사 ID 관리 | 누적 제외 리스트 관리 |

### 3.3 v3 래퍼 모듈 (`scripts/threads/v3/`)

| 파일 | 역할 | 비고 |
|------|------|------|
| `model_router.py` | LLM 호출 라우터 | 무료 체인 + 유료 DeepSeek, 서킷브레이커, MiMo 선택적 사용 |
| `narrative_pitcher.py` | `pipeline.threads.pitch` 재수출 | Strangler Fig 호환 래퍼 |
| `writer_v3.py` | `pipeline.threads.writer` 재수출 | Strangler Fig 호환 래퍼 |
| `auto_poster/` | 영상 자동 포스터 서브시스템 | 별도 파이프라인 (TTS + 영상 제작) |

### 3.4 설정 파일

| 파일 | 내용 |
|------|------|
| `config/models.yaml` | 무료 LLM 체인 구성 (tier_order, providers, models) |
| `config/crawlable_sources.json` | 크롤링 가능 매체 목록 (crawlable + api_based) |
| `.env` / `~/.env.common` | API 키 (THREADS_ACCESS_TOKEN, DEEPSEEK_API_TOKEN 등) |

---

## 4. 파이프라인 상세 흐름

### 4.1 Step 1: 기사 풀 로드 (`db_reader.get_articles()`)

**3단계 우선순위:**

1. **1순위 (브리핑)**: 오늘 발행된 briefing_items에 포함된 news — `priority=1`
2. **2순위 (최근 3일)**: 오늘 브리핑 제외한 최근 3일 news — `priority=2`, 최대 2000개
3. **3순위 (이전)**: 전체 50개 미만 시 추가 — 최대 30일 전, `priority=3`

**중복 제외 5단계:**

| 단계 | 검사 방식 |
|------|----------|
| 1 | `posted_ids` 정확 매칭 (D1 id) |
| 2 | `posted_links` 정확 매칭 (정규화 URL) |
| 3 | `posted_titles` 접두사 매칭 (처음 30자) |
| 4 | `posted_original_titles` 접두사 매칭 (처음 30자) |
| 5 | Vectorize semantic dedup (임베딩 유사도 ≥ 0.85, supplementary) |

**소스 필터:** `config/crawlable_sources.json`에서 `crawlable` + `api_based` 소스만 포함.

### 4.2 Step 2: Pitch 생성 (`pitch.get_pitches()`)

**SYSTEM_PROMPT 핵심:**

> "AI 뉴스 기사에서 통념-현실 간 모순·역설·미해결 질문을 찾아내는 컨트라딕션 파인더"

**주요 제약:**

- 반드시 **단일 기사**만 사용 (article_ids 1개)
- 인과관계를 반대로 서술 금지 (오보 방지)
- 단순 정보 전달·제품 발표·데모·펀딩 라운드 단순 보도 제외
- 출력에 '상식(A):', '실제(B):', 'vs' 같은 라벨 절대 포함 금지

**처리 흐름:**

```
articles (최대 600개)
    │
    ├─ Phase 24-02: _pre_filter_candidates()
    │   ├─ 시의성 점수 (1일 내: +10, 3일 내: +5, 7일 내: +2)
    │   ├─ AI 관련 키워드 점수 (+3 per keyword)
    │   └─ 상위 10개로 축소
    │
    ├─ batched (batch_size=5, 최대 유효 배치 크기)
    │   │
    │   ├─ SYSTEM_PROMPT + 기사 배치 → chat_completion()
    │   ├─ parse_pitches_from_text() → JSON 파싱
    │   ├─ validate_korean_output() — 한국어 검증
    │   └─ fallback: JSON 실패 시 재시도
    │
    ├─ 중복 제거: is_duplicate_pitch()
    │   ├─ article_ids 중복 (Jaccard ≥ 0.5)
    │   ├─ article_urls 중복
    │   ├─ article_titles/Original_titles 중복 (is_same_topic)
    │   └─ but_line + article_ids 유사 중복
    │
    ├─ filter_pitches() — 품질 평가
    │
    └─ TOP 1 선택 → _regenerate_pitch_from_crawl()
        ├─ 크롤링된 원문 본문으로 피치 재생성
        ├─ gap_source: "explicit" / "reconstructed"
        └─ 감정 분류: 불안/놀람/분노/희망
```

### 4.3 Step 3: 쓰레드 작성 (`writer.write_thread()`)

**FORMAT_D (기본) — 2026-08-14 개정:**

- 5개 콘텐츠 카드만 작성 (링크 카드 미포함)
- 카드 구분자: `---`
- 각 카드 최대 500자 (Threads API 제한)
- `write_thread()` 반환값: `dict {"cards": [5개 카드], "link": "url"}`
  - `cards`: 5개 콘텐츠 카드 리스트
  - `link`: 원문 URL 문자열 (publisher가 루트 답글로 별도 발행)
- `FORMAT_CARD_COUNT_TOLERANCE['D']` = `(5, 5)` (5개만 허용, 4카드 시 다음 tier 폴백 유도)

** SYSTEM 프롬프트 (build_system_prompt_D):**

```
You are a journalist writing 5-card Korean threads on Threads, based on AI news articles.

FORMAT:
- 5 content cards only (card 1→5), no link card in the main chain
- Cards separated by ---
- Each card: max 500 characters

RHYTHM (핵심 스타일):
- 짧은 절 단위 줄바꿈 (10~25자)
- 절과 절 사이 빈 줄(\n\n) 필수
- 문장 하나 60자 초과 금지

CONSTRAINTS:
- 종결어미 ~임/~했음/~있음 중심
- 한자·일본어·히라가나·가타카나 절대 금지
- pitch 메타데이터 라벨("핵심 이야기:", "반전:" 등) 절대 금지

OUTPUT FORMAT — JSON only:
{"cards": ["card1", "card2", "card3", "card4", "card5"]}
```

**사용자 프롬프트 구성:**

```
=== PITCH ===
Hook: {pitch['hook']}
Narrative: {pitch['narrative']}
Twist: {pitch['twist']}
Emotion: {pitch['emotion']}
But_line: {pitch['but_line']}
Question: {pitch['question']}
Gap source: {pitch['gap_source']}

=== FORMAT ===
{FORMAT_LABELS[format_choice]} (펀치 브리핑형, 5개 콘텐츠 카드 + 루트 답글 링크)

=== ARTICLES ===
{article_id}: {title}\n발행일: {pub_date}\n본문: {body}\n출처: {source}\n링크: {url}

=== REQUIREMENTS ===
1. Follow the system prompt format exactly.
2. Use ALL numbers from the article body — no vague expressions.
3. Never include pitch metadata labels.
4. Output: JSON only — {"cards": ["card1", ..., "card5"]} (5 content cards only, no link card)
```

**후처리 파이프라인:**

```
cards = parse_cards_json_first(content)    # JSON 파싱 (4단계 fallback)
cards = _cleanup_source_attribution(cards)  # 출처 표기 제거, 볼드 마크다운 제거
cards = fix_cards(cards)                    # (현재 pass-through)
│
├─ validate_cards()     — 카드 수 strict (5개만 허용)
├─ validate_year()      — 연도 조작 검증 (기사 본문 연도만 허용)
├─ validate_card_structure() — 구조 검증 (중복·길이·한글비율·공백과다·문장종결)
│   └─ _validate_last_card_opens_reply() — 마지막 카드 답글 유도형 검사 (2-2)
├─ validate_model_message() — 모델 설명 메시지 탐지 (카드별)
└─ validate_final_output() — 발행 직전 종합 검증 (프롬프트 릭·외국어·한글비율·모델메시지)
```

**반환값 구조 (2-1 변경):**

```
write_thread() → {
    "cards": [card1, card2, card3, card4, card5],  # 5개 콘텐츠 카드
    "link": "https://example.com/article"           # 원문 URL (publisher가 답글로 발행)
}
```

**Humanize (옵션):**

- `humanize_cards()`: 카드별 ThreadPoolExecutor로 병렬 처리
- AI 말투 패턴 교체 (번역투, AI 특유 관용구, 과장 표현, 영어 혼용 등)
- 의미 불변: 수치·날짜·고유명사·직접 인용문·반말체 어미 변경 금지

### 4.4 Step 4: 발행 (`publisher.publish_thread_chain()`)

**연속 답글 체인 방식:**

```
카드 1: https://graph.threads.net/v1.0/{user_id}/threads  (새 포스트 생성)
카드 2: https://graph.threads.net/v1.0/{user_id}/threads?reply_to_id=카드1_id
カード 3: ...?reply_to_id=카드2_id
...
```

**발행 흐름:**

1. **DNS 사전체크**: `graph.threads.net` → 실패 시 발행 시작 안 함 (카드 1만 떠있는 현상 방지)
2. **500자 제한 비상 안전장치**: 문장 분할(`.!?`) → 중간 문장 제거 방식으로 절단
3. **컨테이너 생성**: 3회 재시도 + 지수 백오프 (15초→30초→45초)
4. **토큰 자동 갱신**: HTTP 190 (토큰 만료) 시 `refresh_access_token` → `.env` 갱신
5. **발행**: `threads_publish` 엔드포인트, 3회 재시도
6. **카드 간 대기**: 15초 (API rate limit 회피)

**발행 전 필수 조건:**

- `THREADS_ACCESS_TOKEN` 환경변수 필요
- `THREADS_USER_ID` 환경변수 필요
- Meta Threads API 접근 승인 필요 (2024년 기준 제한적)

### 4.5 Step 5: 발행 후 처리 (`main_v3.run_v3()`)

**posted.json 업데이트:**

```json
{
  "posted_ids": ["1", "2", ...],
  "posted_links": ["https://...", "..."],
  "posted_titles": ["제목 앞 30자", ...],
  "posted_original_titles": ["원문 제목 앞 30자", ...],
  "posted_article_meta": {
    "1": {"title": "...", "original_title": "...", "description": "..."}
  },
  "pitch_history": [...],
  "last_reset": "2026-08-14"
}
```

**dry-run 모드:**

- 발행 없이 쓰레드만 생성, 초안 저장
- posted.json 업데이트 (중복 방지용)
- Vectorize 인덱싱 수행
- 생성된 카드 전체 출력

---

## 5. 검증 게이트 (3중 방어)

### 5.1 1차 방어 — Pitch 단계 (`pitch.py`)

| 검증 | 함수 | 차단 조건 |
|------|------|----------|
| 한국어 검증 | `validate_korean_output()` | 한글 없음, 한글 비율 < 15%, 영문 문장 패턴 |
| 프롬프트 릭 | `detect_prompt_leak()` | 시스템 프래그먼트 6종, 라벨 패턴 3종 |
| 빈 hook | — | hook 길이 < 5자 |

### 5.2 2차 방어 — Write 단계 (`writer.py` + `validator.py`)

| 검증 | 함수 | 차단 조건 |
|------|------|----------|
| 카드 수 | `validate_cards()` | 최소 4개 미만 / 최대 7개 초과 |
| Hook 길이 | `validate_cards()` | 첫 줄 < 3자 |
| 연도 조작 | `validate_year()` | 기사 본문에 없는 연도 사용 |
| 구조 검증 | `validate_card_structure()` | 중복 카드, 길이 비정상, 한글 비율 < 15%, 공백 과다, 문장 종결 과다 |
| 모델 메시지 | `validate_model_message()` | "수정할 게 없음", "원본을 그대로 반환" 등 패턴 |
| 카드별 | (writer.py 내) | 카드별 `validate_model_message()` 호출 |

### 5.3 3차 방어 — 발행 직전 (`validator.validate_final_output()`)

순서:

1. **프롬프트 노출 검사** (`detect_prompt_leak()`)
2. **NFKC 정규화** (전각/반각 통합 → 중국어·일본어 감지 정확도 향상)
3. **외국어 검사**: 한자 ([\u4e00-\u9fff]) / 일본어 ([\u3040-\u309f\u30a0-\u30ff])
4. **한글 비율 검사**: 링크 카드 제외, 30% 미만 시 차단
5. **모델 설명 메시지**: `ALL_MESSAGE_PATTERNS` 28종 매칭

---

## 6. 모델 라우팅 시스템

### 6.1 구성 (`config/models.yaml`)

```yaml
tier_order: [tier1, tier2, ..., tier16, default]
models:
  tier1:
    provider: google
    model: gemini-2.5-pro
  ...
  default:
    provider: deepseek
    model: deepseek-v4-flash
providers:
  google:
    base_url: https://generativelanguage.googleapis.com/v1beta/openai
    api_key_env: GOOGLE_API_KEY
  ...
```

### 6.2 동작 방식 (`model_router.chat_completion()`)

```
model_override=None (기본)
    ├─ CHAIN_CONFIG 있음 → _chain_completion()
    │   ├─ 무료 체인 16모델 순차 시도 (tier_order)
    │   │   ├─ 각 tier당 최대 2회 재시도
    │   │   └─ 성공 시 즉시 반환
    │   ├─ 무료 전부 실패 → 서킷브레이커 확인
    │   │   ├─ open_until > now → 유료 직행
    │   │   ├─ failures >= 10 → 5분 개방
    │   │   └─ 아니면 유료 DeepSeek 시도
    │   └─ 유료 DeepSeek (최후 수단, 최대 2회 재시도)
    │
    ├─ model_override='mimo' → MiMo v2.5 단독
    ├─ model_override='deepseek' → 무료 체인 → 유료 DeepSeek
    └─ model_override='openai' → [차단됨] (2026-08-12 제거)
```

### 6.3 서킷브레이커

- **임계값**: 10회 연속 실패
- **개방 시간**: 300초 (5분)
- **상태**: 모듈 전역 (`_chain_state` dict)

---

## 7. 중복 방지 시스템

### 7.1 3단계 중복 방어

| 단계 | 위치 | 검사 방식 | threshold |
|------|------|----------|----------|
| Phase 1 | `db_reader.is_already_posted()` | id/link/title/original_title 정확매칭 + Vectorize semantic + is_same_topic | Jaccard 0.30 / entity 2개 |
| Phase 2 | `pitch.is_duplicate_pitch()` | article_ids Jaccard + article_urls + article_titles/Original_titles semantic | Jaccard 0.5 / entity 2개 |
| Phase 3 | `save_pitch_to_history().entities` | capitalized entity 저장 → Phase 2에 활용 | — |

### 7.2 언어 통합 중복 탐지 (`dedup.py`)

**3가지 언어 모드:**

| 모드 | 조건 | 판정 기준 |
|------|------|----------|
| EN-EN | 양쪽 모두 original_title 보유 | Jaccard ≥ 0.30 OR entity_overlap ≥ 2 |
| KO-KO | 양쪽 모두 original_title 미보유 + 한글 제목 | jaccard_ko ≥ 0.25 OR entity_overlap ≥ 2 |
| Mixed | 한쪽만 original_title 보유 | jaccard_all ≥ 0.15 OR (entity ≥ 1 AND jaccard_all ≥ 0.10) |
| Fallback | — | jaccard_all ≥ 0.30 |

**가중치 composite score:**

```
score = (0.35*jaccard_en + 0.25*jaccard_ko + 0.25*jaccard_all + 0.15*entity_factor) / total_w
```

---

## 8. 환경 설정

### 8.1 필수 환경변수

| 변수 | 용도 |
|------|------|
| `THREADS_ACCESS_TOKEN` | Threads API 액세스 토큰 |
| `THREADS_USER_ID` | 연결된 Instagram 사용자 ID |
| `DEEPSEEK_API_TOKEN` | DeepSeek API 키 ( 유료 최후 수단) |
| `MIMO_API_KEY` | (선택) MiMo v2.5 API 키 |

### 8.2 선택 환경변수

| 변수 | 기본값 | 용도 |
|------|--------|------|
| `THREADS_PUBLISH_INTERVAL_SECONDS` | 3600 | 스케줄러 체크 간격 |
| `THREADS_MAX_POSTS_PER_DAY` | 10 | 일일 최대 발행 |
| `THREADS_DRY_RUN` | false | dry-run 모드 |

---

## 9. 스케줄링 (launchd)

```xml
<!-- ~/Library/LaunchAgents/com.aikorea24.thread-pipeline.plist -->
<?xml version="1.0" encoding="UTF-8"?>
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.aikorea24.thread-pipeline</string>
    <key>ProgramArguments</key>
    <array>
        <string>/Users/twinssn/Projects/aikorea24/.venv/bin/python3</string>
        <string>/Users/twinssn/Projects/aikorea24/scripts/threads/main_v3.py</string>
    </array>
    <key>WorkingDirectory</key>
    <string>/Users/twinssn/Projects/aikorea24</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <dict>
        <key>SuccessfulExit</key>
        <false/>
        <key>Crashed</key>
        <true/>
    </dict>
    <key>StandardOutPath</key>
    <string>/Users/twinssn/Projects/aikorea24/scripts/threads/logs/pipeline.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/twinssn/Projects/aikorea24/scripts/threads/logs/pipeline-error.log</string>
</dict>
</plist>
```

---

## 10. 주요 숫자/제약

| 항목 | 값 | 비고 |
|------|-----|------|
| 기본 카드 수 (FORMAT_D) | 5 | 콘텐츠 카드만 (링크는 루트 답글로 분리 발행) |
| 카드 최대 길이 | 500자 | Threads API 하드 제한 |
| 카드 최소 길이 (body) | 12자 | validator 구조 검증 |
| 한글 비율 최소 (body) | 15% | 고유명사·숫자 많은 AI 뉴스 고려 |
| 한글 비율 최소 (발행 직전) | 30% | 더 엄격 |
| Hook 첫 줄 최대 | 350자 | validator 구조 검증 |
| 배치 크기 (pitch) | 5개 | LLM context overflow 방지 (Phase 24-01) |
| 사전 필터 후보 | 10개 | 시의성 + AI 관련도 (Phase 24-02) |
| 최대 기사 풀 | 600개 | get_pitches max_articles |
| 재시도 (발행) | 3회 | base_delay=15초, max_delay=45초 |
| 재시도 (전체 파이프라인) | 5회 | main_v3.py max_retries |
| 서킷브레이커 임계값 | 10회 | 5분 개방 |
| 무료 체인 모델 수 | 16개 | config/models.yaml tier_order |
| 중복 threshold (EN-EN) | Jaccard 0.30 / entity 2 | |
| 중복 threshold (KO-KO) | jaccard_ko 0.25 / entity 2 | |
| 중복 threshold (Mixed) | jaccard_all 0.15 / entity 1 | |

---

## 11. 오류 처리 및 재시도

| 오류 유형 | 대응 |
|----------|------|
| API 인증 오류 (HTTP 190) | `refresh_token()` → `.env` 갱신 → 재시도 |
| Rate limit (429) | Exponential backoff (15→30→45초) |
| DNS 조회 실패 | 발행 시작 안 함 (카드 1만 떠있는 현상 방지) |
| 크롤링 실패 | 2회 재시도 → `failed_crawls.json` 기록 → Pitch에서 제외 |
| 카드 500자 초과 | 문장 분할(`.!?`) → 중간 문장 제거 |
| LLM 응답 빈 값 | 다음 tier로 폴백 (무료 체인) → 유료 DeepSeek |
| 콘텐츠 필터 차단 | finish_reason='content_filter' 로그 → 다음 tier |
| 토큰 제한 도달 | finish_reason='length' 로그 → 다음 tier |

---

## 12. 테스트

### 12.1 테스트 파일

| 파일 | 내용 |
|------|------|
| `tests/test_write_thread_validation.py` | Write 파이프라인 E2E 검증 체인 테스트 |

### 12.2 테스트 케이스

| 테스트 | 검증 내용 |
|--------|----------|
| `test_chinese_char_rejected` | 카드 내 한자 포함 → `write_thread()` 빈 리스트 반환 |
| `test_prompt_label_leak_rejected` | '상식(A):' 라벨 포함 → 빈 리스트 반환 |
| `test_success_valid_cards` | 유효한 6개 한글 카드 → 카드 반환 (call_log ≥ 1) |
| `test_link_card_stripped` | 앞 공백 있는 링크 카드도 정상 처리 |

---

## 13. 관련 스킬

| 스킬 | 용도 |
|------|------|
| `thread-auto-pipeline` | 전체 파이프라인 오케스트레이션, 스케줄링, 모니터링 |
| `thread-content-writing` | 5종 프롬프트 구조 (Threads 4단/X 7~8트윗/8~10카드/스토리텔링/뉴스브리핑) |
| `thread-writing-api` | Threads API 인증·발행·검증·오류처리 |
| `thread-scheduling` | 최적 발행 시간 분석, 빈도 관리, 발행 캘린더 |
| `thread-viral-analysis` | 훅 패턴 분석, 이탈률 분석, 80/20 법칙, A/B 테스트 |

---

## 14. Strangler Fig 마이그레이션 현황

Phase 4에서 진행 중인 Strangler Fig 패턴:

| 기존 위치 | 신규 위치 | 상태 |
|-----------|----------|------|
| `scripts/threads/v3/narrative_pitcher.py` | `pipeline/threads/pitch.py` | 신규 구현 완료, v3는 재수출 래퍼로 유지 |
| `scripts/threads/v3/writer_v3.py` | `pipeline/threads/writer.py` + `validator.py` | 신규 구현 완료, v3는 재수출 래퍼로 유지 |
| `scripts/threads/crawler.py` | `pipeline/threads/crawler.py` | 신규 위치 (동일 코드) |
| `scripts/threads/db_reader.py` | `pipeline/threads/` (미이동) | 아직 scripts/에 있음 |
| `scripts/threads/publisher.py` | `pipeline/threads/` (미이동) | 아직 scripts/에 있음 |

`main_v3.py`는 여전히 `scripts/threads/`에 있으며, `pipeline.threads.` 모듈과 `scripts.threads.v3.` 래퍼 모두 임포트 가능.

---

## 15. 주의사항 및 Known Issues

1. **Threads API 접근 제한**: 2024년 기준 Meta Threads API 접근은 제한적. 앱 리뷰 필요.
2. **GPT-4o-mini 제거됨**: 2026-08-12부로 `model_override='openai'` 호출 완전 차단. 구형 모델, RHYTHM 지침 준수율 낮음.
3. **한글-영어 붙어쓰기 검증 비활성화**: 고유명사+조사(예: "OpenAI가")가 지속적으로 검증 실패 유발 → 비활성화 상태.
4. **Vectorize 의존도**: Vectorize 실패해도 파이프라인 차단되지 않음 (supplementary layer).
5. **posted.json 단일 파일**: 동시 실행 시 레이스 컨디션 가능. 단일 launchd 인스턴스 가정.
6. **dry-run 모드에서도 Vectorize 인덱싱 수행**: posted.json과 동기화 유지 목적.

---

## 16. 향후 개선 포인트

1. **posted.json → D1 DB 이전**: 단일 JSON 파일의 레이스 컨디션 위험 해소
2. **카드 수 확장성**: 현재 FORMAT_D(6카드)만 지원. FORMAT_LABELS에 다른 형식 추가 가능 구조
3. **프롬프트 릭 방어 고도화**: `detect_prompt_leak()`의 프래그먼트 목록을 자동화된 방식으로 관리
4. **Humanize 파이프라인 상태 명확화 (2026-08-14 완료)**: `humanize_cards()`는 AI-어휘 방어용으로 보존됨. `AI_KOREAN_PATTERNS` 리스트 추가됨 (실제 한국어 AI 출력 패턴). writer_v3 test comment "removed" → "preserved as AI-vocabulary defense"로 수정 완료.
5. **발행 후 검증(Insight) 수집**: `thread-writing-api`의 `get_post_insights()` 연동 → viral 분석 파이프라인 연결

---

## 17. kicker7 인물중심 스레드 파이프라인 (신규, 운영중)

> 인물·르뽀·서사 중심 뉴스 전용 스레드. 기존 `main_v3` D포맷/contrast 와 **완전 별도 경로** (비동기: 선별→드래프트 저장 → 별도 발행기). 2026-08-27 live 전환 완료.

### 17.1 흐름 개요

```
auto_news_selector.route_person_stories()
  └─ person_gate.py (신호로만 사용, 통과/탈락 무관 전량 생성)
  └─ orchestrator.run_contrast_thread(writer_fn=write_kicker7_thread,
                                       writer_kwargs={'gate_signal': gate})
       ├─ extractor.extract_af() → af_json (A~F)
       ├─ background_search: cross5 + bg3 수집 + 크롤
       └─ kicker7_writer.write_kicker7_thread() → SYSTEM_KICKER7_V3 (v2.5)
  → 드래프트 저장: scripts/threads/logs/drafts/kicker7_selector/k7_{id}_{ts}.txt
       (카드간 구분자 '\n---\n', 카드6 = '--- 카드 6 ---' 출처 블록)

[비동기, 별도 launchd]
publish_kicker7_drafts.py
  └─ k7_selector/*.txt 글로브 → 파싱(6카드) → 루브릭 게이트
  └─ 통과 → publish_thread_chain(cards[:5], article, link_url)
  └─ 미달 → hold/ 이동 / 성공 → published/ 이동 + posted_ids.json 기록
```

### 17.2 생성 구조 (SYSTEM_KICKER7_V3 v2.5)

* 카드1~5 고정 역할: **장면**(인물+진행동작) → **메커니즘** → **반전(조건)** → **현장목소리(인용)** → **책임지도·인적대가**.
* **판단(키커) 카드 제거** — v2.5에서 삭제, 대가귀결은 카드5에 흡수.
* **카드6 = 출처 카드** (시스템 결정적 부착, 모델이 안 씀): `--- 카드 6 ---` + `출처:/발행일:/원문:/추출 사실: B n건 / C n건`.
* 엄격 규칙: 사실봉쇄(A~F only) / 인용 verbatim+bilingual `(원문: …)` / 수치 한정어 / 카드1 첫 문장 날짜 배제(후처리 `_strip_date_from_first_sentence`) / `[재료 신고: …]` 라인 발행 전 제거(`_strip_material_reports`).

### 17.3 발행 게이트 (루브릭 + 기존 검증)

`publish_kicker7_drafts.py` 순서:

1. **무근거 0**: 카드1~5 각각 사실토큰(수치/인용/인명직함) ≥1 — 없으면 HOLD.
2. **화자실명**: 카드4(현장목소리)에 이름+직함 ≥1 — 없으면 HOLD.
3. **출처카드**: 카드6에 `출처:` + `원문:` 존재 — 없으면 HOLD.
4. **기존 검증 재사용**: `validate_final_cards(cards[:5])` (500자/미완결/중복) — 카드6(출처)은 면제.

### 17.4 발행 세부

* `publish_thread_chain(cards, article, link_url)`: 카드 each = 별도 포스트(연속 답글), `link_url` = **루트 답글**로 별도 발행.
* **카드6(출처)은 발행 카드에서 제외**하고 `link_url`로만 붙임 (중복 URL 방지).
* 멱등: `posted_ids.json`(`k7_selector/` 하위)에 발행된 fid 기록, 재실행 시 SKIP.
* 격리: 미달 → `hold/`(사유 접미사), 성공 → `published/`.

### 17.5 스케줄링 (launchd)

* `~/Library/LaunchAgents/kr.aikorea24.kicker7-publisher.plist`
* 2시간마다 `:30` (main_v3 `:00`와 30분 어긋남).
* `CLOUDFLARE_API_TOKEN` unset (`env -u`, AGENTS.md 규정), `.venv/bin/python3` 사용, WorkingDirectory=repo root.
* 점진 배포: 초기 `--dry-run` → 2026-08-27 live 전환(플리스트 `--dry-run` 제거 + unload/load).

### 17.6 운영 상태 (2026-08-27 기준)

* **운영중(live)**. 첫 발행: `k7_46941` (Meta AI 인력 감축 계획 무산, The Decoder) — 5카드+링크답글, root `17866975854642583`.
* 동 사이클 4건은 루브릭 `무근거 카드N` 으로 HOLD (해당 카드 사실토큰 부재 → 보수적 차단, 의도된 동작).
* 드래프트 포맷 버그 이력: 초기 저장이 `\n\n` 구분자여서 카드내부 절구분과 충돌·복구불가 → `auto_news_selector.py:461` 을 `\n---\n` 으로 수정, 파서도 `---` 전용 분리로 교정.

### 17.7 관련 문서

* 비교표/버전 차이: `docs/TECH-thread-writing-versions.md` (kicker7 v3 행 — "미배선" → 본 파이프라인으로 **운영중** 갱신됨).
* person_gate 패치 이력: `docs/person_gate_patch.md`.

---

## 부록 A: 핵심 프롬프트 조각

### A.1 SYSTEM_PROMPT (pitch.py)

```
당신은 AI 뉴스 기사에서 통념-현실 간의 모순·역설·미해결 질문을 찾아내는 컨트라딕션 파인더입니다.
[_LANG_SECTION: 모든 문장은 반드시 한국어로 작성, 고유명사만 영어 허용]

[핵심 원칙]
1. 기사의 인과관계를 정확히 파악하라
2. "A가 B를 하면 C가 된다"는 내용을 반드시 그대로 서술
3. 절대로 인과관계를 뒤집거나 반대로 해석하지 말 것
4. 상식과 실제의 충돌을 찾되, 기사에 근거한 내용만 사용
5. 기사에 없는 내용을 추가하거나 추측하지 말 것
6. 원문에 명시적 모순이 없더라도, 기사 속 사실들을 연결해 간극을 구성할 수 있다면 포함하라

[금지]
- 너무 많이 논의된 상식("AI가 일자리를 뺏는다" 등)은 피함
- 단순 정보 전달·제품 발표·데모·펀딩 라운드 단순 보도 제외
- 출력에 '상식(A):' 또는 '실제(B):' 같은 라벨 절대 포함 금지

[출력 형식]
유효한 JSON 배열만 출력:
[
  {
    "hook": "독자의 호기심을 자극하는 한 줄 (고유명사만 영어)",
    "narrative": "2-3문장 (고유명사만 영어)",
    "twist": "예상 밖의 결과 또는 역설",
    "emotion": "불안/놀람/분노/희망 중 하나",
    "but_line": "\"X인데, 사실은 Y\" 형식",
    "question": "독자에게 남기는 단 하나의 질문",
    "gap_source": "explicit" 또는 "reconstructed",
    "article_ids": [1]
  }
]
```

### A.2 FORMAT_D SYSTEM 프롬프트 (writer.py) — 2026-08-14 개정

```
You are a journalist writing 5-card Korean threads on Threads, based on AI news articles.

FORMAT:
- 5 content cards only (card 1→5), no link card in the main chain
- Cards separated by ---
- Each card: max 500 characters

RHYTHM:
- 짧은 절 단위 줄바꿈 (10~25자)
- 절과 절 사이 빈 줄(\n\n) 필수
- 문장 하나 60자 초과 금지

CONSTRAINTS:
- 종결어미 ~임/~했음/~있음 중심
- 한자·일본어·히라가나·가타카나 절대 금지
- pitch 메타데이터 라벨 절대 금지

CARD 5 RULE (필수):
- 반드시 열린 질문, 불완전한 결론, 또는 반론을 유발하는 형태로 끝낼 것
- 물음표(?) 또는 열린 어미("~일까", "~일수록", "~인데" 등)로 종결
- 완결된 주장("~했다", "~이다")으로 끝내는 것 금지
- 독자가 답글을 쓰고 싶게 만드는 한 줄만 허용

OUTPUT FORMAT — JSON only:
{"cards": ["card1", "card2", "card3", "card4", "card5"]}
```

**발행 구조 (2-1 변경):**
- `write_thread()` → `{"cards": [5개], "link": "url"}` 반환
- `publisher.publish_thread_chain(cards, article, link_url)` → 5카드 체인 발행 후 루트 답글로 링크 발행
- 카드 5 발행 후 15초 대기 → 링크 답글 발행 (reply_to_id = 카드1 ID)

---

*문서 끝*
