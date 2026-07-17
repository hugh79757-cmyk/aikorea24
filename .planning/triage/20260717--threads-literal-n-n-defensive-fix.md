---
date: 2026-07-17
type: fix
status: resolved
---

# Threads 리터럴 `\n\n` 줄바꿈 누출 방어

## What
Threads 발행글에서 `\n\n`이 실제 줄바꿈이 아닌 리터럴 텍스트로 노출되던 문제.
save_draft hexdump에서 `5c 6e 5c 6e` (리터럴 `\n\n`) 확인됨 — Threads에 "AI가 생성한 티" 노출.

## Why
**근본 원인**: DeepSeek V4 Flash API가 JSON 생성 시 `\n`(JSON 개행 이스케이프) 대신 `\\n`(이중 이스케이프, 리터럴 백슬래시+n)을 출력하도록 행동 변경 (2026-07-17 05:31~07:35 사이).

**악화 요인**: `response_format={"type": "json_object"}`가 `chat_completion()` 호출 시 전달되지 않아 API 수준 JSON 강제가 없었음. Phase 15(d844c09)에서 "DeepSeek unstable" 이유로 제거됨.

**방어 부재**: `add_line_spacing()`이 리터럴 `\` 문자를 실제 개행으로 치환하지 않아 Threads API에 리터럴 `\n\n`이 그대로 전송됨.

## Files changed
- `pipeline/threads/writer.py` (line 513): `_try_model()`에 `response_format=json_schema` 추가
- `scripts/threads/publisher.py` (line 239): `add_line_spacing()` 전처리에 `text.replace('\\n', '\n')` 추가

## How
1. **writer.py**: `json_schema = {"type": "json_object"}`가 선언만 되어있던 것을 `_try_model()`의 `chat_completion()` 호출에 `response_format` 파라미터로 전달 — API 수준에서 JSON 출력 강제
2. **publisher.py**: `add_line_spacing()` 시작부에 `text.replace('\\n', '\n')` 추가 — 모델이 `\\n`을 출력해도 실제 개행으로 변환하는 2차 방어

## Additional: 종결어미 ~다 일괄 전환 문제
- 15:54 발행에서 모든 문장이 `~다/~했다`로 종결 — 조회수 300 (정상 1000+)
- 동일한 DeepSeek API 행동 변경의 영향으로 추정
- **시도 1 (hard ban)**: `~다/~했다/~ㄴ다 절대 금지` → 롤백 (모델 창의성 저해 우려)
- **시도 2 (soft guidance)**: `종결어미 ~임/~했음/~있음 중심. ~다/~했다 신문 기사체 지양` → 최종 채택
- 원칙: 금지가 아닌 이유(대화체 vs 신문 기사체)를 알려주는 soft guidance. 모델 판단 존중.

## Files changed (additional)
- `pipeline/threads/writer.py` (line 58): 종결어미 영문 → 한국어 soft guidance로 교체

## Monitoring
- `\n\n` 리터럴: 다음 발행부터 정상 줄바꿈 예상
- 종결어미 `~임`/`~다` 비율: 모니터링 필요
- 조회수 추이: 300(비정상) vs 1000+(정상) — `~다` 비중과 상관관계 확인
