---
date: 2026-07-12
type: fix
status: resolved
---

# Hook 첫 문장 두괄식 개선 — 이해관계 + 구체성 강화

## What
Threads 자동 발행 시 1번 카드(통념) 첫 문장을 **두괄식(핵심 주장 → 구체 근거)**으로 재구성하여 독자 유지율 개선.
- 기존: 상황 묘사로 시작 ("애들 노리는 콘텐츠를 사람 눈으로 거르던", "아이폰을 8년 만든 엔지니어가...")
- 개선: **독자 이해관계(돈/안전/일/권리) + 기사만의 구체적 사실(숫자/인물/기관/결과)** 결합

## Why
첫 2줄이 노출 영역(Threads UI)에서 독자가 계속 읽을지 결정함. 기존 구조는 "무슨 일이지?" 상황 호기심만 유발하고 "내게 왜 중요한가" 가치 약속이 약했음. 두괄식으로 가치 약속 + 구체성 동시 전달.

## Files changed
- `scripts/threads/v3/style_examples.md` — 4개 예시 첫 문장 전부 교체 (틱톡/로빈후드/애플/스페이스X)
- `pipeline/threads/writer.py` — `build_system_prompt_D()` 1번 카드 가이드에 두괄식 첫 줄 명시
- `pipeline/threads/writer.py` — `write_thread()` user_prompt hook 변환 지시 재작성 (이해관계+구체성 원칙 + 3개 변환 예시)

## How
1. **Few-shot 교체**: style_examples.md 4개 예시 첫 문장 → 두괄식(핵심 주장 — 구체 근거) 패턴
2. **System Prompt 구조 명시**: 1번 카드 stanza1 첫 줄 = "두괄식 핵심 주장(한 문장, 35자 내). 둘째 줄 = 구체 근거(숫자/인명/기관)"
3. **User Prompt 변환 지시 강화**: "상황 묘사(X) → 이해관계+구체성(O)" 원칙 + 3개 변환 예시(틱톡/로빈후드/애플)

## Verification
- style_examples.md 4개 예시 첫 문장 모두 두괄식 패턴 확인
- writer.py system/user prompt 변경 사항 문법 확인 (py_compile 통과)
- 다음 발행(launchd 2시간 주기)부터 적용 확인 예정