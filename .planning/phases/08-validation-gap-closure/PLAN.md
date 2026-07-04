# Phase 8: Validation Gap Closure

## Goal
최종 카드 발행 전 프롬프트 노출/외국어 검증을 **2중·3중 안전장치**로 방어.
"지금은 다됐다"는 결론을 신뢰하지 않는다 — 반드시 터진다.

## Mode
ad-hoc

## Depends on
Phase 7

## 핵심 철학
> **완벽해 보일 때가 가장 위험하다.**
> Phase 6가 피치에만 검증 적용 → "해결됨" → 결국 최종 카드에서 재발.
> 어떤 검증도 단 한 곳에서만 의존해서는 안 된다.

## Requirements
- REQ-08-01: 최종 카드에 프롬프트 노출 검증 적용
- REQ-08-02: `detect_prompt_leak()`에 `LEAKED_PROMPT_PATTERNS` 통합
- REQ-08-03: 외국어 + 프롬프트 노출 통합 검증 함수
- REQ-08-04: **3중 방어 체계** 구축
- REQ-08-05: 검증 갭이 TECH.md에 문서화됨

## Success Criteria
1. `validate_final_output()` 함수가 프롬프트 노출 + 외국어 + 한글 비율을 통합 검증
2. **1차 방어**: 피치 생성 시 (`validate_korean_output` + `detect_prompt_leak`)
3. **2차 방어**: 쓰레드 작성 후 (`validate_final_output` — 최종 카드 검증)
4. **3차 방어**: 발행 전 (`validate_cards` + `validate_final_output` 체이닝)
5. `detect_prompt_leak()`가 `LEAKED_PROMPT_PATTERNS` + `_SYSTEM_PROMPT_FRAGMENTS` 모두 검사
6. 모든 테스트 통과, 197개 이상

## Plans
- [ ] 08-01-PLAN.md — 3중 방어 체계 구축

## 반복 오류 방지 교훈
> 1. 검증 로직은 "해당 단계 출력"이 아니라 "다음 단계 입력" 기준으로 설계할 것
> 2. 단일 검증점에 의존하지 말 것 — 반드시 fallback 체인
> 3. "해결됨"이라고 안심하지 말 것 — 반드시 회귀 테스트로 확인
