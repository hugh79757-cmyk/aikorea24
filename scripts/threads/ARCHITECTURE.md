# Threads 자동 발행 파이프라인 — 기술 문서

## 개요

AI 뉴스 기사 100개를 분석하여 5개 카드 Threads 쓰레드로 자동 생성·발행한다.
2시간 간격 데몬으로 동작하며, 중복 주제를 방지하고 발행 이력을 관리한다.

---

## 파일 구조

```
scripts/threads/
├── main_v3.py              # 진입점 — 데몬/dry-run/1회 실행
├── db_reader.py             # D1 데이터베이스 → 기사 풀 로드
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
    │   199개 기사 (posted.json 기준 중복 제외)
    │   1순위: 오늘 브리핑 → 2순위: 최근 7일 → 3순위: 이전
    │
    ▼
[2] narrative_pitcher.get_pitches()
    │   100개 기사 → description 원문 (크롤링 없음, 500자 제한 없음)
    │   → DiffusionGemma → 3개 피치 JSON
    │   ↓ hook[:8]+article_ids 중복 검사 (pitch_history 대조)
    │   ↓ pitch_evaluator.filter_pitches() 0~6점 평가 (4개 기준)
    │     (방향 정확성 0점이면 강제 불통과)
    │   ↓ posted.json pitch_history 저장
    │
    ▼
[3] writer_v3.write_thread()
    │   피치 연결 기사 URL → fetch_article_body() 원문 크롤링 (전문, 글자 수 제한 없음)
    │   build_system_prompt() + user_prompt → 모델 추론
    │   ↑ DiffusionGemma 5회 시도 → 실패 시 GPT-4o-mini 1회
    │   ↓ validate_cards() 검증 (5카드 + hook 일치 + twist 키워드 커버리지 40% + 마지막 키워드)
    │   ↓ assemble_final() URL 1개 추가
    │   ↓ save_draft() 로그/초안 저장
    │
    ▼
[4] publisher.publish_thread_chain()
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
| 2순위 | 최근 7일 news (최대 200개) | 브리핑 제외, 발행 이력 제외 |
| 3순위 | 그 이전 (최대 30일) | 풀이 50개 미만일 때만 보충 |

- `posted.json`의 `posted_ids` / `posted_links`와 대조하여 중복 제외
- wrangler D1 execute remote로 SQL 실행

### 2. narrative_pitcher.py

100개 기사에서 '상식과 실제의 충돌'을 발견한다.

**SYSTEM_PROMPT 핵심 설계:**
- "상식적으로 A였어야 하는데 실제로는 B인 상황" 찾기
- hook: 핵심 긴장 한 줄 (길이 제한 없음)
- 2개 이상의 서로 다른 기사 연결 강제
- `[소스 신뢰도]` 섹션: 주어-동사 방향 보존 지시

**크롤링 정책 (변경 — 2026-06-20):**
- 피치 선별 단계에서는 **크롤링하지 않음**
- DB의 `description` 컬럼을 **500자 제한 없이 전문(全文)** 사용
- 100개 기사를 가볍게 스캔하여 어떤 이야기로 글을 쓸지 선별하는 단계이므로 description으로 충분
- 실제 원문 크롤링은 writer_v3.py에서 선정된 2~3개 기사에 대해서만 수행

**모델:** DiffusionGemma 1순위 → GPT-4o-mini fallback (model_router 경유)

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

**원문 크롤링 (`fetch_article_body()`):**
- `requests` + `BeautifulSoup(lxml)`
- User-Agent 설정, timeout 15초
- 노이즈 태그 제거: script, style, nav, header, footer, aside, iframe
- 7개 CSS selector로 본문 영역 탐색: article, main, [role=main], .article-body, .post-content, .entry-content, .story-body
- 실패 시 description fallback
- **글자 수 제한 없음** — 선정된 2~3개 기사만 크롤링하므로 전문(全文) 전달
  (2026-06-20 변경: 기존 `max_chars=3000` 제거. 방향 정보가 뒷부분에서 잘리는 사고 방지)

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
- DiffusionGemma 5회 시도
- 전부 실패 시 GPT-4o-mini 1회 fallback
- 각 시도마다 `validate_cards()` 검증 (3단계):
  - 카드 수 5개 이상
  - 첫 번째 카드가 pitch hook[:8] 포함
  - twist 키워드 커버리지 40% 이상 + 마지막 키워드(서술어) 카드 포함
    (2026-06-20 추가: 주어-동사 방향 역전 카드 검출, 한국어 조사 제거 후 어간 매칭)
  - 실패 시 상세 로그 출력

**출력 포맷팅:**
- `---` 로 카드 구분
- 같은 주제 문장은 붙이고, 시점/장소/인물 전환 시 빈 줄
- 마지막 카드는 선언형 마무리 (여운)
- `assemble_final()`: 대표 URL 1개를 `🔗 url` 형식으로 마지막에 추가

### 6. publisher.py

Threads Graph API v1.0으로 연속 답글 체인을 발행한다.

**발행 프로세스:**
```
1. 각 카드 → POST /{user_id}/threads (컨테이너 생성)
   - 첫 카드: 일반 발행
   - 2번째 이후: reply_to_id = 이전 카드 post_id
2. 각 컨테이너 → POST /{user_id}/threads_publish (실제 발행)
3. posted.json 갱신 (posted_ids, posted_links, history)
```

- 3회 재시도, 토큰 만료 시 자동 갱신
- 각 단계 간 3초 대기

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
- **리듬**: 한 줄 하나의 정보. 짧게 끊는다.
- **여운**: 마지막 카드 마지막 줄은 선언이나 반전.

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
| 2026-06-20 | **피치 선별 단계 크롤링 제거** — description 원문(500자 제한 없음)으로 충분 |
| 2026-06-20 | **쓰레드 작성 단계 전문 크롤링** — fetch_article_body() max_chars=3000 제한 제거 |
| 2026-06-20 | **방향 정확성 평가 추가** — pitch_evaluator 4번째 기준(direction_ok) + GPT-4o-mini 전환 |
| 2026-06-20 | **twist 키워드 검증** — validate_cards()에 서술어 포함 + 커버리지 40% 체크 |
