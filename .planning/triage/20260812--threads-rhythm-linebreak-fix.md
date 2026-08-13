---
date: 2026-08-12
type: fix
status: resolved
---

# Threads RHYTHM 줄바꿈 통일: 지시문 강화 + add_line_spacing 단일 \n 유지

## What
쓰레드 자동 발행물에서 짧은 절 단위 줄바꿈(RHYTHM) 스타일이 일부 게시물에서만 적용되고 일부는 긴 통단락으로 발행되던 불일치 문제를 해결했다.

## Why
- 2026-08-12 RHYTHM 지침이 시스템 프롬프트에 추가됐으나, (1) LLM이 절 사이에 빈 줄(\n\n) 대신 단일 \n만 쓰는 경우가 있었고, (2) publisher의 `add_line_spacing()`이 단일 \n을 "구조화되지 않은 텍스트"로 간주해 문장 단위 재분할해버리면서 절 리듬이 파괴됐다.
- 지시문도 "~할 수 있음"이라는 권고 수준이라 LLM이 일관되게 따르지 않았다.
- 조회수 차이: 리듬 있게 짧게 줄바꿈된 글은 기본 2000+ 조회수, 길게 늘여쓴 글은 300~500 조회수로 약 4~7배 차이.
- GPT-4o-mini는 구형 모델로 어떤 글쓰기에도 사용하지 않도록 제거.

## Files changed
- `pipeline/threads/writer.py` — RHYTHM 지시문 강화 (권고 → 명령, 출력 예시 추가)
- `scripts/threads/publisher.py` — `add_line_spacing()` 단일 \n 유지 로직으로 확장
- `scripts/threads/v3/model_router.py` — GPT-4o-mini 완전 차단
- `pipeline/threads/pitch_evaluator.py` — `model_override='openai'` → `None`
- `pipeline/threads/writer.py` (humanize_cards) — `model_override='openai'` → `None`
- `scripts/threads/ARCHITECTURE.md` — `model_override` 옵션 문서화 갱신

## How
- 지시문: "빈 줄로 절 사이에 리듬의 쉼을 만들 수 있음" → "절과 절 사이에는 반드시 빈 줄(\n\n)을 넣어라. 빈 줄이 리듬의 쉼표다." + 출력 예시 추가. 권고 → 명령으로 변경.
- 처리 로직: 기존 `if '\n\n' in text` → `if '\n' in text`로 확장. 단일 \n도 AI가 의도한 절 단위 줄바꿈으로 간주하고 그대로 유지. 통단락(개행 없음)만 문장 단위 분할.
- GPT-4o-mini 제거: `model_router.py`에서 `model_override='openai'` 호출 시 차단 메시지 출력 후 `None` 반환. `pitch_evaluator.py`와 `writer.py` humanize_cards에서 `model_override='openai'` → `None`으로 변경.

## Verification
- `add_line_spacing()` 단위 테스트 6케이스 모두 통과 (빈 줄 유지, 단일 \n 유지, 통단락 분할, 혼합 구조, 리터럴 \n 방어)
- 예시 입력: `"AI가 내 돈을\n대신 관리해준다고?\n핀테크 앱이\n은행 계좌에 접근함"` → 그대로 유지됨 (기존에는 문장 분할돼서 리듬 파괴됐음)
