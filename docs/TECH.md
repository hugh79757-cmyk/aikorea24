# TECH.md — aikorea24.kr 시스템 기술 문서

> 프로젝트 루트: ~/Projects/aikorea24
> 변경 이력은 CHANGES.md 참조

---

## 1. 전체 파이프라인

```
keywords.json → D1 DB ← db_reader (기사 수집)
                     ↓
            narrative_pitcher (피치 생성)
                     ↓
               writer (쓰레드 작성, format='D' 고정)
                     ↓
         validate_final_cards (검증)
                     ↓
           publisher (Threads 발행)
                     ↓
            posted.json (중복 방지 저장)
```

### 실행 주기
- **launchd**: 2시간 간격 (`pipeline/__main__.py` → `StepRunThreads` → `main_v3.py`)
- **1회 실행**: `python -m pipeline run` 또는 `python -m pipeline run --dry-run`
- **실패 알림**: `PipelineOrchestrator._send_telegram_failure()`가 step 실패 시 Telegram 전송

### 주요 진입점
- `scripts/threads/main_v3.py` — 메인 파이프라인 (`run_v3()`)
- `scripts/threads/v3/writer_v3.py` — 쓰레드 생성 (`write_thread()`)
- `scripts/threads/v3/narrative_pitcher.py` — 피치 생성 (`get_pitches()`)
- `scripts/threads/v3/format_selector.py` — 형식 선택 (`select_format()`)
- `scripts/threads/db_reader.py` — D1 DB 연결

---

## 2. 형식: D (펀치 브리핑형)

> 유일한 활성 형식. 5개 콘텐츠 카드 + 1개 링크 카드 (자동 추가).

### 프롬프트 구조 (build_system_prompt_D)
- stanza 구조: 3~5줄 + 빈 줄 반복. 빈 줄이 리듬
- 한 줄 25~40자. 카드당 450~500자
- 반말체 강제 (~임, ~했음, ~있음)
- 숫자-설명 쌍 구조: 숫자 먼저 → 의미 풀어쓰기
- 대비 구조: "A였음. 그런데 B."

### 각 카드 역할

| 순서 | 역할 | 설명 |
|------|------|------|
| 1 | 훅 | punch → 빈 줄 → 숫자/날짜 |
| 2 | 충돌 A면 | 구체적 사실, 숫자, 인용, 연구 결과 |
| 3 | 반전 | 예상 못 한 제3의 사실 |
| 4 | 확장 | 더 큰 맥락 또는 연결점 |
| 5 | 여운 | 숫자/사실 반전. 선언형 마무리 |
| 6 | 링크 | 자동 추가 (assemble_final) |

### 금지 규칙 (최소화)
- ~합니다, ~이다 금지 (반말체만)
- "많은", "대규모" 뭉뚱그린 표현 금지
- 없는 사실/연도 금지 (할루시네이션 방지)
- 피치 메타데이터 레이블 출력 금지

---

## 3. DB 구조

### D1 뉴스 DB
- 테이블: `articles` (또는 유사 이름)
- 주요 필드: `id`, `title`, `original_title`, `link`, `description`, `source`, `published_at`, `created_at`, `priority`

### posted.json (중복 발행 방지)
- `posted_ids`: 발행된 기사 ID 목록
- `posted_links`: 발행된 링크 목록
- `posted_titles`: 발행된 제목 목록
- `posted_original_titles`: 발행된 원제목 목록
- `posted_article_meta`: 기사 메타정보 (semantic dedup용)
- `last_reset`: 마지막 리셋 일자

### 중복 발행 방지 (3단계)
1. **Phase 1** (`db_reader.is_already_posted()`): original_title Jaccard + entity overlap (threshold 0.30 / 2개)
2. **Phase 2** (`narrative_pitcher.is_duplicate_pitch()`): article_original_titles entity overlap (2개)
3. **Phase 3** (`save_pitch_to_history().entities`): capitalized entity 저장 → Phase 2에 활용

---

## 4. 모델 라우팅

### model_router.py
- GPT-4o-mini 사용 (기본)
- GPT-4o로 변경 가능하나 현재 미적용

### 호출 포인트
| 단계 | 모델 | 용도 |
|------|------|------|
| 피치 생성 | GPT-4o-mini | 45~600개 기사에서 흥미로운 이야기 발견 |
| 피치 평가 | GPT-4o-mini | 0~5점 점수 + 상식충돌 검증 |
| 쓰레드 작성 | GPT-4o-mini | 5개 카드 + 링크 생성 |
| 휴머나이즈 | GPT-4o-mini | AI 말투 교정 |

---

## 5. 주요 함수 위치

| 함수 | 파일 (라인) | 설명 |
|------|-----------|------|
| `run_v3()` | `main_v3.py:129` | 전체 파이프라인 실행 |
| `validate_final_cards()` | `main_v3.py:41` | 발행 전 최종 검증 |
| `select_format()` | `format_selector.py:19` | 형식 선택 (항상 D) |
| `get_pitches()` | `narrative_pitcher.py` | 피치 생성 |
| `write_thread()` | `writer_v3.py:596` | 쓰레드 작성 |
| `assemble_final()` | `writer_v3.py:940` | 링크 카드 추가 |
| `save_draft()` | `writer_v3.py:980` | 초안 저장 |
| `publish_thread_chain()` | `publisher.py` | Threads 발행 |
| `build_system_prompt_D()` | `writer_v3.py:59` | D 형식 프롬프트 |
| `_FORMAT_COMMON_RULES()` | `writer_v3.py:158` | 공통 규칙 |

---

## 6. 환경 설정

### .env
- `BREVO_API_KEY` — 이메일 발송 API 키
- `BREVO_LIST_ID` — Brevo 구독자 리스트 ID
- `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` — 텔레그램 알림
- Cloudflare API 토큰들
- OpenAI API 키 (GPT-4o-mini / GPT-4o)

### wrangler.toml
- Cloudflare Workers 설정
- D1 DB 바인딩
- `BREVO_API_KEY` / `BREVO_LIST_ID`는 Pages Secrets로 주입 (wrangler.toml에는 주석 처리)

---

## 7. 자주 쓰는 명령어

```bash
# 1회 실행 (실제 발행)
python3 scripts/threads/main_v3.py

# 1회 실행 (발행 없이 초안만)
python3 scripts/threads/main_v3.py --dry-run

# 데몬 모드 (2시간 간격 자동 실행)
python3 scripts/threads/main_v3.py --daemon

# Briefing pipeline (블로그 브리핑, Threads와 별개)
BRIEFING_SCORER_MODE=dry_run python3 scripts/run_pipeline.py    # 점수 tagging만
BRIEFING_SCORER_MODE=shadow python3 scripts/run_pipeline.py     # + 2-Pass diff 로깅
# BRIEFING_SCORER_MODE=live  # Week 4 활성화 예정 — 실제 2-Pass 선택
```

---

## 8. Briefing Pipeline (2-Pass Impact Scoring)

> Threads 쓰레드와 별개로, 블로그 브리핑 생성 시 뉴스를 선정하고 점수를 평가하는 파이프라인.  
> `run_pipeline.py` → `auto_news_selector.py` → `auto_briefing.py`

### 8.1 평가 아키텍처 (Cascade)

```
D1 뉴스 100건 → cluster_by_topic (키워드 클러스터링)
                    ↓
           Phase 1 dedup (21~30건)
                    ↓
           Phase A: light score (4개 항목)
                    ↓
           Top-N 20 → 크롤링 (직렬)
                    ↓
           Phase B: full score (7개 항목)
                    ↓
           Pass 1: impact >= 70 (최대 3slot)
           Pass 2: round-robin + diversity (잔여 slot)
```

| 단계 | 평가 항목 | 데이터 |
|------|----------|--------|
| light (Phase A) | financial_impact, entity_tier, freshness, source_authority | title + description |
| full (Phase B) | + topic_blast_radius, conflict_drama, penalty_low_tier_entity, penalty_duplicate_theme | title + body + description |

### 8.2 3가지 모드

| 모드 | 선택 방식 | 점수 | Shadow diff | DB INSERT | 용도 |
|------|----------|------|-------------|-----------|------|
| `dry_run` (기본값) | 레거시 round-robin | tagging만 | Layer 1·2 | 영향 없음 | 회귀 검증 |
| `shadow` | 레거시 round-robin | tagging + 2-Pass 계산 | Layer 1·2·3 | 영향 없음 | 가중치 튜닝 데이터 |
| `live` (Week 4) | 2-Pass 활성 | tagging + 선택 | — | 변경됨 | 실제 운영 |

### 8.3 설정 파일

| 파일 | 내용 |
|------|------|
| `config/impact_weights.json` | 7개 평가 항목 가중치 + 임계값 + 환율 환산값 |
| `config/entity_tiers.json` | tier1 10개사, tier2 9개사 |

### 8.4 주요 함수

| 함수 | 파일:라인 | 설명 |
|------|---------|------|
| `score_article()` | `briefing_scorer.py:312` | light/full 평가 진입점 |
| `_parse_amounts()` | `briefing_scorer.py:101` | 본문에서 금액 추출 |
| `_match_entity_tiers()` | `briefing_scorer.py:184` | 등장 기업 티어 매칭 |
| `_compute_light_scores()` | `auto_news_selector.py:160` | Phase A (전체 후보) |
| `_crawl_and_full_score()` | `auto_news_selector.py:176` | Phase B (Top-N) |
| `_two_pass_selection()` | `auto_news_selector.py:193` | Pass 1 + Pass 2 선택 |
| `_expand_misc_for_legacy()` | `auto_news_selector.py:134` | 레거시 회귀용 misc 확장 |

### 8.5 Shadow Diff 로그 구조 (3층)

| Layer | 내용 | dry_run | shadow |
|-------|------|---------|--------|
| 1 | 레거시 vs 2-Pass URL set diff | O | O |
| 2 | 후보 전체 light/full score 히스토그램 (10점 bin) | O | O |
| 3 | score 65~75 경계역 기사의 breakdown + evidence | X | O |

로그 파일: `scripts/logs/briefing_shadow_diff.log` (JSONL)

### 8.6 버그 히스토리

| 버그 | 증상 | 수정 |
|------|------|------|
| _two_pass_selection 3개 반환 | misc light_score < 20 skip 후 deficit 처리 안됨 | fallback: misc full_score 순 인출 |
| cluster_by_topic 회귀 | source → misc 통합으로 round-robin 결과 불일치 | _expand_misc_for_legacy() 추가 |
