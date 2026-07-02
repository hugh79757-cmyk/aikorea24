# CHANGES.md — 세션 간 변경 이력

> 기술 문서는 `docs/TECH.md` 참조.
> 세션 종료 시 에이전트가 자동 append.

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
