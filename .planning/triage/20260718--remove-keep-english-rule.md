---
date: 2026-07-18
type: refactor
status: resolved
---

# 고유명사 영어 원문 유지 규칙 제거 — 모델 자유도 향상

## What
프롬프트의 "고유명사는 영어 원문 유지" 규칙을 삭제하고, 이 규칙 때문에 존재하던 코드 레벨 후처리(`_clean_english_leakage`, `_fix_korean_particle_spacing`)를 제거함.

## Why
이 규칙이 오히려 역효과를 내고 있었음:
- `SpaceX` → `스페이스` (X 탈락)
- `OpenAI` → `오픈` (AI 탈락)
- 기사 원문이 이미 정답이므로, 프롬프트로 강제할 필요 없음
- 규칙 제거로 복잡성 ↓ → 모델 자유도 ↑

## Files changed
- `pipeline/threads/writer.py` — build_system_prompt_D() 규칙 삭제 + fix_cards 후처리 2개 함수 제거
- `pipeline/threads/pitch.py` — _LANG_SECTION 동일 규칙 삭제
- `scripts/threads/v3/writer_v3.py` — 삭제된 함수 import 정리
- `tests/test_writer.py` — 삭제된 함수 관련 테스트 3개 클래스 제거

## How
- 프롬프트: `고유명사(기업·인물·제품명)는 영어 원문 유지` 라인 삭제
- 코드: `_clean_english_leakage()` (한글 사이 영어 제거 regex), `_fix_korean_particle_spacing()` (영어-조사 공백 추가 regex) → fix_cards 단순화

## Verification
- 276/277 테스트 통과 (1 pre-existing, 변경 무관)
- 커밋: `448c121` (`main`)
