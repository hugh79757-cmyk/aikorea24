# Phase 11 Defense Hardening — External AI Review Prompt

## 배경
Threads 자동발행 파이프라인에서 프롬프트트킹(모델 설명 메시지)과 중국어/일본어 문자가 가끔 발행되는 문제가 있습니다. 현재 3중 방어 체계(피치 생성, 쓰레드 작성, 발행 전)와 여러 검증 함수가 있지만, 일관성 부족과 중복 패턴 정의 등 문제점이 있습니다.

Phase 11에서는 다음과 같은 개선을 제안했습니다:
1. 패턴 중복 통합 — writer.py의 로컬 `MODEL_MESSAGE_PATTERNS` 제거하고 validator에서 import
2. `validate_final_output()`가 `ALL_MESSAGE_PATTERNS`(26개) 전체를 사용하도록 변경
3. `validate_final_output()`의 한글 비율 기준을 10% → 30%로 상향 조정 (일관성)
4. `validate_model_message()`의 링크 카드 검사에 `.strip()` 추가
5. writer에서 죽은 코드 `validate_no_foreign_language` import 제거
6. `write_thread()` 전체 검증 체인을 검증하는 통합 테스트 추가
7. 문서 업데이트

## 현황과 문제점
- `validate_final_output()`는 현재 8개 패턴만 적용 (ADDITIONAL 18개 누락)
- writer와 validator에 `MODEL_MESSAGE_PATTERNS` 정의가 중복됨
- 한글 비율 기준: validate_model_message/structure ≥30%, final_output ≥10% (너무 낮음)
- link card check에서 strip 불일치
- `validate_no_foreign_language`는 작성자에서 불러오지만 실제 쓰이지 않음
- write_thread() 전체 validation chain을 검증하는 E2E 테스트 없음

## 질문 (한국어로 답변 요청)

1. **개선 방안**: 위 제안 외에 추가로 고려해야 할 개선 사항이 있나요? (예: 새로운 탐지 기법, 검증 순서 최적화, 예외 처리 등)

2. **방지 확률**: 현재 방어 체계 대비 Phase 11 개선 후 문제(프롬프트트킹/중국어) 방지 확률이 얼마나 올라간다고 보시나요? (현재 추정 방지율 ~85-90% 가정, 개선 후目標?)

3. **효과 비교**: 제안한 변경들이 기존 방지책보다 효과가 더 좋을까요? 아니면 일부 중복되거나 영향이 미미한 부분도 있나요?

4. **누락된 시나리오**: 현재 패턴 기반 검사로 커버되지 않을 수 있는 새로운 모델 메시지 패턴이나 우회 기법이 있을까요?

5. **구현 리스크**: 패턴 중복 제거와 threshold 상향로 인해 기존 테스트 실패나 가양성/가음성 증가 가능성은 어떻게 되나요?

6. **구조적 검증**: Structural validation (validate_card_structure)만으로도 충분할까요, 아니면 pattern 기반 검사가 여전히 필요한가요?

7. **대안 검토**: LLM 자체 프롬프트 개선(instruction to avoid leakage)과 현재 코드 기반 검증 중 어느 것이 더 효과적이라고 보시나요?

의견을 가능한 구체적으로 주시고, 제안의 타당성과 위험도를 평가해 주세요. 감사합니다.
