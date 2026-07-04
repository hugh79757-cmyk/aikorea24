---
date: 2026-07-04
type: fix
status: resolved
---

# Temperature & Model Priority Change

## What
- TEMPS [0.3, 0.1] → [0.4] 단일 온도로 변경
- 모델 우선순위 변경: MiMo v2.5 → 1순위, DeepSeek → 2순위, GPT-4o-mini → 3순위

## Why
- 0.3→0.1 fallback은 오류 원인 해결 불가 (비논리적)
- MiMo v2.5 성능 테스트 필요

## Files changed
- pipeline/threads/writer.py (TEMPS 변경)
- scripts/threads/v3/model_router.py (모델 우선순위 변경)

## How
- writer.py: TEMPS = [0.4] 단일 값
- model_router.py: MiMo v2.5 → DeepSeek → GPT-4o-mini 순서로 fallback

## Verification
- python3 -m py_compile 통과
- MIMO_API_KEY ~/.env.common에 존재 확인
