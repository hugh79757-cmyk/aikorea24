# CHANGES.md — 세션 간 변경 이력

> 기술 문서는 `docs/TECH.md` 참조.
> 세션 종료 시 에이전트가 자동 append.

---

## 2026-07-12 — Vectorize threshold 완화 + 워킹트리 정리

### 변경
- `pipeline/infra/vectorize_client.py` — `SIMILARITY_THRESHOLD = 0.85 → 0.60`
  - 의도: 같은 사건/기업/맥락의 다른 각도 기사도 중복으로 차단
  - 0.85는 거의 동일 기사만 잡아서 시간차 관련 기사가 나란히 발행되는 문제 발생
  - 발행 빈도가 낮으므로 보수적 0.85 → 0.60으로 완화
- `.gitignore` — 글로벌 `__pycache__/` + `*.pyc` 패턴 추가
  - 누락 디렉토리 4개 (`api_test/`, `pipeline/`, `pipeline/steps/`, `pipeline/threads/`, `tests/`) 자동 커버
  - 중복된 개별 `__pycache__/` 명시 항목 제거

### 추적 해제 (워크트리 노이즈 정리)
- 80개 파일 `git rm --cached`:
  - `.pyc` ~30개 (4개 `__pycache__/` 디렉토리)
  - `.log` ~15개 (`api_test/cron*.log`, `manual_run.log`, `naver_blog/logs/auto_publish_err.log` 등)
  - 런타임 상태 ~35개 (`scripts/threads/posted.json`, `tools_collector.log` 등)

### 의사결정
- threshold 0.60: 코사인 유사도 0.60 이상이면 중복 처리. 의미적으로 관련된 기사를 한 토픽으로 묶어 발행 빈도 자연 감소
- `.gitignore` 글로벌 패턴: 명시 항목 나열 대신 와일드카드로 단순화, 신규 디렉토리 자동 커버

### 커밋
- `bfeb994` fix(vectorize): 중복 threshold 0.85 → 0.60
- `38906a6` chore: 광범위 런타임 아티팩트 추적 해제 + .gitignore 통합
- `113e377` chore: .gitignore 글로벌 __pycache__ 패턴 명시 추가
- `00b2a95` chore: 추적 해제 — 런타임 아티팩트 + pipeline/infra/__pycache__/

### 검증
- `touch test.pyc test.log` → `git status` 미감지 확인
- 워킹트리 깨끗 (untracked 0, modified 0)

### 미해결
- `.continue-here.md`의 "Option B seed uncommitted" 표기 stale → 실제 `4177c4a`에 커밋됨 (라이브 배포). 핸드오프 갱신 필요

---

## 2026-07-12 — Phase 25: 커뮤니티 레슨 순차 해금

### 변경
- `src/pages/community/[id].astro`:
  - 게이트 재작성 — 강의 레슨 판별을 `category==='강의'`(시드엔 `free`라 분기 누락)에서 **`course_lessons` 매핑 존재 여부**로 변경 (시드 데이터 변경 없음)
  - 순차 해금: 등록 사용자 `days_sent >= day_number` 이면 전체 본문, 아니면 preview + 잠금
  - 3상태 잠금 카드 UI: 비로그인(로그인+강좌 신청 CTA) / 로그인+미등록(수강생 전용) / 로그인+등록+대기("N일차 잠금 해제 전" 안내)

### 의사결정
- 해금 기준 = `days_sent`(이메일 드립 진도 미러). 크론 OFF 상태에선 days_sent=0 유지 → 콘텐츠 검수 끝날 때까지 전 레슨 잠금 (사용자 승인)
- auto-enroll 없음. 강좌 폼(`/api/courses/enroll`)과 뉴스레터 폼(`/api/subscribe`)은 이미 분리 — `enrollments`가 단일 진실원
- 부수 발견(별도 이슈): day 0 고아 레슨(이메일로 절대 안 나감), 랜딩페이지 커리큘럼/시드 불일치

### 배포/커밋
- 코드 변경 완료, `npm run build` 통과. 커밋/배포는 미실행 (명시 요청 대기)

---

## 2026-07-12 — Phase 24: 썸네일 파이프라인 수정 + 이미지 gitignore

### 변경
- `scripts/auto_thumbnail.py`:
  - dedup 재사용 버그 수정 — `photos[0]` 즉시 재사용 → 미사용 사진 탐색(`_pick_unused_photo`), 없으면 `DEEPSEEK_POOL` 대체 쿼리 3개 시도
  - `search_pexels`/`download_image`에 `@retry(max_retries=3, delay=1.0, backoff=2.0)` 적용 (`pipeline/infra/retry.py`)
  - Pexels 전면 실패 시 커밋된 `public/images/news-keyword-og.webp`를 placeholder로 복사 (`_use_default_thumbnail`) — 깨진 `image:` 참조 제거
- `scripts/auto_deep_article.py` / `scripts/blog_draft_generator.py`: 썸네일 파일 존재 시에만 `image:` frontmatter 기록
- `.gitignore`: `public/images/` 추가 (썸네일은 wrangler 배포로만 반영, git 비포함)

### 의사결정
- 배포는 `wrangler pages deploy --commit-dirty=true` 직접 업로드 → git 푸시 불필요. images를 git에서 제외해도 라이브 영향 없음
- placeholder는 의도된 단일 기본 이미지 (재사용된 스톡 사진 위장 문제 해결)
- 오늘(07-12) 3건 재사용 표지 재생성은 보류 — Pexels 실패 시 placeholder가 현재 표지보다 열화 우려

### 배포/커밋
- 커밋 `b49a09b` — 코드 수정 + 5개 블로그 포스트 동기화 (썸네일은 로컬 유지, git 미포함)
- 라이브 사이트 HTTP 200 유지 (코드 변경은 차기 wrangler 배포 시 반영)

---

## 2026-07-11 — 강좌 랜딩 Coming Soon 공지 + 배포 (1 deploy)

### 변경
- `src/pages/courses/7day-starter.astro`:
  - 뱃지 `완전 무료 · 7일 코스` → `🎯 곧 오픈 · 알림 신청 중`
  - 이메일 입력폼 위에 amber 공지 추가: *"📢 강좌가 곧 오픈됩니다. 준비되면 이메일로 알려드리겠습니다."*
  - 버튼 텍스트 `무료 신청하기` → `오픈 알림 신청`
  - 성공 메시지 `신청 완료! X시에 첫 레슨 발송` → `오픈 알림이 등록되었습니다!`
  - 하단 CTA `지금 바로 시작하세요 / 무료 신청하기` → `곧 오픈됩니다 / 오픈 알림 신청`
  - 모든 error/fallback 버튼 텍스트 동기화

### 의사결정
- 콘텐츠가 아직 준비되지 않았으므로 등록은 받되 기대치를 낮추는 UX로 전환
- 기존 enroll API는 그대로 유지 — 등록 데이터는 D1 + Brevo에 정상 저장

### 배포
- 배포 스크립트(`scripts/deploy.sh`)로 1회 배포 완료
- 라이브 (https://aikorea24.kr, HTTP 200)

---

## 2026-07-09 — DeepSeek Tuning + Validation Relaxation (5 commits, push 완료)

### 변경
- `model_router.py`: `thinking={"type":"disabled"}` 추가, DeepSeek timeout 60s→180s, MiMo 기본 라우팅 제거, finish_reason/refusal 상세 로깅
- `writer.py`: humanize_cards 주석처리, max_tokens 8000→16000, DeepSeek 호출 시 `extra_body=thinking:disabled` 적용, 카드별 템플릿 간소화, 중복 길이 검증 제거
- `validator.py`: Hook 첫 줄 최소 길이 30→8자, 한글 비율 30%→15%, body 카드 최소 길이 50→30자
- `pitch_evaluator.py`: 평가 GPT-4o-mini 전용, 추론 금지 프롬프트 추가
- `pitch.py`: 재생성 max_tokens 1500→3000, 첫 번째 프롬프트에 JSON 형식 명시
- `main_v3.py`: retry delays [60,120,300,600] → [60,60,60,60]

### 의사결정
- DeepSeek CoT 출력 차단: `thinking=disabled`로 추론 출력 제거, 16000 max_tokens로 여유 확보
- humanize 제거: DeepSeek raw 출력이 충분히 좋고, humanize가 Hook 첫 줄을 잘라내 검증 실패 유발
- 평가 GPT 전용: DeepSeek가 항상 추론을 붙여서 토큰 초과, GPT가 JSON만 깔끔하게 출력
- Hook 최소 8자: stanza 형식과 호환

### 영향
- DeepSeek 쓰레드 생성 → 검증 → 발행까지 최초로 한 번에 성공 (17:24:21)
- 마지막 발행 후 5시간 이상 발행 중단 문제 해결
- 5개 커밋 push: `5c1fe96`..`88cc015`

---

## 2026-07-08 — Writer Prompt Style Update (커밋 완료)

### 변경
- `pipeline/threads/writer.py` `build_system_prompt_D()` — [문체 원칙] 전면 개정:
  - `"~아님"` → `"~아님, ~함"` 종결어미 확장
  - 줄 길이 20~25자 내외 규칙 신설, 초과 시 무조건 줄바꿈
  - 문장 간 한 줄 띄우기 규칙 추가 (카드 내 호흡)
  - 중국어 예시(`新加坡금융관리국`) 제거
  - [최우선] 섹션 40~60자/25자 금지 규칙 → `줄 길이는 문체 원칙을 따를 것`으로 교체

### 의사결정
- 줄 길이 20~25자: 의미 단위로 끊어 리듬감 향상 (기존 40~60자는 과도)
- [최우선] 줄 길이 규칙 삭제: 문체 원칙과 충돌 방지, 단일 진실 공급원 유지

### 영향
- writer.py prompt 규칙 일관성 개선
- 커밋: `90bb7a6` → `main` 푸시 완료
- 테스트 미실행 (프롬프트 문자열만 변경, 로직 무관)

---

## 2026-07-07 — Hook Validation Fix + Pipeline Verified (실행 완료)

### 변경
- `pipeline/threads/validator.py` — `validate_card_structure()` hook 검증: `cards[0]` 전체 → `cards[0].split('\n')[0]` 첫 줄만 검사 (ThreadForge `role: hook` 정렬)
- `api_test/news_collector.py` — D1 link dedup 버그 수정 (`get_existing()` link 전범위 조회, `save_to_d1()` wrangler `changes` 파싱)
- `pipeline/threads/writer.py` — 4단계 JSON 파싱 복구 + sequential fallback (DeepSeek → GPT-4o-mini)
- `scripts/threads/main_v3.py` — Vectorize 인덱싱 자동 실행 연동

### 의사결정
- Hook 검증 threshold 10 유지하되 대상 범위 축소 (첫 줄만) — 첫 카드 내부 stanza 3개(11문장) 자연스러운 구조 허용
- `response_format={"type": "json_object"}` 미전달 유지 — DeepSeek v4 flash 불안정 회피, 프롬프트 + 4단계 fallback으로 방어

### 영향
- 08:33 발행 성공 (6카드, Threads API 정상)
- 08:59 검증 통과 후 DNS 장애로 발행 실패 (코드 무관, 네트워크 일시적)
- launchd `kr.aikorea24.threads-publisher` 재활성화 → 2시간 간격 자동 발행 개시

---

## 2026-07-06 — Phase 15: Vectorize + TTL + JSON Cards (실행 완료)

### 변경
- `pipeline/infra/vectorize_client.py` — **신규**: OpenAI text-embedding-3-small (1536d) + Cloudflare Vectorize REST API 클라이언트 (`upsert_vectors`, `query_vectors`, `delete_vectors`, `embed_article`, `is_duplicate_with_vectorize`)
- `pipeline/threads/writer.py` — delimiter fallback 제거, JSON-only 파싱 (`parse_cards_json_first`), `_repair_truncated_cards()` / `parse_cards()` 삭제
- `pipeline/threads/crawler.py` — `log_failed_crawl()`에 `expired_at` 필드 추가 (24h TTL)
- `scripts/threads/failed_articles.py` — failed_crawls 24h TTL 만료 로직 (`_is_crawl_expired`), URL 기반 키 매칭 (빈 article_id 문제 해결)
- `scripts/threads/db_reader.py` — `is_already_posted()`에 Vectorize 5차 중복 판정 추가 (similarity threshold 0.85)
- `scripts/threads/main_v3.py` — 발행 성공 시 Vectorize 인덱싱 자동 실행
- `scripts/threads/migrate_to_vectorize.py` — **신규**: 기존 342개 기사 벡터 마이그레이션 스크립트
- `scripts/threads/v3/writer_v3.py` — `parse_cards` import 제거
- `tests/test_writer.py` — `TestParseCards` / `TestRepairTruncatedCards` 삭제, JSON 전용 테스트로 교체

### 의사결정
- Vectorize = 보조 레이어 (기존 `is_same_topic()` 유지, 2차 semantic dedup)
- failed_crawls TTL = 24시간 (AI 뉴스는 시간 민감)
- failed_crawls 키 = URL 기반 (기존 `article_id` 빈 값 문제 해결)
- 카드 출력 = JSON 배열 전용 (delivr fallback 제거)
- 카드 수 = 6개 유지 (ThreadForge 7+1과 달리 5幕 구조 최적화)

### 영향
- 기존 중복 기사 20+건이 failed_crawls에서 자동 만료 해제 → 기사 풀 회복
- Vectorize 인덱싱: 새 발행 시 자동, 기존 342건은 수동 마이그레이션 필요 (`python3 scripts/threads/migrate_to_vectorize.py`)
- 테스트 283개 통과
- commit: `d844c09`

---

## 2026-07-05 — Phase 14: Delimiter Reconfiguration (실행 완료)

### 변경
- `pipeline/threads/writer.py` — `parse_cards_json_first()` 신규 (JSON → delimiter fallback), `response_format={"type": "json_object"}` 전달, `build_system_prompt_D()` JSON 출력 형식 명시
- `scripts/threads/v3/model_router.py` — debug logging 정리
- `scripts/threads/main_v3.py` — 한글+영어 붙어쓰기 검증 비활성화 (고유명사+조사 패턴 지속적 오탐 유발)
- `tests/test_writer.py` — `TestParseCardsJSONFirst` (5개 테스트)
- `tests/test_characterization_validate_final_cards.py` — 한글+영어 검증 테스트 업데이트

### 의사결정
- `response_format={"type": "json_object"}` 채택 (DeepSeek/MiMo 호환성)
- `FORMAT_CARD_COUNT_TOLERANCE` D 포맷: `(4, 7)` (최소 4개 카드 허용)
- 한글+영어 붙어쓰기 검증 비활성화 — 고유명사+조사 패턴이 지속적으로 오탐 유발

### 영향
- Phase 13 이후 지속되던 delimiter collision 문제 해결 (JSON-first 파싱)
- 테스트 292개 통과, 분당 발행 안정성 확보
- DeepSeek write_thread 직접 성공 (GPT 폴백 불필요)

---

## 2026-07-04 — Phase 10-1: Card Structure Validation (실행 완료)

### 변경
- `pipeline/threads/validator.py` — `ADDITIONAL_MESSAGE_PATTERNS` 20개 + `ALL_MESSAGE_PATTERNS` 통합 + `validate_model_message()` + `validate_card_structure()` 신규
- `pipeline/threads/writer.py` — import 추가 + `write_thread()` 검증 체인에 구조 검증 통합
- `tests/test_validator.py` — 20개 새 테스트 (TestValidateModelMessage 10개 + TestValidateCardStructure 10개)

### 의사결정
- 7가지 구조 검증 규칙 채택 (최소 길이, 한글 비율, 문장 완성도, 콘텐츠 밀도, 중복, Hook/Body 길이)
- 20개 추가 모델 메시지 패턴 (정중한 형태, 짧은 응답, 영문 메시지, 설명 접두사)
- `write_thread()` 검증 체인에 구조 검증 먼저 적용 (패턴 필터링 이전)

### 영향
- 전체 테스트: 261개 (241 기존 + 20 신규)
- 모델 메시지 탐지율 향상 (패턴 + 구조 이중 검증)
- 카드 구조 이상치 완전 차단

### 검증
- 261/262 전체 테스트 통과 (1 pre-existing freshness 실패)
- 4개 커밋 생성:
  - `25e99ae`: feat(10-1): add enhanced model message patterns and structural validation
  - `aa47167`: feat(10-1): integrate structural validation into writer validation chain
  - `f1ca3c5`: test(10-1): add TestValidateModelMessage and TestValidateCardStructure
  - `43322d2`: test(10-1): fix test data for correct validation thresholds

---

## 2026-07-04 — Phase 10: Model Message Leakage Fix (실행 완료)

### 변경
- `pipeline/threads/writer.py` — `MODEL_MESSAGE_PATTERNS` 리스트 + `_strip_model_explanatory()` 함수 신규 + `fix_cards()`, `humanize_cards()`에 필터 적용
- `pipeline/threads/validator.py` — `MODEL_MESSAGE_PATTERNS` 리스트 + `validate_final_output()`에 모델 메시지 탐지 추가
- `tests/test_writer.py` — 14개 새 테스트 (TestStripModelExplanatory 4개 + fix_cards/humanize_cards 테스트 10개)

### 의사결정
- 패턴 기반 필터링 채택 (ML 기반 탐지 불필요)
- `split('---')` 이전에 필터링하여 메시지가 카드로 포함되는 것 완전 차단
- `validate_final_output()`에서 이중 검증 (필터링 + validation)

### 영향
- 전체 테스트: 241개 (227 기존 + 14 신규)
- 모델 메시지가 발행 카드에 포함되는 버그 완전 해결

### 검증
- 241/242 전체 테스트 통과 (1 pre-existing freshness 실패)
- 3개 커밋 생성:
  - `5ee5277`: feat(10-mlf): add model message detection utility
  - `676aaa8`: feat(10-mlf): add model message detection to validate_final_output
  - `f6ec5f8`: test(10-mlf): add tests for model message filtering

---

## 2026-07-04 — Phase 9: Test Coverage Expansion

### 변경
- `tests/test_writer.py` — +6 tests: load_style_examples, build_system_prompt_D, assemble_final_without_url, humanize_cards_preserves_count
- `tests/test_crawler.py` — +2 tests: log_appends_multiple, log_deduplicates_url
- `tests/test_pitch.py` — +4 tests: parse_top_pitch, _regenerate_pitch_from_crawl success/failure
- `tests/test_integration_defense.py` — 신규 파일: 10개 integration 테스트 (validate_final_output, detect_clean_pipeline, multiple_defense_layers)

### 의사결정
- 기존 206개 → 227개 (+21개) 확장
- integration 테스트로 3중 방어 체계 연동 검증
- writer/crawler/pitch 핵심 함수 커버리지 강화

### 영향
- 전체 테스트: 227개 (227 passed, 1 pre-existing failure)
- 방어 레이어 간 파이프라인 검증 강화

### 검증
- 227/228 전체 테스트 통과 (1 pre-existing freshness 실패)

---

## 2026-07-04 — Phase 8: Validation Gap Closure (3중 방어 시스템)

### 변경
- `pipeline/threads/pitch.py` — `detect_prompt_leak()` 확장: `LEAKED_PROMPT_PATTERNS` 통합 검사 + 전체 텍스트 검사 범위 확장
- `pipeline/threads/validator.py` — `validate_final_output()` 신규: 프롬프트+외국어+한글 통합 검증 (3차 방어)
- `pipeline/threads/writer.py` — `write_thread()` validation chain: `validate_no_foreign_language()` → `validate_final_output()` 교체 (3차 방어 적용)
- `tests/test_validator.py` — `TestValidateFinalOutput` 5개 테스트 신규 + `TestDetectPromptLeakPatterns` 4개 테스트 신규

### 의사결정
- Phase 6가 피치에만 검증 적용 → 최종 카드 무시 → 재발한 사례를 교훈으로 기록
- MiMo v2.5는 중국 모델이라 한국어 프롬프트에도 한자 생성 경향 → 프롬프트 + 후처리 양쪽 모두 방어
- "Monetary Authority of Singapore"는 한국인이 모르는 고유명사가 아님 → 한자→한국어 번역으로 해결

### 영향
- 3중 방어 체계 완성: 1차(피치 생성) → 2차(쓰레드 작성 후) → 3차(발행 직전)
- 프롬프트 노출 + 외국어(한자/일본어) 최종 카드에서 완전 차단

### 검증
- 21/21 `test_validator.py` 통과
- 205/206 전체 테스트 통과 (1 pre-existing freshness 실패)

---

## 2026-07-03 — 크롤링 실패 시 RSS fallback 폐기 (품질 개선)

### 변경
- `pipeline/threads/pitch.py` `get_pitches()` — 크롤링 실패/URL 부재/재생성 실패 시 RSS description 기반 저품질 피치를 발행하던 fallback 제거, `return []`로 폐기
- `tests/test_pitch.py` — `TestGetPitchesCrawlFail` 클래스 신규 (4개 테스트: URL 없음/크롤링 실패/재생성 실패/성공)

### 의사결정
- RSS description만으로 생성된 피치는 품질이 낮아 발행하지 않음
- 크롤링 성공 시에는 기존과 동일하게 재생성된 피치 사용

### 영향
- Threads 발행 빈도 하락 가능 (크롤링 실패 시 skip)
- 글 품질 향상 (크롤링 기반 피치만 발행)

### 검증
- 34/34 `test_pitch.py` 통과
- 196/197 전체 테스트 통과 (1 pre-existing freshness 실패)

---

## 2026-07-03 — Phase 7: 크롤링 실패 기사 제외 메커니즘

### 변경
- `pipeline/threads/pitch.py` — `get_pitches()`에 `exclude_ids` 파라미터 추가, 반환 타입 `list` → `tuple[list, set]` 변경, 셔플 후 제외 필터 삽입, 크롤링 실패 시 실패한 article_id 반환
- `scripts/threads/main_v3.py` — `failed_article_ids: set[str]` 추가, 튜플 언패킹, `exclude_ids=failed_article_ids` 전달, 누적 로직
- `tests/test_pitch.py` — `TestGetPitchesCrawlFail` 4개 테스트 튜플 어서션 업데이트
- `pipeline/threads/crawler.py` — `log_failed_crawl()`에 `article_id` 파라미터 추가

### GSD 통합
- `AGENTS.md` — `/gsd-pause-work` / `/gsd-resume-work` 절차 정식 추가
- `.planning/CHANGES.md` → `../CHANGES.md` 심볼릭 링크 생성
- `.planning/ROADMAP.md` — Phase 7 항목 추가 (1/1 plan, Complete)
- `.planning/phases/07-crawl-failure-exclusion/` — RESEARCH.md + PLAN.md + SUMMARY.md

### 의사결정
- Session-scoped exclusion: 크롤링 실패는 일시적이므로 프로세스 재시작 시 리셋
- `failed_crawls.json`은 추후 cross-session exclusion용으로 확장 가능 (article_id 컬럼 추가 완료)

### 검증
- 34/34 `test_pitch.py` 통과
- 196/197 전체 테스트 통과 (1 pre-existing freshness 실패)
- Syntax check 5개 파일 전부 통과

---

## 2026-07-03 — Phase 6: Prompt Leakage & Truncation Fix

### 문제 진단
- **문제 A**: `save_pitch_to_history()`가 hook/narrative를 `[:30]`/`[:50]`으로 강제 트렁케이션 → 의미 손실
- **문제 B**: LLM이 출력에 프롬프트 라벨(`상식(A):`, `실제(B):`)을 누출 → `posted.json` 오염 (72건)

### 변경 파일
#### 수정
- `pipeline/threads/pitch.py` — `clean_leaked_prompt()` + `LEAKED_PROMPT_PATTERNS` 리스트 추가; `save_pitch_to_history()`에 방어막 적용; 트렁케이션 `[:15]`→`[:80]`, `[:30]`→`[:120]` 완화; fallback 스키마 `[:18]`→`[:30]`, `[:100]`→`[:200]`
- `scripts/threads/v3/model_router.py` — `response_format` 파라미터 + `**kwargs` 전달
- `tests/test_pitch.py` — 97줄 신규 테스트 (JSON 모드, clean_leaked_prompt, 트렁케이션 완화)

#### 변경
- `pipeline/posted.json` — 오염 entry 18개 정리
- `scripts/threads/posted.json` — 오염 entry 54개 정리

#### 미추적 (파이프라인 산출물)
- 블로그 포스트 5개 (`src/content/blog/2026-07-03-*.md`)
- 썸네일 5개 (`public/images/2026-07-03-*/`)

### 의사결정
- `response_format={'type': 'json_object'}` 채택 — 프롬프트 누출 근본 차단
- 정상 경로(JSON 모드)에서는 hook/narrative 트렁케이션 0%
- `_parse_pitches_fallback()` regex 보존 (이전 데이터 호환성)
- `clean_leaked_prompt()`는 `LEAKED_PROMPT_PATTERNS` 리스트로 확장 가능

### 검증
- 192/193 테스트 통과 (1 pre-existing `test_cascade_2pass` freshness 실패)
- `posted.json` label leak 0건 확인

### 미해결
- `test_cascade_2pass.py` — fixture 날짜 동일로 freshness=0 (pre-existing)
- ROADMAP.md Phase 2/5 상태 업데이트 필요

---

## 2026-07-02 — Tools Collector 버그 수정 + 문서화

### 버그 수정
- `scripts/tools_collector.py`: import 순서 재배열 — `from pipeline.infra.logger`가 `sys.path.insert`보다 먼저 실행되어 ModuleNotFoundError 발생
  - 수정: `_PROJECT_DIR = os.path.dirname(__file__)` 기반 path를 pipeline import 전에 먼저 삽입
  - launchd `kr.aikorea24.tools-collector` (매일 06:00) 정상화, LastExitStatus=256 원인 제거

### 문서화
- `docs/TECH.md` Section 10 신규 — Tools Collection Pipeline: 흐름, 5개 소스, 메타데이터 생성, im-not-ai 3단계, plist 설정, 함수 위치
- `AGENTS.md` — Tools Collection Pipeline 참조 블록 추가
- `docs/TECH.md` Section 1 — 별도 파이프라인 표기

### 검증
- `python3 -m py_compile scripts/tools_collector.py` ✅
- pipeline.infra 3개 모듈 import 테스트 통과 ✅

---

## 2026-07-01 — auto_email_sender: template 2 → template 1 전환 (rich HTML)

### 기능 변경
- `scripts/auto_email_sender.py`: `generate_email_html` 전면 교체 — **템플릿 1(리치)로 복원**
  - TOC 섹션 (오늘의 브리핑 목록)
  - 각 아이템: 숫자 뱃지 + 제목 + 코멘트(파랑박스) + 설명 + 내부 링크(`aikorea24.kr/briefing/`)
  - "전체 보기" 버튼
  - AI 도구 섹션 (D1 tools 테이블, 최신 6개)
  - 헤더: 🤖 + AI코리아24 + 오늘의 AI 브리핑 + 그래디언트 라인
  - 푸터: 커뮤니티 링크 + 구독 해지
- `get_tools()`, `_d1_query()`, `esc()` 함수 신규 추가

### 분석
- 6/26~6/28 사이 simple template이 커밋되었으나, 같은 시기 `send-email.ts`(수동)는 rich template 유지
- working tree에만 rich template이 존재 (미커밋 상태)
- 외부 링크(`news_link`) → 내부 링크(`aikorea24.kr/briefing/`)로 변경

### 배포
- `682ddb7` → `origin/main` push 전 (수동 push 필요)

---

### 기능 변경
- `pipeline/threads/writer.py`: 프롬프트 전면 개선 (발행글 개념 명확화, 예시 형식 추가), temperature 0.7→0.3/0.1 2단계 하강, 카드 수 부족 시 재시도 로직 추가
- `scripts/threads/v3/model_router.py`: 모델 우선순위 변경 — **DeepSeek V4 Flash 1순위**, GPT-4o-mini 2순위 (fallback)
- `scripts/threads/v3/model_router.py`: `model_override='openai'` → DeepSeek 건너뛰고 OpenAI 사용

### 알림 조건 분석
- "Threads 5회 모두 실패"는 publish에 단 한 번도 도달하지 못하고 5회 전부 continue로 끝난 경우만 발송
- publish 성공 시 line 285에서 return하므로 같은 프로세스 내에서는 발송 불가
- **launchd 2개 중복 실행** 의심: `threads-publisher`(2시간) + `pipeline-runner`(06/20시) → 각각 main_v3.py 실행 가능

### 배포
- `d7dd104` → `origin/main` push 완료

---

## 2026-07-01 — Pexels+DeepSeek 썸네일 교체 + 파이프라인 검증

### 기능 변경
- `scripts/auto_thumbnail.py`: og:image 추출 → **Pexels API + DeepSeek 키워드 추출**로 전면 교체
  - DeepSeek `deepseek-chat`으로 description 기반 Pexels 검색 키워드 생성
  - Pexels 검색 결과 중 미사용 ID 선택 (JSON dedup, `config/pexels_used_ids.json`)
  - 폴백 체인: DeepSeek → Pexels → `artificial intelligence` fallback
- `scripts/run_pipeline.py`: `process_thumbnail()`에 `title`/`description` 인자 전달

### 버그 수정
- `src/content/blog/2026-07-01-vibe-코딩-플랫폼-base44-ai-스타트업-방어력을-위해-자체-모델-출시.md`: frontmatter `---` 누락 → 빌드 실패 원인 → 수정
- 배포 실패(rc=127) 원인 파악: `set -e` + `.env` 내 `source ~/.env.common` 충돌

### 배포
- git push → Cloudflare Pages auto-build 작동 안 함 (대시보드 설정 필요)
- wrangler CLI 수동 배포로 대체 (44f1c18a)
- 기존 썸네일 332개 git 복구 완료, 46개 Pexels 생성 완료

### 검증
- 파이프라인 전체 실행 성공 (썸네일 제외): 6기사 → 브리핑(id=148) → 블로그 6개 → 이메일 발송
- 371/388 블로그 썸네일 매칭 (17개 미해결: 5개 대소문자 + 9개 신규 + 3개 기타)

---

## 2026-07-01 — 파이프라인 복구 + D 형식 6카드 변경 + 썸네일 이슈

### 버그 수정
- `run_pipeline_with_notify.py` 제거로 인한 briefing pipeline 중단 → git에서 복원
- `auto_news_selector.py`: `from pipeline.infra.d1_client` import 시 `ModuleNotFoundError` → `sys.path` 추가
- `main_v3.py`: launchd 실행 시 동일 import 문제 → `sys.path` 추가
- `pipeline-runner` launchd plist 업데이트 → `run_pipeline_with_notify.py` 호출로 복원
- D1 `pipeline_runs` 테이블 migration 적용 (누락)
- `tests/test_pitch.py`: monkeypatch 버그 수정

### 기능 변경
- D 형식 5카드(4내용+링크) → **6카드(5내용+1출처링크)** 로 변경
  - `FORMAT_CARD_COUNTS: 5→6`, `FORMAT_CARD_COUNT_TOLERANCE: (4,6)→(5,7)`
  - `assemble_final`: 6장이면 6번 교체, 5장이면 append
  - 시스템 프롬프트, 유저 프롬프트 업데이트

### 썸네일
- `blog-draft` launchd job unload (키워드 블로그 중단)
- og:image 기반 썸네일 저작권 문제 확인 (13개 깨짐)
- `2026-06-26-패트로너스-ai` ~ `2026-06-30-eclerx` 사이 ~50개 og:image 기반 식별

### 검증
- Threads 발행: ✅ Tesla FSD 6카드 성공
- 브리핑+블로그+이메일: ✅ id=147, 6아이템, 이메일 발송 성공
- 배포: ⚠️ 수동으로 성공 (launchd 환경에서 정상)
- Tests: 167/168 통과

---

## 2026-06-30 — Phase 5: Dead Code Removal & Final Polish 실행 완료

### 변경 파일
#### 삭제 (105+ dead files)
- `backup_*.txt` 14개 — 이미 정리됨 (0개 남음)
- `.bak*` 80+ 파일 프로젝트 전체 제거
- `patch_*.py`, `test_*.py` (tests/ 외), `spotlight_*.sh`, `quick_check.sh` — 13개
- `scripts/threads/scorer.py`, `enricher.py`, `backfill_meta.py`, `run_dry.py`
- `scripts/threads/run_loop.sh`
- `scripts/threads/archived/` 디렉토리 (6개 파일)
- `scripts/threads/prompts/` + `prompts_legacy/` (4개 파일 + 디렉토리)
- `scripts/threads/threads-publisher.plist` (old generated plist)

#### 삭제 (Dead code files)
- `scripts/threads/v3/format_selector.py` — writer.py에 인라인
- `scripts/threads/validator.py` — standalone duplicate
- `scripts/run_pipeline_with_notify.py` — orchestrator Telegram으로 대체

#### 수정
- `pipeline/threads/writer.py` — `_FORMAT_COMMON_RULES()` 제거, format_selector import → `format_choice = 'D'` 인라인
- `pipeline/threads/validator.py` — `validate_thread()` 함수 제거
- `pipeline/threads/pitch.py` — import 순서 버그 수정 (sys.path.insert before db_reader import)
- `pipeline/orchestrator.py` — `_send_telegram_failure()` 추가 (step 실패 시 Telegram 알림)
- `pipeline/steps/step_run_threads.py` — `--once` 플래그 제거
- `scripts/threads/main_v3.py` — `load_env()`, `reset_posted_daily()`, `--once` 플래그 제거
- `scripts/threads/v3/writer_v3.py` — `_FORMAT_COMMON_RULES` re-export 제거
- `tests/test_validator.py` — `TestValidateThread` 클래스 제거
- `tests/test_characterization_pure_functions.py` — 3개 `validate_thread` 테스트 클래스 제거

### 의사결정
- import 순서 버그: pitch.py의 `from db_reader`가 `sys.path.insert`보다 먼저 실행되어 실패 → 모듈 초기화 재배열로 해결
- format_selector.py는 항상 'D'만 반환하던 dead module — 인라인 후 제거
- main_v3.py는 Strangler Fig 전략에 따라 유지 (subprocess entry point), dead code만 정리

### 검증
- 167/168 테스트 통과 (5개 validate_thread 테스트 제거 + 1 pre-existing 실패)
- Pipeline dry-run 성공
- D1 posts/comments 테이블 정상 (posts=6건)
- Launchd threads-publisher job 정상 등록

### 미해결
- `test_cascade_2pass.py` — fixture 날짜 동일로 freshness=0 (pre-existing, Phase 2)

---

## 2026-06-30 — Phase 4: Monolith Splitting 실행 완료

### 변경 파일
#### 신규 생성
- `pipeline/threads/validator.py` — validate_cards, validate_year, validate_keywords, validate_thread + 3 상수
- `pipeline/threads/crawler.py` — fetch_article_body, log_failed_crawl
- `pipeline/threads/pitch_evaluator.py` — evaluate_pitch, filter_pitches
- `pipeline/threads/pitch.py` — fill_article_ids, parse_pitches_from_text, parse_top_pitch, load_pitch_history, is_duplicate_pitch, save_pitch_to_history, get_pitches, _regenerate_pitch_from_crawl
- `pipeline/threads/writer.py` — build_system_prompt_D, parse_cards, fix_cards, humanize_cards, assemble_final, save_draft, write_thread 등 13개 함수 + 4개 상수
- `tests/test_validator.py` — 14개 테스트
- `tests/test_crawler.py` — 4개 테스트
- `tests/test_orchestrator.py` — 10개 테스트
- `tests/test_pitch_evaluator.py` — 5개 테스트
- `tests/test_pitch.py` — 11개 테스트
- `tests/test_writer.py` — 13개 테스트

#### 수정 (Strangler Fig wrapper)
- `scripts/threads/v3/writer_v3.py` — 831→50라인 thin wrapper (모든 함수 pipeline.threads.*로 re-export)
- `scripts/threads/v3/narrative_pitcher.py` — 589→40라인 thin wrapper
- `scripts/threads/v3/pitch_evaluator.py` — 94→2라인 re-export wrapper

### 의사결정
- extraction sequence: validator(zero deps) → crawler(breaks cross-dep) → pitch+pitch_evaluator → writer(depends on validator+crawler)
- Strangler Fig: old files become thin re-export wrappers, all old import paths continue working
- 2 waves: W1=04-01+04-04 (independent), W2=04-02+04-03 (depend on 04-01)

### 검증
- 173/173 테스트 통과 (116 기존 + 57 신규)
- 기존 import 경로 및 __main__ 블록 정상 동작

### 미해결
- Phase 5: Dead Code Removal & Final Polish 대기

---

## 2026-06-29 — 형식 A 실험 / D 통일 / 하드코딩 템플릿 제거

### 변경 파일
- `scripts/threads/v3/writer_v3.py` — A/B/C 형식 함수 제거, 하드코딩 템플릿 4개 제거, build_system_prompt_D stanza 예시 정리
- `scripts/threads/v3/format_selector.py` — LLM 호출 제거, 항상 D 반환
- `scripts/threads/main_v3.py` — 한글+영어 붙어쓰기 검증 완화 (고유명사+조사 허용)
- `scripts/threads/prompts/`, `prompts_legacy/` — A/B/C 마크다운 파일 삭제
- `docs/TECH.md` — 신규 생성 (시스템 기술 문서)
- `CHANGES.md` — 신규 생성 (세션 변경 이력)
- `AGENTS.md` — 세션 시작/종료 규칙 추가

### 의사결정
- A 형식 실험 → GPT-4o-mini 한계로 D 통일
- 67개 금지 규칙 → 최소화 (모델 자유도 향상)
- 문서 분리: TECH.md(고정 참조) / CHANGES.md(변동 이력)

### 미해결
- GPT-4o-mini만 사용 중. 4o 전환 검토 필요
- 논쟁적 기사 선택 방식 미실험

---

## 2026-06-30 — Phase 2: Infrastructure & Portability (Strangler Fig)

### 변경 파일
#### 신규 생성
- `pipeline/infra/config.py` — project_root() 함수 (경로 계산)
- `pipeline/infra/models.py` — 5개 데이터클래스 (NewsArticle, BriefingItem, ThreadsPost, PipelineStepResult, PipelineRun)
- `pipeline/infra/retry.py` — @retry 데코레이터 (지수 백오프)
- `pipeline/infra/d1_client.py` — d1_query() (wrangler d1 execute 래퍼)

#### 수정
- `pipeline/infra/__init__.py` — 6개 모듈 re-export
- `pipeline/infra/logger.py` — PipelineLogger(Adapter), get_pipeline_logger(), log_step() 추가
- `scripts/*.py` (19개) — PROJECT_DIR 절대경로 → project_root() 교체
- `scripts/*.py` (9개) — load_env() 옆 EnvConfig() 추가 (Strangler Fig)
- `scripts/*.py` (3개) — d1_query() 옆 d1_client.d1_query 추가 (Strangler Fig)
- `scripts/*.py` (21개) — get_scrubbed_logger import 추가
- `tests/conftest.py` — d1_query 이중 목킹 (old + new path)
- `.planning/phases/02-infrastructure-portability/02-01-PLAN.md` — duration gap 보강

### 의사결정
- Strangler Fig 패턴: 기존 함수 유지 + 새 import 병행 (D-14)
- PipelineLogger: run_id/step_name + log_step() 컨텍스트 매니저로 duration 자동 측정
- 모든 변경사항 py_compile + pytest 통과

### 미해결
- `scripts/threads/validator.py`: 하드코딩 glob 경로 1개 (exempt, Phase 3)
- `scripts/test_crawl_sources.py`: 하드코딩 출력 경로 1개 (exempt, Phase 3)

---

## 2026-06-30 — D 형식 단일화 / 문서 체계 정립

### 변경 파일
- `scripts/threads/v3/writer_v3.py` — `build_system_prompt_A/B/C()` 함수 제거, FORMAT_BUILDERS/LABELS/COUNTS/TOLERANCE에서 A/B/C 삭제, write_thread user_prompt 분기 A/B/C 제거
- `scripts/threads/v3/format_selector.py` — SELECTOR_PROMPT 전제 + LLM 호출 제거, 항상 D 반환으로 단순화
- `scripts/threads/main_v3.py` — 한글+영어 붙어쓰기 검증 완화 (고유명사+조사 허용)
- `scripts/threads/prompts/` — A/B/C 마크다운 파일 삭제
- `scripts/threads/prompts_legacy/` — A/B/C 마크다운 파일 삭제
- `docs/TECH.md` — 신규 생성 (시스템 기술 문서)
- `CHANGES.md` — 신규 생성 (세션 변경 이력)
- `AGENTS.md` — 문서 성격 표 추가, 세션 시작/종료 절차 구체화

### 의사결정
- A/B/C 형식 완전 제거, D 단일 형식으로 통일
- 문서 3분화: TECH.md(고정) / CHANGES.md(변동) / AGENTS.md(규칙)
- "세션 끝" 명령어로 에이전트가 자동 정리하도록 프로토콜 확립

### 미해결
- GPT-4o-mini → GPT-4o 전환 검토
- 논쟁적 기사 선택 방식 미실험
- A 형식 실험 결과: 반응 저조 (GPT-4o-mini 한계)

---

## 2026-06-30 — 2-Pass Briefing Scoring System 구현

### 변경 파일
- `scripts/briefing_scorer.py` — 신규: 독립 평가 엔진 (light/full 모드, 7개 평가 항목)
- `config/impact_weights.json` — 신규: 평가 가중치 + 임계값
- `config/entity_tiers.json` — 신규: tier1 10개사, tier2 9개사
- `scripts/auto_news_selector.py` — 수정: cluster 라벨 부착, cascade scoring, 2-Pass 선택, mode 스위치, misc→source 회귀 fallback
- `scripts/auto_briefing.py` — 수정: INSERT 컬럼 추가, `_expand_misc_for_legacy` import
- `scripts/migrations/20260630_add_impact_score_columns.sql` — 신규: ALTER TABLE
- `tests/` — 신규: 103개 테스트 (conftest, fixtures, 3개 파일)
- `pytest.ini` — 신규: unit/integration 마커
- `docs/TECH.md` — 수정: Section 8 (Briefing Pipeline) 추가

### 발견/수정 버그
1. **`_two_pass_selection` 3개 반환**: misc cluster light_score < 20 skip 후 deficit 처리 안됨 → full_score fallback 추가
2. **`cluster_by_topic` 회귀**: source→misc 통합으로 round-robin 결과 불일치 (6/6 ID mismatch) → `_expand_misc_for_legacy()`로 출처별 확장

### 의사결정
- `BRIEFING_SCORER_MODE=dry_run` 기본값, shadow/live는 환경변수로 전환
- `live` 모드는 Week 4 PR에서 활성화 예정
- `scorer.py(threads)` import 금지 — 완전 독립 모듈 유지
- Top-N=20, 임계값=70 초기값, Week 2에 가중치 튜닝 별도 진행

### 미해결
- light_score 변별력 부족 (20/21 기사가 5점 동점)
- `live` 모드 미활성화
- 원문 사전 저장(D1 body 컬럼) 별도 PR 필요

---

## 2026-06-30 — Brevo IP 차단 문제 진단 및 해결

### 변경 파일
- 없음 (설정 변경, 코드 수정 불필요)

### 발견/수정 버그
1. **launchd 파이프라인 이메일 401 오류**: Brevo Authorized IPs에 `49.228.170.171` 미등록으로 API 차단
   - 수동 실행 시엔 동작했으나 launchd 환경에서 IP가 달라 실패
   - 해결: Brevo 대시보드 → Security → Authorized IPs → IP 제한 OFF

### 의사결정
- IP 동적 변경 문제 → IP 제한 해제로 해결 (자동 업데이트 코드 불필요)

### 미해결
- (기존과 동일)

---

## 2026-06-30 — Phase 3: Landing Zone & Orchestrator

### 변경 파일
#### 신규 생성
- `pipeline/orchestrator.py` — PipelineStep protocol + PipelineOrchestrator class
- `pipeline/__main__.py` — CLI entry point (`python -m pipeline {run|status}`)
- `pipeline/__init__.py` — Package re-exports
- `pipeline/migrations/20260630_create_pipeline_runs.sql` — D1 pipeline_runs schema
- `pipeline/steps/__init__.py` + `pipeline/steps/step_run_threads.py` — Strangler Fig step wrapper
- `pipeline/threads/__init__.py` — Empty package marker
- `scripts/threads/threads-publisher.plist.template` — string.Template 기반 plist
- `scripts/install_launchd.sh` — Plist 생성기 + launchd 설치
- `tests/test_characterization_validate_final_cards.py` — 8개 characterization 테스트
- `tests/test_characterization_pure_functions.py` — 5개 characterization 테스트

#### 수정
- `scripts/threads/main_v3.py` — `--daemon` 플래그 제거, `import schedule` 제거 (THR-01)
- `scripts/deploy.sh` — 한글 주석, `.env` 소싱 명확화
- `pipeline/__main__.py` — CR-01 수정: `StepRunThreads` 등록
- `pipeline/orchestrator.py` — WR-02 수정: SQL 모든 문자열 필드 이스케이프

### 의사결정
- PipelineOrchestrator: PipelineStep protocol + 단일 subprocess step wrapper (Strangler Fig)
- Plist: string.Template (stdlib) — Jinja2 불필요
- SCRIPT_PATH: `install_launchd.sh`가 생성한 plist는 `pipeline/__main__.py`를 진입점으로 지정
- Characterization tests: 13개 테스트, D1/네트워크 의존성 없음 (완전 격리)
- Threads 단일 스케줄러: launchd 전용 — `--daemon`/`schedule` 라이브러리 제거

### 검증
- 116개 테스트 통과 (103 기존 + 13 신규)
- 8/8 Success criteria VERIFIED
- Code review: CR-01(수정), WR-01~06(경고), IN-01~06(정보)

### 미해결
- `--once` 플래그가 `main_v3.py`에서 파싱만 하고 사용 안 함 (기능상 무해, WR-01)
- Phase 4 Monolith Splitting 대기

---

## 2026-07-05 — Phase 12: Writer Instability Fix (실행 완료)

### Wave 1: Per-card processing (12-01-PLAN)
- `humanize_cards()`: `--- join → LLM → --- split` → per-card loop (count 불변)
- `fix_cards()`: 동일한 per-card 재작성 — card count explosion 제거
- `validator.py`: Hook 250→350자 + content boundary safety check
- 커밋: `f10b8a4` · `43b4707` · `a322d43` · `e030662`

### Wave 2: Pipeline efficiency (12-02-PLAN)
- `writer.py`: 3-model parallel race (`ThreadPoolExecutor`, ~15초 → ~2분 개선)
- `writer.py`: write_thread single-pass (loop/fallback 제거)
- `main_v3.py`: write 실패 시 `failed_article_ids.add()` — 다른 기사로 retry
- `validator.py`: content boundary threshold 2→5 (format D merge 허용)
- 커밋: `39f9f72` · `84c62f9` · `c3b7bbc` · `1019b89`

### 검증
- 268/268 전체 테스트 통과
- 10시간 publish 장애 근본 원인 2중 교정:
  1. `--- join/split` 자체 제거 (원인) → per-card processing
  2. 3-model sequential fallback 누적 대기시간 (지연 원인) → parallel race

---

## 2026-07-05 — Phase 13: Card Separation Fix & Validation Hardening (완료)

### 의사결정
- `---` 구분자 강제 → `\n\n` 방식 유지 결정 (지난 세션에서 수많은 `---` 실패를 경험)
- `\n\n` split의 근본적 한계(문장 중간 절단, 중복 링크)는 `_repair_truncated_cards()` 강화로 보완
- 중국어 마침표 `。`(U+3002) 문제는 MiMo v2.5 중국어 모델 특성 → 검증/파싱 로직에 추가
- Phase 13의 3개 Plan으로 분할: 13-01(영구 실패 추적) / 13-02(빠른 수정) / 13-03(구조 개선)

### 13-01: Persistent Failed Article Tracking
- `scripts/threads/failed_articles.py` 신규 모듈 (load/save/is_failed/clear)
- `scripts/threads/main_v3.py` 에 통합 (indentation 버그 수정 포함)
- 커밋: (미커밋, 워킹 디렉토리)
- 영향: article 38290 영구 재시도 루프 차단
- 검증: 268개 기존 + 13개 신규 테스트 통과 = 281개

### 13-02: Validation Fixes (중국어 마침표 + 중복 링크)
- `pipeline/threads/validator.py` — `sentence_enders`에 `\u3002`(중국어 마침표) 추가
- `pipeline/threads/writer.py` — `_repair_truncated_cards()` enders에 `\u3002` 추가
- `pipeline/threads/writer.py` — `_remove_duplicate_links()` 신규 함수, `parse_cards()`에 통합
- 영향: MiMo v2.5 중국어 마침표 `。`로 인한 "문장 미완성" 검증 실패 해결
- 검증: 287/287 테스트 통과

### 13-03: Repair Logic Strengthening
- `pipeline/threads/writer.py` — `_repair_truncated_cards()` backward pass 추가 (마지막 카드 불완결 시 앞 카드에 병합)
- `tests/test_writer.py` — `TestRepairTruncatedCards` 클래스 신규 (6개 테스트)
- 영향: 카드 절단으로 인한 "너무 짧음" / "문장 미완성" 실패율 감소
- 검증: 287/287 전체 테스트 통과

### 발견 — 미해결
- **Hook 문장 종결 과다** (YouTube 기사 케이스): `\n\n` split이 너무 늦게 발생해 hook이 6개 문장 포함 → D 형식 구조적 한계, 별도 논의 필요
- **중복 링크**: `_remove_duplicate_links()` 적용으로 해결 (13-02)
- `writer.py`: `_repair_truncated_cards()` — `\n\n` fallback 후 문장 중간 split 병합
- `writer.py`: fix_cards 프롬프트 `--- 카드 시작/끝 ---` 템플릿 제거 → artifact 근절
- `writer.py`: 프롬프트 강화 — `---` 직전 완전한 문장 요구
- `writer.py`: humanize_cards/fix_cards 병렬화 (ThreadPoolExecutor, 144s→37s)
- 커밋: `8b2203e` · `1677eee` · `6148ada`

### 발견 — 미해결
- **기사 38290 무한 재시도 루프**: write_thread()가 항상 validation 실패 → save_posted() 미호출 → 영원히 기사풀에 남음
- `failed_article_ids`가 per-run 메모리 set이라 다음 launchd 실행 시 초기화
- 영구 실패 기사 추적(persistent failed_article_ids) 필요 — failed_crawls.json 패턴 참조

---

## 2026-07-06 — GPT-4o 사용 중단 + 런타임 아티팩트 정리

### 변경
- **GPT-4o → MiMo v2.5 교체** (월 ~$17.66 절감):
  - `outline_generator.py`: 기사 있음/없음 아웃라인 생성 2곳 → `model_router.chat_completion()` 전환
  - `thread_topic_finder.py`: 스레드 아웃라인 생성 1곳 → `model_router.chat_completion()` 전환
  - `blog_draft_generator.py`: 블로그 초안 생성 1곳 → `model_router.chat_completion()` 전환
  - `gpt-4o` 모델 문자열 executable code에서 완전 제거 확인
  - `gpt-4o-mini`는 model_router 3순위 fallback으로 유지 ($0.15/$0.60/M, 저비용)
- **런타임 아티팩트 git 추적 제거**:
  - `.gitignore` 추가: `pipeline/posted.json`, `config/pexels_used_ids.json`, `scripts/__pycache__/`, `scripts/threads/posted.json`, `scripts/threads/logs/`, `scripts/tools_collector.log`
  - `git rm --cached`로 추적 해제
- **쓰레드 발행 비활성화**: `kr.aikorea24.threads-publisher` launchd 에이전트 언로드

### 이전 세션 보강 (07:00~07:34 KST)
- 7/5 06:00 빌드 실패 (rc=127): `~/.env.common` 내 실행문 (`redis-cli`, `https://router...`) 주석 처리
- `run_pipeline.py`: frontmatter 검증 게이트 (step_deep_articles 후) + deploy 에러 메시지 정확화 + `/bin/bash` 경로
- `auto_deep_article.py`: `normalize_frontmatter()` 안전장치 (없는/잘린 frontmatter 자동 복구)
- `validate_blog_posts.py`: `validate_all()` 프로그래밍 사용 가능 노출
- `deploy.sh`: `.env` 소스 `set +e` 보호 + Python 바이너리 폴백
- `run_pipeline_with_notify.py`: Telegram 메시지 `html.escape()` + `<pre>` 태그

### 커밋
- `30666a6` fix(blog): frontmatter 정규화 + 검증 게이트 + 배포 안정화
- `f5820c8` fix(notify): 텔레그램 HTML 파싱 오류 방지
- `c3ec42f` fix(deploy): .env.common 내 실행문 무시
- `b3fdef5` chore: 런타임 아티팩트 git 추적 제거

---

## 2026-07-09 — Threads v2: Selection Logic + Writer Prompt (커밋 완료)

### Phase 17 (Threads v2 Phase 1): 기사 선택 로직 개선 — `39fe67c`
- `db_reader.py`: 시의성 7일→3일, `load_api_based_sources()`, `get_source_filter()`에 api_based 병합
- `pipeline/threads/pitch.py`: 1차 선별 "모순/역설/미해결 질문"으로 개편. but_line/question/gap_source 출력. 단일질문 규칙, 유형2(재구성) 대응, 중복 방지 but_line 유사도, pitch_history 저장
- `pipeline/threads/pitch_evaluator.py`: 6개 평가기준 0~9점/통과≥5, 역설 0점=불통과, 시의성 3일
- `main_v3.py`: api_based 한국어 모니터링 로그 (옵션 A)
- `crawlable_sources.json`: 지자체 전체 제거, count 수정
- D1 쿼리 확인: 네이버뉴스(4,571), 과기부 보도자료(171), 과기부 사업공고(50), 중소벤처기업부(29) 매칭 확인

### Phase 16 (Threads v2 Phase 2): Writer Prompt 개선 — `ef530e5`
- `writer.py` `build_system_prompt_D()`: 카드 구조 재정의 (훅→충돌→반전→확장→여운 → 통념→전환→증거A→증거B→열린질문→링크)
- `writer.py` `write_thread()`: 유저 프롬프트에 but_line/question/gap_source 전달, 카드별 규칙, gap_source 분기(explicit/reconstructed) 추가
- `style_examples.md`: 새 카드 구조 예시 추가 (SpaceX/Cursor 기반 템플릿)
- 5번 카드 닫힌 결론 금지 규칙 추가

---

---

## 2026-07-10 — Phase 17: 강좌 시스템 MVP-1 — 등록 흐름 (신규)

### 마일스톤
- v2.0 마일스톤 신규 생성
- Phase 17 정의: 강좌 시스템 MVP-1 등록 흐름

### 변경 파일
#### 신규
- `schema.sql` — courses, course_lessons, enrollments, lesson_clicks 테이블 + posts.visibility 컬럼
- `scripts/migrations/20260710_add_course_system.sql` — D1 마이그레이션 SQL
- `scripts/seed_course_7day_starter.py` — 7일 AI 입문 강좌 시드 데이터 생성기 (540줄)
- `src/pages/api/courses/enroll.ts` — 강좌 등록 API (신규/중복/오류 3종 응답)
- `src/pages/courses/7day-starter.astro` — 강좌 랜딩 페이지 (신청 폼 + 커리큘럼 + FAQ)

#### 수정
- `.planning/ROADMAP.md` — v2.0 마일스톤 + Phase 17 추가
- `.planning/STATE.md` — 현재 위치 Phase 17로 업데이트

### 의사결정
- **커뮤니티 게이트웨이 패턴**: 강좌 콘텐츠는 `posts`에 저장, 이메일은 티저 + 링크만
- **posts.visibility 3종**: public/members/premium (유료 전환 대비)
- **Brevo 유지**: Brevo 트랜잭셔널 API로 발송, 태그 체계로 세그먼테이션
- **MVP 분할**: 4개 (등록 → 게이트 → 발송 → 완강)
- **시작 정책**: 등록 후 첫 18:00에 1일차 발송
- **course_lessons.email_send_hour NULL = courses.default_send_hour 사용

### 검증
- Python seed script: syntax OK
- enroll.ts: 구조 정상 (import 1, export 있음)
- 랜딩 페이지: Astro 구조 정상
- 산출물 5개, 총 1,153줄

### 다음 스텝 (수동 실행 필요)
1. `npx wrangler d1 execute aikorea24-db --remote --file scripts/migrations/20260710_add_course_system.sql`
2. `python3 scripts/seed_course_7day_starter.py`
3. `npm run dev`로 랜딩 페이지 확인
4. 본인 계정으로 등록 테스트 → Brevo 태그 확인

---

## 2026-07-10 — Phase 20: 오케스트레이터 프레임 + 메타강의 + 중간 강좌 완료

### 의사결정
- **프레임 확정**: 오케스트레이터 — "코드를 쓰는 사람에서, AI를 지휘하는 사람으로"
- **타겟**: AI로 혼자 무언가를 만드는 사람 (개인사업자 + 직장인 부업러 + 프리랜서 + 1인 창작자)
- **로드맵**: "코드를 쓰는 사람에서, AI를 지휘하는 사람으로. 21일."
- **분기**: 선형 분기 (완강 → 다음 강좌 오픈), slug 브랜드 통일 안 함
- **slug**: `7day-starter` / `7day-infra` / `7day-agent`
- **메타강의 공개**: 실제 사이트 직접 링크 + 스크린샷 자리
- **중간·히어로 범위**: 축소 (기본기 중심, 80개는 비전으로)
- **진행 순서**: 메타강의 → 제로 운영 → 중간·히어로 순차
- **발송 cron**: 모든 콘텐츠 준비 후 마지막에 활성화

### 변경 파일
#### 신규
- `scripts/seed_course_7day_infra.py` — 0원 인프라 강좌 시드 데이터 생성기 (7개 레슨, day 8~14)

#### 수정
- `scripts/seed_course_7day_starter.py`:
  - day 0 메타강의 "오케스트레이터, 시작합니다" 추가
  - 과목명 변경: "첫 AI, 7일 — AI에게 말로 일을 시키는 첫 7일"
  - `--update` 모드 UPSERT 개선 (신규 lesson + courses UPDATE 지원)
  - 6개 검토 수정 반영 (히어로 주어, 1/2인칭, Vercel→CF, CTA, 스크린샷, 도구 분리)
- `.planning/STATE.md` — Phase 20 상태로 업데이트
- `.planning/ROADMAP.md` — Phase 20~22 신규 추가

### D1 상태
| 강좌 | slug | 레슨 | 상태 |
|------|------|------|------|
| 첫 AI, 7일 | 7day-starter | day 0~7 (8개) | ✅ 시드 완료 |
| 0원 인프라, 7일 | 7day-infra | day 8~14 (7개) | ✅ 시드 완료 |
| 무료 에이전트, 7일 | 7day-agent | day 15~21 (7개) | ⏳ 설계 대기 |

### 발송 상태
- `enroll.ts`, `send-daily.ts`, `lesson-email.ts`, `track.ts` — 코드 완료
- launchd plist **미설치** — 모든 콘텐츠 준비 후 마지막에 활성화 예정
- day 0 등록 즉시 발송 hook **미구현** — Phase 22에서 처리 예정

### 다음 스텝
1. 히어로 강좌(7day-agent) 설계
2. Phase 22 발송 시스템 활성화 (launchd plist + day 0 hook)
3. E2E 테스트 (등록→발송→완강)

## 2026-07-10 — Phase 18 체류 퍼널 재설계 + CSP 차단 해결 (3 deploy)

### 변경
- `src/pages/index.astro`: HeroSection/BriefingSection 순서 변경 (히어로 먼저)
- `src/components/home/HeroSection.astro`: CTA 3종 + 카피 개선 (강좌/브리핑/소개)
- `src/pages/blog/[...id].astro`: 본문 하단 CTA 3카드 (강좌/구독/용어) — 350+개 글 일괄 적용
- `src/pages/subscribe.astro`: 신규 구독 랜딩 페이지
- `src/layouts/Layout.astro`: "구독" 네비게이션 링크 추가
- `src/middleware.ts`: CSP 확장 — AdSense(pagead2), GTM(googletagmanager), CDN(jsdelivr), Cloudflare beacon, Google Analytics, DoubleClick, shields.io, Pretendard/Google Fonts 허용

### 의사결정
- CSP allowlist 방식: 필요한 도메인만 허용하여 보안 유지
- 블로그 CTA 3카드: 템플릿 1회 수정으로 전체 prerendered 글에 적용
- 히어로 CTA 3종: 두 타겟(입문자→강좌, 뉴스관심자→브리핑) 동시 공략

### 영향
- 방문자 첫 인상: 뉴스 브리핑 → AI 시작하기 히어로로 변경
- 블로그 이탈률 개선: 모든 글에서 CTA → 강좌/구독/용어
- AdSense/GTM 정상 로드 (CSP 차단 해결)
- 3회 빌드+배포 완료, commit `b7dd210`

---

## 2026-07-11 — Phase 17 xfade offset 버그 수정 + 텍스트 밀도 전환 (미커밋)

### 변경
- `pipeline/instagram/video_renderer.py`:
  - **xfade offset 버그 수정**: 4개 함수에서 `offset=cumulative_offset` → `offset=cumulative_offset - trans_dur` (전환이 0.5초씩 늦게 시작)
  - **`compute_xfade_offset()` 헬퍼 함수** 추가 — offset 계산 단일화
  - **`pick_transition_for_types()`** 추가 — 텍스트 밀도 기반 전환 선택
    - TEXT_HEAVY_TYPES(HOOK/CONFLICT/TWIST/EXPANSION): wipeleft/slideleft/circleopen
    - 저밀도(CTA/LINK/BRANDING/COVER): dissolve/fade
  - **crop filter 구분자 수정**: `crop={output_size}` → `crop={output_size.replace('x', ':')}` (FFmpeg는 `:` 필요)
- `pipeline/instagram/templates/tokens.css`: 신규 — 디자인 토큰 파일
- `pipeline/instagram/templates/carousel_slide.html`: tokens.css, grain, CTA button, EXPANSION label
- `pipeline/instagram/templates/reel_cover.html`: tokens.css, grain, font loading
- `pipeline/instagram/html_renderer.py`: _ensure_tokens_css(), viewport comma format
- `pipeline/instagram/config.py`: CTA caption + brand callout

### 의사결정
- xfade offset은 항상 `cumulative_duration - trans_dur`로 계산 (클립 종료 시점에서 전환 시간 차감)
- dissolve는 텍스트 빽빽한 슬라이드에 부적합 → text-heavy 타입은 wipe/slide 전환
- `build_xfade_filter()` 호출 미사용 코드 제거 (dead code)
- Ken Burns ease-in-out 커브 도입 (sin² 기반)

### 렌더링 테스트
- `tmp_test/carousel_test_hook.mp4` — 8.0s, 1080×1350, H.264, 30fps, 2.4MB
- 전환 오프셋 검증 완료 (xfade at 2.5s / 5.0s, 정상)
- 키 프레임 5장 추출 완료

### 상태
- 🔴 사용자 피드백 대기 중 (영상 확인)
- 미커밋 — git status 확인 필요
