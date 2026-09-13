---
date: 2026-09-12
type: config
status: resolved
---

# LLM 폴백 체인 확장 — OpenRouter 무료 4종 + Gemini/NVIDIA/Groq2 추가 (9→16 tier)

## What
쓰레드 파이프라인 LLM 폴백 체인을 9 tier → 16 tier로 확장. 2차 작업(당일 오후)으로
OpenRouter 새 키 발급 + 무료 모델 4종 체인 추가. 발행 실패 원인이 "체인 전체 동시 소진"
이었으므로 무료 tier 다각화로 재발 방지.

## Why
- 14:16-14:22 발행 2연속 실패: groq 3 tier TPD 소진, orca 2 tier 계정 자격 429,
  zhipu 일일 제한, mistral JSON 실패, cohere 400, 유료 DeepSeek 401(키 무효) —
  9 tier 전부 동시 사망이 근본 원인
- 무료 tier 수가 적어 오후 고갈이 잦음. 파이프라인 1회 발행에 수십 회 LLM 호출

## Files changed
- `.env` — GEMINI_API_KEY, GROQ_API_KEY_2, OPENROUTER_API_KEY (sk-or-v1-bff...cd4) 추가
- `config/models.yaml` — providers: gemini/groq2/nvidia/openrouter 추가. tier_order:
  기존 9 + groq2 2 + gemini 1 + nvidia 1 + openrouter 4 = 16 tier (default 유료 맨 뒤)
- `scripts/threads/v3/model_router.py` — 수정 0건 (제네릭 provider 처리라 불필요)

## How
1. OpenRouter 무료 모델 19개 목록 조회 → 한국어+프로브로 선별:
   - or-nexpro (nex-agi/nex-n2.5-pro:free) — 스모크 ✅ 6.2s
   - or-nexmini (nex-agi/nex-n2.5-mini:free) — 스모크 ✅ 0.8s, 체인 내 최속
   - or-nemotron (nvidia/nemotron-3-super-120b-a12b:free) — curl ✅ 1.0s, 스모크 빈 choices (thinking 모델 mt=200 아티팩트로 추정)
   - or-lingvl (inclusionai/ling-3.0-flash-vl:free) — curl ✅ 1.6s, 스모크 429 (free 분당 제한, 일시적)
   - 탈락: gemma-4-26b 429, poolside 429, lfm-2.5 빈 content, nemotron-ultra 35s timeout
2. 새 키는 is_free_tier=true, usage 0 확인
3. Gemini 키는 1개 고유값이 3곳 등록됨: project .env GEMINI_API_KEY == ~/.env.common
   GOOGLE_API_KEY == ~/.env.common GEMINI_API_KEY (전체값 일치 검증) — 쿼터 1개 공유

## Verification
- curl 프로브: nex-pro 200(2.2s), nex-mini 200(0.67s), nemotron-super 200(1.0s), ling-vl 200(1.6s) — 한국어 content 정상
- smoke_test_chain.py 8/16: 새 tier 중 or-nexpro✅ or-nexmini✅. 8/16 수치는
  max_tokens=200 아티팩트(gpt-oss 3종, zhipu) + orca 429(GitHub 연동 전) + 유료 키 401 포함 — 실 writer 호출(수천 토큰)과 무관한 항목들
- 16:04 실발행 성공 — 5카드 + 링크 답글 (루트 ID 18122478067876109)으로 체인 가동 확인

## Verification 제약
[부분검증] or-nemotron/or-lingvl은 실발행 트래픽에서 아직 미검증 — 다음 발행 로그로
content 품질 확인 필요. 실패해도 회전만 되고 정상 tier가 흡수하므로 파이프라인 정지 없음

## Follow-up (같은 날 저녁)
- OrcaRouter GitHub 연동 완료 (사용자 OAuth "binding successful")
- orca 2 tier 부활 확인: ds4free 200 OK 1.8s, hy3 200 OK 3.0s (mt=500 필요 —
  thinking 모델이라 mt=200은 빈 content)
- smoke_test_chain.py 8/16 → 12/16 (16 tier 중 orca 2 + 신규 4 중 2 등 증가)
- 스킬 카탈로그 orca 상태 ❌→✅ 갱신 완료
