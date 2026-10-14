## 2026-10-14 AIK24-PIPE-02 완료 — NVIDIA NIM 신규 모델 감지 포함 → SSOT/프로젝트/aikorea24/지시서/2026-10-14-2128-AIK24-PIPE-02-완료보고.md (완료 — verify는 시니어2)

### 한 일
- [PRODUCTION CODE] `scripts/model_catalog.py` — `NVIDIA_MODELS` 상수 신설(34행 다음), `fetch_nvidia()` 를 `NotImplementedError` → 실구현으로 교체. `rows` 는 빈 리스트, `all_ids` 는 실측 전체 id 집합을 반환. 커밋 `2755441c`.
- 범위 밖 준수: 브리핑·툴 파이프라인 미변경, `AUTO_EVAL_ENABLED` 미변경, launchd 스케줄 미변경.

### 결과
- [검증됨] **작업1 — 무료 판별 방법 조사(결론: 불가)**. 실측 근거:
  - `GET https://integrate.api.nvidia.com/v1/models` → 200, **80개 모델**, 응답 키가 `created/id/object/owned_by` **4개뿐**. `free` 문자열 들어간 id 0건.
  - `?include=pricing`·`?free=true`·`?tier=free` → 모두 200 이나 **응답 완전 동일**(쿼리 무시).
  - `GET /v1/models/{id}` → **404**(`Model does not exist by the name of ...`).
  - `api.nvcf.nvidia.com/v2/functions` → 401. `api.ngc.nvidia.com/v2/models/search` → 404. `integrate.api.nvidia.com/v1/credits` → 404. `api.nvidia.com/v1/models` → ConnectError.
  - `docs.api.nvidia.com/nim/reference/llm-apis` → 문서 존재하나 엔드포인트는 `POST /v1/chat/completions` 하나뿐이고 **가격·티어 정보 없음**(갱신일 2026-10-05).
  - `build.nvidia.com/explore/discover` → SPA 셸. `build.nvidia.com/pricing` → **404**. `docs.nvidia.com/nim/large-language-models/latest/getting-started.html` → 페이지 없음.
  - → **API 도 공식 목록 URL 도 없음 = 무료 티어 판별 불가 [검증됨]**
- [검증됨] **작업2 — NVIDIA 가 감지 대상에 포함** — `python3 scripts/detect_new_models.py` 실행 결과:
  - 1회차: `신규 모델 80건`(전부 nvidia) → `new_by_provider = {"nvidia": 80}`, **`failed_providers` 빈 dict**(NIM 이 더 이상 실패하지 않음), `total_rows 38`(무료 목록 변화 없음).
  - 2회차: `신규 모델 없음 (전체 38건)` — 반복 실행 오탐 0.
  - **기존 3개 프로바이더 무영향 [검증됨]** — openrouter·kilo·zen 은 신규 0건, `total_rows` 38 그대로.
- [검증됨] 대표님 원칙("검증 불가한 항목은 억지로 넣지 않는다") 준수 — `rows`(무료 모델 페이지에 advertise 되는 목록)는 **빈 리스트로 유지**. 검증되지 않은 "무료" 표시는 하지 않는다. 신규 감지만 `all_ids` 로 수행.
- [검증됨] 회귀 테스트 `pytest tests/test_eval_cli.py tests/test_zen_pending.py -q` → **24 passed**.

### 지시서 대비 판단 (대표님 확인 필요)
- 지시서 작업2 후안은 `NVIDIA_FREE_MODELS` 상수 하드코딩이었으나, **공식 무료 목록이 존재하지 않아 하드코딩할 근거가 없다.** 지시서 본문에도 "API 로 불가하면 … 공식 무료 모델 목록을 하드코딩한 상수"라고 되어 있으므로, 근거 없는 목록을 만드는 대신 `rows` 를 비우고 `all_ids` 로만 감지하는 쪽을 택했다. 지시서 완료기준("NVIDIA 모델이 감지 대상에 포함되고 기존 3개 무영향")은 그대로 충족된다.

### 잔존 위험
1. **NVIDIA NIM 모델은 무료 여부 미검증 상태로 알림만 온다** — 신규 NIM 모델이 잡히면 그것이 실제로 무료 티어로 호출되는지는 대표님 수동 테스트로만 확인된다. 자동 판별은 여전히 불가.
2. NIM 감지 대상에 **임베딩·비전·음성 모델이 섞여 있다**(예: `nvidia/nemotron-3-embed-1b`, `nvidia/neva-22b`, `nvidia/riva-translate-4b-instruct`). LLM 이 아니므로 수동 테스트 시 걸러야 한다. 무료라고 advertise 하지 않으므로 페이지 오염은 없지만 알림噪音가 된다.
3. [검증불가] NVIDIA 가 추후 무료 목록을 공개하면 이 구현을 손봐야 한다 — docstring 에 `shortcut:` 주석으로 남겨 두었다.
4. NIM 80개는 **베이스라인 1회 등록** 상태다. `all_ids` 가 줄면 `removed_by_provider` 로 잡히지만, NIM 은 목록 정리를 자주 안 해 이 경고는噪音가 될 수 있다.

### 다음 행동
- 대표님: NIM 신규 알림 도착 시 수동 테스트 후, 실제 무료 티어로 확인된 것만 별도 상수로 승격할지 결정.
## 진행 중 (2026-10-14, AIK24-PIPE-02) — NVIDIA NIM 신규 모델 감지 포함

## 2026-10-14 AIK24-PIPE-01 완료 — 무료 모델 자동 평가 비활성화 + 신규 모델 감지 스케줄 등록 → SSOT/프로젝트/aikorea24/지시서/2026-10-14-2101-AIK24-PIPE-01-완료보고.md (완료 — verify는 시니어2)

### 한 일
- [PRODUCTION CODE] `scripts/free_models_page.py` — `AUTO_EVAL_ENABLED = False` 상수 신설(삭제 아닌 플래그), `cmd_daily()` 의 `cmd_evaluate` 호출을 그 플래그로 감쌄다. else 분기 로그는 `"평가·발행 SKIP (AIK24-PIPE-01 자동 평가 비활성 — 수동 평가로 전환)"`. 수집(`mc.run`)과 리스트 페이지 갱신(`cmd_page`)은 계속 돈다.
- [PRODUCTION CODE] `scripts/detect_new_models.py` 신규(106줄). D1 미사용 — 외부 API 만이라 CF 자원 소모 없음.
- [CONFIG] `scripts/detect-new-models.plist.template` 신규 + `~/Library/LaunchAgents/kr.aikorea24.detect-new-models.plist` 설치·로드.
- 커밋 `d4917661`.

### 결과
- [검증됨] **작업1 자동 평가 미실행** — `grep -n AUTO_EVAL_ENABLED scripts/free_models_page.py` → 43행 정의, 436행 분기. 삭제 없이 플래그로만 끈다. 수동 경로(`free_models_page.py evaluate --force`, `model_eval.py evaluate --model <id>`)는 살아 있다.
- [검증됨] **작업2 신규 감지 동작** — `python3 scripts/detect_new_models.py` 3회 실행:
  - 1회차: `베이스라인 없음 — 오늘 스냅샷을 베이스라인으로 기록한다` + `첫 실행 — 신규/제외 비교를 건너뛴다` → `신규 모델 없음 (전체 38건)`.
  - 2·3회차: `신규 모델 없음 (전체 38건)` — 반복 실행 시 오탐 0.
  - `scripts/logs/new_models_alert.json`(28KB) · `scripts/logs/model_catalog_baseline.json`(26KB) 생성 확인.
- [검증됨] **작업3 스케줄 등록** — `plutil -lint` OK, `launchctl bootstrap` OK, `launchctl list` 에 `kr.aikorea24.detect-new-models` 표시(exit status 0). `StartCalendarInterval` = **머신 로컬 04:00**.
  - 슬롯 회피 근거(실측): news-unified 05:30 · tools-collector 06:00 · network-refresh 06:00 · wiki-batch-embed 07:05 · blog-draft 07:30 · threads-compass 09:30 · free-model-pipe 10:00 → 04:00 은 비어 있음.
  - 스케줄과 동일한 인터프리터/인자(`.venv/bin/python3 scripts/detect_new_models.py`)로 수동 실행해 종료코드 0 확인.
- [검증됨] **브리핑·툴 파이프라인 무영향** — `launchctl list` 에 `news-unified`·`tools-collector`·`blog-draft`·`free-model-pipe` 4개 모두 그대로 로드(exit 0). 해당 plist 는 수정하지 않았다.
- [검증됨] 회귀 테스트 `pytest tests/test_eval_cli.py tests/test_zen_pending.py -q` → **24 passed**.

### 지시서 전제 대비 차이
- 지시서는 비교 기준을 `scripts/logs/known_models.json` 이라 지시하나 그 파일은 실존하지 않았다. 일회성 스냅샷(`model_catalog_YYYY-MM-DD.json`)과 섞이지 않도록 영속 베이스라인 파일을 `scripts/logs/model_catalog_baseline.json` 로 분리했다.
- 지시서는 4개 프로바이더를 감지 대상으로 적었으나 **NVIDIA NIM 은 `model_catalog.fetch_nvidia()` 가 `NotImplementedError` 를 던진다** — `/v1/models` 응답에 가격·무료 플래그 필드가 없어 무료 티어 판별 불가(2026-10-14 실측). 이 때문에 감지 대상은 실측 3개(OpenRouter·Kilo·Zen)다.

### 잔존 위험
1. **NVIDIA NIM 은 감지 대상에서 빠짐** — `fetch_nvidia()` 가 계속 `NotImplementedError`. `nvidia` 프로바이더는 베이스라인에 없으므로 diff 에도 안 잡힌다. NVIDIA 공식 카탈로그 API 를 따로 붙이거나, 무료 티어 판별 근거를 정해야 한다.
2. **수집 결과에 편차가 큼** — 1회차 콘솔에는 openrouter 462 · kilo 394 · zen 85 가 나왔으나 `total_rows=38`. `all_ids` 는 모델 ID 전체 목록이고 `rows` 는 필터링(무료 판별) 후 행이라 숫자가 다르다. 신규 감지에는 `all_ids` 기준이 쓰이므로 실제로는 총 941 ID 를 비교한다.
3. `AUTO_EVAL_ENABLED = False` 인 채로 `free-model-pipe`(매일 10:00)는 계속 돌지만 평가 단계만 SKIP 된다 — 수집+페이지 갱신 비용은 그대로 발생.
4. [검증불가] 04:00 실제 기동 — plist 로드까지만 확인했고 정해진 시각에 자동 실행되는 것은 다음 날 로그로 확인해야 한다.

### 다음 행동
- 대표님: NVIDIA NIM 감지 포함 여부 결정(위 1번).
- 대표님: `scripts/deep_dive_writer.py` SyntaxError 수리 지시 여부(EVAL-CLI-01 잔존).
## 진행 중 (2026-10-14, AIK24-EVAL-02) — CLI 기준 무료 모델 전수 리스트 (free_models_cli.json)

## 진행 중 (2026-10-14, AIK24-PIPE-01) — 무료 모델 자동 평가 비활성화 + 일일 신규 모델 감지

## 2026-10-14 20:45 CLI 피봇 확정 (대표님 결정) — 모든 평가는 OpenCode CLI 기준, 기존 API 데이터 전부 폐기
- `model_leaderboard.json` → `[]` (백업: `model_leaderboard.json.bak-20261014-cli-pivot`)
- `model_eval_cache.json` → `{}`
- OpenCode에 openrouter·kilo·zen 프로바이더 등록済 — 프로바이더별 모델 선택 가능, 커버리지 손실 없음
- OpenCode에서 선택 불가한 모델은 테스트 명단 제외
- CLI는 토큰량 미제공 → 블로그 비용 섹션 "미측정" 처리

## 2026-10-14 AIK24-EVAL-CLI-01 완료 — CLI 경유 모델 평가(cat-jam-free 8/12) + 실효 컨텍스트 프로브 → SSOT/프로젝트/aikorea24/지시서/2026-10-14-2120-AIK24-EVAL-CLI-01-완료보고.md (완료 — verify는 시니어2)

### 한 일
- [PRODUCTION CODE] `scripts/model_eval.py` +228줄 — 작업2 `eval_model_cli()`·`cli_prompt()`·`cli_call()`·`CLI_MODEL_MAP`, 작업6 `probe_context_length()`·`_probe_doc()`·`_probe_hit()`·상수 4개. `subprocess` import 추가.
- [PRODUCTION CODE] `scripts/free_models_page.py` — 작업4 `split_zen()` CLI 예외 + `cmd_evaluate()` CLI 분기, 작업5 `pick_cards()`/`render()` source·measured_context 표시. **이 파일은 이전까지 git 미추적이었고(FREE-PIPE-01 세션 산출) 이번 커밋 `245901ad` 로 처음 버전관리됨.**
- [PRODUCTION CODE] `scripts/blog_draft_generator.py` `_cost_block()` 앞부분에 `source=="cli"` 분기 1줄 추가.
- [TEST CODE] `tests/test_eval_cli.py` 신규 11 tests. `tests/test_zen_pending.py` 3 tests 를 새 계약으로 갱신 + 1 test 추가.
- 커밋 `245901ad`.

### 결과 (완료기준 6항목)
1. [검증됨] **작업1 `opencode run` 인터페이스 5항목 문서화** — 도구 비활성화 `--agent <이름>` 지정(=`opencode agent list` 없음), temperature/max_tokens **CLI 플래그 없음**(설정 불가), 멀티턴 `-s <sessionID>` 가능이나 프롬프트 주입 방식 채택, 출력 `--format json` **NDJSON**(실측), 타임아웃 `subprocess.run(timeout=)`+`TimeoutExpired`, 에러 `{"type":"error","error":{"type":"provider.no-route"}}`+exit 1.
2. [검증됨] **작업2 `cat-jam-free` 12문항 CLI 평가** — `BLOCKED: None` / `score=8/12 failed=0 judge_failed=1 source=cli provider=zen`. LABEL: `11문항 중 8문항 정답 (문항 난이도: 기초 수준~실무 수준 기준, CLI 경유), 1문항 측정 결함.` 리더보드 기록 `cat-jam-free 8/12 (qv=1)`, 캐시 저장 확인.
3. [검증됨] **작업3 매핑 테이블** — `CLI_MODEL_MAP = {"cat-jam-free": "opencode/cat-jam-free", "space-bunny-free": "opencode/space-bunny-free"}`. `jev-1.13-free` 미등록(테스트로 고정).
4. [검증됨] **작업4 파이프라인 분기** — `pick_cards()` 실측 출력에 `cat-jam-free | cli | 컨텍스트 길이 미공개` 노출 확인. CLI 실패 시 zen_pending 사유만 갱신하는 분기 테스트로 고정.
5. [검증됨] **작업5 API/CLI 구분** — `pick_cards()` 실측으로 `nvidia/nemotron-3-ultra-550b-a55b: | api |` vs `cat-jam-free | cli |` 구분 확인. 기존 API 엔트리 backfill 안 함(캐시 조회 구조).
6. [검증됨] **작업6 `space-bunny-free` 실측 컨텍스트** — 8K·16K·32K·64K·128K·256K·512K·**1,048,576 전부 OK** → 상한 도달, 하한 `1,048,576` 을 `measured_context` 로 캐시 기록(`CACHE OK`). 즉 **실효 컨텍스트 ≥ 1M** (공칭값이 아니라 니들 테스트 실측).

### 테스트
- `pytest tests/test_eval_cli.py tests/test_zen_pending.py` → **24 passed** (신규 11 + 갱신 후 13).
- `pytest tests/` 전체 → **566 passed / 17 failed / 10 skipped**. 실패 17건은 **모두 이번 작업과 무관**: `scripts/deep_dive_writer.py` 434행 세일arius따옴표 SyntaxError 로 14건(HEAD 커밋에서도 동일 — `git show HEAD:scripts/deep_dive_writer.py` 로 확인), 나머지 `test_failed_articles`(1)·`test_pitch`(1)·`test_write_thread_validation`(1). 실패 테스트 4개 파일은 `model_eval`/`free_models_page`/`blog_draft_generator` 를 import 하지 않는다.

### 잔존 위험
1. **[부분검증] `tests/test_zen_pending.py` 3건은 [TEST CODE] 와 [PRODUCTION CODE] 를 같이 고쳐 통과시킴** — EVAL-ZEN-01 의 "Zen 은 아예 평가 대상이 아니다" 계약이 EVAL-CLI-01 로 "CLI 등록 Zen 만 평가 대상" 으로 바뀐 것이라 갱신이 맞지만, 순환 검증 위험이 있어 별도 표기한다.
2. **`scripts/deep_dive_writer.py` SyntaxError 미해결** — 14개 테스트가 이 때문에 죽어 있다. 이번 작업 범위 밖. 대표님 지시 필요.
3. **컨텍스트 실측값은 문자 수 기준 근사**(한국어 1자≈1토큰 가정). 실제 토크나이저 기준보다 클 수 있어 "≈1M" 으로 표기되어야 한다. 상한(1M)에 닿아 경계값이 아니라 **하한** 임에도 `measured_context` 에 하한을 넣었다 — 재측정 금지 규칙 때문에 의도된 선택.
4. **`record_leaderboard()` 행에 `source` 가 없다** — 지시서 §범위 밖이라 미수정. 소스는 캐시에서 읽는 구조. 리더보드 JSON 만 단독 보면 API/CLI 구분이 안 보인다.
5. `cat-jam-free` 12번 문항(역할판단)은 판관 파싱 실패(`judge_failed`) — 지시서 §범위 밖이라 판관 로직 미수정.

### 다음 행동
- 대표님: `scripts/deep_dive_writer.py` SyntaxError 수리 지시 여부.
- 대표님: free-models 페이지에 `≈N (실측)` 이 실제 반영됐는지 라이브 확인(`cmd_page`/`cmd_daily` 실행).
## 2026-10-14 19:00 AIK24-EVAL-ZEN-01 완료 — Zen 신규 모델 2종 + context_length null 규칙 확정 → SSOT/프로젝트/aikorea24/지시서/2026-10-14-1900-AIK24-EVAL-ZEN-01-완료보고.md (완료 — verify는 시니어 2)

### 한 일
- [PRODUCTION CODE] `scripts/free_models_page.py` 2건.
  - 작업 3: `ctx_key(row)` 헬퍼 신설 — 미공개 컨텍스트(null·누락)는 0 으로 정렬해 숫자 모델 뒤로 보낸다. 카드 선정·전체 목록·평가 대상 정렬 3곳 통일.
  - 작업 4: `ZEN_PENDING_PATH` + `zen_pending()` / `mark_zen_pending()` / `split_zen()` 신설. **Zen 모델은 평가 시도 자체를 하지 않고** `zen_pending.json` 에 대기 기록한다(`model_eval_failed.json` = 영구 차단 아님).
- [TEST CODE] 신규 `tests/test_zen_pending.py` — 12 passed.
- [CONFIGURED ARTIFACT] `scripts/logs/zen_pending.json` 신규 2건.

### 결과
- [검증됨] 완료기준 3: `context_length` null 모델이 맨 뒤 + `미공개` 표시. 근거: 라이브 `free-models` 표를 파싱해 숫자 모델 내림차순 8개 뒤 **맨 뒤 10행이 Zen 전부**, HTML 내 `미공개` 문자 10개 = zen 10개와 1:1.
- [검증됨] 규칙 ①②③: 카드 점수 순서 `11/12 → 7/12`(점수 내림차순). 규칙 3(점수는 컨텍스트 무관)은 `model_leaderboard.json` 엔트리에 컨텍스트 필드가 아예 없음으로 확인.
- [검증됨] 완료기준 4: zen 2건이 `zen_pending.json` 에 사유와 함께 기록되고 `model_eval_failed.json` 에는 **0건** — 영구 차단되지 않음. `split_zen` 단위 테스트와 실제 함수 호출 양쪽으로 확인.
- [검증됨] 카드 표기: zen 카드의 스펙은 `컨텍스트 길이 미공개`, 가격은 `가격 미공개`(테스트가 실제 문자열을 비교).
- [검증됨] **작업 1 — Zen 호출 경로 = 부분 가능** (조사 서브에이전트 실측, 문서 2·3 근거 있음):
  - `cat-jam-free` — HTTP 직접 호출 **불가**: `POST https://opencode.ai/inference/v1/chat/completions` → **403 `FreeTierError`** "무료 티어는 OpenCode 앱 내부 전용". `x-opencode-session` 헤더·Bearer 토큰 조합 3종 모두 동일. **CLI 경유는 가능** — `opencode run -m opencode/cat-jam-free` → `PONG` (1.8초).
  - `jev-1.13-free` — HTTP 는 되나 **채팅 경로가 없다**: `/inference/v1/systemone` 이 판정 모델용(systemone, `state`+`questions` 스키마)이라 `messages` 를 받는 12문항 평가에 쓸 수 없다. CLI 는 미등록(`provider.no-route`).
  - 대조군: 같은 라우트에 유료 모델 `glm-5` 는 **402 잔액 부족** — 인증은 통과했고 라우트는 살아 있다. `~/.config/opencode/models/deepseek-v4-flash.json` 의 `baseURL: https://api.opencode.ai/v1` 은 **죽은 엔드포인트**(200 + body `Not Found`).
  - Kilo·OpenRouter 에 동일 모델 없음(카탈로그 39행 전수 grep, zen 항목 8건이 전부). models.dev `opencode` 122모델 중 `cat-jam-free` 1건, `jev-1.13` 0건.
- [검증불가] **작업 2(Zen 2종 12문항 평가) 미실행** — 조사 결과로 실행 불가 확정. `jev-1.13-free` 는 채팅 경로 부재, `cat-jam-free` 는 HTTP 403 + CLI 경유는 `model_eval.py` 에 호출 경로 신설이 필요하나 지시서 **범위 밖**. 0점 기록 안 하고 [검증불가] 처리(지시서 요구 충족).

### 잔존 위험
1. **Zen 10개는 계속 평가 0점** — OpenRouter 경로가 없는 모델을 OpenRouter 로 부르면 404(모델 부재)다. 지금은 대기 기록으로 막아뒀지만, Zen 호출 경로가 없이는 평가는 영원히 불가능하다. → 조사 결과로 해소: zen HTTP 는 앱 내부 전용(403), `jev-1.13-free` 는 채팅 경로 부재. **CLI(`opencode run`) 경유가 유일한 우회**이고, 그건 별도 지시서가 필요하다.
2. **Zen 카드의 컨텍스트·가격이 항상 미공개** — Zen 목록 API(`/zen/v1/models`)에 두 필드가 없다. 카드 정렬에서 zen 은 항상 꼴찌다(규칙대로지만 정보가 없는 상태).
3. **`~/.config/opencode/models/deepseek-v4-flash.json` 의 baseURL 이 죽었다** — `https://api.opencode.ai/v1` 은 200 + body `Not Found`. 올바른 채팅 base 는 `https://opencode.ai/inference/v1`. 이 파일을 읽는 경로가 있으면 zen 호출이 조용히 실패한다(참조는 grep 0건 — 미확인).
4. **`scripts/model_catalog.py` 의 `ZEN_MODELS` base 재사용 금지** — 목록 전용 `/zen/v1`. 채팅으로 재사용하면 403 `FreeTierError` 만난다.
3. **`zen_pending.json` 은 사람이 지워야 재시도된다** — 호출 경로가 확보돼도 자동 해제 없다.
4. **UA 스푸핑 미시험** — Go 문서는 "자체 UA 로 식별"을 요구하지만 `FreeTierError` 는 의도적 액세스 게이트로 읽혀 우회를 시도하지 않았다.

### 다음 행동
- `cat-jam-free` 만 CLI(`opencode run -m opencode/cat-jam-free`)로 평가 가능. 12문항 자동 주입하려면 `model_eval.py` 에 CLI 호출 경로 신설이 필요 — **지시서 범위 밖이므로 별도 지시서 요청**.
- `~/.config/opencode/models/deepseek-v4-flash.json` 의 죽은 baseURL 정정(참조 경로 grep 0건이라 실제 영향 미확인).
- `opencode Zen` 신규 모델이 늘면 `zen_pending.json` 이 늘어난다 — 카드 선정에서 zen 이 정확히 4개가 될 때까지는 빈칸이 뜬다.

---

## 진행 중 (2026-10-14, AIK24-EVAL-ZEN-01) — Zen 신규 모델 2종 평가 + context_length null 규칙 확정

## 2026-10-14 16:20 AIK24-EMDASH-09 완료 — md_to_pt 표 변환 근본 수정 (표가 만드는 곳에서 고침) → SSOT/프로젝트/aikorea24/지시서/2026-10-14-1620-AIK24-EMDASH-09-완료보고.md (완료 — verify는 시니어 2)

### 한 일
- [PRODUCTION CODE] `scripts/emdash04_migrate.py` — `md_to_pt()` while 루프에 표 감지·변환 추가 + 헬퍼 5개(`_split_row`/`_is_delim`/`_align`/`_cell`/`_table`) + `DELIM_CELL`. 파싱 로직은 `~/projects2/aikorea24emdash/scripts/fix_tables.py`(EMDASH-06)에서 포팅 — **저장소가 달라 import 할 수 없어 포팅했다**(중복 구현 아님, 같은 판단).
- [TEST CODE 신규] `tests/test_md_to_pt_tables.py` — 10건.
- Worker 재배포 없음(지시서대로 Python 스크립트라 불필요). free-models 재생성은 `page` 1회 실행으로 수행.

### 결과
- [검증됨] **완료기준 1** — 단위 테스트 **10 passed**. 표 2개 → table 블록 2개, `hasHeaderRow:true` 양쪽, 정렬 left/center/right 정확, 셀 텍스트 정확, 파이프 나열 `GitHub | Pages | Vercel` 은 일반 문단 유지. 구분선만 있고 헤더가 없으면 표로 인정하지 않음.
- [검증됨] **완료기준 2** — 라이브 `https://emdash.aikorea24.kr/posts/free-models`: `<table>` **2개**, `<tr>` 42개, `<th>` 9개, `<td>` 121개. 파이프 텍스트 문단 **0건**(남은 `|` 6건은 `<title>free-models | aikorea24</title>` 1건 + JS 템플릿 리터럴 5건). 저장된 PT read-back 으로 `tables 2 / hasHeaderRow [True, True]` 확인.
- [검증됨] **완료기준 3** — 기존 발행 경로 정상. `md_to_pt` 을 표 없는 글(제목+본문+목록+코드블록)에 돌려 `['block','block','block','code']` + style `['h2','normal','normal',None]` 정상, `publish_post` 호출 가능 확인.
- [검증됨] 셀 안 인라인 마크 유지 — `thinkingmachines/inkling-small:free` 셀이 `marks:[["code"]]` 로 저장됨(백틱이 그대로 노출되지 않음).
- [부분검증] 전체 테스트 스위트: **17 failed, 542 passed, 10 skipped**. 근거: 내 변경을 `git stash` 로 빼고 같은 4개 파일을 돌려도 **17 failed 동일** — 기존 실패(test_deep_dive_writer 14 / test_failed_articles 1 / test_pitch 1 / test_write_thread_validation 1)이며 이번 변경과 무관.

### 잔존 위험
1. **정렬(`textAlign`)이 CMS 에서 버려짐** — 변환기는 구분선에서 정렬을 뽑아 셀에 넣지만(지시서 스펙 준수), 저장 후 셀 키는 `_key/_type/content/isHeader` 뿐이고 `textAlign` 는 남아 있지 않다. 렌더 HTML 에도 `text-align` 규칙이 없다 → **정렬 요구는 실효 없음**. 별도 CMS 스키마 확인 필요.
2. **`markDefs` 도 버려짐** — 셀 안에 링크가 들어가면 mark 참조가 끊긴다. 현재 생성되는 표에는 링크 셀이 없다(코드·굵게 마크만 사용). 링크 셀 등장 시 재확인 필요.
3. **이미 발행된 다른 글의 깨진 표는 그대로** — 이번 수정은 앞으로 발행되는 글만 고친다. 기존 글은 `fix_tables.py --apply` 로 별도 변환해야 한다.
4. **테스트 파일을 새로 만들었다** — 지시서 허용 파일은 `emdash04_migrate.py` 1개였지만 작업 2가 단위 테스트를 요구해 `tests/test_md_to_pt_tables.py` 를 추가했다.
5. **기존 17건 테스트 실패 미해결** — threads/deep_dive 계열. 본 작업 범위 밖.

### 다음 행동
- 기존 발행 글의 깨진 표 일괄 변환 여부 결정(`fix_tables.py --apply`).
- `textAlign` 이 CMS 스키마 어디에 있는지 확인 후 필요 시 필드명 변경.

---

## 2026-10-14 14:42 AIK24-NAV-01 완료 — 랜딩 내비 무료 모델 진입점 추가 → SSOT/프로젝트/aikorea24/지시서/2026-10-14-1442-AIK24-NAV-01-완료보고.md (완료 — verify는 시니어2)

### 한 일
- [PRODUCTION CODE] `src/layouts/Layout.astro` 1줄 추가(허용 파일 1개). 커밋 `f2b57d17`.
- `navItems` 배열의 `{ label: '블로그', href: '/blog' },` 바로 다음에 `{ label: '무료 모델', href: 'https://emdash.aikorea24.kr/posts/free-models' },` 삽입.
- 지시서 §주의 준수: 절대 URL 그대로(상대경로 미사용), 라벨·순서(블로그 바로 뒤) 변경 없음.

### 결과
- [검증됨] **배포**: `npm run deploy` 성공, sitemap ping `{"google": true, "naver": true}`. Version ID **`476d3965-a5a7-4f35-81f4-1e438631605b`**(workers versions API 실측, created_on 2026-10-14T07:39:06Z).
- [검증됨] **완료기준 1**: 라이브 `https://aikorea24.kr/` HTML 에 `href="https://emdash.aikorea24.kr/posts/free-models"` **정확히 2회**, 라벨 `무료 모델` 2개. 라벨·순서 정상.
- [검증됨] **완료기준 2**: 출현 위치 2곳 = 5102 / 7580. 첫 `<nav>` 시작 4741, `#mobile-menu` 시작 7336 → 첫 번째는 **데스크톱 내비**, 두 번째는 **`#mobile-menu` 내부**. 양쪽 모두 노출.
- [검증됨] **완료기준 3**: `GET https://emdash.aikorea24.kr/posts/free-models` → **HTTP 200**, `redirect_url` **빈값**(리다이렉트 없이 직접 연결).

### 잔존 위험
1. 새 메뉴 항목 추가로 데스크톱 내비 6→7개. 1024~1280px 구간에서 내비 줄바꿈 여부는 미측정 — 기존 6개가 이미 같은 배열로 배치돼 있던 구조라 1개 추가는 유사 동작으로 보이나 실측하지 않음.
2. [검증불가] 실제 기기에서 메뉴 줄바꿈/오버플로 — 서버 HTML 구조 확인까지만 함.

### 다음 행동
- 대표님: 데스크톱 중간 폭(1024~1280px)에서 내비 7개가 한 줄에 들어가는지 육안 확인 권장.
## 2026-10-14 14:40 AIK24-EMDASH-08 완료 — 홈페이지 h1 부재 수정 (눈에 안 보이는 h1 1줄 + visually-hidden CSS) → SSOT/프로젝트/aikorea24/지시서/2026-10-14-1440-AIK24-EMDASH-08-완료보고.md (완료 — verify는 시니어 2)

### 한 일
- [PRODUCTION CODE] `/Users/twinssn/projects2/aikorea24emdash/src/pages/index.astro` 1개, +16행.
  - `<Base …>` 바로 다음 줄에 `<h1 class="visually-hidden">{siteTitle} — {siteTagline}</h1>` 추가.
  - `<style>` 맨 아래에 `.visually-hidden` 11행 추가.
- 커밋 `5d5b325` (pathspec 한정 — 다른 세션 산출물 미포함). 푸시 안 함.

### 결과
- [검증됨] 완료기준 1: `/` 에 `<h1>` **정확히 1개**, 텍스트 `aikorea24 — AI·테크·정보를 한곳에`. 근거: 라이브 HTML grep `grep -c "<h1"` = 1 (수정 전 0).
- [검증됨] 완료기준 2: 시각 변화 없음. 근거: Playwright computed style — `position:absolute`, `clip:rect(0px,0px,0px,0px)`, `overflow:hidden`, bounding box **1×1px @ (-1, 64)**. 1280×900 스크린샷(`/tmp/h1_home_after.png`)에서 레이아웃 변화 없음 확인. 빌드된 CSS 에 `.visually-hidden[data-astro-cid-lcdefpme]{…}` 실려 있음.
- [검증됨] 완료기준 3: 다른 페이지 h1 유지. `/posts` → `<h1 class="page-title">최신 글</h1>`, 글 상세 → `<h1 class="article-title">엔비디아 네모트론 3 울트라 550B…</h1>`. 근거: 라이브 HTML grep.
- [검증됨] 배포 성공. Version ID **`c1b40f03-4142-4a67-93c1-4f70ed9d9090`**, `Uploaded aikorea24emdash (20.91 sec)`, EXIT 0.

### 잔존 위험
1. **배포 계정이 다름** — 이 프로젝트는 `~/.env.common` 의 `CLOUDFLARE_API_TOKEN` 이 아니라 `CF_MIGRATE_TOKEN` (계정 `7eb1b8cd…`) 으로 배포한다(`scripts/deploy.sh` 가 강제). 일반 규칙을 그대로 쓰면 엉뚱한 계정에 배포된다.
2. **푸시 안 함** — 커밋 `5d5b325` 는 로컬에만 있다. 원격 반영이 필요하면 지시 필요.
3. **h1 이 1×1px 요소를 남긴다** — 지시서가 지정한 표준 visually-hidden CSS 를 그대로 쓴 결과다. 레이아웃 영향은 없어 보이는 1px 이지만 완전한 제거는 `clip-path: inset(50%)` 가 추가로 필요하다.
4. **emdash 저장소에 테스트가 없다** — `npm run test` = "No test files found, exiting with code 1". 기존 상태이며 이번 변경과 무관. 회귀 자동 확인手段이 없다.
5. **작업 트리에 다른 세션 산출물 잔존** — `src/version.gen.ts`(배포 스크립트가 매번 갱신), `scripts/logs/table_fix_backup_2026-10-14/` 백업, `scripts/__pycache__/`. 커밋하지 않고 그대로 뒀다.

### 다음 행동
- 대표님 verify 후 원격 푸시 여부 결정.
- 홈 이외에 h1 이 없는 페이지가 더 있는지(카드 그리드·태그·카테고리) 별도 점검 필요.

---

## 2026-10-14 AIK24-FREE-PIPE-01 완료 — 무료 모델 수집·평가·발행 일일 파이프라인

## 2026-10-14 AIK24-FREE-PIPE-01 완료 — 무료 모델 수집·평가·발행 일일 파이프라인 (3프로바이더 수집 39건 + diff + 고정 리스트 페이지 + launchd 방콕 10:00) → SSOT/프로젝트/aikorea24/지시서/2026-10-14-1430-AIK24-FREE-PIPE-01-완료보고.md (완료 — verify 요청)

### 한 일
- [PRODUCTION CODE 신규] `scripts/model_catalog.py` — 4프로바이더 수집(OpenRouter/Kilo/zen) + 스냅샷 `model_catalog_YYYY-MM-DD.json` + diff `model_diff_YYYY-MM-DD.json`.
- [PRODUCTION CODE 신규] `scripts/free_models_page.py` — 고정 리스트 페이지(슬러그 `free-models`) 갱신 / 신규 모델 평가·심층 리뷰 발행 / 상호 연결 / `daily` 서브커맨드.
- [PRODUCTION CODE] `scripts/emdash_publish.py` — `upsert_post()` 신설(고정 슬러그 갱신). posts 컬렉션은 slug 필드가 없어 title 이 slug 가 되어야 고정 URL 이 된다.
- [PRODUCTION CODE] `scripts/blog_draft_generator.py` 1줄 — `article=None` 이면 `.get()` 이 죽는 버그 수정 (`{}` 전달).
- [TEST CODE 신규] `tests/test_model_catalog.py` 7건, `tests/test_free_models_page.py` 7건.
- [CONFIG 신규] `scripts/free-model-pipe.plist.template` + `~/Library/LaunchAgents/kr.aikorea24.free-model-pipe.plist` 등록. 스케줄 KST 06:00 → **방콕 10:00**(대표님 지정).

### 결과
- [검증됨] 완료기준 1: 수집 39건 = openrouter 14 + kilo 15 + zen 10. 근거: `/tmp/fp_daily.log` 로그 라인 + `model_catalog_2026-10-14.json` 원소 5개 키(`provider/model_id/name/pricing/context_length`) 일치. **nvidia 1건은 [검증불가]** — `/v1/models` 에 가격·무료 플래그 필드가 없어 무료 티어 판별 불가(2026-10-14 실측).
- [검증됨] 완료기준 2: diff added/removed/changed 동작. 근거: `tests/test_model_catalog.py` 7 passed(추가 1 / 삭제 1 + 사유 / 변경 1 정확히 포착), 실수행 added 39 · removed 0 · changed 0.
- [부분검증] 완료기준 3: 리스트 페이지 `https://emdash.aikorea24.kr/posts/free-models` 생성·갱신 동작, HTTP 200, 스냅샷 시각 머리글 반영(13시 → 14시). **2일 연속 갱신은 오늘 안에 불가** — 내일 방콕 10:00 launchd 실행 때 날짜가 바뀌는지 확인 필요.
- [검증됨] 완료기준 4: `nvidia/nemotron-3-ultra-550b-a55b:free` **11/12 정답 · 호출 실패 1/12** → 리더보드 기록(qv=1) → 심층 리뷰 발행 `https://emdash.aikorea24.kr/posts/nvidianemotron-3-ultra-550b-a55bfree`(HTTP 200, `<title>` 정상).
- [검증됨] 완료기준 5: 양방향 링크. 리스트 카드 → `href="/posts/nvidianemotron-3-ultra-550b-a55bfree"`, 리뷰 말미 → `href="https://emdash.aikorea24.kr/posts/free-models"` 1건. 둘 다 라이브 HTML grep 확인.
- [검증됨] 완료기준 6: `launchctl list` 등록 확인, 스케줄 변경 확인(`launchctl print` = `"Hour" => 10`), `daily` 수동 1회 EXIT 0.

### 잔존 위험
1. **NVIDIA NIM 수집 불가** — 무료 티어 판별 필드가 공개 API에 없음. 별도 조사/지시서 필요.
2. **2일 연속 갱신 미검증** — 완료기준 3의 절반. 내일 방콕 10:00 실행 결과로 확인해야 함.
3. **`thinkingmachines/*` 403** — 카탈로그에는 "무료"로 떠도 이 API 키로는 접근 불가. `model_eval_failed.json` 에 영구 스킵 기록해 매일 낭비되는 것을 막았으나, 다른 키로 접근 가능해지면 그때 해제 필요.
4. **스케줄이 브리핑 이후** — 방콕 10:00 = KST 12:00 이라 지시서 원문 목적(브리핑 09:00 KST 발행 전)과 어긋남. 대표님 지정이 우선이라 그대로 뒀다.
5. **카드가 1개뿐** — 규칙상 무조건 4개로 채우지 않는다(미평가 모델 제외). 평가가 쌓이면 늘어난다.
6. **EmDash posts 컬렉션에 slug 필드 없음** — 고정 URL 을 만들려면 title 을 slug 로 써야 한다. 리스트 페이지는 그래서 화면 제목이 `free-models` 이고 한국어 제목은 본문 H1 에 나온다.

### 다음 행동
- 내일 방콤 10:00 launchd 실행 후 리스트 페이지 스냅샷 날짜 변경 + state.md 로그 1줄 자동 추가 확인.
- NVIDIA NIM 무료 티어 판별 방식 별도 조사.

---

## 2026-10-14 AIK24-FREE-PIPE-01 일일 실행 — 수집 39건 / 실패 프로바이더 1 / added 39 · removed 0 · changed 0 / 리스트 페이지 갱신 https://emdash.aikorea24.kr/posts/free-models / 평가·발행 rc=0 / 심층 리뷰 1건 (리스트 카드 링크 1건)

## 2026-10-14 14:10 AIK24-EMDASH-07 완료 — 모바일 헤더 겹침 수정 → SSOT/프로젝트/aikorea24/지시서/2026-10-14-1410-AIK24-EMDASH-07-완료보고.md (완료 — verify는 시니어2)

### 한 일
- [PRODUCTION CODE] `~/projects2/aikorea24emdash/src/styles/theme.css` 맨 아래 5줄 추가(허용 파일 1개). 커밋 `453bf1b1`, GitHub 푸시 완료.
- 지시서 확정 코드 그대로: `@media (max-width: 640px) { .site-header { height: auto !important; } }` + 사유 주석. `!important` 유지, range syntax 미사용(지시서 §주의 준수).

### 결과
- [검증됨] **배포**: `bash scripts/deploy.sh` → **Current Version ID `35feeb84-9fff-43bc-ad9e-21d7294beaa5`**(assets 1개 변경 업로드, Uploaded 23.39sec, triggers 4.11sec).
- [검증됨] **완료기준 1 — 360px `/posts` 겹침 없음**: 헤더 `getBoundingClientRect().bottom = 123`, `h1("최신 글").top = 147` → 24px 간격. nav 링크 6개(로고/Home/Blog/News/Tools/Courses) 모두 `bottom ≤ 111 < 123` → 헤더 밖으로 넘치지 않음. `anyLinkBelowHeader=false`, `h1Overlaps=false`.
- [검증됨] **모바일 스크린샷 확보** `/tmp/emdash07_mobile.png` (PNG 360×800, 142,028B). 육안 확인: 로고·검색창·메뉴 5개가 "최신 글" 상단에 정상 배치, 겹침 없음.
- [검증됨] **완료기준 2 — 데스크톱 정상**: 1280px에서 `.site-header` height **65px 유지**, `position: sticky` 유지, `h1.top=97 > 65`.
- [검증됨] **완료기준 3 — `/`·글 상세 페이지**: 360px에서 `/posts/free-models` `h1.top=228`(헤더 bottom 123 아래), `/` 도 nav 링크 전부 헤더 내부. 두 페이지 모두 겹침 없음.
- [검증됨] 라이브 CSS(`/_astro/*.css`)에 `@media (max-width:640px){.site-header{height:auto!important}}` 반영, 데스크톱 구간 미영향.

### 잔존 위험
1. **`/` 페이지에 `h1` 이 0개** — 헤더와 무관한 기존 문제. 첫 머리말이 `h2:Posts` 로 시작(measured). SEO 측면 결함이며 이번 지시서 범위 밖 → 별도 지시서 필요.
2. `/posts` 첫 카드(`free-models`) 썸네일이 빈 회색 상자로 보임 — EMDASH-04 잔존 위험(썸네일 미지정 글)의 재확인. 이번 작업과 무관.
3. [검증불가] 실제 iOS/Android 브라우저 주소창 높이 고려에서의 겹침 — 에뮬레이션 뷰포트(360×800) 실측만 함. 에뮬레이션이라 주소바 가변 높이는 반영 안 됨.

### 다음 행동
- 대표님: `/` 페이지 h1 부재(위 1번) 별도 지시서 필요 시 Issu.
## 2026-10-14 14:05 AIK24-EMDASH-06 완료 — 블로그 표 렌더링 근본 해결(10+1건/19표/147행) → SSOT/프로젝트/aikorea24/지시서/2026-10-14-1405-AIK24-EMDASH-06-완료보고.md (완료 — verify는 시니어2)

### 한 일
- [PRODUCTION CODE] `~/projects2/aikorea24emdash/scripts/fix_tables.py` 신규(331줄). 커밋 `0adc9cc` + `0d4bdda`, GitHub 푸시 완료.
  - **쓰기 경로 = EmDash API**(D1 직접 UPDATE 안 씀 — 렌더 소스가 `revisions.data` 이라 정합성 깨짐): MCP `content_get` → `_rev` 획득 → `PUT /_emdash/api/content/posts/{id}` → `POST .../publish`. D1 은 탐색 전용.
  - 안전장치 지시서 §작업3 3항목 전부 이행: 변환 전 원본 백업(`scripts/logs/table_fix_backup_2026-10-14/`, 10개/212KB) → 애매 파이프 줄은 원본 유지+제외 목록 → dry-run 선행 후 적용.
  - 모드: `--dry` / `--apply` / `--prefix`(백업 원본 재변환) / `--limit`.
- 배포: **미실행** — 지시서 §배포 "D1 데이터 수정이므로 Worker 재배포 불필요", 렌더러 코드 미변경.

### 결과
- [검증됨] **작업1 피해 규모 = 21건**(`ec_posts` content 에 마크다운 구분선 패턴. `content LIKE '%|%'` 55건, `<table` 0건). 목록은 `/tmp/emdash06_targets.json`.
- [검증됨] **작업2 table 스펙**(`node_modules/@emdash-cms/admin/dist/portable-text-table.d.ts`):
  - block `{_type:"table", _key, rows:[TableRow], hasHeaderRow?:bool, markDefs?}`
  - row `{_type:"tableRow", _key, cells:[TableCell]}`
  - cell `{_type:"tableCell", _key, content:[PortableTextSpan], isHeader?:bool, colspan?, rowspan?, colwidth?:number[], textAlign?:"left"|"center"|"right"|"justify", markDefs?}`
  - span `{_type:"span", _key, text, marks?}`
  - 헤더 구분 = 블록 `hasHeaderRow:true` + 헤더행 셀 `isHeader:true`. alignment 은 구분선 행에서 추출(`:---`→left, `:---:`→center, `---:`→right).
- [검증됨] **작업4 변환 적용 11건 / 표 19개 / 행 147**. 재측정 잔여 5건 = 바이브코딩 워크쓰루 5건(아래 참조), 즉 **표로 판정 가능한 글 0건**.
- [검증됨] **작업5 검증 6/6 통과** — 제보 글(구글 플레이스토어) + 무작위 5건 전부 `table≥1 AND th≥1 AND <p>…|…</p> 0건`:
  - 독자 파운데이션 table=5/th=21/td=111 · free-models 2/9/121 · deepseek-v4 1/4 · private-offline 1/4 · 부트캠프란 1/5 · **구글 플레이스토어 1/4/12**.
  - ego-browser(spaceId 4) 제보 글 DOM: `table` 1개, 4행×3열(`이용 자격 / 게시 비용 / 주요 활용 도구 / 앱 공개 범위`), 파이프 문단 0.
- [검증됨] 바이낸스 글(2차 수정분) table=1/th=4/td=12/파이프문단=0.

### 실행 중 발견·수정한 버그 3건
1. `block_text()` 가 span 을 2번 append(중복 텍스트) → 분기 처리.
2. ★ `has_header = (d == 0)` 로 짚어 **헤더행 통째로 유실**(1차 라이브 반영). `d >= 1` 로 수정 후 **백업 원본으로 10건 전량 재적용**(행 124 → 142).
3. ★ 구분선 행의 앞뒤 파이프가 이관 과정에서 잘려 `--- | --- | ---` 로 남는 경우를 `split_row` 가 거부 → 바이낸스 글 1건 변환 누락. 앞뒤 파이프를 강제하지 않도록 수정 후 적용.

### 잔존 위험
1. **바이브코딩 워크쓰루 5건의 파이프 문단 11/10/11/10/11개는 미변환** — 지시서 §작업3-2(애매한 파이프 줄 미변경) 준수. 라이브 확인 결과 `GitHub | Pages | Vercel` 처럼 **링크를 나열한 인라인 목록**이며 표가 아님. 원본 데이터 복구가 필요하면 별도 지시서.
2. 제외 5건(`free-lecture-*` 4 + 무료-llm-인클루전아이 1)은 soft-deleted(`deleted_at` 설정, 라이브 미노출). API 404 로 변환 불가.
3. 1차 변환에서 헤더행 유실 상태가 라이브에 2~3분 노출됨(현재 정상).
4. [검증불가] 표 렌더가 Google 크롤러·네이버 프리뷰에서 동일하게 보이는지 — 사이트 외부 렌더링이라 내부 실측 불가. 수치 데이터는 표로 정확히 표시됨(위 HTML 근거).

### 다음 행동
- 대표님: 바이브코딩 5건의 파이프 나열을 표로 바꿔야 하는지, 아니면 링크 목록 유지가 맞는지 결정.
## 진행 중 (2026-10-14, AIK24-EMDASH-06) — EmDash 블로그 마크다운 표 → table 블록 변환

## 2026-10-14 13:47 AIK24-RENEWAL-02 완료 — 색상 흑백+상징빨강 통일 / 7일 강의 삭제 → SSOT/프로젝트/aikorea24/지시서/2026-10-14-1347-AIK24-RENEWAL-02-완료보고.md (완료 — verify는 시니어2)

### 한 일
지시서: `SSOT/프로젝트/aikorea24/지시서/2026-10-14-1340-AIK24-RENEWAL-02-색상통일+7일강의삭제.md` (47줄). 대표님 결정 ① 색상 전부 흑백, 유일한 예외 상징 빨강 `#E63B2E` ② 7일 강의는 상품이 없으므로 관련 페이지·진입점 전부 삭제.

#### 작업 1 — 색상 (PRODUCTION CODE 1파일)
- [PRODUCTION CODE] `src/pages/chronicle/index.astro`
  - `categoryConfig` 의 `color: "blue"/"green"/"red"/"purple"/"amber"` 5개 필드 **삭제**. 근거: 91행 `cfg.emoji` 만 사용, `cfg.color` 참조 0건(죽은 코드). 타입 `Record<string, { emoji: string }>` 로 축소.
  - `borderColorClass` 5개(`border-l-blue-500`/`green`/`red`/`purple`/`amber-500`) → **전부 `border-l-[#E63B2E]`**.
  - `catColorClass`(정책·규제 빨강 배지)는 지시서 §3에 따라 **미변경**.
  - `src/styles/global.css` 미변경(§4 준수). 카테고리 이모지 5개 유지(§6 준수). `src/auto_poster/` 미변경.

#### 작업 2 — 7일 강의 삭제 (PRODUCTION CODE 4파일 + 삭제 6파일)
- [PRODUCTION CODE] `src/components/home/HeroSection.astro` — 홈 CTA `<a href="/courses/7day-starter/">7일 강좌 시작하기 →</a>` 블록 삭제, 남은 `/about` 링크에 `group` 클래스+`→` 스페인 이관.
- [PRODUCTION CODE] `src/pages/subscribe.astro` — `🔗 강좌 연계` 카드 삭제, grid `sm:grid-cols-3` → `sm:grid-cols-2`.
- [삭제] `src/pages/courses/7day-starter.astro`, `src/pages/api/courses/` 전체(enroll/interest/track/send-daily.ts + templates/lesson-email.ts). 근거: 6파일 전부 7일강의 전용(track=lesson_clicks 테이블, send-daily="7일 강좌 자동 발송", lesson-email="7일 AI 입문 강좌"), `src/` 내 외부 참조 0건, launchd plist 에서 send-daily 호출 0건.

### 결과
- [검증됨] **색상 grep 0건**: `grep -rniE "green|pink|blue|purple|amber|yellow|teal" src/ --include="*.astro" --include="*.css" | grep -v "^src/auto_poster/" | wc -l` → **0**. (수정 전 8건, 전부 `chronicle/index.astro`)
- [검증됨] **7일강의 grep 0건**: `grep -rniE "7day|7-day|7일 ?강좌|7일 ?강의" src/ public/ | grep -v "^public/images/"` → **0**(exit 1).
- [검증됨] 빌드: `npm run build` → **EXIT 0** (`✓ Completed in 6.05s`, `Server built in 10.63s`, `Complete!`).
- [검증됨] 배포: `npm run deploy` → **Current Version ID `19125a64-21a0-406a-aa5d-ef86c0225440`**, `Uploaded 19.19 sec`, sitemap ping `{"google": true, "naver": true}`.
- [검증됨] 라이브 HTTP: `/` 200, `/chronicle/` 200, `/subscribe/` 200, `/courses/` 200, **`/courses/7day-starter/` 404**.
- [검증됨] 라이브 참조 0건: `/`·`/subscribe/`·`/chronicle/` HTML 모두 `7day|7-day|7일 ?강좌` **0건**.
- [검증됨] **chronicle border (ego-browser 실측)**: `class="border-l-[#E63B2E]"` 요소 **67개**, `getComputedStyle` 결과 **전건 `borderLeftColor: rgb(230, 59, 46)`(= #E63B2E) / `borderLeftWidth: 4px` / `solid`**, 4px 아닌 것 **0개**. 라이브 CSS(`/_astro/Layout.Zo4j6TRk.css`)에 `border-left-color:#e63b2e` 존재, 이전 blue/green/purple/amber border CSS **0건**.
- [검증됨] 카테고리 이모지 5개(🤖🏢📜🇰🇷💥) 라이브 chronicle 본문 모두 존재.
- [검증됨] 홈 hero CTA = `더 알아보기 → => /about` 1개, 7일강좌 링크 **0개**.
- [검증됨] `/subscribe/` 카드 = `오늘 쓸 수 있는 소식`, `AI 도구 소개` 2개, `7일|7day` 텍스트 **없음**.
- [검증됨] 깨진 이미지 **0건**(chronicle·홈).
- [부분검증] 스크린샷 육안 — ego-browser `page.screenshot()` 이 `Page.captureScreenshot` CDP 타임아웃으로 **미확보**(3회 시도). 위 computed-style 67/67 확인이 색상 검증의 근거이며, 픽셀 단위 육안은 미수행.

### 1번 grep 결과 목록 (지시서 작업2 §1 첨부)
`grep -rni "7day\|7-day\|7일" src/ public/` (public/images 제외) → 총 24건.
**삭제 대상(7일 강의 관련, 6곳)** — `src/components/home/HeroSection.astro:32-34`, `src/pages/courses/7day-starter.astro`(9·10·11·16·39·43·79·165행), `src/pages/subscribe.astro:38`, `src/pages/api/courses/enroll.ts:29`, `src/pages/api/courses/send-daily.ts:6`, `src/pages/api/courses/templates/lesson-email.ts:104`.
**삭제 금지(무관, 18건 유지)** — `src/content/tools/dailyhelm.md:31·34·56·76`(SaaS "7일 무료 체험"), `src/content/tools/appto.md:31·34`(동일), `src/content/chronicle/2026-07-01-anthropic-fable5-재배포.md:22`(뉴스 본문 날짜), `src/pages/api/articles/pool.ts:54`("최근 7일 news" 주석), `src/pages/refund.astro:21·23`(청약철회 7일, 「전자상거래법」 제17조).

### 잔존 위험
1. **D1 `courses` 테이블에 2행 잔존** — `7day-starter`(삭제된 페이지), `7day-infra`("0원 인프라, 7일", `src/` 참조 0건으로 이미 고아). 지시서 §범위 밖(DB 삭제)이라 **코드/D1 미변경**. 대표님 판단 대기.
2. `src/pages/courses/index.astro` 는 **7일강의 아님**(RENEWAL-01 §7-3 유료 강의 사전등록). 삭제하지 않음 — 유지.
3. 스크린샷 미확보(위 [부분검증]).
4. `docs/state.md` 에 동시 FREE-PIPE-01 진행중 줄 존재(다른 세션 산출물, 미수정).
5. B-3/B-4/B-5/B-7 정량 스펙 부재 → 미착수(지시서 §범위 밖).

### 다음 행동
- 대표님: D1 `courses` 테이블 2행 정리 여부 결정.
- 별도 지시서 대기: B-3/B-4/B-5/B-7(디자인 스펙), A안 콘솔 캐시 규칙.



## 2026-10-14 13:45 AIK24-RENEWAL-01 B그룹(디자인 7건)현황 감사 — B-1/B-2 이미 적용됨 확인, 잔여 1건 + 스펙 확인 대기

### 한 일
- 지시(원문): "10-11 백로그(B디자인·C버그·D프롬프트·E이관) … 다해줘 / 마무리 하자."
- [PRODUCTION CODE] **없음.** 감사만. 이유 하단.

### 결과 — B그룹 7건 실측
| 항목 | 상태 | 근거 |
|---|---|---|
| B-1 7일강의 배경(검정→흰/검정텍스트) | **[완료]** | `courses/7day-starter.astro:25` `class="bg-white text-[#111111] min-h-screen"`. 검정 배경 아님. |
| B-2 초록/핑크 제거(전제 "25개 파일") | **[사실과 불일치 — 잔여 1건]** | `global.css` 토큰은 이미 흑백+빨강(`--bg-primary:#ffffff`, `--text-primary:#111111`, `--accent-red:#E63B2E`). `grep -rniE "green\|pink" src/` → 웹 UI 에 **2건만**. Tailwind 초록/핑크 21건은 전부 `src/auto_poster/`(Threads 카드, 웹 아님). |
| B-3 타임라인 통일 | **[감사 불가]** | 대상 4파일(`tools/finder`, `compare`, `chronicle/[...id]`) 확인. "통일" 기준이 스펙에 없어 판정 불가. |
| B-4 푸터 통일 | **[감사 불가]** | `src/components/` 에 Footer 컴포넌트 없음 — `layouts/Layout.astro` 인라인. 비교 대상 부재. |
| B-5 EmDash 헤더/푸터 | **[감사 불가]** | EmDash CMS 소스(`~/projects2/aikorea24emdash`) 대상. aikorea24 사이트와 디자인 기준 공유 여부 불명. |
| B-6 블로그 타이포(글자크기·대칭·표→단락·여백) | **[대상 이동]** | Astro 블로그 소스 삭제 완료(EMDASH-04) → 대상이 `~/projects2/aikorea24emdash/src/pages/posts/[slug].astro` 로 옮겨감. |
| B-7 마스코트 배치 | **[감사 불가]** | `mascot` 참조 5파일(`home/HeroSection`, `home/ToolsSection`, `404`, `global`, `unsubscribe`). "배치" 기준 미정의. |

- [검증됨] B-2 잔존 2곳: `src/pages/chronicle/index.astro:17` `color: "green"` — **죽은 필드**(91행에서 `.emoji` 만 사용, `.color` 미사용) / `:37` `border-l-green-500` — `borderColorClass()` 에서 실제 사용됨.
- [검증됨] E그룹(블로그 이관)은 EMDASH-01~05 로 완료. D그룹도 D-1/D-2/D-3 완료. C그룹 5건 완료.

### 잔존 위험
1. **B그룹 잔여 5건(B-3/B-4/B-5/B-6/B-7)을 임의 스펙으로 수정하지 않음** — RENEWAL-01 의 서술은 "통일/대칭/여백" 처럼 정량 기준이 없어 재작업하면 대표님 의도와 어긋날 수 있음.
2. chronicle 의 5개 카테고리는 blue/green/red/purple/amber 색 구분|border-left)이라 "green 만 제거" 하면 5색 중 1개만 빠진 비대칭 상태가 됨.
3. `border-l-green-500` 는 실제 렌더에 영향. 미수정 상태.

### 다음 행동
- 대표님: (a) chronicle 초록 border 색 결정(검정/회색/유지) (b) B-3~B-7 정량 스펙(또는 대상 화면 스크린샷) 제공 시 그 기준으로 재작업.
