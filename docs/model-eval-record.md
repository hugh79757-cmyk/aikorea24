# 모델 실측 기록 운영 절차 (AIK24-PIPE-11 작업 2)

> 작성: 2026-10-22 · 관련: `AIK24-PIPE-10` 완료보고 §6-3 · `scripts/model_attribution.py`

## 왜 필요한가

AIK24-PIPE-10 **규칙 2** 는 "정량 실측 수치는 실제 실행 기록이 있을 때만 본문에 넣는다" 를 자동 발행에서
강제한다. 기록이 없으면 해당 글은 **발행 보류(hold)** + 사유 기록 + 알림 된다.

- 검사 기준: `scripts/model_attribution.py::evaluated_model_ids()` — 실행 기록 존재 확인
- 기록으로 인정하는 정본 3종:
  1. `scripts/logs/model_eval_cache.json` (모델별 평가 캐시)
  2. `scripts/logs/model_leaderboard.json` (리더보드)
  3. `scripts/logs/model_eval_runs.jsonl` (실행 로그, append-only)
- 2026-10-22 보정: `scripts/logs/*eval_result*.json` (1회성 평가 산출물) 도 **임시로** 기록으로 인정한다.
  단, 정본 등록이 정석이며 이 보정은 임시 안전장치다.

## 사람이 직접 실측한 경우의 절차

### 1. 실측 → 결과 객체 만들기

`model_eval.cache_put(model_id, result)` 의 `result` 는 아래 키를 쓴다(최소한 model_id·점수·실측일).

```python
result = {
    "model_id": "recursive/flint-v1.0:free",   # OpenRouter 모델 ID (정본 키)
    "score": 9,                                 # 정답 수
    "max_score": 12,                            # 문항 수
    "failed": 0,                                # 응답 실패 수
    "details": {...},                           # 문항별 결과
    "by_axis": {...},                           # 축별 점수
    "measured_context": 262144,                 # 실측 컨텍스트 길이
}
```

### 2. 정본에 적재 (이 한 줄이 규칙 2 통과의 조건)

```bash
cd /Users/twinssn/Projects/aikorea24
.venv/bin/python3 -c "
import sys; sys.path.insert(0, 'scripts')
import model_eval, json
result = json.load(open('<결과.json>', encoding='utf-8'))
model_eval.cache_put(result['model_id'], result)
"
```

`cache_put()` 은 실패해도 조용히 넘기지 않는다(로그 남김) — **로그에서 "저장" / "생략" 중 무엇이 떴는지 반드시 확인**한다.
- 응답 실패가 절반을 넘으면(전멸) 저장을 **의도적으로 건너뛴다**(점수 0이 순위를 오염시키는 것 방지).
- 저장되면 정본 3종이 한꺼번에 갱신된다: 캐시(`model_eval_cache.json`) · 실행 로그(`model_eval_runs.jsonl`) ·
  리더보드(`model_leaderboard.json`).

### 3. 통과 확인

```bash
.venv/bin/python3 -c "
import sys; sys.path.insert(0, 'scripts')
import model_attribution as ma
print('recursive/flint-v1.0:free' in ma.evaluated_model_ids())
"
```

True 면 해당 모델을 언급하는 글은 규칙 2 에서 hold 되지 않는다.

## 주의

- **특정 모델의 `cache_put` 실행 자체는 대표님 결정 사항**이다(AIK24-PIPE-11 지시서 §작업 2 명시).
  이 문서는 절차만 정의하고, 특정 모델을 기록하는 실행은 하지 않는다.
- 1회성 산출물(`*eval_result*.json`)만 남기고 정본에 적재하지 않으면:
  - 규칙 2 는 통과한다(12:10 보정) — 단, **캐시 TTL(20시간) 이후에는 실측 기록이 사라진다**
    (`cache_get()` 은 TTL 이 지나면 None 을 돌려준다).
  - 리더보드·재평가 경로에는 반영되지 않아 모델 점수가 누락된다.
  → **정본 적재가 정석**이며, 1회성 파일은 보정용이다.
- 점수는 문항 체계 버전(`EVAL_QUESTIONS_VERSION`, 현재 2)과 함께 의미가 있다. 문항이 바뀌면
  스키마 불일치로 재평가 대상이 되므로(캐시가 자동으로 무효화된다) 점수를 그대로 재사용하지 않는다.
- 채점기 오탐이 있는 채점(2026-10-22 Recursive Flint 평가: 인라인 백틱·정확일치 규칙)은
  **코드를 고치지 않으면** 보정 점수가 정본에 "오탐 보정 전 점수"로 남는다. 보정 사실을
  `result["notes"]` 에 남겨 두고, 가능하면 채점기 수정이 별도 지시로 진행한다.
