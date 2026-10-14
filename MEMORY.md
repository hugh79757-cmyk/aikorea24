# AIK24 프로젝트 메모리 — 정책·관례·누적 지식

> 이 파일은 세션 간 전달되는 핵심 정책과 관례를 기록한다. 주니어가 인계받을 때 가장 먼저 읽어야 한다.
> 갱신: 2026-10-14 (AIK24-EVAL-06 완료 시점)

---

## 1. 무료 모델 페이지 갱신 정책 (AIK24-EVAL-06, 2026-10-14 대표님 확정)

**핵심 원칙**: **날짜를 매일 바꾸지 않는다.**

| 상황 | 조치 | 갱신 날짜 표시 |
|------|------|---------------|
| 모델 리스트에 실제 변경(추가/제거) 발생 | 페이지 갱신 + `마지막 갱신: YYYY-MM-DD` 업데이트 | 변경일로 갱신 |
| 모델 리스트 변경 없음 | 페이지 **그대로 둠** (갱신 안 함) | 기존 날짜 유지 |
| 외부 평가 데이터만 갱신됨 (리스트 동일) | 페이지 **그대로 둠** | 기존 날짜 유지 |

**구현 위치**: `scripts/free_models_page.py` → `cmd_page()` / `cmd_daily()` 에서 diff(`added`/`removed`/`changed`) 확인 후 분기.

**이유**: 독자가 "오늘 날짜인데 내용이 똑같네"라며 신뢰를 잃지 않게 하기 위함. 무료 모델 페이지는 **변경 로그**이지 **일일 리포트**가 아니다.

---

## 2. 대표님 확정 원칙 (무료 모델 조사·평가 공통)

1. **검증된 것만 싣는다.** — CLI 호출로 실제 동작 확인된 모델만. 서비스 안 되는 것(Hy3 등) 제외.
2. **검증 불가 항목은 넣지 않는다.** — 빈 칸·"미확인"·추측 금지. "가능하다면"이 안 되면 항목 자체를 뺀다.
3. **모든 평가는 CLI 기준, API 호출 금지.** — OpenCode에서 선택할 수 없는 모델은 테스트 명단에 올리지 않는다.
4. **비용 섹션 없음.** — 무료 모델 페이지에 비용은 불필요.
5. **실용적 추천.** — "이 용도엔 이 모델" 식의 판단 근거 제공.

---

## 3. 프로바이더별 현황 (2026-10-14 기준)

| 프로바이더 | 검증 모델 | 상태 | 비고 |
|-----------|----------|------|------|
| **kilo** | 8개 | ✅ 검증됨 | NVIDIA Nemotron, Poolside, Cohere, Liquid, Dots Studio |
| **openrouter** | 2개 | ✅ 검증됨 | thinkingmachines/inkling* (직접 경로만 작동) |
| **zen (OpenCode)** | 8개 | ✅ 검증됨 | mimo, space-bunny, muse-spark, cat-jam, longcat, nemotron 2종, step-5 |
| **nvidia-nim** | 0개 | ❌ 무료 티어 없음 | 80개 모델 중 `-free` 0개, 404 |
| **groq** | 0개 | ⚠️ CLI 평가 불가 | Direct API 2개 작동, opencode CLI TPM 한도(8k/min) 초과 |
| **googleai** | 0개 | ⚠️ 크레딧 소진 | 402 quota exhausted — 충전 전까지 차단 |
| **cerebras** | 0개 | ❌ 제외 | 카드 필수로 제외 확정 |

---

## 4. 데이터 소스 및 파일 위치

| 용도 | 파일 | 비고 |
|------|------|------|
| CLI 검증 모델 (18개) | `scripts/logs/free_models_cli.json` | `free_models_cli.py` 산출 |
| 외부 평가 데이터 | `scripts/logs/external_evals.json` | `fetch_external_evals.py` 산출 (retention, kilobench, zen_policy) |
| 모델 리더보드 | `scripts/logs/model_leaderboard.json` | CLI 평가 점수 기록 |
| 모델 캐시 | `scripts/logs/model_eval_cache.json` | 평가 상세 결과 |
| free-models 페이지 | `https://emdash.aikorea24.kr/posts/free-models` | EmDash 고정 슬러그 |

---

## 5. EmDash 발행 규칙

- 고정 슬러그: `free-models` (매일 같은 URL)
- `title` 필드에 slug 문자열 입력 → EmDash가 자동 slugify
- `slug` 필드는 **없음** (400 unknown field 에러)
- PUT은 published 항목에도 draft revision으로 스테이징 → **publish 후행 필수**
- 인증: `Authorization: Bearer <EM_DASH_API_TOKEN>` + `X-EmDash-Request: 1` + `Origin`
- 토큰 만료 시 `INVALID_TOKEN` 401/500 → PAT 재발급 필요
- **⚠️ 오진 주의 (2026-10-14 정정)**: 그날의 `INVALID_TOKEN`/500 은 **토큰 만료가 아니었다.**
  D1 무료 한도 초과로 토큰 조회 쿼리 자체가 실패해 401 로 위장된 것이다. 토큰을 재발급해도
  한도가 소진된 동안에는 똑같이 실패한다. EmDash 전체가 죽었을 때는 **먼저 `/` 가 0바이트인지,
  `/_emdash/admin/login` 이 404 인지**를 보고 D1 사용량을 의심할 것.

---

## 6. 실행 환경 주의사항

- `opencode run` 은 **현재 폴더를 프로젝트로 인식** → `scripts/` 에서 돌리면 `AGENTS.md` 가 컨텍스트에 들어감
- **해결**: `os.chdir(tempfile.gettempdir())` 로 임시 디렉터리로 이동 후 실행
- `opencode models` 명령: JSON 플래그 없음, 프로바이더 인자 없음 → 전체 파싱 후 grep 필터링
- `opencode models <provider>` 전부 exit 1

---

## 7. 병렬화·성능 (EVAL-02에서 확립)

- 직렬 45건 → 20분+ → **병렬 4워커 + 30초 타임아웃 = 5분**
- `ThreadPoolExecutor(max_workers=4)` + `PROBE_TIMEOUT=30`
- 타임아웃 시 15초 대기 후 1회 재시도

---

## 8. 잔존 위험 (다음 세션 인계용)

1. **D1 무료 한도 초과 가능성 (2026-10-14 실사고)** — 계정 D1 은 5,000,000행/일 (자정 UTC 초기화).
   초과하면 EmDash 관리자 로그인·게시물 렌더·API 가 **전부** 죽는다(`/` 0바이트, `/admin/login` 404).
   폭주 원인은 행 수가 아니라 **요청 수**(한 시간에 최대 1.7만 질의).
   → 이제 `cfnew.require_d1_headroom()` 가 폭주 스크립트 진입부를 막고, D1-GUARD 가 30분마다 감시한다.
   수동 확인: `.venv/bin/python3 -c "import sys;sys.path.insert(0,'scripts');import cfnew;print(cfnew.get_daily_rows_read(force=True))"`
2. **openrouter 직접 경로 4회 연속 타임아웃** — 회복 시 8종 재추가됨 (kilo 경유로는 정상)
3. **Groq TPM 한도** — opencode 시스템 프롬프트 최소화 없이는 CLI 평가 불가
4. **Google AI 크레딧 소진** — `ai.studio/projects` 충전 필요
5. **회차 간 락 없음** — `free_models_cli.py` 동시 실행 시 JSON 경합 발생 (`os.setsid()` 래퍼가 SIGTERM 회피)

---

## 9. 다음 행동 (우선순위)

1. **D1 한도 리셋(자정 UTC = 방콕 07:00) 후** → EmDash 대시보드 로그인·게시물 복구 확인,
   quota 로 막혔던 인증 테이블 행 데이터 생존 확인(`SELECT COUNT(*) FROM users`)
2. **`free_models_page.py page` 재실행** → free-models 페이지 발행 (토큰은 문제가 아니었으므로 재발급 불필요)
3. **CLI 평가 2~3종 진행** — 별도 지시서에서 `model_eval.py` CLI 평가 실행 → 블로그 발행
4. **Google AI 크레딧 충전** 후 `googleai` 프로바이더 추가 재탐색
5. **Groq Direct API 평가 파이프라인** 필요 시 별도 구축

---

*이 문서는 세션마다 `docs/state.md`와 함께 갱신된다. 주니어는 `MEMORY.md` + `docs/state.md` 맨 위 30줄로 현황 파악 가능.*