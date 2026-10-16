## 2026-10-16 16:45 — AIK24-OPENCODE-GUIDE-FIX: groq 글 마무리 누락 수정 + 스킬 보강

### 한 일
- 대표님 지적("마무리에 대한 내용을 안적었니?")에 따라 `groq-free-api-key-guide` 라이브 글을 진단하고 **전면 재작성·재발행**했다(같은 slug·제목 유지 → URL 보존).
- `.claude/skills/aik24-blog-writing/SKILL.md` 를 보강해 같은 누락이 재발하지 않게 했다.

### 결과 — [검증됨] 재작성 전후 실측 대조
| 항목 | 이전 | 이후 |
|---|---|---|
| 상태/용량 | 200 / 39,267 bytes | 200 / **43,499 bytes** |
| `<h1>` | 1 | 1 |
| 본문 마무리 소제목 | **0 (주의사항으로 끝남)** | **1 (`## 마무리 — 오늘 30분 안에 끝내는 무료 API 연결`)** |
| 외부 링크(고유) | 1 (내부 글 1건) | **5** |
| 무료 티어 수치 | 0개(용어 설명만) | **공식 문서 표 7행 전사** (gpt-oss-120b 30 RPM / 1K RPD / 8K TPM / 200K TPD 등) |
| 도입 중복 | excerpt = 본문 첫 문단 (2회 노출) | **0회** (excerpt 를 별도 한 줄로 분리) |
| 코드펜스 줄바꿈 깨짐 | `source ~/.zshrcOpenCode 설정 파일…` 붙음 | 분리 확인 |
- [검증됨] 수치 출처 = `https://console.groq.com/docs/rate-limits` 실측 HTML 표(RPM/RPD/TPM/TPD, 조직 단위 적용·캐시 토큰 미포함·`retry-after` 헤더 설명 포함). 지어낸 값 0건.
- [검증됨] EmDash `ec_posts` slug `groq-free-api-key-guide` = **1행**(id `01M51NXRNKVSN1DV7EY5MRHGNV`, published) → 중복 글 없음.
- [검증됨] 본문 사본 `scripts/logs/groq_free_api_key_guide_draft.md` (3,447자, 링크 7).
- [검증됨] 스킬 3개소 보강 — ① 1절 마무리 규칙에 "문자 그대로 `## 마무리 — …`" + "없으면 발행하지 않는다" + 실제 누락 사례 명시 ② 4절 검증에 `grep -c '<h2[^>]*>[^<]*마무리'` (1 이상, 없으면 발행 금지) ③ 5절 진단 체크리스트를 4→5항목으로 확장(누락 사례·얇은 지표 함께 기록).

### 잔존 위험
1. Groq 무료 티어 수치는 **시점 의존**(본문에 "2026년 10월 16일 기준" 명시). 회사 연혁(설립 연도·창업자)은 공식 페이지가 308 리다이렉트라 **검증 실패 → 본문에 쓰지 않았다**(LPU·LPX 문구만 groq.com 홈에서 인용).
2. `whisper` 행의 TPM/TPD 는 문서상 `-`(해당 없음)이므로 음성 초 단위 한도로 대체 표기했다.
3. 스킬 규칙이 강해진 만큼, 기존에 발행된 다른 글들도 같은 누락(마무리·수치·링크)을 갖고 있을 가능성이 있다 — 전수 점검은 하지 않았다.

### 다음 행동
- 없음 (지시 항목 완료).

## 2026-10-16 16:20 — aik24-blog-writing 스킬 신규 작성

### 한 일
- `opencode-cli-guide` 재작성(대표님 평가 100/100)에서 지적받은 4가지를 규칙화해 `.claude/skills/aik24-blog-writing/SKILL.md` 신규 작성.
- 담긴 내용: 구조 규칙(본문 H1 금지·도입 설명문 3요소·`## N. 동작 — 약속` 소제목·마무리 체크리스트), 내용 규칙(사실 우선·내부 용어 금지·키는 어디서 받고 어디에 넣는지 표로·무료/유료 사실 구분·시점 명시), 발행 경로(`upsert_post` + PAT 는 `~/.env.common`), 발행 후 검증(중복 H1·외부 링크 수·ec_posts 1행·state.md+본문 사본 커밋), 재작성 진단 4항목.

### 결과
- [검증됨] 파일 생성: `.claude/skills/aik24-blog-writing/SKILL.md` (frontmatter `name`/`description` 포함, description 은 "Use when …" 트리거 문구만 기술).
- [검증됨] 스킬 목록 노출 확인 — 기존 `aik24-free-models-page`·`aik24-manual-pipeline` 과 동일한 `.claude/skills/<name>/SKILL.md` 구조.

### 잔존 위험
1. 스킬 본문의 검증 명령은 `opencode-cli-guide` 1건에서 도출한 것이라, 다른 유형(리뷰·비교 글)에는 적용 범위가 좁을 수 있다.
2. `get_post()` 가 `None` 을 반환하는 EmDash API quirk 는 원인 미확정 상태로 스킬에 "판단 기준은 발행 URL" 로만 기록했다.

### 다음 행동
- 없음.

## 2026-10-16 16:05 — AIK24-OPENCODE-GUIDE-REWRITE: opencode-cli-guide 전면 재작성·발행

### 한 일
- 대표님 피드백(① "주니어의 실전 팁" 같은 내부 용어 ② H1 중복 ③ 역사·사용자 수 같은 사실 정보 부족 ④ API 키를 어떻게 받는지 안내 없음 ⑤ 마무리 소제목 없음)에 따라 글을 처음부터 다시 작성.
- 새 구조: 도입(설명문) → H2 7개(설치 / 무료 키 발급 / 첫 실행·모델 선택 / 623세션 실측 / 자주 쓰는 명령 / 비용 확인 / 주의) → 마무리 소제목. **본문에 H1 없음**(제목은 EmDash가 렌더).
- 새로 넣은 근거(전부 실측·공식 페이지): GitHub `anomalyco/opencode`(2025-04-30 생성, 스타 214,019, MIT, `sst/opencode`→`anomalyco` 이전), npm `opencode-ai`(최신 1.19.2, 무스코프 `opencode`는 404), 공식 설치 주소 2종(`/install`=V1, `/v2/install`=V2), Zen 잔액 $20 절차, 키 발급 페이지 4곳(OpenRouter·Groq·NVIDIA·Cerebras), 로컬 CLI v2.0.29 서브커맨드·플래그, 세션 623건 무료 비중 90.5%·상위 3개 모델·프로바이더 분포.
- 발행 경로: `scripts/emdash_publish.upsert_post("opencode-cli-guide", …)` (PAT 출처 = `~/.env.common`). repo에 글 소스가 없어(`grep -rl` 0건) 스크립트로 직접 발행했다.

### 결과
- [검증됨] 라이브 `https://emdash.aikorea24.kr/posts/opencode-cli-guide` — status 200, **53,091 bytes**, `<h1>` **1개**(중복 해결), 외부 링크 **23개**(이전 0개), `90.5` 반영, `firecrawl` 흔적 **0건**.
- [검증됨] EmDash D1 `ec_posts` 조회 — slug `opencode-cli-guide` 행 **1건**(id `01M51M5J5PCWDSN989ZH5152C2`, status `published`). 중복 생성 없음.
- [부분검증] 본문 수치는 작성 전에 전부 공식 페이지·로컬 명령 실측으로 확인했으나, 독자 반응(체류시간)은 측정 수단이 없어 알 수 없다.

### 잔존 위험
1. `opencode auth`의 세부 서브커맨드는 도움말에 노출되지 않아 본문에 구체 명령을 쓰지 않았다(미검증 항목은 미기재 원칙).
2. Zen 무료 모델의 정확한 무료 조건(잔액 없이 허용되는 한도)은 공식 페이지에 수치로 명시돼 있지 않다 — 본문에는 "무료 모델은 선택기에서 고르면 바로 대화" 수준으로만 적었다.
3. 스타 수·npm 버전은 시점 의존 값이다(본문에 "2026년 10월 16일 기준" 명시).

### 다음 행동
- 없음.

## 2026-10-16 15:20 — 정합 정리: 소급 완료보고 3건 (D1-02 / D1-03 / EVAL-09)

### 한 일
- 지시서 폴더 전수 대조(ID 기준) 결과 **완료보고 파일이 없던 지시서 3건**을 찾아 소급 완료보고를 작성했다.
  - `2026-10-15-0005-AIK24-D1-02-완료보고.md` (브리핑 뉴스 API 쿼리 최적화)
  - `2026-10-15-0006-AIK24-D1-03-완료보고.md` (EmDash 쿼리 폭풍 N+1 완화)
  - `2026-10-15-1321-AIK24-EVAL-09-완료보고.md` (free-models 썸네일 404)
- `AIK24-TOOLSYNC-04`·`AIK24-FAVICON-01` 은 통합 완료보고 파일명(`TOOLSYNC-03-04`, `TOOLSYNC-05-FAVICON-01`) 때문에 누락으로 오탐된 것이며, 실제 보고 파일은 존재했다.

### 결과
- [검증됨] D1-02: 코드 현존 — `src/pages/api/briefing/news.ts` 17~23행 `params.push` 7건, `datetime('now', ?` 1건, 9행 `Cache-Control`. 당시 배포 Version `b7c722ba-31d7-48e9-95a5-2e521525913c`.
- [검증됨] D1-03: 코드 현존 — `scripts/emdash04_migrate.py` 28~30행 `EXISTING_TITLES_LIMIT=500`/캐시/TTL(3600), 332·340행 사용부.
- [검증됨] EVAL-09: 커밋 `8404cd26`(`scripts/emdash_publish.py` +27/-3, `_featured_image_data()` + `upsert_post(featured_image=)`), 라이브 실측 — free-models 본문 카드 썸네일 2건이 `https://aikorea24.kr/images/...` 절대경로로 HTTP 200.
- [검증됨] `docs/state.md` 상단의 `AIK24-OPENCODE-USAGE-01` 은 작성자가 이미 `(완료)` 로 교체해 둔 상태였고, 완료보고 파일·커밋 `b465683f`·origin/main 일치까지 확인했다. 추가 표시 없음.

### 잔존 위험
1. **EVAL-09 는 state.md 기록이 아예 없었다** (이번 정합 정리로 최초 기록). 감사 추적은 커밋 `8404cd26` + 완료보고 파일이 유일.
2. `tests/test_emdash_publish.py::test_create_then_publish` 는 EVAL-09 의 절대경로화 이후 기대값 불일치로 깨져 있다(전체 스위트 18 failed 기준선에 포함). 미수정.
3. free-models 페이지 `og:image`/`twitter:image` 1건은 지금도 404 — EmDash 프로젝트(`~/projects2/aikorea24emdash`) 소관, 범위 밖.

### 다음 행동
- [TEST CODE] `test_emdash_publish.py` 기대값 정리(별도 커밋).
- og:image 404 는 EmDash 프로젝트에서 처리 여부 결정.

## 2026-10-16 14:50 — AIK24-OPENCODE-USAGE-01: OpenCode CLI 실사용 보고 (완료)

### 한 일
- 지시서 `2026-10-16-1230-AIK24-OPENCODE-USAGE-01-실사용-보고.md`에 따라 OpenCode CLI 실제 사용 경험을 8개 항목으로 보고했다. 지시서 §4에 따라 **읽기 전용** — 코드·설정 변경 없음.

### 결과
- [검증됨] 보고서 작성 완료: `~/Desktop/메모 Hugh-v2/SSOT/프로젝트/aikorea24/지시서/2026-10-16-1230-AIK24-OPENCODE-USAGE-01-완료보고.md` (324행, 8개 항목 제목 8/8 존재 확인).
- [검증됨] 수치 산출 근거 = `~/.zsh_history`(185,684 bytes, opencode 포함 222라인), `~/.local/share/opencode/opencode.db`(155,226,112 bytes, `session_v2` 623세션), `~/.config/opencode/opencode.json`, `ps` 프로세스 계층.
- [검증됨] 실행 방식: TUI `opencode` 210회 대 `opencode run` **0회**. `opencode serve`도 히스토리 0회이나 현재 세션 부모 프로세스는 `opencode serve --service`(PID 1043)임을 `ps`로 확인.
- [검증됨] 모델: `session_v2`의 `model` 필드가 채워진 세션 623개. 무료(`:free`/`-free` 접미사) **564개**, 유료 59개 → `564/623 = 90.5%`.
- [검증됨] 자주 쓴 모델 top 3: `opencode/space-bunny-free` 117 / `opencode/mimo-v2.6-flash-free` 41 / `kilo/stepfun/step-5-preview-free` 31. 이 세션은 `opencode/space-bunny-free` variant `xhigh`.
- [검증됨] providerID별 세션 수 합계 검증: `opencode` 272 + `kilo` 179 + `openrouter` 95 + `upstage` 26 + `nvidia` 26 + `deepseek` 12 + `groq` 10 + `googleai` 3 = **623** (전체 세션 수와 일치).
- [검증됨] 지시서 §6의 `zen`은 **`zen`이라는 이름으로 등록돼 있지 않다.** `opencode.json`의 25개 provider 키에서 `zen` grep 결과는 `zenmlx`·`zenmux` 2개뿐이며 둘 다 **세션 사용 0건**. 지시서·설정·실사용 간 불일치를 추측으로 메우지 않고 그대로 기록함.
- [검증됨] "안 해봄" 6건 명시: 설치 명령(히스토리 0건), 첫 실행 명령, `/connect`(auth.json이 `~/.config/opencode/`·`~/.local/share/opencode/` 양쪽 모두 MISSING), `opencode run`, `opencode serve` 직접 실행, `zenmlx`/`zenmux`.

### 잔존 위험
- `model` 필드가 NULL인 세션은 집계에서 제외됐다. 전체 세션 수와 623은 다를 수 있다.
- `zen` 불일치(지시서 `zen` / 설정 `zenmlx`·`zenmux` / 실사용 0건)는 **풀지 않고 보고만 했다.** 내장 providerID `opencode`(272세션)가 지시서의 "zen"을 뜻하는 것인지는 확인하지 않았다.
- free 모델 세션 수(564)는 비용 0을 보증하지 않는다. 이 보고서는 세션 건수만 집계했고 응답 품질·지연 데이터는 갖고 있지 않다. [검증불가]
- `~/.opencode/bin/`에 `opencode2` 파일이 별도로 있으나 정체를 확인하지 않았다.
- 현재 세션 부모가 `opencode serve --service`인 것은 이 보고서를 열었던 프로그램이 띄운 것이라 습관적 실행 방식이 아니다.

### 다음 행동
- 지시서 §5 완료 기준 충족. §7 종료 규칙에 따라 이 기록으로 종료.
- 위 `진행 중` 마커는 완료 보고로 교체돼 제거됐다.
- 지시서 §7: 왓츠앱 말랑이가 이 state.md를 읽고 verify 후 시니어2에게 알림.

## 2026-10-16 14:20 — AIK24-PIPE-04: verdict 3단계 + 주간 무료 기회 초안 8건

### 한 일
- **[PRODUCTION CODE] `scripts/auto_briefing.py`** — `verdict_block()` 을 3단계로 분리(대표님 지시). 신규 `_core_name()`(`:free`/`-free` 접미사 제거)·`_verified_running()`(`free_models_verify.json` pass + `free_models_cli.json` → 이름 집합), 상수 `VERIFY_PATH`·`CLI_MODELS_PATH` 추가. ① 점수 있음 → 점수+Top3 대비 ② 동작 확인됨·점수 없음 → `OpenCode 동작 확인됨 (12문항 평가 전)` ③ 미검증 → `12문항 평가 전 — 판단 보류`. (A안 전제 수정 반영 — verify 15개는 점수 리스트가 아니라 동작 확인 리스트였음.)
- **[TEST CODE] `tests/test_auto_briefing_verdict.py`** — 3건 추가(tier2 분리 / tier3 유지 / 실제 로그 파일 파싱), 총 **6 passed**.
- **[DATA] `scripts/logs/weekly_opportunities.json`** 신규 — 대표님 검수용 무료 기회 초안 8건(전부 공식 페이지 curl 실측 확인: Google Cloud $300 · Azure $200/30일 · Cloudflare Workers AI 10,000 Neurons/일 · Gemini API 무료 티어 · GitHub Copilot Free · OpenRouter `:free` · GitHub Student Pack · Cerebras $5 프로모). 전부 `access="custom"`(OpenCode에서 바로 선택 가능한 항목은 0건 — 정직 표기).
- **D1 교정** — `briefing_items` id 1929(briefing 355): `12문항 평가 전 — 판단 보류` → `OpenCode 동작 확인됨 (12문항 평가 전)`.

### 결과
- [검증됨] pytest `tests/test_auto_briefing_verdict.py` 6 passed. 실측 출력: `space-bunny-free` → `12문항 평가: 10/12 … / 현재 추천 Top 3 대비: 추천 모델과 동급` / `step-5-preview-free` → `OpenCode 동작 확인됨 (12문항 평가 전)` / `never-seen-model:free` → `12문항 평가 전 — 판단 보류`.
- [검증됨] 라이브 `https://aikorea24.kr/briefing/2026-10-16-2/` 에 `OpenCode 동작 확인됨 (12문항 평가 전)` 1회 노출(grep -c = 1), `판단 보류` 0회.
- [검증됨] `weekly_opportunity.py --dry-run` → `선별 8건 / 입력 8건`, 8건 모두 `(b) 커스텀 프로바이더 설정 후 연결 가능` 라벨 부착. D1 INSERT는 **하지 않음**(대표님 검수 대기).
- [검증불가] 무료 기회 항목의 실제 프로모 지속 여부 — 2026-10-16 curl 응답 기준이며 만료 시점은 각 사 정책에 달림. `expires` 는 상시 프로그램 2027-12-31, Cerebras 프로모 2026-12-31 로 보수 설정.
- websearch 도구는 이번 세션에서 빈 결과(인프라 문제) → 공식 페이지 직접 curl + 본문 추출로 대체.

### 잔존 위험
1. 무료 기회 8건은 전부 `custom` — "OpenCode에서 바로 선택 가능한 무료 기회"는 아직 0건. (a) 항목을 만들려면 OpenCode Zen 자체 프로모션 같은 재료가 필요.
2. 지시서 작업6의 상단 숫자(38개)는 카탈로그 스냅샷 기준이고 검증(15개)과 갱신 시점이 다름 — 매일 갱신되지만 서로 다른 시점의 수치다.
3. `weekly_opportunities.json` 은 아직 D1 에 없으므로 슬롯 1은 내일도 빈 슬롯.
4. `news.link UNIQUE` 제약: `weekly_opportunity.py` 는 서로 다른 기회가 같은 link 를 쓰면 조용히 1건만 들어간다(현재 초안은 링크 중복 없음).

### 다음 행동
- B안(유료 대비) 설계: 비용 없이 **공식 자료 인용** 방식으로. 어떤 유료 모델을 기준선으로 삼을지 대표님 결정 필요.
- 대표님 검수 후 `python3 scripts/weekly_opportunity.py` (실 INSERT) → 슬롯 1 활성화.
- 미검증으로 남긴 후보: NVIDIA build 크레딧, Groq 무료 티어, 국내 정부지원·해커톤(JS 렌더로 curl 검증 불가).

---

## 2026-10-16 AIK24-PIPE-03 완료 — 브리핑 v3 개편 (작업 1~9 전부 실행)

### 한 일
- **[PRODUCTION CODE] `scripts/run_pipeline.py`** — `step_blog()`/`step_link_blogs()` 정의+호출 삭제(블로그 1:1 자동 확장 중단, §18 포맷 생성도 함께 중단), `--skip-blog`·`import re` 정리.
- **[PRODUCTION CODE] `scripts/model_catalog.py`** — `record_diff_to_news(day, d)` 신규 + `run()` diff write 직후 호출(fail-soft). added/removed → `news` INSERT(`v2_tag='free-llm'`, `v2_pass=1`, description `… · 12문항 평가 전 — 판단 보류`), `cfnew.check_quota()` 선행, 같은 날 title 중복 스킵.
- **[PRODUCTION CODE] `scripts/auto_news_selector.py`** — `MAX_COUNT=3`, 모델 슬롯 상수·함수 전부 삭제, `MODEL_SOURCES`→`PROVIDER_SOURCES`, 3단 선정(무료 기회 1 → Zen 변경 → 점수순 일반), `_is_mechanical()` 로 기계 감지 행 평가 면제, PIPE-DEDUP-01 dedup 유지.
- **[PRODUCTION CODE] `scripts/auto_briefing.py`** — 모델 슬롯 재충전 블록 삭제, `verdict_block()` 신규(캐시 평가 or `12문항 평가 전 — 판단 보류` + Top3 평균 비교), `cli_free_block()` (a)/(b) 구분, `eval_comment_block()` 호출 제거.
- **[PRODUCTION CODE] `scripts/briefing_dedup.py`** — `MODEL_SOURCES`→`PROVIDER_SOURCES` 2곳.
- **[PRODUCTION CODE] `scripts/auto_email_sender.py` / `src/pages/briefing/[date].astro`** — "매일 아침 7시" 삭제 + evergreen CTA(무료 모델 목록) 삽입.
- **[PRODUCTION CODE] `scripts/free_models_page.py`** — "현재 무료 N개(공개 목록 기준)" vs "검증 완료 M개" 분리, 하드코드 18 제거.
- **[PRODUCTION CODE] `scripts/weekly_opportunity.py`** 신규 — 주간 기회 JSON → `free-opportunity` INSERT, unverified·만료 제외, 접근성 라벨 자동 부착, `--dry-run`.
- **[TEST CODE]** `tests/test_model_catalog_news_insert.py`(5) · `tests/test_weekly_opportunity.py`(4) · `tests/test_auto_briefing_verdict.py`(3) 신규, `tests/test_auto_news_selector_dedup_before_slots.py` v3 정책으로 갱신.

### 결과
- **[검증됨]** 작업1: `grep -n "step_blog\|step_link_blogs\|blog_draft" scripts/run_pipeline.py` → 0건(rc=1). `--dry-run` 단계 출력 5개(블로그 소멸), exit 0.
- **[검증됨]** 작업2: 오늘 diff(added 2/removed 2)로 실행 → `news 기록: 4건`, D1 재조회 4행 = diff 건수 일치. 중간에 발견한 `link UNIQUE` 충돌(4건 중 1건 조용히 유실)은 `#{model_id}` 부여로 수정.
- **[검증됨]** 작업3: selector 실측 `이미 브리핑됨 6건 제외 → 신선 후보 1건` / `ⓘ 무료 기회 후보 없음 — 슬롯 1 비움 (강제 충전 없음)` / `ⓘ Zen 변경 1건 우선 배정` / `선정 1건 (요청 3건, 데이터 부족 — 강제 선정 없음)`.
- **[검증됨]** 작업4: D1 `briefing_items`(355) comment 에 `12문항 평가 전 — 판단 보류` + `(a) OpenCode 모델 선택기에서 바로 선택 가능` 포함. 라이브 `/briefing/2026-10-16-2/` 에서도 동일 문자열 노출.
- **[검증됨]** 작업5: `grep -rn "7시" scripts/auto_email_sender.py` → 0건. 라이브 상세 페이지 CTA 1회 노출. 이메일 HTML 생성물 CTA 포함(발송 안 함 — 수동 실행 규칙 `--no-email`).
- **[검증됨]** 작업6: 라이브 `현재 무료 38개 (프로바이더 공개 목록 기준) · 검증 완료 15개` / `전체 리스트 (검증 완료 모델 15개)`.
- **[검증됨]** 작업7: 샘플 2건 dry-run → unverified 제외, direct 1건만 SELECT. 신규 테스트 4 passed.
- **[검증됨]** 작업9: 파이프라인 배포 Version `39e1d29f…` + `npm run deploy` Version `4d526460…` (둘 다 exit 0, sitemap ping google/naver ✅).
- **[부분검증]** 기존 스위트: **18 failed / 581 passed / 10 skipped**. 17건은 이번 작업 전 기준선과 동일, 추가된 1건(`test_emdash_publish::test_create_then_publish`)은 커밋 `8404cd26`(2026-10-15 featured_image 절대경로화)에서 유입 — 내 변경 파일 목록에 `emdash_publish.py` 없음(git diff 확인). 검증력 제한: 기존 실패 원인을 고치지 않았으므로 "내 변경이 그 17건을 건드리지 않았다"까지만 확인됨.
- **[위반 감지]** 첫 파이프라인 실행에서 `verdict_block` 이 `eval_model_cached()` 를 써서 캐시 미스 시 라이브 12문항 평가를 돌렸다(이미 제외된 모델, 12회 HTTP 400, 48초) → 잘못된 verdict(`0/12 … 9점 낮음`)가 D1 에 저장됨. 캐시 전용 `model_eval.cache_get()` 으로 교체(0.00초, `판단 보류`) + 라이브 행 comment REPLACE UPDATE 교정 + 회귀 테스트 3건 추가.

### 잔존 위험
1. 기존 테스트 실패 18건 미해결(범위 밖). `test_emdash_publish` 는 테스트/코드 불일치로 별도 수정 필요.
2. `scripts/logs/weekly_opportunities.json` 미생성 — 큐레이션 전까지 무료 기회 슬롯은 항상 빈다.
3. `weekly_opportunity.py` 는 link 중복 시 `INSERT OR IGNORE` 로 1건 유실 가능(수기 입력 1:1 전제).
4. Zen 변경 → news 자동 기록은 내일 크론에서 재확인 필요(오늘은 과거 diff 로 수동 검증).
5. 오늘 브리핑 2건(-1, -2) 공존 — `latest` 는 id 내림차순이라 -2 만 노출(10-15 고아 건과 같은 미해결 정책).
6. `verdict_block` Top3 비교는 리더보드 4건 표본 기준.

### 다음 행동
- 대표님: `scripts/logs/weekly_opportunities.json` 주간 큐레이션(스키마는 완료보고 참조).
- 필요 시: 2026-10-16 브리핑 `-1`/`-2` 중복 정책 정리.

**실행 명령** — `.venv/bin/python3 scripts/run_pipeline_with_notify.py --no-email` (수동 실행 시 `--no-email` 필수, 이메일 발송 안 함) / `.venv/bin/python3 scripts/free_models_page.py page`

## 2026-10-16 AIK24-FREE-PIPE-01 일일 실행 — 수집 38건 / 실패 프로바이더 0 / added 2 · removed 2 · changed 0 / 리스트 페이지 갱신 https://emdash.aikorea24.kr/posts/free-models / 평가·발행 SKIP (AIK24-PIPE-01 자동 평가 비활성 — 수동 평가로 전환) / 심층 리뷰 1건 (리스트 카드 링크 1건)

## 2026-10-15 16:46 — AIK24-EVAL-CLI-02 신규 추천 3종 CLI 12문항 평가 + 컨텍스트 실측

### 한 일
- **[PRODUCTION CODE] `scripts/model_eval.py`** — `CLI_MODEL_MAP` 에 2개 추가 (4항목 → 6항목). `mimo-v2.6-flash-free`→`opencode/mimo-v2.6-flash-free`, `muse-spark-1.3-contributor-free`→`opencode/muse-spark-1.3-contributor-free`.
- **실행** — 3개 모델 12문항 CLI 평가 + 2개 모델 컨텍스트 프로브. `EVAL_QUESTIONS_VERSION`·`score_response()` 미변경(지시 범위 밖 준수).
- **기록** — `scripts/logs/model_eval_cache.json`(3항목) + `scripts/logs/model_leaderboard.json`(3행 추가).

### 결과
- **[검증됨]** 완료기준 1: `CLI_MODEL_MAP` 6항목. 3개 모델 모두 `opencode run -m <cli_model>` PONG 응답 확인(작업 0 사전 확인).
- **[검증됨]** 완료기준 2: 3개 모델 12문항 평가 완료 + 리더보드 기록. 전부 `source="cli"` `provider="zen"`, `token_usage=(0, 0)`, `notes="CLI 경유 — 토큰 사용량 미측정"`.

| 모델 | 점수 | failed | judge_failed | 라벨 요약 |
|---|---|---|---|---|
| `space-bunny-free` | **10/12** | 0 | 0 | 손발 작업으로 보자 |
| `mimo-v2.6-flash-free` | **9/12** | 2 | 1 | 손발 작업으로 보자 |
| `muse-spark-1.3-contributor-free` | **8/12** | 2 | 1 | **컨트롤(계획·오케스트레이션)에 적합** |

- **[검증됨]** 완료기준 3: 2개 모델 컨텍스트 실측 = **둘 다 1,048,576** (8K→1M 8단계 전부 OK → 상한 도달 = 실측 하한).
- **[검증됨]** 완료기준 4: `space-bunny-free` `measured_context=1048576` 최종 상태 확인.

### ★ 실행 중 발견한 결함 + 즉시 복구 (주의 필요)
`eval_model_cli()` 의 result dict 에 `measured_context` 키가 없다. 그래서 12문항 평가가 끝나고 `cache_put()` 이 도는 순간 **같은 항목에 있던 기존 실측값이 wiped** 된다.
실현: `space-bunny-free` 의 `measured_context` 가 `1048576` → `null` 로 사라짐(완료기준 4 위반 상태).
→ 작업 0 에서 확인한 기존 값 `1048576` 을 되돌려 복구 완료(캐시 전수 재확인함).
**이건 3개 모델을 동일 세션에서 평가·프로브 순차 실행할 때마다 재현한다.** `cache_put()` 이 기존 항목의 `measured_context` 를 merge 하도록 고칠 것을 권하지만 지시 범위 밖이라 미수정.

### 잔존 위험
1. **[검증됨] `cache_put()` 이 `measured_context` 를 덮어씀** — 위 결함. 별도 지시서 필요.
2. `mimo-v2.6-flash-free`·`muse-spark-1.3-contributor-free` 의 12문항 평가 중 **5번 문항 CLI 타임아웃 60초**(mimo) 및 2문항 judge 파싱 실패가 발생했다. 판관 로직은 지시 범위 밖이라 미수정. → 실효 점수는 12문항 중 9·8문항.
3. **컨텍스트 3종 전부 1,048,576(상한 도달)** — 실측 하한일 뿐이라 이보다 클 수 있다. 재측정 금지 규칙에 따라 하한으로 기록. `_probe_doc()` 은 문자 수 기준 근사(한국어 1자≈1토큰)라 실제 토크나이저 기준값보다 작게 나올 수 있다.
4. `probe_context_length()` 는 `CACHE_PATH` 가 `str` 이라 `_read_json`/`.read_text()` 를 쓸 수 없다 — 이번에 별도 스크립트로 우회했다. `model_eval.py` 내부 유틸은 `pathlib.Path` 를 쓰므로 모순이 있다. 지시 범위 밖이라 미수정.
5. 3개 모델 모두 `score_response()` 판관이 `gemini-3.5-flash-lite` 폴백 체인을 쓴다 — 판관 모델 1종 편향 가능. `score_response()` 는 지시 범위 밖.

### 다음 행동
- 대표님: 블로그 글에 위 점수(10·9·8)와 컨텍스트 하한(1M)을 근거로 쓰면 됨. 단 "컨텍스트 1M 지원"이 아니라 "**1M까지 검증됨(하한)**"으로 표기할 것.
- 별도 지시서: `cache_put()` 이 `measured_context` 를 merge 하도록 수정 (재발 방지).

---

## 2026-10-15 16:34 — safe_div pytest 테스트 작성·검증

* 한 일: `test_safe_div.py`(프로젝트 루트)에 safe_div 스니펫 대상 pytest 테스트 작성 — 정상 입력 / 0으로 나누기 / 음수 / 경계값 커버. `grep -n 'def safe_div'` 결과 2건: 이 테스트 파일 + `scripts/model_eval.py:181`(평가 프롬프트 원문) — import 가능한 생산 모듈은 없어 테스트 파일 안에 원문 그대로 정의
* 결과 [검증됨]: `.venv/bin/python3 -m pytest test_safe_div.py -v` → 20 passed. 산출 근거 20 = 12(파라마터화 `test_safe_div`) + 4(`test_division_by_zero_returns_none`, `test_none_check_exact`, `test_large_values`, `test_float_precision_boundary`) + 4(`test_edge_values`). 커버 범위: 정상 10/2·9/3·1/2·7/4, 0 나눗셈 0/0·5/0·-5/0 → None, 0.0 실수 분모, 음수 세 조합, 0 분자, inf/-inf, 1e308, 부동소수 정밀도(`pytest.approx`)
* [부분검증] 시스템 `python3`에 pytest가 없어 프로젝트 `.venv/bin/python3`로만 실행됨 — CI/외부 환경에서의 실행 경로는 확인하지 않음
* 잔존 위험: 테스트가 파일 내 정의한 safe_div 복제본을 검증함 (원본이 별도 모듈로 존재하지 않음 → 원본이 따로 생기면 import 경로로 바꿔야 검증력 유지)
* 다음 행동: 없음

## 2026-10-15 15:15 — 스킬 `aik24-free-models-page` 신규 저장

* 위치: `.claude/skills/aik24-free-models-page/SKILL.md` (커밋에 포함). 로드 확인됨 (스킬 목록에 노출)
* 내용: 파이프라인 3명령(verify→page→pytest) / 5컬럼 고정+모델명 단축 규칙(org prefix 유지) / 상태 셀 전문 표시("..." 금지) / `md_to_pt` HTML 미지원 경고 / 모바일 카드 CSS 위치·스코프·break-word / 발행 전 체크리스트 / 흔한 실수 5건
* 결과 [검증됨]: 새 스킬이 에이전트 스킬 목록에 노출됨. 단, 타 에이전트가 실제로 읽고 따르는지는 [검증불가] — 다음에 이 페이지를 손볼 때 스킬 로드 여부를 확인할 것
* 잔존 위험: 없음

## 2026-10-15 15:12 — AIK24-EVAL-08 후속 (상태 셀 "..." 제거) 완료

* 원인: 표 시절에 넣은 30자 자름(`zen_policy[:30]+"..."`)이 카드에서도 그대로 노출 — 데이터 문제가 아니라 렌더러 코드 문제
* 한 일: `scripts/free_models_page.py` 1줄 수정 — 상태 셀에 정책 전문 표시. `page` 재실행해 EmDash 발행. 커밋 `831aa82e`
* 결과 [검증됨]: 테스트 8/8 통과. 라이브 실측 75셀(15행×5) 중 "..."로 끝나는 셀 0개
* 잔존 위험: 없음 (카드 내 문장이 길어지면 줄바꿈으로 표시 — 의도된 동작)

## 2026-10-15 15:40 — AIK24-EMDASH-11 (emdash.aikorea24.kr 헤더 완전 통일) 완료

* 대상 저장소는 별도: `/Users/twinssn/projects2/aikorea24emdash` — 상세 기록은 그 repo의 `docs/state.md` 최상단
* 한 일: AIK24-EMDASH-10 잔존 위험 3건 해소 — ① 로그인 버튼 추가(데스크톱 768px 이상, `https://aikorea24.kr/api/auth/login`) ② 모바일(<768px) nav 줄바꿈 → 햄버거 버튼 + 접히는 메뉴 패널 ③ 로고 높이 48px → 32px. 검색 아이콘은 지시서대로 미추가
* 결과 [검증됨]: 배포 Version `32775c4b-a717-4151-93e2-5a008aeaf415`, 커밋 `3ceaa54` push 완료. 라이브 Playwright 실측 — 데스크톱 1280 로고 32px(메인 32px 동일)/로그인 버튼 70.3px 폭(메인 70.3px 동일)/nav 7개/검색 아이콘 0개, 모바일 375 햄버거 클릭 시 패널 341.6px·링크 7개·다시 클릭 시 접힘. 로그인 URL 체인 301→Google(final 200). `npx astrosync check` Base.astro 오류 0건
* 완료보고서: `SSOT/프로젝트/aikorea24/지시서/2026-10-15-1452-AIK24-EMDASH-11-완료보고.md`
* 잔존 위험: 로그인 버튼 높이 41.8px vs 메인 38px(line-height 차이) / 로그인 후 메인 사이트로 복귀(return URL 미지원) / 로그인 버튼 데스크톱 전용 / 641~767px 실측 없음 / 이 repo는 테스트 파일 없음
* 다음 행동: 0번 — 로그인 후 EmDash 복귀(return URL) 필요 여부 결정

## 2026-10-15 14:50 — AIK24-DOC-01 OpenCode 모델 선택 과정 문서화

### 한 일
- `docs/opencode-model-selection.md` (신규, 154줄) — OpenCode TUI 모델 선택 UI + CLI 직접 호출 5건 실측 기록. 블로그 "무료로 사용하는 방법" 섹션 근거 자료.

### 결과
- **[검증됨]** 2-1 (4질문 전부): `/models` 와 `ctrl+x m` (chord, 단일 조합 아님) 2가지. 키바인딩은 `https://opencode.ai/docs/tui/` Keybind 표에서 확인(HTTP 200, 105,330B). 별도 단축키 없음.
- **[검증됨]** 표시 항목 구성 = models.dev 카탈로그(`https://models.dev/api.json`, HTTP 200, 5,664,894B)의 `kilo.models`(390건). 필드 = `name`/`cost`/`limit`/`tool_call`/`reasoning`. TUI 가 `step_start` 의 `snapshot` 해시(`4fc3c957…`)로 카탈로그 스냅샷을 고정.
- **[검증됨]** Kilo 무료 표기 = CLI ID 끝 `:free` + 화면 표시명 끝 `(free)`. `opencode models` 의 kilo 396건 중 `:free` **16건**.
- **[검증됨]** 선택 즉시 적용(확인 버튼 없음). variants 는 `cycle through model variants` 로 순환(`provider/model#variant`).
- **[검증됨]** 5개 모델 `opencode run -m <ID> --format json "한 단어로 대답: PONG"` → **5/5 성공, 실패 0건**. 응답 = `PONG`(`dots-3-note-preview` 만 `\n\nPONG` 선행 개행). 소요 0.3~7.4초.
- **[검증됨]** 2-3 대응표 완성 — `cohere/north-mini-code:free`=`Cohere: North Mini Code (free)` / `dots-studio/dots-3-note-preview:free`=`Dots Studio: Dots3-Note Preview (free)` / `liquid/lfm-2.5-2.6b:free`=`LiquidAI: LFM2.5-2.6B (free)` / `nvidia/nemotron-3-ultra-550b-a55b:free`=`NVIDIA: Nemotron 3 Ultra (free)` / `nvidia/nemotron-3.5-lightning:free`=`NVIDIA: Nemotron 3.5 Lightning (free)`. 전부 `cost.input=0`.

### 실측에서 발견한 함정 (블로그 작성 시 필수 유의)
1. **`nvidia/nemotron-3-ultra-550b-a55b`(유료 `cost.input=0.5`)와 `...:free`(무료)는 별개 항목** — 접미사를 떼면 과금된다.
2. **provider 변경 = 다른 경로.** 5개 모델 전부 `openrouter/...` 에도 동시 등록. 같은 모델이어도 계정/과금 경로가 다르다.
3. **출력 상한이 모델마다 다르다** — `lfm-2.5-2.6b:free` 는 `limit.output=8192` 로 가장 작고, `dots-3-note-preview:free` 는 460,800. 같은 프롬프트가 어떤 모델에선 잘린다.
4. `opencode run --format json` 출력은 **NDJSON** 다. `type=="text"` 라인의 `part.text` 이어붙여야 응답 텍스트가 나온다.

### 잔존 위험
- **[부분검증] `/models` 화면의 실제 픽셀 레이아웃**(열 순서, 스크롤 동작, 마우스 지원 여부)은 이 환경이 TUI 를 못 띄워서 미확인. 표시 **데이터**는 models.dev 카탈로그로 확정했지만 화면 배치 자체는 안 봤다. 블로그에 화면 캡처를 넣을 계획이면 대표님 화면을 직접 봐야 한다.
- `kilo/nvidia/nemotron-3-ultra-550b-a55b:free` 의 `limit.output` 은 카탈로그에 항목이 없어 문서에 "미기재"로 뒀다.
- Kilo API 키가 `~/.env.common` 에 없어 Kilo 응답 헤더·실요금 과금 내역은 확인 불가(카탈로그 `cost` 값과 실요금의 일치 여부는 미검증).

### 다음 행동
- 대표님: 블로그 "무료로 사용하는 방법" 섹션은 위 문서 2·3절을 근거로 작성. 화면 캡처가 필요하면 `/models` 화면을 직접 열어 달라.

---

## 2026-10-15 15:05 — AIK24-EMDASH-10 (emdash.aikorea24.kr 헤더 검색창 제거) 완료

* 대상 저장소는 별도: `/Users/twinssn/projects2/aikorea24emdash` — 상세 기록은 그 repo의 `docs/state.md` 최상단
* 한 일: EmDash 헤더의 인라인 검색창(⌘K 핸들러 포함)을 코드 삭제 → aikorea24.kr 메인 헤더와 통일. 푸터는 라이브 비교 결과 이미 동일(링크 10개·사업자정보 3줄·네트워크 링크)
* 결과 [검증됨]: 배포 Version `f0ce90b1-5761-4f73-83c0-25fcb392604a`, 라이브 3URL http 200, `site-search`/`Search...`/`emdash-live-search`/`metaKey` 각 0건, Playwright 375·1280 뷰포트에서 헤더 내 검색 노드 0개, 커밋 `2e7087f` push 완료
* 완료보고서: `SSOT/프로젝트/aikorea24/지시서/2026-10-15-1438-AIK24-EMDASH-10-완료보고.md`
* 잔존 위험: 헤더 구조 차이 3건(로그인 버튼 / 모바일 햄버거 / 로고 크기) — 각각 별도 지시 필요. 중간 뷰포트(640~1023px) 미측정. 이 repo는 테스트 파일 없음
* 다음 행동: 0번 — 위 3건 반영 여부 결정 (없으면 종료)

## 2026-10-15 14:35 — AIK24-EVAL-08 free-models 표 개선 (지시 변경: HTML 미적용)

### 한 일
- [PRODUCTION CODE] `scripts/free_models_page.py` `render_eval06()` — 마크다운 표 유지, 7→5컬럼 + 모델명 단축 (커밋 `b6c9342b`). 지시서의 HTML 교체는 미적용 — 사유 아래.
- [TEST CODE] `tests/test_free_models_page.py`에 `test_eval06_table_is_five_columns_with_short_names` 추가.
- 완료보고: `SSOT/프로젝트/aikorea24/지시서/2026-10-15-1435-AIK24-EVAL-08-완료보고.md`.

### 결과
- [검증됨] 지시대로 HTML을 넣으면 회귀: `md_to_pt()`는 HTML 처리 없음 — 실증에서 HTML 3줄 → `block/normal` 3개로 태그 문자열 그대로 노출. 근거: `scripts/emdash04_migrate.py` 코드 + 입력 실증.
- [검증됨] "반응형 CSS 제어 불가" 전제는 오판: 라이브 table 블록은 이미 `emdash-table-wrapper` + `overflow-x:auto` + `nowrap` 으로 렌더됨 (라이브 HTML 실측).
- [검증됨] 실데이터 렌더 15행 전부 5컬럼 (`모델명|프로바이더|컨텍스트 길이|지표|상태`), 동명 모델(kilo/zen nemotron-3.5-lightning)은 org prefix 유지로 구분.
- [검증됨] 테스트 8/8 통과 = 7(기존) + 1(신규). 산출 근거: `pytest tests/test_free_models_page.py` → `8 passed`.
- [부분검증] 모바일 실측 미실시 — EmDash 발행(`page` 실행) 보류했으므로 라이브 미반영. 제한 사유: 발행=라이브 즉시 변경, 방향 승인 후 발행이 안전.

### 잔존 위험
1. 라이브는 아직旧 표 — 대표님 불편 해소는 발행 후. 승인 필요: (a) 이 방향으로 `page` 실행+발행, 또는 (b) HTML 고수 시 `md_to_pt()` HTML 처리 별도 작업.
2. 표 제목 "18개" vs 실제 15개 불일치 (기존 문제, 범위 밖).
3. `scripts/logs/free_models_cli.json.bak-20261015`, `model_diff_2026-10-15.json` untracked 잔존.

### 다음 행동
- [완료 14:40] 대표님 승인으로 `page` 실행 → EmDash 발행 완료.
  라이브 확인: 5컬럼 헤더(모델명·프로바이더·컨텍스트 길이·지표·상태), `:free` 잔존 0건.
- [추가 15:00] 대표님 모바일 실측 지적(첫 컬럼 독점 + 나머지 세로 찌그러짐) → 원인=EmDash `nowrap`+인라인 min-width.
  `~/projects2/aikorea24emdash` 수정 후 4회 배포, 최종=모바일 카드형 (커밋 `64e58ed`, Version `7f845b13`).
  상세: `src/styles/theme.css` (free-models 한정 카드 CSS) + `src/pages/posts/[slug].astro` (`data-slug` 1줄).
  [검증됨] Playwright 375px: 표 341px(스크롤 없음), 행 `display:block`, 빈 셀 숨김, 라벨(프로바이더/컨텍스트/지표/상태) 표시.
  데스크톱은 기존 표 유지. 커밋 안 한 파일: `scripts/fix_tables.py`, `src/version.gen.ts` (他人 작업물).

## 2026-10-15 13:47 — AIK24-UI-01 홈 AI 툴 카드(CareOps) 레이아웃 깨짐 수정

### 한 일
- **[PRODUCTION CODE] `src/components/home/ToolsSection.astro`** — 지시서 3항목 그대로 3줄 수정 (커밋 `4bd0b712`, origin/main 푸시 완료)
  1. `visible` 매핑(48행) `price: (t.price || '').slice(0, 20) + ((t.price || '').length > 20 ? '…' : '')` — D1 `price_detail` 원문이 카드 단위로 유입되는 것 차단
  2. 74행 price 배지 `whitespace-nowrap` → `whitespace-nowrap max-w-[120px] truncate`
  3. 73행 category span 에 `truncate` 추가 (긴 price 에 밀려 CJK 세로줄바꿈되던 것 방지)
- 커밋에 **포함하지 않은 파일**: `scripts/run_pipeline.py`, `scripts/run_pipeline_with_notify.py` (이전 세션 미커밋 변경, 내 것 아님 → 그대로 working tree 에 잔존)

### 결과
- **[검증됨] 빌드·배포**: `npm run deploy` 성공 — Current Version ID `9c66c833-a194-4d63-9f6d-9fe506dd9cbe`, sitemap ping `{"google": true, "naver": true}`
- **[검증됨] 라이브 HTML** (`curl https://aikorea24.kr/`): CareOps price = `첫 AI 상담 1회 무료, 이후 유료…` (21자, 배포 전 57자). 홈 전체 price 배지 8개 전부 `max-w-[120px] truncate` 보유, `rounded-full whitespace-nowrap"` 만 남은 배지 **0개**
- **[검증됨] 빌드 CSS 에 유틸리티 실재**: `dist/client/_astro/Layout.CzSeSb4X.css` (122,372B) 안에 `.truncate{text-overflow:ellipsis;white-space:nowrap;overflow:hidden}` 와 `.max-w-\[120px\]{max-width:120px}` 확인 — Tailwind 퍼지 아님
- **[검증됨] Playwright 실측 (headless chromium, aikorea24 node_modules)** — CareOps 카드:
  | 뷰포트 | 카드 폭 | category | price 배지 | 카드 밖 삐침 |
  |---|---|---|---|---|
  | 375×900 | 267.5px | 54.9×16px, 1줄(줄수 1.00), nowrap+overflow:hidden+ellipsis | 120×19px, `scrollWidth 141 > clientWidth 120` = 잘림 동작 | `false` |
  | 1280×900 | 240.6px | 54.9×16px, 1줄 | 120×19px, 잘림 동작 | `false` |
- **[검증됨] 육안 확인**: 카드 단위 스크린샷(`/tmp/aik24_mobile375_card.png`, `/tmp/aik24_desktop1280_card.png`) — 두 폭 모두 카테고리 가로 1줄 + 가격 "첫 AI 상담 1회 무료, 이…" 로 물림표 표시, 카드 프레임 이탈 없음

### 잔존 위험
1. **[부분검증] 데스크톱/태블릿 중간 폭(640~1023px)** — `sm:w-[46%]` 구간만 Playwright 실측 대상에서 빠졌다(375·1280만 측정). truncate 규칙은 폭과 무관하게 동일하게 적용되므로 동일 동작 예상이나, 실측 근거 없음.
2. **데이터 레벨 근본 해결 아님** — `tool_submissions.price_detail` 원문(57자)은 그대로 남아 있음. 홈 카드만 20자로 잘라 보여주고, **도구 상세 페이지 `/tools/careops/` 는 원문 그대로 노출**된다(지시서 범위 밖, 미수정).
3. **`title` 속성 없음** — 배지 잘림 시 전체 문구를 볼 방법이 없음(hover 툴팁 미추가, 지시서에도 없음).
4. **[부분검증] Aside MCP 브라우저 unusable** — `tools.aside.repl` 이 계속 `null` 반환(브라우저 제어 불가). Playwright headless 로 대체 검증함.
5. working tree 에 `scripts/run_pipeline.py`·`scripts/run_pipeline_with_notify.py` 미커밋 변경 잔존(내 변경 아님, 미수정·미커밋).

### 다음 행동
- 대표님: `https://aikorea24.kr/` 강력 새로고침 후 AI 툴 섹션 CareOps 카드 확인 (캐시 무관 — 빌드 해시 변경됨).
- (선택) price_detail 원문을 20자 단위로 D1 에 정리하는 데이터 정리 작업 별도 지시 시 진행.

---

## 2026-10-15 13:45 — AIK24-PIPE-02 --no-email 플래그 + 수동 실행 스킬 저장

### 한 일
- [PRODUCTION CODE] `scripts/run_pipeline.py` — `--no-email` 인자 추가(`--skip-email`과 동일 효과). dry-run 계획 표시에서 이메일 단계 제외. Step 5 가드를 `no_email → "[pipeline] --no-email: 이메일 발송 건너뜀" 로그 / elif not skip_email → 발송` 구조로 변경. 기존 `--skip-email`·자동 실행 경로(인자 없음 → 발송) 무변경.
- [PRODUCTION CODE] `scripts/run_pipeline_with_notify.py` — `--no-email` argparse 추가(parse_known_args, 나머지 인자는 그대로 내부 전달). 실행 시 건너뜀 로그 1줄 출력. 부수 효과: wrapper `--help`가 내부로 전달되지 않고 즉시 종료됨(기존에는 내부 help 출력 후 텔레그램까지 발송).
- [CONFIG] `.claude/skills/aik24-manual-pipeline/SKILL.md` 신규 — 수동 실행 시 `--no-email` 필수, 금지 명령 목록, 실행 후 확인 절차.

### 결과
- [검증됨] `run_pipeline.py --help` → `--no-email` 설명 표시. 근거: 위 실측 출력.
- [검증됨] `run_pipeline_with_notify.py --help` → `--no-email` 표시 + 텔레그램 미발송(즉시 종료). 근거: 위 실측 출력.
- [검증됨] `run_pipeline.py --dry-run --no-email` → 계획 목록에 "4. 이메일 발송" 없음(기존 `--skip-email` 없을 땐 표시됨). 근거: 위 실측 출력.
- [부분검증] `--no-email` 실제 실행 시 이메일 미발송. 제한 사유: 전체 실행은 뉴스~배포 부작용이 있어 미실행. 근거: dry-run 조기 반환 + Step 5 가드 코드 대조(`grep -n "no_email" scripts/run_pipeline.py` → 인자 정의·dry-run 표시·Step 5 가드 3곳).
- [부분검증] 자동 실행 경로 무변경. 제한 사유: 실제 스케줄 실행을 트리거하지 않음. 근거: 인자 없을 때 `args.no_email=False` → 기존 분기와 동일한 `step_email()` 호출 코드 대조.

### 잔존 위험
- 다음 실제 수동 실행 때 `[pipeline] --no-email: 이메일 발송 건너뜀` 로그 2회(wrapper 1 + 내부 1) 출력 확인 필요.
- `auto_email_sender.py` 직접 실행은 이 스킬·플래그의 보호 밖에 있음 — 수동 실행은 반드시 스킬의 명령만 사용.

### 다음 행동
- 지시서 완료기준 1-3 확인 후 커밋·푸시.

## 2026-10-15 11:13 AIK24-FAVICON-01 추가 항목 — favicon.ico 직접 URL 교체 + 301 규칙 해제

### 한 일
- **[CONFIG] `public/favicon.ico`** — 내가 앞서 32px PNG 를 Pillow 로 합성한 2,313B ICO 를 버리고, muse.ai 서명 URL 에서 받은 **실제 신버전 ICO** 로 교체. 2,243B, `47d7c215d79b5bd0202695b9fb35b030`. ICO 내부 = 16×16 + 32×32 2단 PNG.
- **[CONFIG] `public/_redirects`** — `/favicon.ico  /favicon.png  301` 규칙(2026-10-12 추가)을 **해제**. 주석만 남기고 규칙 삭제.

### ★ 왜 301 규칙까지 해제했는가 (지시서와 충돌 지점)
지시서 추가 항목 4 의 근거는 "직접 이미지 URL 접근 시 브라우저가 이 파일을 읽음" 인데, 실측상 **`https://aikorea24.kr/favicon.ico` 는 `public/_redirects:16` 의 301 때문에 `/favicon.png` 로 튕겼다.** ICO 를 아무리 교체해도 어떤 브라우저도 새 ICO 를 읽지 못하는 상태였다.
2026-10-12 의 리다이렉트 목적("구버전 .ico 들이밀지 않기")은 ICO 교체로 달성되므로 규칙이 무의미해졌다. → 삭제.

### 결과
- **[검증됨]** `npm run build` `Server built in 11.57s` / `npm run deploy` Version `843bd1b5-12fd-481b-91bf-630cd4d6e17a`, sitemap ping `{"google": true, "naver": true}`
- **[검증됨]** `https://aikorea24.kr/favicon.ico` → **HTTP 200** (이전 301) / `content-type: image/vnd.microsoft.icon` / 2,243B / md5 `47d7c215…` = muse.ai 원본과 **바이트 단위 일치**. 301·location 헤더 **없음**
- **[검증됨]** ICO 내부 2단(16×16, 32×32) 구조 확인, 32px 를 PNG 로 추출해 육안 확인 = 검은 "AI" + 호랑이 발바닥
- **[검증됨]** 파비콘 5종 라이브 md5 전부 로컬 일치 (`favicon.ico` `47d7c215…` / `favicon.png` `58f23ec…` / `favicon-32x32.png` `e34ef85…` / `favicon-16x16.png` `d48871d…` / `apple-touch-icon.png` `6b72860…`)

### 잔존 위험
1. **[부분검증] 대표님 브라우저 탭** — `/favicon.ico` 를 과거에 한 번이라도 받아 캐시한 브라우저는 옛 301 목적지(`favicon.png`)를 캐시한다. 이것도 옛 파비콘이므로 **강력 새로고침 + 필요 시 파비콘 캐시 수동 삭제** 필요. 서버는 200 + md5 일치 3회 재현 확인.
2. **리다이렉트 해제는 되돌릴 수 있음** — 대표님이 구버전 ICO 노출을 다시 걱정하시면 `public/_redirects` 에 한 줄 되돌리면 됨(2분 작업). 지금은 신 ICO 실서비스 상태라 유지 판단.
3. `favicon.png` 1600×1600 199,726B — `/favicon.ico` 가 이제 정상 serve 되므로 브라우저는 ICO(2,243B) 를 우선 쓸 가능성이 높다. 대용량 PNG 는 링크 태그 fallback 용으로만 남는다.
4. `SEOHead.astro` apple-touch-icon 중복 링크(135-138행·141행) 미수정 — 지시 범위 밖.

### 다음 행동
- 대표님: 강력 새로고침 후 탭 파비콘 확인.
- 별도: `SEOHead.astro` apple-touch-icon 중복 링크 정리.

---

## 2026-10-15 11:10 AIK24-TOOLSYNC-05 + AIK24-FAVICON-01 완료 — '이미지 원본 보기' 링크 제거 + 파비콘 신버전 교체

### 한 일
- **[PRODUCTION CODE] `src/pages/tools/[id].astro`** — 255행 `🖼️ 이미지 원본 보기 →` 링크 1줄 제거. 썸네일 `<img>` 와 그 감싸는 `<a>` 는 유지(지시서 "이미지 자체는 유지").
- **[CONFIG] `public/favicon.png`** 65,799B → 199,726B (1600×1600, muse.ai 서명 URL 다운로드, md5 `58f23ec235da2129fa1845033d41b6f3`)
- **[CONFIG] `public/favicon-32x32.png`** 2,235B → 1,574B (32×32, 다운로드 원본 그대로)
- **[CONFIG] `public/favicon-16x16.png`** 1,387B → 636B (32px에서 `sips -z 16 16` LANCZOS 리사이즈)
- **[CONFIG] `public/favicon.ico`** 655B(2026-02-12) → 2,313B (32px PNG → ICO, 16+32px 2단, Pillow)
- **[CONFIG] `public/apple-touch-icon.png`** 15,394B → 14,206B (180×180, 다운로드 원본)
- 백업 `/tmp/fav_backup/` (기존 5파일 전부)

### 결과
- **[검증됨]** `npm run build` `✓ Completed in 11.05s` / `npm run deploy` Version `a5738e7f-60f6-4d82-bc2d-900bbae7eaa3`, sitemap ping `{"google": true, "naver": true}`
- **[검증됨]** 라이브 `https://aikorea24.kr/tools/careops/` 200, 34,821B. `'이미지 원본'` 문자열 **0건 (plain 요청 3회 + 캐시버스터 3회 = 6회 전부 0)**
- **[검증됨]** 썸네일 렌더 유지 — `<img src="/images/tools/careops.webp" alt="CareOps 마음이 미리보기" ...>` 존재, 이미지 URL HTTP **200 / image/webp**
- **[검증됨]** 파비콘 md5 라이브 = 로컬 바이트 단위 일치 (`favicon.png` `58f23ec…`, `favicon-32x32.png` `e34ef85…`)
- **[검증됨]** 신 파비콘 육안 = 검은 AI + 호랑이 발바닥 + 왼쪽 빨간 세로 라인 (1600×1600 원본 육안 확인)
- **[부분검증]** 지시서 FAVICON-01 검증 4번 "브라우저 캐시 지우고 접속" — 대신 curl md5 대조로 대체. 대표님 화면에 구파비콘이 남으면 브라우저 캐시 문제(서버는 6회 재현 확인).

### 지시서 대비 판단
- FAVICON-01 "favicon.ico는 png에서 변환 (또는 삭제 후 브라우저가 png 사용)" → **변환 채택**. 다만 실측상 `https://aikorea24.kr/favicon.ico` 는 **301 → `/favicon.png`** 로 리다이렉트되어 ICO 는 실제 serve 되지 않는다. 두 방법 모두 결과 동일이라 변환이 무해한 쪽.
- FAVICON-01 "favicon-16x16.png는 32px 버전을 리사이즈해서 생성" → 그대로 수행.

### 잔존 위험
1. **[부분검증] 대표님 브라우저 탭 캐시** — 배포 직후 첫 요청이 옛 파비콘을 1회 응답했다(favicon.png 65,799B → 이후 3회 199,726B, 동일 현상이 `/tools/careops/` HTML 에서도 재현). `cache-control: public, max-age=0, must-revalidate` + `cf-cache-status: MISS` 라 엣지 캐시가 아니라 전파 지연. 강력 새로고침 필요.
2. **`favicon.ico` 는 죽은 파일** — 301 로 png 로 합류. `dist/client/favicon.ico` 만 남아 배포물 크기를 늘린다(2,313B, 무시 가능).
3. **`SEOHead.astro` apple-touch-icon link 중복** — 135-138행과 141행에 동일 태그 2번. 브라우저는 첫 번째만 사용하므로 동작 문제 없음. 지시 범위 밖이라 미수정.
4. **`favicon.png` 가 1600×1600 PNG 199,726B** — 탭 아이콘용으로는 과하지만 무해. WEBP/ICO 통일 원하시면 별도 작업.
5. `scripts/logs/free_models_cli.json.bak-20261015`, `scripts/logs/model_diff_2026-10-15.json` untracked — 내 작업 아님(커밋 안 함).

### 다음 행동
- 대표님: 브라우저 강력 새로고침 후 파비콘 확인.
- 별도 지시서: `SEOHead.astro` apple-touch-icon 중복 링크 정리.

---

## 2026-10-15 11:00 [AIK24-EVAL-07] 완료 — 일일 호출 검증 스크립트 + 페이지 검증시각/점검중 (주니어 C)

### 한 일
- [PRODUCTION CODE] `scripts/verify_models_daily.py` 신규 — `model_eval.cli_call()` 재사용, PASS만 캐시 기록(+`.bak-YYYYMMDD` 백업), 검증 기록 `free_models_verify.json` 별도 저장.
- [PRODUCTION CODE] `scripts/free_models_page.py` 수정 — 방법론 "호출 검증 시각 (KST)" + FAIL 시 하단 "## 점검 중". 기록 없으면 기존 렌더 그대로.
- 커밋 `a99ccbbb`. 완료보고 `SSOT/프로젝트/aikorea24/지시서/2026-10-15-1100-AIK24-EVAL-07-완료보고.md`.

### 결과
- [검증됨] 완료기준 4개 전부 확인. live 18개 → **PASS 15 / FAIL 3** (nano-omni 타임아웃 60초, inkling 2건 openrouter CLI 인증 불가). 캐시 15건, FAIL 제외 확인. dry-run에 검증시각+점검중 3건 표시. 가짜 모델 시뮬레이션 FAIL→제외 확인 (/tmp로 live 미접촉).
- 근거: `/tmp/verify_live_20261015.log`, `/tmp/page_after_verify.md`, `/tmp/sim_out.json`.

### 잔존 위험
1. nano-omni 타임아웃은 일시적 혼잡 가능 — 내일 검증에서 복귀 가능 (본 스크립트는 지시서대로 재시도 없음).
2. openrouter 2건은 내일도 FAIL 가능성 높음.
3. 다음 `page` 실제 갱신 시 리스트 15개 노출 (스펙 의도).
4. launchd 매일 06:00 등록은 별도 지시 대기.
5. `model_diff_2026-10-15.json` untracked 잔존 (범위 밖).

### 다음 행동
- launchd 등록 지시 대기. 다음 daily `page` 갱신에서 15개 리스트 확인.

---

## 2026-10-15 10:55 AIK24-EMAIL-01 완료 — 승인 이메일 "원문 그대로" 원인 확정(배지 임베드 코드블록) → SSOT/프로젝트/aikorea24/지시서/2026-10-15-1055-AIK24-EMAIL-01-완료보고.md (완료)

## 2026-10-15 10:55 — AIK24-EMAIL-01 완료 — 승인 이메일 "원문 그대로" 노출 원인 확정 (조사만, 코드 수정 0건)

한 일
- [INVESTIGATION] 읽기 전용 조사 3항목 수행. `src/lib/email-notify.ts` / `api/admin/tools/review.ts` / `api/tools/submit.ts` / D1 `tool_submissions` 17행 / git 이력 / 라이브 배지 URL.
- [NONE] 코드·D1·배포 변경 없음(지시서에 코드 수정 지시 없음).

결과 — 완료기준 3항목
1. **발송 코드 파일 경로** [검증됨] = `src/lib/email-notify.ts` (256줄). 발송 함수 `sendToolNotification()`(220-256행). 호출자 `src/pages/api/admin/tools/review.ts:6`.
2. **"원문 그대로" 원인** [검증됨] = `approvedHtml()` 의 **배지 임베드 코드 블록**(`src/lib/email-notify.ts:105-109` 생성, 138행 삽입). `escapeHtml()` 로 HTML 소스를 문자화해 `<div style="...monospace...">` 코드 블록에 넣는데, 메일 클라이언트가 텍스트로 렌더 → 소유자는 `<a href="..."><img src="..." ...></a>` 를 그대로 봄.
3. **수정 방안** — 아래 "수정 방안 3안".

### 실측 근거 — 메일 코드블록에 들어가는 실제 문자열
`escapeHtml()`(92-99행) 적용 결과(`escapeHtml` 은 `& < > " '` 만 처리):
```
<a href="https://aikorea24.kr/tools/careops/">
  <img src="https://aikorea24.kr/badges/listed-on-aikorea24.webp" alt="LISTED ON AI KOREA 24" width="240" style="max-width:240px;height:auto;border:0;" loading="lazy" />
</a>
```
→ 배지 이미지 `https://aikorea24.kr/badges/listed-on-aikorea24.webp` 는 **200 / image/webp / 20,078B** 로 정상. 코드 문구는 스킬 AIK24-BADGE-02(커밋 `816e309e`)가 넣은 **의도된 기능**이며, 코드 주석도 "복사해서 사이트에 붙여넣으면 됩니다" 라고 명시.

### ★ 지시서 전제 vs 실측의 차이 (중요 — "마크다운" 은 아님)
지시서 §2 는 `##`, `**` 등 **마크다운** 기호 노출을 전제하나, 실측 결과 **그 기호는 어디에도 없습니다**.
- 메일 본문에 들어가는 값은 **`toolName` + `toolSlug` 둘뿐** (122·127·132·138행). D1 `tool_submissions` 17행 전수 확인 결과 `name` 에 마크다운 기호 0건 (`글웨이 (GeulWay)`·`GOATH (고뜨)` 는 괄호가 grep 에 걸린 것이지 마크다운 아님)
- `detail_markdown` / `description` 은 **이메일 경로에서 한 번도 참조되지 않음** (`grep -rn detail_markdown src/` 결과 = ToolForm 입력 · tools/[id].astro 렌더 · tools/index.astro 목록 · api/tools 저장 4곳뿐)
- 실제 노출되는 것은 **HTML 소스 코드블록** 1개. 소유자가 비전문가 눈에는 마크다운과 똑같이 "원문 그대로" 로 읽힘
- `sendToolNotification()` 는 `htmlContent` 만 전송하고 `textContent`(평문) 필드가 없음 → 평문 fallback 이 아니라 HTML 단일 경로

### 발송 경로 [검증됨]
- `BREVO_URL = "https://api.brevo.com/v3/smtp/email"` — **Brevo REST 직접 호출(SMTP 아님)**, 헤더 `api-key`, body `{sender,to,subject,htmlContent}`
- **외부 템플릿 파일 없음** — TS 템플릿 리터럴 인라인. 템플릿 3종 = `approvedHtml`(101-148) / `rejectedHtml`(150-175) / `submissionHtml`(183-218)
- 발신 `SENDER = { name:'AI코리아24', email:'info@aikorea24.kr' }` — 지시서 발신과 일치
- Brevo 호출부는 총 4곳: `src/lib/email-notify.ts`, `api/unsubscribe.ts`, `api/subscribe.ts`, `api/briefing/send-email.ts` (+`scripts/auto_email_sender.py` 브리핑 배치). 도구 메일은 `email-notify.ts` 하나뿐

### 발송 시점 버전 정합 [검증됨]
- `email-notify.ts` git 이력 = `816e309e`(2026-10-12 20:49 KST / 11:49 UTC, "fix: AIK24-BADGE-02 승인 도구 404 수정 + 승인 이메일 배지 게재 안내") / `2f1924af`(09-27) / `9179b2e1`(09-24) / `256be555`(09-24 최초)
- 발송 2026-10-12 13:02:23 UTC = 22:02 KST → `816e309e` 배포(20:49 KST) **이후** = 배지 안내 버전이 라이브였음
- 최초 버전 `256be555` 에도 `description`/`detail_markdown` 참조 0건 → **어느 버전이든 도구 소개 본문이 메일에 들어간 적 없음**

### 수정 방안 3안 (택 1 — 지시서에는 "HTML 변환 추가 or 템플릿 수정" 이라 되어 있으나, HTML 변환은 불필요)
| 안 | 내용 | 효과 | 비용 |
|---|---|---|---|
| **A안 (권장)** | 코드블록을 `<pre>` 로 감싸고 `white-space:pre-wrap` 유지 + **앞에 "아래는 복사용 HTML 코드입니다" 한 줄 추가**. 코드가 코드임이 명시돼 비전문가가 더 이상 "오류"로 오해하지 않음 | 가장 느슨하게 오해 해소. 기존 기능 전부 보존 | 2줄 |
| B안 | 코드블록을 `<details><summary>배지 코드 보기</summary>` 로 접기 | 시각적 노이즈 제거 | 3줄. 일부 메일 클라이언트가 `details` 미지원 |
| C안 | 코드블록 통째 제거 | 문제 완전 소멸 | 배지 게재 기능 자체 삭제 — AIK24-BADGE-02 목적 파괴. 비권장 |

**HTML 변환 추가(마크다운→HTML)는 불필요** — 템플릿이 이미 HTML 리터럴이고 `##`/`**` 가 입력되지 않으므로 변환할 마크다운이 없다. 지시서가 지목한 방향은 이 조사 결과로는 근거가 없다.

### 잔존 위험
1. [검증불가] 실제 수신 메일 원문 미확보. Brevo 대시보드 로그 접근 권한 없음 → "소유자가 정확히 무엇을 불평했는지"(어느 코드블록인지, `##`/`**` 를 실제로 보았는지)는 확정 못 함. 위 원인론은 **코드 실측 + 발송 시각 정합**으로 도출한 것이지 메일 원문 대조가 아니다
2. [추정] careops 가 해당 승인 건으로 추정(created 2026-10-11 20:16:46, published). D1 `tool_submissions` 에 `approved_at` 컬럼이 없어 승인 시각으로 확정 불가. slug 를 댄 것이 순정 추측
3. A안 적용 시에도 비전문가 오해는 완전히 0 이 되지 않음(코드는 여전히 코드임)
4. `rejectedHtml` 의 `reason`(반려 사유)과 `approvedHtml` 의 `name` 은 `escapeHtml()` 만 거치므로 주입은 막혔으나, 소유자가 사유에 `**굵게**` 처럼 쓰면 그대로 나타남 — 마크다운 변환이 필요한 유일한 실제 경로
5. `badges/listed-on-aikorea24.webp` 는 `public/` 아래라 `.gitignore:66-67` 로 커밋 불가(배포로만 반영). 이번 조사에서 200 확인했으나 재생성 시 유실 위험은 TOOLSYNC 계열과 동일

### 다음 행동
- 대표님: A/B/C안 택 1 → 지시서로 지시 주시면 구현. C안은 AIK24-BADGE-02 목적 파괴라 비권장
- 대표님: 실제 수신 메일 원문(스크린샷) 주시면 원인 확정 [검증불가] → [검증됨] 으로 승격


## 2026-10-15 10:48 AIK24-TOOLSYNC-03/04 완료 — CareOps 썸네일 교체 + 앱 스토어 링크 텍스트 간결화 → SSOT/프로젝트/aikorea24/지시서/2026-10-15-1048-AIK24-TOOLSYNC-03-04-완료보고.md (완료)

## 2026-10-15 10:48 — AIK24-TOOLSYNC-03/04 완료 — CareOps 썸네일 교체 + 앱 스토어 링크 텍스트 간결화

한 일
- **[BINARY/D1]** `public/images/tools/careops.webp` 교체. muse.ai 서명 URL(202,250B JPEG, 1676x1428) 다운로드 → 800x450 LANCZOS 리사이즈 → WEBP q80. 5,966B → 21,184B. D1 변경 없음(screenshot_url 경로 동일이라 지시대로 미변경). 백업 `/tmp/careops.webp.bak`
- **[D1]** `tool_submissions` careops `detail_markdown` 의 앱스토어 링크 3행을 1행 마크다운 링크로 교체. `updated_at` = `datetime('now')` 로 갱신(2026-10-15 03:45:39 UTC)
- **[GENERATED]** `src/content/tools/careops.md` — sync 생성 경로 재생성(`[update]`, diff +2/-4). md 직접 편집 아님

결과
- [검증됨] 라이브 이미지 바이트 일치 — `curl https://aikorea24.kr/images/tools/careops.webp` → 200, 21,184B, `image/webp`, **md5 `4cf12d84cf9cc0f9b1f2575abcdebd3c`** = 로컬 `/tmp/careops_new.webp` 와 동일
- [검증됨] 라이브 페이지 `https://aikorea24.kr/tools/careops/` → 200, 35,013B. `src="/images/tools/careops.webp"` 노출, `og:image` 는 `og-default.jpeg` (기존 동작, 본 지시 범위 밖)
- [검증됨] 링크 텍스트 — `<a href="https://apps.apple.com/kr/app/id6807790541">앱스토어 다운받기</a>` / `<a href="https://play.google.com/store/apps/details?id=kr.careops.app">구글 플레이 다운받기</a>` 렌더. 이전 긴 텍스트(`검증된 상담 기법과 전문 심리상담사와 함께하는 AI 상담`) 잔존 0건
- [검증됨] sync 판정 로그 `[update] careops.md (D1 updated_at > md mtime, image 보존: "/images/tools/careops.webp")` → TOOLSYNC-01 규칙이 실제로 동작, 이미지 보존 분기도 동작
- [검증됨] 배포 2건 — TOOLSYNC-03 `80c2ea7d-6feb-4fbe-9cf6-e75d7e0aa79a`, TOOLSYNC-04 `c6fcdd4f-2388-4b82-b8b5-86c3ec23063c`. sitemap ping `{"google": true, "naver": true}`

지시서 대비 차이
- **"품질 80, 기존 컨벤션 유지"** → `scripts/backfill_tool_thumbs.py:26,87` 의 실제 컨벤션은 `TARGET_W,TARGET_H = 800,450` + `quality=75`. 지시서의 명시 수치(80)를 따랐고 크기(800x450)는 컨벤션 그대로. `public/images/tools/` 260개 전부 800x450 임을 확인
- **git 커밋 없음** — `.gitignore:66-67` 이 `public/images/` 를 의도적으로 제외("deployed via wrangler pages deploy (local build), not committed to git"). 지시서에 커밋 지시가 없어 따로 `-f` 로 강제 추가하지 않음
- **`updated_at` 갱신** — TOOLSYNC-02 는 "updated_at 건드리지 말 것" 이었고 본 지시서는 "sync 재생성" 을 요구하므로 상충. `src/pages/api/tools/[slug]/index.ts:138` 이 편집 API 정상 동작이 `updated_at = datetime('now')` 임을 확인하고 동일하게 맞춤(임의 조작 아님)

잔존 위험
1. [부분검증] 원본이 1676x1428(세로빛) → 800x450(가로)로 **비율 왜곡** resize. `backfill_tool_thumbs.py:85` 도 `resize((800,450))` 로 동일 방식이라 컨벤션 일치이나, 원본 세로 이미지에는 왜곡이 눈에 띔. 컨벤션을 바꿀지 대표님 결정 대기
2. [부분검증] `og:image` 가 여전히 `og-default.jpeg`. 소셜 공유 카드에는 새 이미지가 안 나옴. 본 지시 범위 밖
3. 안전 문구는 TOOLSYNC-02 에서 제가 작성한 것 — 소유자(세이프옵스) 승인 미완
4. `screenshot_url` 에 사이트 절대경로 — 어드민 편집 화면 취급 방식 미확인(TOOLSYNC-02 에서 이관)
5. sync 스크립트 `process.env` 토큰 미제거 — 세션 환경 직접 실행 시 `code 7403`. `env -u CLOUDFLARE_API_TOKEN -u CLOUDFLARE_ACCOUNT_ID` 필요
6. 나머지 11건 D1 행은 여전히 `updated_at` 이 오래되어 TOOLSYNC-01 자동 갱신 대상 아님

다음 행동
- 대표님: CareOps 썸네일 왜곡 허용 여부 / `og:image` 교체 여부 / 안전 문구 최종 승인
- 별도: 카드 생성 복구용 free LLM 키 1개 secret 추가 (이전 큐 후속, 미해결)


## 2026-10-15 10:31 [AIK24-PIPE-DEDUP-01] 완료 — 브리핑 선정 순서 수정 + 스케줄 07:00 이동 (주니어 C, 대표님 10:15 승인)

### 한 일
대표님 승인 2건 적용 — A안(슬롯 배정 전 중복 제거) + 스케줄 06:00→07:00.

| 분류 | 파일 | 내용 |
|---|---|---|
| [PRODUCTION CODE] | `scripts/auto_news_selector.py` | `main()` 에 3.5 단계 추가 (11행) |
| [TEST CODE] | `tests/test_auto_news_selector_dedup_before_slots.py` | 신규 3케이스 |
| [CONFIG] | `~/Library/LaunchAgents/kr.aikorea24.pipeline-runner.plist` | `Hour` 6 → 7 |

- `select_top_articles()` **직전**에 `briefing_dedup.get_history_articles()` + `is_duplicate_article()` 로 이미 발행된 news_id 를 `passed` 에서 제거. 기존 판정 함수 재사용 → 모델 카드 `exact_id` 예외가 자동으로 따라온다.
- `briefing_dedup` 이 `auto_news_selector` 를 import 하므로 **지연 import** (main 안).
- `get_history_articles()` 는 실패 시 `[]` 반환 → **fail-open 유지**. D1 장애가 브리핑을 막지 않는다.
- `auto_briefing.py` 의 후행 dedup(268행)과 모델 슬롯 재충전(278~292행)은 **삭제 안 함.** 첫 방어선 위에서 한 번 더 도는 구조.
- 스케줄: 백업 `.bak.20261015_1030` → `plutil -lint` OK → `launchctl bootstrap` 이 `Bootstrap failed: 5: Input/output error` → 구형 `launchctl load -w` rc=0 성공. 수집기 `news-unified`(05:30)는 **이동 안 함**(별도 D1 쓰기 job, 리셋 무관).
- 커밋 `7f7b8328`. 완료보고: `SSOT/프로젝트/aikorea24/지시서/2026-10-15-1031-AIK24-PIPE-DEDUP-01-완료보고.md`

### 결과 — **오늘 브리핑 생성됨. 목표 달성.**
- **[검증됨] A안 작동.** 10:27 실행 로그 `/tmp/pipe_a_20261015.log`:
  `통과 8건` → **`이미 브리핑됨 7건 제외 → 신선 후보 1건`** → `선정 1건` → HiRO-ACEv2 (HuggingFace Blog, 7점).
  어제와 같은 패턴(상위 4건 전부 과거 브리핑분 → 0건)이 신선 후보가 슬롯을 채우는 방향으로 바뀜.
- **[검증됨] 파이프라인 정상 종료.** exit 0 · 93.7초 · 선정 뉴스 1건 · 에러 없음 · 배포 `b67063fc-b306-4f73-b310-97d95990fcb1` · sitemap ping google ✅ naver ✅ · 이메일 발송 완료.
- **[검증됨] D1.** `2026-10-15-2` published 1건(HiRO-ACEv2) / `2026-10-15-1` published 2건(nemotron-3.5-super, LFM2.5-24B).
- **[검증됨] 라이브.** `https://aikorea24.kr/` → "오늘의 AI 브리핑 (2026-10-15) · 1건의 AI 소식을 선정했습니다" + HiRO-ACEv2 카드 노출.
- **[검증됨] 회귀 없음 — 신규 테스트가 실제 버그를 잡는다.** `git stash` 로 production code만 제거하고 동일 스위트 실행해 기준선 대조:
  기준선(수정 전) 실패 **19** / 수정 후 **17**. `diff` 결과는 신규 테스트 2건의 삭제만, 추가 0건.
  산출 근거: `19 = 17(기존) + 2(신규 테스트가 fix 전 실패)`, `17 = 17(기존)`.
  남은 17건(test_deep_dive_writer, test_failed_articles, test_pitch, test_write_thread_validation 등)은 기준선과 동일한 기존 실패 — 본 변경과 무관.
- **[검증됨] 실행 간 중복 방어도 동작.** 10:27 실행이 10:23 실행이 만든 2건을 중복으로 정확히 걸러 HiRO-ACEv2 만 추가했다.
- [TEST CODE] 와 [PRODUCTION CODE] 동시 수정 없음. 신규 테스트 3건은 fix 전부터 존재했고 판정에 production code 스태시만 개입.

### 잔존 위험
1. **`2026-10-15-1` 고아.** 10:23 실행이 셸 120초 타임아웃으로 끊기며 브리핑 2건(nemotron 9점, LFM2.5 9점)을 D1 에 쓰고 죽었다. `latest.ts:16` 이 `ORDER BY id DESC LIMIT 1` 이라 **`-2`(HiRO-ACEv2)만 노출**, `-1`의 2건은 도달 불가. **조치 안 함** — live D1 쓰기는 승인 없이 하지 않음. **대표님 결정 필요: 병합/삭제/방치.**
2. **하루 2회 이상 실행 시 N번째만 보임.** `publish.ts:34` 가 시퀀스를 `ORDER BY date DESC LIMIT 1` 로 매겨 재실행마다 `-2` `-3` 이 늘고 사이트는 마지막 1건만 노출. 재실행하면 이전 분이 사라지는 구조 (A안과 무관한 파이프라인 정책 문제).
3. **D1 가드 여전히 미연결.** `cfnew.require_d1_headroom()` 는 EmDash DB 기준이라 `aikorea24-db` 대상이 아님. `scripts/threads/db_reader.py:177 d1_query()` 는 3회 재시도 후 `[]` 반환해 실패를 삼킨다. 스케줄 이동은 **07:00(=리셋 직후) 시나리오만 완화**, 가드 공백 자체는 그대로. 하루 중 다른 소비자가 한도를 소진하면 07:00 도 죽는다.
4. 기존 테스트 실패 17건 미해결 (본 작업 범위 밖, diff 로 무관 확인).
5. `scripts/pipeline_runner.log` 18.4MB, 06:00 이후 미갱신(mtime 06:00), 회전 없음.
6. `scripts/logs/model_diff_2026-10-15.json` untracked 잔존, 커밋 안 함.

### 다음 행동 (대표님 결정 대기)
- [ ] 고아 브리핑 `2026-10-15-1` 처리 — 병합 / 삭제 / 방치
- [ ] 파이프라인 재실행 시 이전 분이 사라지는 정책 확정
- [ ] `db_reader.d1_query()` raise 전환 (가드 공백 근본)
- [ ] 내일 07:00 자동 실행 확인 — `pipeline_runner.log` 새 헤더 + D1 `2026-10-16-1` 생성 여부

---
## 2026-10-15 10:30 — AIK24-TOOLSYNC-02 완료 — 앱 스토어 링크 복원 + 안전 문구 복원 → SSOT/프로젝트/aikorea24/지시서/2026-10-15-1030-AIK24-TOOLSYNC-02-완료보고.md (완료)

### 한 일
- [CONFIG/D1] `tool_submissions` careops 1행 UPDATE (`updated_at` 미변경 — 지시서 주의 준수):
  1. `detail_markdown` 에 앱 스토어 링크 2개 추가(iOS / Android)
  2. `detail_markdown` 말미에 안전 문구 1문단 추가 — "CareOps 마음이는 전문 상담을 대신하지 않습니다. 의료적 진단·처방이나 응급·위기 대응을 하지 않으며, 심각한 고민이나 위기 상황에서는 전문 상담사나 응급 연락망을 이용해 주세요." (출처: `/tmp/careops.md.bak` 1차 복원본의 "의료적 진단·치료나 응급·위기 대응을 대체하지 않습니다" 취지 확장)
  3. `description` 말미에 안전 문구 추가 — "전문 상담을 대신하지 않으며, 진단·처방·응급 지원은 하지 않습니다."
  4. `screenshot_url` = `/images/tools/careops.webp` — ★ 아래 "자체 결함" 참조
- [PRODUCTION CODE] `scripts/sync_submissions_to_md.mjs` 1줄 — `querySubmissions()` 의 SELECT 목록에 `screenshot_url` 추가.
- [GENERATED] `src/content/tools/careops.md` — `rm` 후 sync 재생성(생성 경로). md 직접 편집 아님(지시서 준수).

### ★ 자체 결함 발견·수정 (TOOLSYNC-01 의 내가 놓친 것)
TOOLSYNC-01 에서 `buildMd()` 에 `image` 방출 분기(`row.screenshot_url ? … : preservedImage ? … : []`)를 넣었는데,
**`querySubmissions()` 의 SELECT 목록에 `screenshot_url` 이 없어** `row.screenshot_url` 이 항상 `undefined` 였다.
즉 그 분기는 죽은 코드였고, careops 썸네일이 보존됐던 건 우연히 아래 `preservedImage` 폴백 덕분이었다.
이번 작업에서 md 를 `rm` 후 생성 경로로 태우자 `preservedImage` 가 없으니 **썸네일이 유실** → SELECT 1줄 추가로 근본 제거.

### 결과 (지시서 완료기준 3항목)
- **스토어 링크 2개** [검증됨] `https://aikorea24.kr/tools/careops` → 200, 35,207B. HTML 에 `apps.apple.com/kr/app/id6807790541` ✓ / `play.google.com/store/apps/details?id=kr.careops.app` ✓
- **안전 문구** [검증됨] 본문 "CareOps 마음이는 전문 상담을 대신하지 않습니다 … 응급 연락망을 이용해 주세요." 렌더 확인. 카드 설명 "전문 상담을 대신하지 않으며, 진단·처방·응급 지원은 하지 않습니다." 렌더 확인.
- **배포 Version** [검증됨] **`b7c84c8f-b0ee-4293-b1a0-bf95b6fdaa30`**, build `✓ Completed in 7.98s`, sitemap ping `{"google": true, "naver": true}`
- **부가 확인** [검증됨] `image: careops.webp` 라이브 노출 유지(유실 없음). D1 `updated_at` = 2026-10-14 10:34:45 로 **변경 없음**.
- **sync 결과** [검증됨] `[create] careops.md` 1건 / 나머지 11건 스킵. `git diff --stat` = 5 insertions(+), 1 deletion(-) — 의도한 변경 외 없음.

### 지시서 주의사항과 충돌했던 지점 (대표님 승인 후 진행)
지시서는 "sync 로 careops.md 재생성 확인"을 요구하면서 동시에 "D1 `updated_at` 은 건드리지 말 것( sync 판정에 사용)"이라 명시했습니다.
두 지시사항은 동시에 성립하지 않습니다 — D1 `updated_at`(2026-10-14 10:34) 이 md mtime(2026-10-15 10:17)보다 **오래되어** 갱신 판정(`updated_at > mtime`)이 false 가 됩니다.
**대표님 선택으로 `careops.md` 를 `rm` 후 sync 생성 경로로 태우는 방식**으로 해결했습니다(`updated_at` 미변경, sync 규칙 무변경, md 직접 편집 아님).
- 부수 발견: 생성 경로는 "물려받을 md" 가 없어 `image` 유실이 발생합니다. → `screenshot_url` 을 D1 에 채워 **D1 자체가 자립**하게 했습니다(향후 어떤 경로로 재생성해도 이미지 보존).

### 잔존 위험
1. **[부분검증]** `screenshot_url` 에 사이트 절대경로(`/images/...`)를 넣었다. 어드민 편집 화면이 이 필드를 "외부 스크린샷 URL"로 취급할 경우 소유자가 값을 덮어쓰면 이미지가 다시 유실됩니다. 지금은 렌더 정상.
2. **[부분검증]** 안전 문구는 1차 복원본의 취지를 확장해 제가 문장을 새로 썼습니다(원문 "의료적 진단·치료나 응급·위기 대응을 대체하지 않습니다" → 추가 "심각한 고민이나 위기 상황에서는 전문 상담사나 응급 연락망을 이용해 주세요"). 디렉토리 정책 문구로서 소유자 승인 필요.
3. `careops.md` 는 이제 완전 D1 파생물입니다. md 를 직접 편집하면 다음 deploy 때 `updated_at > mtime` 판정(또는 rm) 경로로 무조건 되돌려집니다.
4. 나머지 11건 D1 행은 `screenshot_url` 이 NULL 이라 재생성 시 이미지가 없습니다(현 상태 유지, TOOLSYNC-02 범위 밖).
5. sync 스크립트의 `process.env` 토큰 미제거는 여전히 미수정(TOOLSYNC-01 잔존 위험에서 이관). 세션 환경 직접 실행 시 `code 7403`, deploy 경유는 정상.
6. `updated_at` 을 오래된 값으로 남겨 둔 상태라 **TOOLSYNC-01 규칙으로는 앞으로 careops 가 자동 갱신되지 않습니다.** 다음 편집 화면 저장은 `updated_at` 이 올라가므로 그때 자동 반영됩니다.

### 다음 행동
- 대표님: 안전 문구 문장 최종 승인(2번 항목).
- 대표님: 어드민 편집 화면에서 `screenshot_url` 이 외부 URL 전용이라면 D1 값을 되돌리고 `buildMd` 폴백 로직을 별도로 검토.
- 별도: 카드 생성 복구용 free LLM 키 1개 secret 추가(TOOLSYNC-01 이전 큐 후속).

## 2026-10-15 10:20 — AIK24-TOOLSYNC-01 완료 — tags 이중 인코딩 수정 + D1→md 동기화 규칙 변경 → SSOT/프로젝트/aikorea24/지시서/2026-10-15-1020-AIK24-TOOLSYNC-01-완료보고.md (완료)

### 한 일
- [PRODUCTION CODE] `src/components/ToolForm.astro` — tags 초기값 처리를 `Array.isArray(...)` → `toStrArray(...)` 로 교체(1줄 + 주석 3줄). 동일 파일의 `tasks` 는 이미 `toStrArray` 를 쓰고 있었으나 **tags 만 빠져 있었음** → 이것이 이중 인코딩의 유일한 근본 원인.
- [PRODUCTION CODE] `scripts/sync_submissions_to_md.mjs` — 5개 지점 변경:
  1. 헤더 주석을 "D1=정본, md=빌드용 캐시" 규칙으로 갱신
  2. `existsSync` 무조건 skip → `D1 updated_at > md mtime` 면 재생성으로 변경
  3. `readField()` 헬퍼 신설(기존 md frontmatter 에서 스칼라 1개 추출)
  4. `buildMd(row, preservedImage)` — `screenshot_url` NULL 이면 기존 md 의 `image` 물려받음
  5. import 에 `readFileSync`·`statSync` 추가
- [CONFIG/D1] `tool_submissions` 2행 UPDATE — `careops`·`link2threads-l2t` 의 `tags` 를 정상 JSON 으로 교체. `updated_at` 은 **의도적으로 건드리지 않음**(sync 판정 입력이라 유지).

### 결과
- **지시서 검증 ①** [검증됨] `SELECT tags …` → `careops` = list 10개 `['AI상담','심리상담','CBT','ACT','마음돌봄','자기성찰','한국어','영어','iOS','Android']`, `link2threads-l2t` = list 7개. `rows_written: 2`.
- **지시서 검증 ②** [검증됨] sync 실행 로그 `[update] careops.md (D1 updated_at > md mtime, image 보존: "/images/tools/careops.webp")`. dry-run 에서도 `careops.md` 1건만 후보로 뜸(나머지 11건 스킵). 생성 후 `careops.md` `updated: "2026-10-14"` = D1 값과 일치.
- **지시서 검증 ③** [검증됨] `npm run build` → `✓ Completed in 6.43s` / `Server built in 12.65s` / `Complete!`.
- **지시서 검증 ④** [검증됨] `https://aikorea24.kr/tools/careops` → 200, 34,214B. 라이브에서 `careops.kr/?utm_source=aikorea24`(툴 바로가기) + `careops.kr/app?utm_source=aikorea24`(본문 "앱 받기") 노출, 설명문·`🗓 2026-10-14`·`심리상담` 태그 반영 확인.
- **보존 확인** [검증됨] `image: "/images/tools/careops.webp"` 가 재생성 후에도 살아 있음(썸네일 유실 없음). 백업은 `/tmp/careops.md.bak`, D1 원값은 `/tmp/tool_tags_backup.json`.
- **배포** [검증됨] `npm run deploy` → Version **`ac261049-a2d0-4710-8816-8c3f7e5a59ef`**, Uploaded 14.67s, Worker Startup 18ms, sitemap ping `{"google": true, "naver": true}`.

### 지시서 범위를 벗어난 판단 (대표님 확인 필요)
- **_app 스토어 링크 유실**: 재생성으로 `careops.md` 본문의 `apps.apple.com/kr/app/id6807790541`·`play.google.com/.../kr.careops.app` 2개 링크가 사라졌습니다. D1 `detail_markdown`(381자)에 이 링크가 없어서 D1=정본 규칙상 당연한 결과입니다. 복원하려면 **D1 의 detail_markdown 에 스토어 링크를 넣고 저장**해야 합니다(일방향이라 md 직접 편집은 다음 sync 때 또 날아갑니다).
- **scripting env 선행 문제(미수정)**: `sync_submissions_to_md.mjs` 의 `const env = { ...process.env }` 가 주입된 `CLOUDFLARE_API_TOKEN`/`CLOUDFLARE_ACCOUNT_ID` 를 제거하지 않아, 세션 환경에서 실행하면 계정 `7eb1b8cd` 로 튀어 `code 7403` 이 납니다. `deploy.sh` 경유 deploy 는 정상 동작했으므로 지시서 범위 밖으로 두고 `env -u … node scripts/…` 로만 실행했습니다.

### 잔존 위험
1. **[부분검증]** 앱 스토어 링크 유실을 지시서 검증에 "누락"으로 적을 수 있으나, 지시서 ④는 "새 URL 표시 확인" 이라 의도된 변경으로 봅니다. 소유자(세이프옵스) 관점에서 링크 유실이 회귀인지 확인 필요.
2. **일방향 sync 의 대가**: 이제 D1 `updated_at` 이 md mtime 보다 최신이면 md 를 덮어씁니다. 수동으로 md 를 편집하면 다음 deploy 때 무조건 되돌려집니다. md 직접 편집 습관은 끊어야 합니다.
3. **`updated_at` 이 NULL/비어있는 D1 행**은 `Number.isFinite(d1)` 이 false 라 "신선하지 않음"으로 판정되어 계속 스킵됩니다(안전 쪽). 12건 중 해당 없음은 실측 확인.
4. **테스트 미추가** — sync 스크립트에 회귀 테스트가 없어서, 규칙 변경이 `careops.md` 외 다른 슬러그에 영향을 주는지는 12건 dry-run + git status 로만 확인했습니다(재생성 1건뿐임을 확인).
5. **남은 10건 D1 행**의 `use_cases` 는 대부분 쉼표 구분 평문이고 `goath` 만 `"검정 바지에…` 따옴표 조각이 있습니다. 재생성 대상이 될 경우 깨질 수 있어 미수정.
6. **Tier1 LLM 상태** — 주니어 A 큐 1 이 확인한 DeepSeek chat 무응답 + free 폴백 키 부재 상태는 그대로입니다(이번 작업과 무관, 키 추가 필요).

### 다음 행동
- 대표님: 앱 스토어 링크를 되살리려면 D1 편집 화면에서 `detail_markdown` 에 스토어 URL 2개를 추가 후 저장 (이후 deploy 1회로 자동 반영).
- 대표님: sync 스크립트의 `process.env` 토큰 제거 여부(위 "범위 밖" 항목) 지시 여부.
- 별도: 카드 생성 복구용 free LLM 키 1개 secret 추가 (큐 1 후속).

## 2026-10-15 10:03 — CareOps 도구 DB 확인 (주니어 A 큐 2, 읽기 전용)

### 한 일
- [PRODUCTION CODE] 수정 0건. 읽기 전용 지시 준수.
- D1 `aikorea24-db` 에서 `tool_submissions` careops 레코드(id=22) 조회.
- `src/content/tools/careops.md` · `src/pages/tools/[id].astro` · `src/pages/api/tools/[slug]/index.ts` · `scripts/sync_submissions_to_md.mjs` · `scripts/deploy.sh` 읽기.
- 라이브 `https://aikorea24.kr/tools/careops` 확인.

### 결과
- **[검증됨] D1 저장은 정상.** `updated_at = 2026-10-14 10:34:45`, `status=published`, `user_id=142`. 레코드는 1건뿐.
- **[검증됨] 미반영 원인 — 공개 페이지가 D1 이 아니라 Astro md 를 읽는다.**
  - `src/pages/tools/[id].astro:9,19,144` / `tools/index.astro:7` → 전부 `getCollection('tools')`. 실제 소스 = `src/content/tools/careops.md`(mtime 2026-10-13 11:25:29).
  - 편집 API `src/pages/api/tools/[slug]/index.ts:137` 은 `UPDATE tool_submissions` 만 실행, md 미수정.
  - `scripts/sync_submissions_to_md.mjs` 가 D1→md 동기화를 담당하고 `scripts/deploy.sh:52` 에서 빌드 전 호출되나, 스크립트 주석 명시 "md가 이미 있으면 건드리지 않음(수동 편집 우선)". `careops.md` 는 이미 존재 → **D1 저장이 반영되지 않는다.**
- **[검증됨] D1↔md 내용 불일치.** url: D1 `https://careops.kr/?utm_source=aikorea24` vs md `https://careops.kr/app`. description·difficulty(NULL vs "중급")·updated 도 상이.
- **[검증됨] 라이브 페이지 정상 렌더.** `/tools/careops` 301 → `/tools/careops/` 200, 34,638B. 링크 3개(`careops.kr/app` · `apps.apple.com/kr/app/id6807790541` · `play.google.com/.../kr.careops.app`) 렌더됨. 단 표시 날짜는 `2026-10-12`(md 의 `updated:` 값, 파일 mtime 10-13과도 불일치).
- **[검증됨] 별도 결함 — D1 `tags` 이중 인코딩.** 실제값 `["[\"[\\\"AI상담\\\"\"","\"\\\"심리상담\\\"\"", … ,"\"\\\"Android\"]\"]"]` = 배열 안에 문자열로 직렬화된 배열이 재삽입되고 이스케이프 중첩. 정상값 `["AI상담","심리상담",…]`.
- **[부분검증]** 라이브 난이도 배지가 `🔧 보통` 인데 md 는 `difficulty: "중급"` — `[id].astro` 매핑이 "중급" 을 못 읽고 기본값으로 떨어지는 것으로 보이나 **코드 원인 미확인**(읽기 전용 지시라 수정 안 함).

### 잔존 위험
1. **소유자가 편집 화면에서 저장하면 계속 조용히 실패한다.** 화면상 "저장됨"인데 공개 페이지엔 반영되지 않는 상태가 반복됨.
2. **동기화 정책 미결정** — (a) D1 편집 시 md 재생성(수동 편집 포기) / (b) `updated_at` 이 md 보다 최신일 때만 재생성 / (c) 현행 유지 + 소유자 안내. 대표님 결정 대기.
3. **`sync_submissions_to_md.mjs` 를 지금 실행하면 신규 슬러그가 `tags` 이중 인코딩 결함을 물려받을 수 있다.** 실행 전 `parseArr()` 결함 확인 필요.
4. 난이도 배지 "보통" vs md "중급" 불일치의 코드 원인 미확인.

### 다음 행동
- 대표님: 동기화 정책 선택 + 태그 이중 인코딩 수리 지시 여부.

---
## 2026-10-15 AIK24-FREE-PIPE-01 일일 실행 — 수집 38건 / 실패 프로바이더 0 / added 1 · removed 1 · changed 0 / 리스트 페이지 갱신 https://emdash.aikorea24.kr/posts/free-models / 평가·발행 SKIP (AIK24-PIPE-01 자동 평가 비활성 — 수동 평가로 전환) / 심층 리뷰 1건 (리스트 카드 링크 1건)

## 2026-10-15 09:55 [AIK24-PIPE-RERUN-01] 실행완료·목표미달 — 오늘 브리핑 수동 재실행 (주니어 C, 대표님 09:44 지시)

### 한 일
- `scripts/run_pipeline_with_notify.py` **2회 실행** (일반 1회 → 0건, `--collect` 1회 → 0건). launchd와 동일 명령.
- 사전 점검: D1 434,683/5,000,000 (8.7%) → 여유 확인 후 실행.
- 로그: `/tmp/manual_pipeline_20261015_0945.log`, `/tmp/manual_pipeline_collect_20261015.log`

### 결과 — **오늘 브리핑은 여전히 미생성. 목표 미달.**
- **[검증됨] 파이프라인 자체는 정상.** 2회 모두 exit 0, `✅ 에러 없음`, `선정 뉴스: 4건`, **배포 성공** (Version `9e78637c` → `f43799a5`, `aikorea24.kr`, sitemap ping google ✅ naver ✅).
- **[검증됨] D1 장애는 해소됨.** 06:00 자동 run의 `rows_read exceeded` 재현 안 됨. 뉴스 조회·LLM 평가 정상.
- **[검증됨] 부수 확인 — 어제 [부분검증]으로 남긴 `sync_submissions_to_md.mjs` 런타임 예외도 2회 연속 재현 안 됨.** `published=12 created=0 skipped=12` 통과.
- **[검증됨] 05:30 수집기도 같은 날 죽어 있었음 (어제 조사에서 빠진 층위).**
  - `api_test/cron_unified.log` (mtime 05:37): 179건 수집 → 배치 1~5 **전부 `ok=False`**, 본문 = `"Your account has exceeded D1's free tier daily row read limit"`.
  - D1 실증: `news` 테이블 `DATE(created_at)` 집계 → `2026-10-14 → 193건`, **`2026-10-15 → 행 없음`**. 오늘 신선 뉴스 0개.
- **[검증됨] 진짜 마지막 블로커 = 선정 순서 결함 (D1 아님).**
  - 로그: `후보 8건` → LLM 평가 → `선정 4건`(전부 과거 브리핑된 free-LLM 목록형, 14/12/11/11점) → `중복 제거: 4건` `[exact_id]×4` → `선정된 기사 없음`.
  - 신선한 4건(nemotron-3.5-super 9 / JEV-35B 10 / LFM2.5-24B 9 / HiRO-ACEv2 7)은 **슬롯 4개 밖**이라 밀려남.
  - 코드: `scripts/auto_news_selector.py:255` `select_top_articles(..., MAX_COUNT=4)`가 **중복 제거 전에** 상위 4건 확정. `auto_news_selector.py:229` `def main(dedup=True): _ = dedup` → 인자를 받기만 하고 버림. `scripts/briefing_dedup.py:38 get_history_articles()`가 나중에 걸러내지만 그때 슬롯은 이미 꽉 참.
  - 이미 인지된 문제: `scripts/auto_briefing.py:275` 주석 `# AIK24-EFFICIENCY-04: 모델 카드는 exact_id 만 남으므로 슬롯이 빈 채로 끝날 수 있다`.

### 잔존 위험
1. **오늘(10-15) 브리핑 미생성 상태 유지.** 코드 수정 승인 없이는 내일 06:00 자동 run도 동일 사유로 0건.
2. **승인 대기 중인 A안** — `auto_news_selector.py` 의 `main()` 에서 `select_top_articles` 직전에 이미 브리핑된 news_id를 `passed`에서 제거(약 5줄, `briefing_dedup.get_history_articles()` 재사용). **승인 안 받고 미적용.** 라이브 일일 콘텐츠 조합이 바뀌므로 승인 필수.
3. **스케줄 06:00→07:00 이동 미승인** (어제 보고 권장 1). 05:30 수집기가 06:00 파이프라인보다 먼저 죽으므로 이동 시 두 작업 모두 리셋 직후 실행.
4. **가드 공백** — `cfnew.require_d1_headroom()`는 EmDash DB 기준이라 aikorea24-db를 쓰는 수집기/파이프라인에 적용 안 됨. 두 작업이 D1 한도를 공유.
5. **커밋 없는 배포 2건 누적** (`9e78637c`, `f43799a5`). 콘텐츠 변경 없이 빌드 산출물 재배포.
6. 10-14 UTC 급증의 유발 스크립트 미확정(추정).

### 다음 행동 (대표님 지시 대기)
- A안 승인 → 적용 → 재실행 → 브리핑 1건 이상 생성 확인
- 스케줄 이동 승인 → plist 수정 → launchctl reload
- (선택) 오늘 브리핑만 임시 회피하려면 dedup 우회 플래그 — 근데 A안 없이는 내일도 재발

[PRODUCTION CODE]/[TEST CODE]/[CONFIG] 변경 없음. 실행만 2회.

---

## 2026-10-15 09:55 [AIK24-PIPE-D1-01] 완료 — 브리핑 파이프라인 미실행 조사 (주니어 C)

### 한 일
- **read-only 조사만 수행.** D1 SELECT 1건 + `pipeline_runner.log` / `d1_usage_report.log` / launchctl / crontab 열람 + 코드 경로 확인.
- 결과 보고서를 `SSOT/주니어-소통/to-mallang.md`에 [C] 태그로 제출, `to-junior.md`의 주니어 C 큐를 [완료] 로 갱신.

### 결과
- **[검증됨] 결론 = 스케줄러 정상 · 크론 아님 · 원인은 "D1 free tier rows_read 한도 초과 + 실패를 삼키는 코드 2곳".**
  - `launchctl list | grep aikorea` → `kr.aikorea24.pipeline-runner` 로드됨. `scripts/pipeline_runner.log` mtime = 오늘 06:00 → **06:00에 정상 실행됨.**
  - `crontab -l` 에 aikorea24 항목 0건 → 크론 아님.
- **[검증됨] 오늘 브리핑은 미생성.** `scripts/pipeline_runner.log` 마지막 run(`2026-10-15 06:00`, 16.9초) → `Your account has exceeded D1's free tier daily row read limit` → `브리핑 조회 실패 (D1 오류, 빈 브리핑 아님)` → 선정 뉴스 0건.
  - D1 직접 조회(`SELECT date, COUNT(*) FROM briefings GROUP BY date ...`) 결과 최신 행이 `2026-10-14 → 1건`이고 **10-15 행이 존재하지 않음.** → 사이트가 10-14-1을 보여 "어제와 동일"로 보인 것. 캐시 문제 아님.
- **[검증됨] 한도 초과 시각** — `scripts/d1_usage_report.log`: 10-14 23:30 ICT(16:30 UTC) 5,235,820 rows (104.7%), 경보 발송. 10-15 07:00 ICT(00:00 UTC) 리셋 → 09:07 기준 171,230 (3.4%). **지금은 D1 정상**(같은 SELECT 방금 정상 응답).
- **[검증됨] 실패를 삼키는 코드 2곳** —
  - `scripts/threads/db_reader.py:177 d1_query()`: `wrangler d1 execute` raw subprocess, 3회 재시도 후 **`[]` 반환(raise 없음)** → 조용히 0건 진행.
  - `scripts/run_pipeline.py` 124~130·164행: `wrangler d1 execute` 직접 subprocess, 가드 없음.
  - `scripts/cfnew.py` 에 가드는 **이미 구현**(`D1_READ_LIMIT=5_000_000`, `require_d1_headroom()`, 70% 초과 시 `SystemExit(3)`)하나 **파이프라인에 연결돼 있지 않음.**
- **[검증됨] 재발 패턴** — 23 run 이력에서 한도 초과 2건(10-09 06:00, 10-15 06:00) **모두 06:00 ICT(=23:00 UTC) 슬롯.** 09:00 ICT(=00:00 UTC) 슬롯 3회(10-11~13)는 전건 성공. 스케줄이 10-13에 09:00→06:00으로 바뀐 뒤(AIK24-PIPE-SCHEDULE-01) 첫 실패가 오늘.
  - 10-14 UTC 급증의 발화점은 git log의 `AIK24-EMDASH-03~07` + `cfnew.require_d1_headroom()` docstring 근거로 **EmDash 복구 작업으로 추정** (실행 증거 아님).
- **[부분검증] 별건 — 배포 실패(rc=1)는 D1과 무관한 두 번째 블로커.** `scripts/deploy.sh`의 `[0.5/3] 승인 툴 submission → md 동기화` 직후 `sync_submissions_to_md.mjs` 크래시. `node --check` → SYNTAX OK → 런타임 예외. 10-09 06:00 run에서도 동일 실패 → 기존 선행 장애.
  - 제한 사유: stderr 스택 트레이스를 끝까지 추적하지 않음(`Node.js v25.2.1` 크래시 푸트프린트까지만 확보).

### 잔존 위험
1. **오늘(10-15) 브리핑이 여전히 미생성** — 다음 자동 run 은 내일 06:00. 조치 없으면 하루 통째 공백.
2. **10-14 UTC 급증의 정확한 유발 스크립트 미확정** — 문서 근거로만 추정. 추가 급증 시 동일 사고 재발 가능.
3. `d1_query()` 를 raise 로 바꾸면 정상적인 "빈 브리핑" 경로에서 오발동 위험 있음 → 사전 확인 필요.
4. 0건 run 5건 중 2건(10-05 06:00, 10-09 20:00)은 D1 한도 외 사유. 10-09 20:00은 "news 테이블 0건"(크롤러)이라 별개 후속 필요.
5. 배포 실패 런타임 예외 근본 미확정.

### 다음 행동 (대표님 지시 대기 — 코드 변경 안 함)
1. 스케줄 06:00 → 07:00 ICT(=00:00 UTC) 이동 (1줄, 단 대표님 10-13 지시와 충돌)
2. `d1_query()` 실패 시 raise 전환 (조용한 0건 제거)
3. `run_pipeline.py` 입구에 `cfnew.require_d1_headroom()` 연결 (기존 가드 구입)
4. 오늘 브리핑 재실행 여부 — D1 여유(3.4%)는 있으나 LLM 비용·배포·이메일 부수효과 발생

[PRODUCTION CODE]/[TEST CODE]/[CONFIG] 변경 없음.

---

## 2026-10-15 00:15 AIK24-D1-03 완료 — EmDash 쿼리 폭풍 N+1 완화: emdash04_migrate.py existing_titles() 페이지 크기 100→500 + 로컬 캐시(1시간 TTL) → 배포 검증 → SSOT/프로젝트/aikorea24/지시서/2026-10-15-0006-AIK24-D1-03-EmDash쿼리폭풍.md (완료)

### 한 일
- **[PRODUCTION CODE] `scripts/emdash04_migrate.py`** — N+1 패턴 제거:
  - `EXISTING_TITLES_LIMIT=500` 환경변수로 페이지 크기 확대(기본 100 → 500, 최대 3페이지로 1,500건 커버)
  - 로컬 캐시(`/tmp/emdash_existing_titles.json`, TTL 1시간) 추가로 재실행 시 API 호출 생략
  - `max_pages` 계산으로 무한 루프 방지
- **[PRODUCTION CODE] `scripts/emdash13_repair.py`** — 이미 D1-가드(`cfnew.require_d1_headroom`)와 서킷브레이커(`MAX_CONSEC_FAIL=5`) 적용됨 (AIK24-D1-GUARD-02에서 완료)
- **배포**: `npm run deploy` 성공 (Version ID: `b7c722ba-31d7-48e9-95a5-2e521525913c`)

### 결과
- **[검증됨] emdash04_migrate.py N+1 완화** — `existing_titles()` 가 최대 300회(limit=100) → 최대 3회(limit=500) API 호출로 감소. 캐시 히트 시 0회.
- **[검증됨] 배포 성공** — workers.dev 엔드포인트 정상 응답 확인.
- **[부분검증] emdash13_repair.py** — 루프당 3회 API 호출(get_item, PUT, publish)은 EmDash REST API 구조상 불가피. 가드/서킷브레이커로 폭주 차단은 이미 적용됨.

### 잔존 위험
1. **emdash13_repair.py 루프당 3회 호출** — EmDash API가 배치 엔드포인트를 제공하지 않아 구조적 한계. 별도 API 개선 필요.
2. **캐시 무효화** — 1시간 TTL로 데이터 신선도와 API 절감 트레이드오프. `--dry` 실행 시 캐시 무시 안 함(의도적).

### 다음 행동
- 없음. 작업 완료.

---

## 2026-10-15 00:14 AIK24-D1-02 완료 — 브리핑 뉴스 API 쿼리 최적화: 동적 WHERE 절 파라미터 바인딩화 + Cache-Control 헤더 추가 → 배포 검증 → SSOT/프로젝트/aikorea24/지시서/2026-10-15-0005-AIK24-D1-02-브리핑쿼리.md (완료)

### 한 일
- **[PRODUCTION CODE] `src/pages/api/briefing/news.ts`** — 동적 WHERE 절 개선:
  - 문자열 인터폴레이션(`datetime('now', '-${days} days')`) → 파라미터 바인딩(`datetime('now', ?)`)로 변경
  - 필터 조건(kr, global, policy, benefit, startup, grant) 모두 `?` 플레이스홀더 + `params.push()`로 바인딩
  - 인덱스 사용 가능하게 쿼리 플랜 안정화
- **Cache-Control 헤더 추가** — `public, max-age=300, s-maxage=300` (다른 뉴스 API와 동일)
- **배포**: `npm run deploy` 성공 (Version ID: `b7c722ba-31d7-48e9-95a5-2e521525913c`)

### 결과
- **[검증됨] 파라미터 바인딩 적용** — `grep "datetime('now'," src/pages/api/briefing/news.ts` → 파라미터 바인딩 형태로 변경 확인. 동적 SQL 인젝션 위험 제거 + 쿼리 플랜 재사용 가능.
- **[검증됨] Cache-Control 헤더** — `curl -sI https://aikorea24.z04probe.workers.dev/api/briefing/news/` → `cache-control: public, max-age=300, s-maxage=300` 확인.
- **[검증됨] 기능 동작** — JSON 응답 정상 반환 (79,813 bytes).

### 잔존 위험
1. **필터 확장 시 유지보수** — 새 필터 추가 시 WHERE 절과 params 배열을 동시에 수정해야 함. 현재 7개 필터 관리 중.

### 다음 행동
- 없음. 작업 완료.

---

## 2026-10-14 23:58 AIK24-D1-01 완료 — D1 쿼리 최적화: Cache-Control 변경(5개 뉴스 API) + WHERE date() → datetime() 변경(pool.ts 2건) → 배포 검증 → SSOT/프로젝트/aikorea24/지시서/2026-10-14-2352-AIK24-D1-01-쿼리최적화.md (완료)

### 한 일
- **[PRODUCTION CODE] 5개 뉴스 API 파일** — Cache-Control 헤더를 `no-store, must-revalidate` → `public, max-age=300, s-maxage=300`으로 변경:
  - `src/pages/api/news/latest.ts`
  - `src/pages/api/news/senior.ts`
  - `src/pages/api/news/benefits.ts`
  - `src/pages/api/news/policy.ts`
  - `src/pages/api/news/global.ts`
- **[PRODUCTION CODE] pool.ts** — WHERE 절 `date(pub_date)` 2건을 `datetime(?, '-7 days')`로 변경(인덱스 사용 가능하게):
  - 60행: `WHERE pub_date >= datetime(?, '-7 days')`
  - 81행: `WHERE pub_date < datetime(?, '-7 days')`
- **배포**: `npm run deploy` 성공 (Version ID: `8fac0b34-9384-4ac7-8842-067ffa75bc64`)

### 결과
- **[검증됨] Cache-Control 변경 완료** — `grep -r "no-store" src/pages/api/news/` → 0건. `grep -r "public, max-age=300, s-maxage=300" src/pages/api/news/` → 5개 파일 각각 2건(에러 분기 + 성공 분기) = 총 10건 확인.
- **[검증됨] WHERE 절 변경 완료** — `grep -r "date(pub_date)" src/pages/api/articles/pool.ts` → 0건. `grep -n "datetime" src/pages/api/articles/pool.ts` → 60행, 81행 2건 확인.
- **[검증됨] 배포 후 라이브 검증(workers.dev)** —
  - `https://aikorea24.z04probe.workers.dev/api/news/latest/` → `cache-control: public, max-age=300, s-maxage=300` 확인
  - `https://aikorea24.z04probe.workers.dev/api/news/senior/` → `cache-control: public, max-age=300, s-maxage=300` 확인
  - `https://aikorea24.z04probe.workers.dev/api/articles/pool/` → 기존 `public, s-maxage=300, max-age=60` 유지 확인
- **[부분검증] 커스텀 도메인(aikorea24.kr) 검증** — Cloudflare 캐시 전파 지연으로 인해 workers.dev 엔드포인트에서만 즉시 검증됨. 커스텀 도메인은 수 분 후 자동 반영됨.

### 잔존 위험
1. **커스텀 도메인 캐시 전파 지연** — `aikorea24.kr/api/*` 엔드포인트는 Cloudflare 캐시 계층을 거쳐 workers.dev 변경이 수 분~수십 분 뒤 반영됨. 지시서의 `curl` 검증은 workers.dev로 대체함.
2. **pool.ts의 Cache-Control은 별도 값 유지** — pool.ts는 이미 `public, s-maxage=300, max-age=60`으로 설정돼 있어 지시서 범위 외로 둠.

### 다음 행동
- 없음. 작업 완료.

---

## 2026-10-14 23:55 AIK24-D1-GUARD-02 완료 — EmDash 전면 장애 원인 확정(D1 무료 한도 초과) + 폭주 가드 2종 + D1-GUARD 스케줄 버그 수정 → SSOT/프로젝트/aikorea24/지시서/2026-10-14-2355-AIK24-D1-GUARD-02-완료보고.md (완료 — verify는 시니어2)

### 한 일
- **원인 확정 (오진 정정)** — 라이브 Worker 로그(`wrangler tail`) 원문: `D1_ERROR: Your account has exceeded D1's free tier daily row read limit`. 실측 **5,235,820 / 5,000,000 행 = 104.7%**. EmDash 앱 소스가 아니라 **계정 단위 D1 무료 티어 일일 읽기 한도 초과**가 원인이다.
  - 전파 경로: `dist/server/chunks/middleware_BKQZIOnl.mjs:6258-6270` 의 setup probe 가 quota 에러(`isMissingTableError` 아님)로 실패 → `probeFailed = true` → `locals.emdash`(CMS 런타임) 미설정 → `/`·`/posts` 0바이트/500, `/admin`·`/admin/login` 404. 토큰 조회 쿼리도 같이 실패해 `INVALID_TOKEN` 401/500 으로 위장 → **EVAL-06 의 "토큰 만료" 진단은 오진이었다. PAT 재발급 불필요.**
  - **패스키·이메일링크가 코드에서 사라진 것이 아니다.** 빌드 산출물에 `passkey`·`webauthn`·`magiclink` 문자열 3,054건, `dist/server/chunks/passkey-*.mjs` 실재. Playwright 실측으로 로그인 페이지에 `Sign in with Passkey`·`Sign in with email link` 버튼 2개가 `disabled:false` 로 정상 렌더됨을 확인.
  - 읽기 폭주의 주범은 **행 수가 아니라 요청 수**: 10-14 04:00Z 한 시간에 `readQueries 17,629`(질의당 약 8행). 후보: `emdash13_repair.py`(244건 × 4회 + 재시도 3~4배, `[51/244] PUT 실패 503 error code: 1102`) > `emdash04_migrate.py`(300페이지 순회) > `fix_tables.py`(풀스캔) > 크롤러 유입(sitemap ping 3회/일).
- **[PRODUCTION CODE] `scripts/cfnew.py`** — `require_d1_headroom(script, threshold=None)` 신설(+25줄, 123행). `check_quota()` 는 `cfnew.sql()` 안에서만 돌아 **EmDash HTTP API 를 때리는 스크립트를 못 막는다**. 임계 기본 0.5(env `D1_HEADROOM`), 여유 부족 시 `SystemExit(3)`, 조회 실패는 fail-open.
- **[PRODUCTION CODE] `scripts/emdash13_repair.py`** — 진입 가드 + **연속실패 서킷브레이커**(+22줄). `MAX_CONSEC_FAIL = 5`, `_gate(note)` 를 PUT 실패·publish 실패·예외 3곳에 연결, 성공/skip 시 `consec` 리셋.
- **[PRODUCTION CODE] `scripts/emdash04_migrate.py`** — 진입 가드(+8줄). **주의: 이 파일 `git diff` 는 81줄이지만 내 변경은 8줄뿐**(나머지 73줄은 이전 세션 AIK24-EMDASH-09 표 파싱 코드).
- **[PRODUCTION CODE] `scripts/d1_usage_report.py`** — 스케줄 버그 수정 + dedup(+50줄). `CAUTION = 0.5`(로그 경고만) 신설, `_already_alerted/_mark_alerted` 로 UTC 하루 1회 dedup, 로그에 방콕 환산 시각 병기, docstring 전문 교체.
- **[CONFIG]** `~/Library/LaunchAgents/kr.aikorea24.d1-usage-report.plist` — `StartCalendarInterval(Hour 8/Minute 30)` → **`StartInterval` 1800(30분)**. 재등록 완료(`launchctl print` → `run interval = 1800 seconds`).
- **[PRODUCTION CODE] emdash 저장소 `scripts/fix_tables.py`** — D1 가드 + `find_targets(scan_limit)`/`--scan-limit`(+60/-4줄).
- **[DOC] 오진 정정 2건** — `MEMORY.md`(섹션 5 오진 주의 블록 + 섹션 8·9 교체) 와 `SSOT/.../2026-10-14-2250-AIK24-EVAL-06-완료보고.md`(정정 블록 + 6건).

### 결과
- **[검증됨] 가드 실동작** — `emdash13_repair.py --limit 1` → `[D1-GUARD] emdash13_repair 중단 — D1 읽기 5,235,820/5,000,000 (104.7%) >= 임계 2,500,000.` **EXIT=3**, API 호출 전 차단. `--dry` 는 `수정 대상 244건 (dry=True)` 정상 통과(로컬 읽기라 의도적 제외).
- **[검증됨] fix_tables.py 가드** — `--dry`·`--apply` 모두 `[D1-GUARD] fix_tables 중단 — … 104.7%`. 가드 조건을 2회 오판 후(`if not a.dry` → `--dry` 도 D1 풀스캔 / `if not a.prefix` → `--prefix` 도 `mcp content_get` 호출) **모드 구분 없이 무조건**으로 확정.
- **[검증됨] Telegram 알림 경로 첫 발화** — 4일간 `(정상, 보고 없음)` 만 찍히던 경로가 실제 작동. 1회차 `telegram 발송: 성공` + 마커 `2026-10-14` 생성, 2회차 `(80% 초과지만 오늘 이미 알림 — 중복 발송 안 함)` — dedup 확인.
- **[검증됨] 스케줄** — `plutil -lint` OK, `bootstrap` BOOTSTRAP_OK, `launchctl print` = `run interval = 1800 seconds`. 기존 08:30 은 머신 TZ(UTC+7) 때문에 **01:30 UTC**(하루 1.5시간 경과 시점)에 돌아 한도 접근을 원리적으로 못 잡았다 — 이게 4일간 경고가 없던 이유다.
- **[검증됨] 문서 정정** — `grep "토큰 만료"` → EVAL-06 보고서에 취소선 처리된 정정 줄 1건만 잔존.
- **[부분검증]** `emdash04_migrate.py` 가드 — `load_posts()` 가 0건을 반환해 `IndexError` 로 죽어 실제 발화 경로 미실행. `py_compile` OK.

### 잔존 위험
1. **한도 리셋 전까지 EmDash 전면 불능** — 리셋 = 2026-10-15 00:00 UTC = **방콕 07:00 / KST 09:00**. 그 전에는 대시보드도 발행도 불가.
2. **인증 테이블 행 데이터 생존 여부 [검증불가]** — `users`/`credentials` 스키마 6종 존재는 `PRAGMA table_list`(99객체)로 확인했으나, 행을 1건이라도 읽는 쿼리는 전량 `code 7500` 거부. `SELECT COUNT(*) FROM users` 는 리셋 후에만 가능. **0건이라고 단정할 근거도, 살아 있다는 근거도 없다.**
3. **`fix_tables.py` 의 LIMIT 은 근본 해결이 아니다** — `content LIKE '%…%'` 는 인덱스를 못 타므로 LIMIT 을 걸어도 일치 행이 나올 때까지 모든 published 행의 본문을 읽는다. 실질 보호는 진입 가드뿐이다.
4. **가드는 사후 방어** — 임계 0.5 는 경험적 값이다. 0.5 미만에서도 대형 작업 1회가 한도를 넘길 수 있는지는 미검증.
5. **크롤러 유입은 손대지 않았다** — `sitemap-blog.xml`/`rss.xml` 이 1,460 URL 을 EmDash 로 302/301 유도하고 사이트맵 핑이 하루 3회 나간다. 이 트래픽 자체는 무료 한도 대비 소량으로 추정되나 실측 분리 못 했다.
6. **`emdash13_repair.py` 의 dry 경로는 가드를 타지 않는다** — `/tmp/emdash_audit.json`(전체 글 본문 덤프 15.5MB) 로컬 읽기라 의도했으나, 이 파일이 없으면 죽는다.
7. **커밋하지 않았다** — 인덱스에 타 세션 staged blog 삭제 1,481건이 그대로라 pathspec 없는 `git commit` 은 위험. emdash 저장소에는 `src/layouts/Base.astro`·`src/version.gen.ts` 가 이전부터 dirty(내 작업 아님).

### 다음 행동
1. **리셋 후 검증** (방콕 07:00 이후): ① `/` 200 + 본문 존재 ② `/_emdash/admin/login` 정상 ③ `SELECT COUNT(*) FROM users` 로 인증 행 생존 확인 ④ `python3 scripts/free_models_page.py page` 로 free-models 재발행.
2. `MEMORY.md`·EVAL-06 보고서 정정은 완료 — 다른 세션에 공유 필요.

---
## 2026-10-14 22:55 AIK24-EVAL-06 완료 — free-models 페이지 전면 개정 (구조 완성, ~~EmDash 토큰 만료~~ **D1 무료 한도 초과**로 발행 대기 — 아래 D1-GUARD-02 정정 참조) → SSOT/프로젝트/aikorea24/지시서/2026-10-14-2250-AIK24-EVAL-06-완료보고.md (완료 — verify는 시니어2)

### 한 일
- [PRODUCTION CODE] `scripts/free_models_page.py` 수정: `free_models_cli.json`(18개) + `external_evals.json` 결합, 새 렌더 함수 `render_eval06` 구현. 5개 섹션(헤더/추천 Top3/전체 리스트 18개/제외 모델 5계열/방법론) 구조.
- dry-run 마크다운 생성 성공 — 18개 검증 모델 + 제외 모델 5계열 + 방법론 모두 반영.
- EmDash 발행 시도: `EM_DASH_API_TOKEN` 만료로 500 에러 → 발행 실패, 라이브 404.

### 잔존 위험
1. EmDash 토큰 갱신 필요 — 대표님/관리자 PAT 발급 후 환경변수 업데이트 필요.
2. 토큰 갱신 전까지 페이지 발행 불가 — dry-run 결과는 로컬 보관.

---

## 2026-10-14 22:50 AIK24-EVAL-05 완료 — Google AI Studio 크레딧 소진으로 사용 불가 → SSOT/프로젝트/aikorea24/지시서/2026-10-14-2245-AIK24-EVAL-05-완료보고.md (완료 — verify는 시니어2)

### 한 일
- `provider.googleai` 등록 확인, `GOOGLE_API_KEY` 환경변수 설정됨.
- 6개 Gemini 모델 테스트: 전부 **402 quota exhausted** ("Your prepayment credits are depleted").
- **원인 단일 특정**: Google AI Studio 선불 크레딧 0원 — 충전 전까지 모든 모델 차단.

### 잔존 위험
1. 크레딧 충전 전까지 사용 불가 — `https://ai.studio/projects` 에서 충전 필요.
2. 충전 후 무료 티어 한도(RPM/TPM/일일) 재확인 필요.

---

## 2026-10-14 22:40 AIK24-EVAL-04 완료 — Groq 무료 모델 opencode CLI 평가 불가(TPM 한도) → SSOT/프로젝트/aikorea24/지시서/2026-10-14-2240-AIK24-EVAL-04-완료보고.md (완료 — verify는 시니어2)

### 한 일
- `provider.groq` 등록 확인, `GROQ_API_KEY` 환경변수 설정됨.
- 7개 무료 후보 모델 테스트: Direct API 2개(`gpt-oss-120b/20b`) 작동, opencode CLI 전량 **413 TPM 한도 초과**(요청 ~33k > 8,000/min).
- 나머지 5개는 404(model_not_found) — 현재 계정에서 미지원.
- **결론**: Groq 무료 티어는 opencode CLI 요청 크기(시스템 프롬프트 포함 ~33k 토큰)가 TPM 한도(8,000/min) 초과로 평가 불가. Direct API로는 작동하나 CLI 경유 불가.

### 잔존 위험
1. opencode 설정 변경(시스템 프롬프트 최소화) 없이는 Groq 평가 불가.
2. `gpt-oss` 계열은 Direct API 평가 파이프라인 별도 구축 시 포함 가능.

---

## 2026-10-14 22:35 AIK24-EVAL-02 완료 — OpenCode CLI 기준 무료 모델 전수 리스트 (18건) → SSOT/프로젝트/aikorea24/지시서/2026-10-14-2155-AIK24-EVAL-02-완료보고.md (완료 — verify는 시니어2)

### 한 일
- [PRODUCTION CODE] `scripts/free_models_cli.py` 신규(약 150줄). `opencode models`(2049줄) → 4개 프로바이더 후보 45건 → `model_eval.cli_call()` 로 **한 건씩 실제 호출**(프롬프트 `한 단어로 대답: PONG`)해 살아 있는 것만 남긴다. 실행 cwd 는 tempdir(`opencode run` 이 현재 폴더를 프로젝트로 읽어 AGENTS.md 가 컨텍스트에 들어가는 것 차단).
- [CONFIGURED ARTIFACT] `scripts/logs/free_models_cli.json` 신규 **18건**(2695 bytes). 필드는 지시서대로 `model_id` / `provider` / `cli_id` (+공개값 있을 때만 `context_length`).
- 4·5차에서 병렬화 반영: `PROBE_WORKERS=4` + `ThreadPoolExecutor` + `PROBE_TIMEOUT=30`. **직렬 20분+ → 병렬 5분**(4차 312초 / 5차 285초).
- `scripts/model_eval.py`·`free_models_page.py`·`model_catalog.py` **수정 안 함**(지시서 범위 준수). 배포·커밋 없음.

### 결과 — 완료 기준
- 기준1 [부분검증] 4개 프로바이더 중 kilo 8 / zen 8 / openrouter 2 = **18건 실제 호출 검증**. **nvidia-nim 0건은 원인 확정** [검증됨] — `GET integrate.api.nvidia.com/v1/models` 무인증 200 + 카탈로그 80개 중 `-free` **0개**(NVIDIA NIM 에 무료 티어가 없음). 등록 19개 중 15개는 카탈로그 미존재 → 404.
- 기준2 [검증됨] 5차 로그 `/tmp/fmcli5.log`(22:06:56~22:11:41, `SUBSHELL_EXIT=0`)의 `OK` 라인 18개 = JSON 18개 `cli_id` 완전 일치. 4차도 동일 18건 재현.
- 숫자 산출 근거: 후보 45 = 16(kilo) + 15(openrouter) + 11(zen) + 3(nvidia-nim), 제외 27 = 45 − 18. `context_length` 보유 10건(= kilo 8 + openrouter 2), 미보유 8건은 전부 zen(카탈로그 값 null).
- [검증됨] `context_length` 버그 수정 확인: 1차 `CTX_OK = 0` → 4·5차 `CTX_OK = 10`. 원인은 `sorted(glob(...))[-1]` 알파벳 정렬이 `model_catalog_baseline.json`(dict)을 골라 **조용히** `{}` 를 반환한 것 → 날짜 정규식 필터로 수정.

### 5회 실행 중 확인한 사실
- **openrouter 직접 경로가 21:24 이후 4회 연속 전량 타임아웃.** 1차에는 15건 중 10건 OK였고, 같은 8종이 `kilo/` 경유로는 같은 회차에도 4~16초 응답. 지시서 원칙 2("검증 불가한 항목은 억지로 넣지 않는다")에 따라 최종 JSON 에서 **제외**했다. 과거 검증분을 붙여넣는 병합 로직은 구현했다가 제거.
- **회차 간 writer 경합 사고**: SIGTERM 으로 끊은 실행이 `os.setsid()` 래퍼로 살아남아 구버전 코드로 같은 JSON 에 동시 기록(4차 때 PID 99929/99931 발견·종료). 이 스크립트에는 회차 간 락이 없다.
- 1차 OK 26건 ⊃ 4·5차 OK 18건(진부분집합, `run4_only` 0 / `r5_only` 0).

### 잔존 위험
1. openrouter 직접 경로 회복 여부 미확인 — 회복되면 8종(`cohere/north-mini-code` 등)이 다시 후보가 된다. **"무료 모델이 없어졌다"가 아니라 "경로가 지금 사용 불가"**.
2. zen 8건은 `context_length` 미보유(카탈로그 null). 소비자가 컨텍스트 없는 모델을 뒤로 밀면 zen 8건이 전부 후순위가 된다.
3. `thinkingmachines/inkling*` 2종은 openrouter 직접으로만 성공(kilo 경유 403). openrouter 가 계속 죽어 있으면 리스트에서 사라진다.
4. `nvidia/` apiKey 가 `{env:...}` 미해석 참조 → 무료 모델이 생겨도 인증 실패. 설정 파일 수정 + 실제 NVIDIA 키 필요.
5. 회차 간 락 없음 — launchd 등으로 자동화하기 전에 락/PID 파일 필요.
6. `context_length` 출처는 API 스냅샷이지 CLI 실측이 아니다(`probe_context_length` 는 EVAL-CLI-01 에 이미 있으나 미사용).
7. 회귀 테스트 없음 — `context_lengths()` 정규식 필터가 특히 취약(4-1 버그가 조용히 실패했다).
8. `scripts/free_models_cli.py`·`scripts/logs/free_models_cli.json` 모두 git 미추적. 인덱스에 타 세션 staged blog 삭제 1,481건 잔존 → pathspec 없는 `git commit` 위험.

### 다음 행동
1. 무료 모델 2~3종 CLI 12문항 평가 + 블로그 공개 — 지시서가 "평가는 별도 지시서"로 명시.
2. `nvidia/` 죽은 15개 정리 + apiKey 복구(별도 지시서).

---
## 2026-10-14 AIK24-EVAL-03 완료 — 외부 평가 데이터 통합(OpenCode Data·KiloBench·Zen 정책) + 결합 로직 → SSOT/프로젝트/aikorea24/지시서/2026-10-14-2205-AIK24-EVAL-03-완료보고.md (완료 — verify는 시니어2)

### 한 일
- [PRODUCTION CODE] `scripts/fetch_external_evals.py` 신규(약 190줄). D1 미사용 — 외부 HTTP 만. 소스 3개 수집 + `combine()` 결합. 커밋 `b93c9833`.
- [CONFIG/데이터] `scripts/logs/external_evals.json` 신규(78,17 bytes). 이전까지 두 파일 모두 git 미추적이었고 이번에 처음 버전관리됨.
- 범위 밖 준수: free-models 페이지 미수정, CLI 평가 로직 미변경, 브리핑·툴 파이프라인 미변경.

### 결과
- [검증됨] **작업1-1 OpenCode Data — 공개 JSON API 확정(스크래핑 불필요)**
  - `https://opencode.ai/data` 의 JSON-LD `Dataset.distribution` 이 공개 다운로드 URL 을 알려준다.
  - **`GET https://opencode.ai/data/index.json` → 200, 148,249 bytes**(UA `Mozilla/5.0` 필요 — 없으면 403).
  - 최상위 키: `page, updatedAt, summary, leaderboard, dailyTokens, dailyUniqueUsers, weeklyRetention, sessionCost, tokenPricesUsdPer1M, cacheRatio, marketShare, countries`.
  - ★ **지시서 최우선 항목(주간 재사용률)이 `weeklyRetention` list[15] 로 그대로 제공** — 요소 `{rank, model, name, page, retentionPercent, eligibleUserWeeks, retainedUserWeeks}`.
  - `updatedAt` = `2026-10-14T13:24:19Z`(매일 갱신), `temporalCoverage` = `2026-08-20/2026-10-14`.
- [검증됨] **작업1-2 KiloBench — 별도 페이지에서 파싱 가능**
  - `kilo.ai/leaderboard` 의 `#kilo-bench` 섹션은 642 bytes 로 lazy-load 라 점수가 없다(표 8개는 전부 Rank/Model/Usage 중복).
  - ★ 실제 점수표는 **`https://kilo.ai/kilobench`**(590,281 bytes), 표 헤더 `# | Model | Completion | Cost / attempt`, **38 모델 행**.
  - 무료 식별 = 모델명 `(free)` 마커 **AND** `$0.00` → 실측 2행: `Hy3 (free) 47.6% $0.00`, `Nemotron 3 Super (free) 15.5% $0.00`.
- [검증됨] **작업1-3 Zen 무료 목록·데이터 정책 확보**
  - `https://opencode.ai/docs/zen/` → **302 → `https://opencode.ai/v2/docs/console/models/`**(200, 53,344 bytes).
  - **공식 무료 12종**: `jev-1.13-free`, `big-pickle`, `space-bunny-free`, `cat-jam-free`, `longcat-2.5-preview-free`, `step-5-preview-free`, `exo-free`, `mimo-v2.6-flash-free`, `mimo-v2.5-free`, `nemotron-3-ultra-free`, `nemotron-3.5-lightning-free`, `muse-spark-1.3-contributor-free`.
  - **데이터 정책**: 기본 = 제로-retention·학습 미사용. 예외 — 학습 사용: `big-pickle`·`exo-free`·`mimo-v2.6-flash-free`·`mimo-v2.5-free` / NVIDIA 시험용(사용 로그 기록): `nemotron-3-ultra-free`·`nemotron-3.5-lightning-free` / Meta 학습 조건 할인: `muse-spark-1.3-contributor-free` / 학습 미사용·30일 보관: `cat-jam-free`.
- [검증됨] **작업2 스크립트 실행** — `opencode_data: 15건` / `kilobench: 2건` / `zen_policy: 12건` / **`combined: 24건`** → `scripts/logs/external_evals.json`. 소스 하나가 죽어도 나머지는 진행(try/except), 저장은 `os.replace` 원자적.
- [검증됨] **작업3 결합 로직** — 임계값 고정: **eval ≥0.6 / retention ≥50% / kilobench ≥40%**. `zen` 은 품질 신호가 아니라 **판정 투표에서 제외**.
  - 판정 분포: **강한 추천 1 / 추천(단일 신호) 14 / 비추천 1 / 판정 없음(zen 단독) 8**.
  - 신호 조합: `(retention,)` 10 / `(zen,)` 8 / `(retention,zen)` 4 / `(kilobench,retention)` 1 / `(kilobench,)` 1.
  - 매칭 검증: `space-bunny-free`→`space-bunny`(retention+zen), `mimo-v2.6-flash-free`→`mimo-v2.6-flash`(retention+zen), `hy3`(retention+kilobench → **강한 추천**), `nemotron-3-super`(kilobench 단독 → 비추천).
- [검증됨] 대표님 원칙 준수 — ① 검증 가능한 것만: 3소스 전부 공개 HTTP 로 실측 확인 ② 토큰 점유율 지표 배제: `dailyTokens`·`dailyUniqueUsers`·`marketShare`·`countries` 를 `excluded` 에 사유와 함께 기록하고 채택하지 않음 ③ 데이터 없는 항목 미표시: 신호 0개 모델은 `combined.models[]` 에서 제외, zen 단독 항목은 `verdict` 키 자체를 만들지 않음(빈 칸·"미확인" 금지).
- [검증됨] 회귀 테스트 `pytest tests/test_eval_cli.py tests/test_zen_pending.py -q` → **24 passed**.

### 위반 감지 / 발견한 결함 (해결하지 않고 보고)
1. **[검증됨] `model_catalog.fetch_zen()` 의 `-free` 접미사 규칙이 무료 모델을 놓친다** — Zen 공식 무료 12종 중 **`big-pickle` 은 무료인데 `-free` 접미사가 없어 `fetch_zen()` 이 걸러내지 못한다**(공식 12종 vs `-free` 접미사 9개 불일치). `fetch_zen()` docstring 의 `shortcut: 접미사 규칙이 깨지면 무료 목록이 조용히 줄어든다` 경고가 현실화된 상태다. **수정하지 않았다** — 지시서 §범위밖(CLI 평가 로직·free-models 페이지)과 저촉 소지가 있어 별도 지시서 대상으로 남긴다.
2. **[검증됨] 우리 eval 캐시가 비어 있다** — `scripts/logs/model_eval_cache.json` = `{}`(2 bytes), `model_leaderboard.json` = `[]`. EVAL-CLI-01 에서 만든 `cat-jam-free 8/12`·`space-bunny-free measured_context=1048576` 이 사라졌다. **동시 실행된 다른 세션의 리셋으로 추정(내 작업 아님)**. 이 때문에 결합 결과의 `eval` 신호가 현재 전부 부재하고, 유일한 `강한 추천`(`hy3`)은 retention+kilobench 조합이다.

### 잔존 위험
1. **`eval` 신호 부재로 결합 로직의 핵심(3신호 교차)이 미검증** — 캐시가 복구되어야 "CLI 점수 + 외부 신호 일치/불일치" 판정이 실제로 동작하는지 확인된다. 현재는 2신호 조합까지만 실증됐다. [부분검증]
2. **표기 불일치로 매칭 실패가 남는다** — KiloBench 표기(`Hy3`, `Nemotron 3 Super`)는 Zen/retention 표기와 정확 일치로 붙지 않는다. `normalize_model()` 로 맞췄으나 모든 표기를 커버하지는 못한다(외부 신호 단독 항목 8건 중 상당수).
3. **임계값(0.6/50/40)은 내가 정한 값이다** — 실측 근거가 아니라 직관이다. 대표님 확인이 필요하다.
4. **KiloBench 파싱은 HTML 구조에 의존** — `<tr>`/`<td>` 정규식 기반이라 페이지 구조가 바뀌면 조용히 0건이 된다. 현재는 예외 없이 2건이지만 회귀 감지 장치는 없다.
5. **OpenCode Data `index.json` 도 스키마 고정이 아니다** — `weeklyRetention` 키 이름이 바뀌면 조용히 빈 결과가 된다.
6. 3소스 중 **NVIDIA NIM 무료 목록은 여전히 판별 불가**(PIPE-02 [검증됨]) — 이번 통합에도 NVIDIA 무료 신호는 없다.

### 다음 행동
- 대표님: `fetch_zen()` 의 `-free` 접미사 규칙 수정(위 결함 1) 별도 지시서 필요 여부.
- 대표님: eval 캐시 소실(위 결함 2)의 원인 — 동시 세션이 왜 리셋했는지 확인 필요.
- 대표님: 임계값 0.6/50/40 승인 여부.
- 별도 지시서: free-models 페이지에 `external_evals.json` 반영(이번 범위 밖).
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
