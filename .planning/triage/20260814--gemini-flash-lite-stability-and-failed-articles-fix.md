---
date: 2026-08-14
type: debug
status: ongoing
---

# gemini-3.1-flash-lite 안정화 + failed_articles 기록 버그

## What
1. **gemini-3.1-flash-lite 쓰레드 카드 생성 불안정** — JSON 파싱 실패, 한국어 처리 불안정
2. **5회 모두 실패 시 failed_articles 기록 누락** — 마지막 시도 기사가 기록되지 않아 동일 기사 재시도 위험

## Why
1. **gemini-3.1-flash-lite**: lite 모델의 추론 능력 한계, JSON 모드 불안정, 한국어 토큰화 문제
2. **failed_articles 버그**: `main_v3.py:372`에서 5회 모두 실패 시 로그만 남기고 종료 — `save_failed_article()` 호출 없음

## Files changed
- `config/models.yaml` — 모델 순서 변경 필요 (gemini-2.5-flash를 1순위로)
- `scripts/threads/main_v3.py:372` — 5회 실패 시 마지막 기사 기록 추가 필요
- `scripts/threads/failed_articles.py:50` — retention 2h → 24h 확대 검토

## How
1. **모델 교체**: `config/models.yaml`에서 `gemini-2.5-flash`를 1순위로 변경
2. **실패 기록 강제**: `main_v3.py` 루프 밖에서 마지막 시도 실패 기록
3. **retention 확대**: `failed_articles.py`에서 `_get_retention_days()` 기본값 2h → 24h

## Verification
- dry-run 실행으로 카드 생성 성공률 확인
- failed_articles.json에 5회 실패 시 기사 기록 확인
- 다음 실행 시 동일 기사 제외 확인

## Analysis Details

### gemini-3.1-flash-lite 문제 원인
| 원인 | 설명 |
|------|------|
| JSON 구조 파싱 실패 | lite 모델이 복잡한 JSON 카드 구조 생성 시 불안정 |
| 한국어 처리 불안정 | lite 모델의 한국어 토큰화 한계 |
| 화각(Hallucination) | 긴 카드 생성 시 사실과 다른 내용 생성 |
| temperature=0.4 + JSON 모드 충돌 | lite 모델에서 JSON 모드와 temperature 불안정 |

### 5회 실패 기록 버그
```python
# main_v3.py:128-374
for attempt in range(1, max_retries + 1):
    # ...
    if not result or not result.get('cards'):
        # Line 204-208: 실패 시 기록
        first_id = _get_first_article_id(pitch)
        if first_id:
            failed_articles.save_failed_article(aid_str, reason="write_validation_failed")
        continue
    
    # Line 372: 5회 모두 실패
    log(f'❌ {max_retries}회 모두 실패')
    # ⚠️ 여기서 마지막 시도의 기사가 기록되지 않음!
```

### 권장 모델 순서
```yaml
tier_order:
  - gemini-2.5-flash       # 1순위 (더 안정적)
  - gemini-3.5-flash-lite  # 2순위
  - gemini-3.1-flash-lite  # 3순위로 하향
```
