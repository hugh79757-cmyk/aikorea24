# Phase 2: Infrastructure & Portability — Context

**Gathered:** 2026-06-30
**Status:** Ready for planning

<domain>
## Phase Boundary

Create all remaining shared infrastructure modules in `pipeline/infra/` and wire all 20+ existing Python scripts to use them. Eliminate duplicated utility code (`load_env()`, `d1_query()`, `send_telegram()`), hardcoded `PROJECT_DIR` paths, and scattered `print()`-based logging.

Deliverables: `config.py` (project_root), `d1_client.py` (D1 wrapper), `models.py` (typed dataclasses), `retry.py` (retry decorator), plus wiring all old files to `pipeline.infra.*` modules. No code behavior changes — infrastructure consolidation only.
</domain>

<decisions>
## Implementation Decisions

### config.py — 경로 관리 (INF-01)
- **D-01:** `project_root()` 함수만 생성. 클래스나 ProjectPaths 객체는 불필요. `Path(__file__).resolve().parent.parent.parent` 로 프로젝트 루트 계산.

### d1_client.py — DB 래퍼 (INF-03)
- **D-02:** `d1_query(sql: str, params: Optional[dict] = None, retries: int = 2)` 함수 형태. 클래스 불필요. `wrangler d1 execute --remote` 호출을 표준화.
- **D-03:** 기존 3가지 버전(`auto_news_selector.py`, `threads/db_reader.py`, `threads/backfill_meta.py`)의 차이점을 통합: 일관된 타임아웃(60초), 재시도 동작, 결과 파싱.

### retry.py — 재시도 로직 (INF-06)
- **D-04:** `@retry(max_retries=3, delay=1.0, backoff=2.0)` 범용 데코레이터. API 호출과 DB 쿼리 모두 동일한 데코레이터 사용, `max_retries` 파라미터로 조절.

### models.py — 데이터 타입 (INF-05)
- **D-05:** 파이프라인 전반의 모든 데이터 타입을 한번에 정의: `NewsArticle`, `BriefingItem`, `ThreadsPost`, `PipelineStepResult`, `PipelineRun` 등.

### Wiring 전략 (POR-01, INF-02, INF-04)
- **D-06:** 일괄 wiring — 하나의 plan에서 20개 스크립트 모두 교체. Strangler Fig 방식으로 기존 함수는 그대로 두고 새 `from pipeline.infra.*` import 만 추가.
- **D-07:** env_loader.py (Phase 1) 를 모든 스크립트가 사용하게 wiring. 기존 `load_env()` 호출을 `EnvConfig()` 로 대체.
- **D-08:** logger.py (Phase 1) 를 모든 스크립트가 사용하게 wiring. 기존 `print()` 를 구조화 로깅으로 대체.

### 구조화 로깅 (OBS-01)
- **D-09:** run_id, step_name, duration 필드를 로그 레코드에 포함. 기존 `get_scrubbed_logger()` 를 확장하여 structured context 지원.
- **D-10:** PipelineLogger 클래스 또는 logging.LoggerAdapter 확장으로 구현. 파이프라인 실행 ID를 컨텍스트에 전달.

### 설계 원칙
- **D-11:** 복잡도가 낮아지는 방향으로 설계. 같은 기능이면 더 적은 코드로.
- **D-12:** Python 3.14 stdlib only — no third-party dependencies.
- **D-13:** 한국어 주석.
- **D-14:** Strangler Fig — 기존 파일은 그대로 동작, 새 모듈은 점진적으로 적용.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### 새로 생성할 모듈
- `pipeline/infra/config.py` — 생성 예정: `project_root()` 함수
- `pipeline/infra/d1_client.py` — 생성 예정: `d1_query()` 함수
- `pipeline/infra/models.py` — 생성 예정: 데이터 타입 정의
- `pipeline/infra/retry.py` — 생성 예정: `@retry` 데코레이터

### Phase 1에서 이미 생성된 모듈 (wiring 대상)
- `pipeline/infra/env_loader.py` — `EnvConfig` 클래스 (.env → ~/.env.common)
- `pipeline/infra/logger.py` — `ScrubRegistry`, `get_scrubbed_logger()`, `scrub_print()`

### 주요 중복 함수 현황 (wiring 대상)
- `scripts/auto_news_selector.py` — 자체 `d1_query()`, `PROJECT_DIR` 하드코딩
- `scripts/threads/db_reader.py` — 자체 `d1_query()`, `load_posted()`, `PROJECT_DIR` 하드코딩
- `scripts/threads/backfill_meta.py` — 자체 `d1_query()`
- `scripts/threads/v3/model_router.py` — 자체 `load_env()`
- `scripts/threads/main_v3.py` — 자체 `load_env()`, `send_telegram()`
- `scripts/threads/publisher.py` — 자체 `load_env()`, `load_posted()`
- `scripts/keyword_updater.py` — 자체 `load_env()`, `send_telegram()`
- `scripts/blog_draft_generator.py` — 자체 `load_env()`, `send_telegram()`
- `scripts/tools_collector.py` — 자체 `load_env()`, `send_telegram()`
- `scripts/dynamic_seed_generator.py` — 자체 `load_env()`, `send_telegram()`
- `scripts/run_pipeline_with_notify.py` — 자체 `load_env()`, `send_telegram()`
- `scripts/thread_topics/outline_generator.py` — 자체 `load_env()`, `send_telegram()`
- `scripts/thread_topics/thread_topic_finder.py` — 자체 `load_env()`, `send_telegram()`
- `scripts/auto_email_sender.py` — 자체 `load_env()`
- `scripts/threads/token_refresh.py` — 자체 `load_env()`

### 요구사항 참조
- `.planning/REQUIREMENTS.md` §INF-01, INF-03, INF-05, INF-06, POR-01, OBS-01
- `.planning/ROADMAP.md` §Phase 2 — Infrastructure & Portability

### 프로젝트 문서
- `.planning/PROJECT.md` — 프로젝트 컨텍스트 및 결정 이력
- `.planning/STATE.md` — 현재 상태 및 세션 정보

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `pipeline/infra/env_loader.py` (Phase 1) — `EnvConfig` class. Ready for use by all scripts.
- `pipeline/infra/logger.py` (Phase 1) — `ScrubRegistry`, `get_scrubbed_logger()`, `scrub_print()`.

### Established Patterns
- **Strangler Fig migration** — 새 모듈을 추가하고 기존 코드는 점진적으로 교체. Phase 1에서 확립.
- **`project_root` 패턴** — 일부 스크립트(`generate_thumbnails.py`, `auto_thumbnail.py`, `auto_deep_article.py`, `test_email_send.py`)는 이미 `Path(__file__).parent.parent` 로 상대 경로 사용. 이 패턴을 표준화.
- **`@retry` 데코레이터 패턴** — `auto_news_selector.py`의 `d1_query` 가 내부적으로 재시도 루프 구현. 공통 데코레이터로 추출 필요.

### Integration Points
- **config.py → 모든 스크립트** — 29곳의 하드코딩된 `PROJECT_DIR` 을 한 번에 교체
- **d1_client.py → auto_news_selector.py, db_reader.py, backfill_meta.py** — 3개 d1_query 구현체 통합
- **env_loader.py → 16개 load_env() 구현체** — 각 스크립트의 자체 load_env() 를 EnvConfig 로 교체
- **logger.py + OBS-01 → 모든 스크립트** — print() 로깅을 구조화 로깅으로 교체

</code_context>

<specifics>
No specific requirements — open to standard approaches. User specified 설계 기준: "복잡도가 낮아지는 방향. 같은 기능이면 더 적은 코드로."
</specifics>

<deferred>
None — discussion stayed within phase scope.
</deferred>

---

*Phase: 02-Infrastructure & Portability*
*Context gathered: 2026-06-30*
