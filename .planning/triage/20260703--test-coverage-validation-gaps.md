---
date: 2026-07-03
type: fix
status: ongoing
---

# 체계적 방지 프레임워크 — 테스트 커버리지 갭 발견

## What
5-Layer Korean Language Defense Framework의 테스트 커버리지에 갭 발견. `validate_korean_output`, `detect_prompt_leak` 단위 테스트와 fallback 흐름 검증이 누락됨.

## Why
현재 17개 테스트는 validate_korean_output을 전혀 커버하지 않음. 특히:
- 영어 hook 모킹 → _lang_valid=False → fallback 재시도 흐름
- prompt leak 탐지 → fallback 재시도 흐름
- detect_prompt_leak 단위 테스트

이 3개 경로는 실제 프로덕션 장애가 발생했던 경로임. 빠진 커버리지가 정확히 "장애가 났던 경로".

## Files changed
- `pipeline/threads/pitch.py` (5레이어 적용 완료)
- 테스트 파일 (아직 미추가)

## How
추천 테스트 케이스 3건:
| 테스트 | 입력 | 기대 결과 |
|--------|------|-----------|
| `test_english_hook_triggers_fallback` | `hook="Boeing's Wisk Aero faces..."` | `_lang_valid=False`, fallback 호출 |
| `test_prompt_leak_triggers_fallback` | narrative에 시스템 프롬프트 일부 포함 | `detect_prompt_leak=True`, fallback 호출 |
| `test_normalize_output_truncation` | hook 200자 입력 | `[:100]`으로 잘려서 저장됨 |

## Verification
- 아직 테스트 미추가 상태 (status: ongoing)
- 5레이어 구현 자체는 py_compile ✅ / pytest 17/17 ✅ / 한국어 검증 로직 수동 테스트 ✅
- 15% threshold 현실 검증 완료: "AI 기반 B2B SaaS 스타트업 XYZ가 Series A 투자 유치" → 37.9% ✅
