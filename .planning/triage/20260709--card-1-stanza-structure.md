---
date: 2026-07-09
type: fix
status: resolved
---

# Card 1/2/5 prompt refinements (Phase 16-18)

## What
Phase 16 writer prompt v2 dry-run 샘플 분석 결과 3개 이슈 발견:
1. 1카드 줄바꿈 안 됨 — "기사 본문 인용 금지"로 인해 추상적 통념만 길어짐
2. 5카드 닫힌 결론 — "선언형 마무리"가 답을 주는 구조
3. 5카드 꼬리 — 질문 뒤에 "수렴함" 등 메타 진술 붙음

## Why
1. 프롬프트가 "기사 본문 직접 인용 금지" → 구체적 숫자/인명 부재 → 줄바꿈 단위 안 생김
2. "여운/선언형 마무리" → GPT-4o가 답을 줌
3. 질문 후 추가 문장 금지 규칙 부재

## Files changed
- `pipeline/threads/writer.py` (build_system_prompt_D, write_thread user prompt)
- `scripts/threads/v3/style_examples.md` (card structure template)

## How
3단계에 걸쳐 수정:
1. Card 1: "기사 본문 인용 금지" 제거 → 통념+전환+증거 구조
2. Card 1: 3-stanza 강제 (stanza1: 통념2줄 → stanza2: 전환+증거 → stanza3: 증거 각1줄)
3. Card 5: "질문 이후 어떤 문장도 추가 금지" + 메타 진술("되돌아보면"/"결국"/"수렴함") 금지
4. 줄바꿈 규칙: 20~30자 통일, 35자 초과 시 줄바꿈, 40자 이상 절대 금지
5. 통념 프레이밍: 긍정 통념 → 부정 현실 구조 명시화

## Verification
2회 dry-run 샘플에서 1카드 증거 포함 확인, 5카드 열린 질문 확인.
줄바꿈 개선은 다음 dry-run에서 확인 예정.
