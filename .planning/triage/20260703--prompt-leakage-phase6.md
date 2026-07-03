---
date: 2026-07-03
type: fix
status: resolved
---

# Phase 6: Prompt Leakage & Truncation Fix

## What
Threads 발행글 hook/narrative에 프롬프트 라벨(`상식(A):`, `실제(B):`)이 누출되고, 30/50자 강제 트렁케이션으로 문장이 중간에 잘리는 문제 수정. 이후 `validate_korean_output()`, `detect_prompt_leak()`, `_lang_valid` 게이트, JSON 모드 → 한국어 검증 → fallback 체인 추가.

## Why
- LLM이 시스템 프롬프트의 "상식(A) vs 실제(B)" 템플릿을 그대로 출력에 복사
- `[:30]`/`[:50]` 하드 트렁케이션으로 hook/narrative가 문장 중간에서 절단
- JSON 모드가 깨져 프롬프트가 출력에 새는 경우 탐지 불가능

## Files changed
- `pipeline/threads/pitch.py` — `clean_leaked_prompt()`, `LEAKED_PROMPT_PATTERNS`, `detect_prompt_leak()`, `validate_korean_output()`, `_lang_valid` 게이트
- `scripts/threads/v3/model_router.py` — `response_format` 파라미터 + `**kwargs` 전달
- `tests/test_pitch.py` — `TestDetectPromptLeak`(3), `TestValidateKoreanOutput`(5), `TestNormalizeOutput`(5) = 13개 단위 테스트
- `pipeline/posted.json` — 오염 entry 18건 정리
- `scripts/threads/posted.json` — 오염 entry 54건 정리

## How
- **Layer 1**: `response_format={'type': 'json_object'}` — LLM 출력을 JSON으로 강제, 프롬프트 누출 근본 차단
- **Layer 2**: `detect_prompt_leak()` — JSON 모드가 깨져도 프롬프트 누출 탐지
- **Layer 3**: `validate_korean_output()` — 15% 한글 threshold, 영어/빈 hook fallback
- **Layer 4**: `_lang_valid` 게이트 — `_lang_valid=False`면 fallback 재시도
- **Fallback**: JSON → 일반 텍스트 → detect_prompt_leak → validate_korean_output

## Verification
- 17/17 triage 테스트 통과
- 15% threshold 검증: "AI 기반 B2B SaaS" 37.9% ✅, "OpenAI의 ChatGPT가" 31.4% ✅, 순영어 0% ❌
- _lang_valid + _lang_reason 이제 posted.json pitch_history에 저장
- 전체 파이프라인 테스트 영향 없음 (기존 192/193 통과)
