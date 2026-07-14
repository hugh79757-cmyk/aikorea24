---
date: 2026-07-14
type: refactor
status: resolved
---

# writer_v3: 프롬프트 오버엔지니어링 제거 + OpenAI 검증 제거

## What
Threads 쓰레드 생성 시스템 프롬프트(`build_system_prompt_D()`)를 150줄 → 20줄로 다이어트.
GPT-4o-mini에 의존하던 2개 검증/수정 단계 제거.

## Why
- 150줄 프롬프트가 오히려 비문을 유발 (예: `~이라고 되고 싶지 않다` — 강제 줄바꿈 35자 제한 + 과도한 stanza 규칙 충돌)
- `humanize_cards()`는 CoT 훅 약화로 이미 제거됐으나, `_fix_one()`(MiMo 오류수정) + OpenAI fallback이 남아 있어 DeepSeek에 대한 불신 구조
- "프롬프트로 모든 걸 규제하려는" 오버엔지니어링이 품질을 떨어뜨림

## Files changed
- `pipeline/threads/writer.py`

## How
1. **`build_system_prompt_D()` 전면 재작성**: 150줄 → 20줄
   - 제거: 줄 길이 제한(20~35자), stanza 구조, 어미 규칙표(~임/~했음), 금지 패턴 10개, 대비 구조 설명, 숫자-설명 쌍 규칙, 연도 원칙, 키워드 규칙, 카드 역할 정의
   - 유지: 6카드 포맷, 500자 제한, 한자/일본어 금지, 고유명사 영어 유지, 반말체, JSON 출력 형식, 예시 4개
2. **`fix_cards()` 내 `_fix_one()` 제거**: OpenAI GPT-4o-mini로 글자 오류 수정하던 단계 삭제. 정규식 클린업만 남김.
3. **OpenAI fallback 제거**: DeepSeek 2회 실패 시 GPT-4o-mini로 fallback하던 코드 제거.
4. **user prompt 중복 규칙 정리**: "한 줄 20~35자" 등 시스템 프롬프트와 중복되던 요구사항 제거. 한국어에서 영어로 변경.

## Key principle
"예시 4개면 DeepSeek가 충분히 패턴을 학습한다. 프롬프트로 규제하지 말고, 자연스러운 한국어를 신뢰하자."

## Verification
- Python syntax check 통과 (`py_compile`)
- 기존 validators (validate_cards, validate_year, validate_keywords, validate_card_structure, validate_final_output) — 전부 정규식/패턴 기반, AI 미사용 — 유지
- 다음 쓰레드 발행 주기부터 변경사항 적용됨
