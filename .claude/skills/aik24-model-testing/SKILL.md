---
name: aik24-model-testing
description: Use when testing, benchmarking or measuring any LLM in the aikorea24 project — 12문항 평가(model_eval.py) 실행, 무료 모델 실측 결과 확인, "모델 테스트 결과"로 블로그 글 쓰기, 또는 새 측정·하네스·벤치마크 스크립트를 만들려고 할 때. Triggers: "모델 테스트", "12문항", "모델 평가", "벤치마크", "측정 스크립트", "하네스", "실측 결과", "모델 점수", "어떤 모델이 낫나".
---

# aik24-model-testing — 이 프로젝트의 모델 테스트 기준

> ⛔ **이 스킬을 열었다는 것은 새 측정 도구를 만들려는 순간이라는 뜻이다.**
> 아래 "0. 생성 전 게이트"를 먼저 통과하지 않고 파일을 만들지 않는다.
> 2026-11-15: 게이트를 건너뛰고 `eco-bench.network.ts`를 만들어
> 이미 존재하던 12문항 평가를 놓쳤다 — 토큰·$0.0037·글 1건 낭비 + 글 회수.

## 0. 생성 전 게이트 (AIK24-PREFLIGHT-01) — 순서 고정, 생략 금지

1. **먼저 찾는다.** 만들기 전에 **cwd 기준**으로 검색한다.

   ```bash
   cd /Users/twinssn/Projects/aikorea24 && \
   grep -rln -E "model_eval|12문항|eval_model|벤치마크|측정 스크립트|하네스|실측" \
     scripts/ docs/ tests/ *.md .planning/ 2>/dev/null
   ```

   - **직전 작업이 어떤 저장소였든 지금 서 있는 곳을 검색한다.**
     모델이 *호출되는* 곳(link2threads)과 모델이 *평가되는* 곳(aikorea24)은 다르다.
   - 지시문이 "결과로 올려줘"라면 → **이미 있는 결과를 찾는다.**
     "결과를 만들어 올려줘"로 바꿔 읽지 않는다.

2. **0건 = `[검증불가]`.** "없음"으로 단정하지 않는다. 보고에 `[검증불가]`로 올리고
   사용자에게 **"이 프로젝트에 이미 재는 측정 도구가 있나요?"** 를 **먼저** 묻는다.
   답을 받기 전 새 파일을 만들지 않는다.

3. **기존 하네스를 답습한다.** 이 프로젝트의 기준은 아래 12문항이다.

---

## 1. 기준 하네스: `scripts/model_eval.py` (AGENT-EVAL-01)

### 문항 구성 — 12문항, 가중치는 의도적 불균등

| 축 | 문항 | 근거 |
|---|---|---|
| 코딩실무 | 4 | 버그·테스트·리팩토링·명세 구현 |
| 에이전트 | 4 | tool/CLI 환경에서의 실무 |
| 지시이행 | 2 | 형식·경계(contract compliance) |
| 맥락유지 | 2 | 장문 문서 참조 |
| **합계** | **12** | 코딩+에이전트 = 8/12 = 67%. 챗봇 글쓰기 항목은 의도적으로 축소 |

- `TEST_QUESTIONS` (model_eval.py:168~), `EVAL_QUESTIONS_VERSION = 2`
- 채점은 **결정적 함수**: `grade_q1_korean_sentinel` … `grade_q12_priority_split` (9개)
  + 공통 분기 `grade_answer()`
- **판관 모델은 폐지됨** (`AIK24-EVAL-JUDGE-04`) — 같은 답안은 언제나 같은 점수.
  `eval_variance.py`는 `[비활성]` 레거시다. 다시 살리지 말 것.
- **sandbox 실행검증**: `sandbox: True` 문항은 말이 아니라 코드를 실제로 돌려 본다
  (예: `get_expired_tokens` — 고친 코드를 reference와 대조)

### 호출 경로 — OpenCode CLI 단일 경로

> 2026-10-14 대표님 결정: **"모든 평가는 OpenCode CLI 기준, 기존 API 데이터 전부 폐기."**
> OpenRouter 직접 HTTP는 `eval_model()` 에 남아 있으나 **기본 경로가 아니다.**
> CLI id를 못 찾으면 **점수 없이 제외**한다 ("OpenCode에서 선택 불가한 모델은 명단 제외").

```python
import model_eval
res, blocked = model_eval.eval_model_cli(model_id, cli_model=cli_id)   # 12문항
ctx = model_eval.probe_context_length(model_id)                        # 컨텍스트 프로브
model_eval.cache_put(model_id, res)                                    # 캐시는 이 함수만
```

CLI 1건 실행: `.venv/bin/python3 scripts/model_eval.py <model_id>`

### 제약값 — 건드리지 말 것

| 상수 | 값 | 의미 |
|---|---|---|
| `QUESTION_TIMEOUT` | 60초 (재시도 180초) | 문항당 |
| `QUESTION_MAX_TOKENS` | 1500 | 짧게 자르면 실무 답이 잘린다 |
| `RATE_GAP_SEC` | 4 | 문항 간격 — OpenRouter 무료 20req/min 대비 |
| `HTTP_429_RETRIES` | 3 | Retry-After/지수백오프 존중 (15→30→60초) |
| `CACHE_TTL_HOURS` | 20 | 하루 블리핑 안에서 재평가 금지 |
| `CACHE_SCHEMA` / `qv` | 4 / 2 | 문항 세트 버전. 바뀌면 캐시 전부 무효 |

### 실패·점수 표기 규칙 — 여기서 틀리면 수치가 거짓이 된다

- **429·타임아웃·첫 문항 도달 불가 ≠ 0점.** 1회 재시도 → 그래도 실패면 `retry`로
  다음 날 이월한다. **실패를 "0점"으로 기록하지 않는다** (능력 실패와 구분).
- **미응답 문항은 분모에서 뺀다.** `7/12 (미응답 2 제외)` 형태로 표기.
- **게이트 미달 글은 발행하지 않는다** → `scripts/logs/rejected/YYYY-MM-DD-...md` 보존.
  (2026-11-15: `longcat-2.5-free` 7/12 → 게이트 미달 → 발행 안 함)
- 캐시·리더보드 **JSON 직접 편집 금지** — `cache_put()` 만 쓴다 (EVAL-03 교훈).
  쓰기는 항상 tmp → `os.replace()` 원자적.

### 산출물

| 파일 | 내용 |
|---|---|
| `scripts/logs/model_eval_cache.json` | 모델별 상세 (by_axis·details·failures·measured_context) |
| `scripts/logs/model_leaderboard.json` | `{model_id, score, max_score, qv, ts, judge_failed_n}` — **상대비교** |
| `scripts/logs/model_eval_runs.jsonl` | 실행 원본 (elapsed_sec 등) |
| `scripts/logs/free-model-eval-auto.log` | 일일 파이프라인 로그 |

### 자동 실행 경로 (launchd)

```
kr.aikorea24.free-model-eval-auto  08:30  free_model_eval_auto.py run
   트리거 = 오늘 발행된 브리핑 항목 (카탈로그에 있다고 미리 재지 않는다)
   → opencode models 라이브 확인 → eval_model_cli → probe_context_length
   → cache_put → 결정적 템플릿 초안 → gate_draft → 발행
kr.aikorea24.verify-models         09:30  verify_models_daily.py  → model_eval.cli_call() PONG
kr.aikorea24.free-model-pipe                free_models_page.py page  (허브 렌더)
```

수동: `.venv/bin/python3 scripts/free_model_eval_auto.py run|status|evaluate <model_id> [--cli <id>]`

외부 지표는 `scripts/fetch_external_evals.py` — OpenRouter·Hugging Face·KiloBench
무료($0) 행만. 임정값 고정: eval ≥ 0.6 / retention ≥ 50% / kilobench ≥ 40%.

---

## 2. "모델 테스트 결과"로 글을 쓸 때

1. **이미 있는 결과부터 읽는다**: `model_leaderboard.json` + `model_eval_cache.json`
   (최신 순) + `free-model-eval-auto.log` + `docs/state.md`의 `### 12문항 실측 리뷰`.
2. 허브 글의 `### 12문항 실측 리뷰 (N개)` 절은 `free_models_page.py:625`가 렌더한다 —
   실측 글 제목 매칭으로 링크를 만든다. 새 글이 생기면 이 절에 자동으로 들어간다.
3. 표기는 **"7/12 (미응답 2 제외)"** 처럼 분모를 밝힌다. "7/12 통과"만 쓰지 않는다.
4. 점수와 급수를 대응시키지 않는다 — 티어 라벨은 `AIK24-EVAL-02`에서 삭제했다
   ("Claude Sonnet 4.5급" 같은 표기는 근거가 없다).

## 3. 12문항 밖의 일회성 측정을 해야 한다면 (예: 특정 모델의 카드 생성 실측)

**12문항과 같은 규율을 그대로 적용한다.** 여기서 어긋나면 결과는 공정하지 않다:

- **소재 길이는 실서비스 분포를 따른다.** 카드당 하한(300자/450자)을 거는 측정이라면
  소재도 그 하한 × 카드수 이상이어야 한다. 646자 소재 + 5장 + 300자 하한 =
  물리적으로 못 채우는 조건 (2026-11-15 실수).
- **대조군 없이 절대숫자를 쓰지 않는다.** 지금 운영 중인 모델을 같은 소재·같은
  게이트로 동시에 재서 상대 비교한다.
- **N ≥ 10.** 언어당 3회로 평균을 말하지 않는다.
- **지연은 입력 길이와 같이 보고한다.** 짧은 입력 지연을 실서비스 지연과 나란히 놓지 않는다.
- **실패·미응답·0점을 분리한다** (위 §1 규칙 그대로).
- 측정 스크립트는 **프로덕션 프롬프트·게이트를 import** 해서 단일 조건을 반복한다.
  별도 평가 프롬프트를 만들지 않는다.

## 4. 보고 형식

전역 `AGENTS.md` 섹션 2(3분법 · 금지어 · 근거 강제 · 잔존 위험)를 따른다.
"전부 통과"/"완료" 단독/✅만 있는 체크리스트 금지. 0건은 `[검증불가]`.

## 5. 이 스킬이 다루지 않는 것

- LLM 폴백 체인 운영 → 스킬 `llm-fallback-chain-management`
- 무료 모델 허브 글의 표 레이아웃·CSS → 스킬 `aik24-free-models-page`
- AI phase의 평가 계획 감사 → `gsd-eval-review` (모델 평가가 아니다)
