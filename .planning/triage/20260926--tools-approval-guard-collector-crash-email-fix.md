---
date: 2026-09-26
type: fix
status: resolved
---

# 툴 승인 워크플로우 고정 + 이메일 툴 섹션 10일 정체 해소

## What
1. visibility API 서버 가드 — pending/retired가 직접 공개 전환 불가 (승인 우회 차단)
2. tools_collector 크래시 수정 — 이메일 "신규 AI 도구" 섹션이 9/16 이후 고정된 이유 해소
3. 부수: ToolForm 카페 공유 URL tool page로 교체, briefing 이메일 URL id 기준

## Why
- **어제 승인 없이 올라간 이유**: 9/23 `5fdfa9d5` 이전 코드가 INSERT를 `'published'`로 하드코딩 → 이전 배포본으로 등록분 즉시 노출. 9/23 이후 `pending`-by-default로 변경되어 "항상 승인 필요"가 이미 코드상 구현됨.
- **남은 구멍**: `visibility.ts`는 클라이언트 가드(`canToggle`)만 있고 서버에 무조건 허용 → API 직접 호출로 pending→published 우회 가능.
- **이메일 툴 정체**: `tools_collector.py:1268` `'\n'.join(lines)`에 LLM 출력 list 섞이면 TypeError 크래시(launchd exit 1) → 마지막 `sync_tools_to_d1()` 미도달 → D1 `tools.updated_at` 9/16 고정 → 이메일이 매번 같은 6개(OpenAI Agents API 등) 발송.

## Files changed
- `src/pages/api/tools/[slug]/visibility.ts` — 현재 status가 pending/retired면 PATCH 403
- `scripts/tools_collector.py` — build_body join에서 non-str 항목 flatten 방어
- `src/components/ToolForm.astro` — cafe share text 마지막 URL: CAFE_URL → `${origin}/tools/${slug}/`
- (DB) D1 `tools` 302행 수동 재동기화

## How
- 승인 워크플로우 분석: `submit.ts`(pending INSERT 유일 경로) + `review.ts`(approve→published)만이 정상 경로. visibility 우회 서버측 차단.
- collector: join 지점 1줄 flatten 수정으로 크래시 루트 제거. 이메일 정체는 D1 동기화 미수행이 원인이라 `sync_tools_to_d1.mjs` 수동 실행(302 INSERT)으로 즉시 해소.

## Verification
- D1 재조회: 최신 6개 = RRSI(9/23), Jev(9/23), claudebill(9/21)… — 9/16 고정 해소 확인
- `build_body()` 스모크 테스트 2건 str 반환
- prod `<img>` + 목록 노출 curl 확인 (quick 260926-c73 배포분)
- 커밋: `42a07f78` `f57a8b98` `17d31178` (+ quick task `7abdc7bf` `61e639bc` `35b27601`)

## 잔존 위험
- collector 전체 파이프라인 재현은 내일 06:00 launchd 확인 필요 (log에 "D1 tools 테이블 동기화 완료 ✅")
- visibility 403 E2E는 로그인 세션 부재로 미검증 — 다음 등록 테스트 시 육안 확인
- Gemini free-tier 429 잔존 (폴백 체인으로 부분 가동, 범위 밖)
