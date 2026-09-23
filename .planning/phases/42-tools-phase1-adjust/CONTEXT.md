# CONTEXT — Phase 42: /tools Phase 1 스펙 정합 조정 (시니어 결정 반영)

## Goal
Phase 41 구현(41-01/02/03 완료)을 시니어 Gray Areas 결정 6항에 맞게 조정.
DDL 수정 → 보고 → 코드 작업 순. Phase 2까지만. Phase 3(R2/my/PUT-DELETE)은 시니어 리뷰 후.

## Locked decisions (시니어, 2026-09-23 — 재논의 없음)
1. **status**: `DEFAULT 'published'`, TEXT 유지, `'hidden'` 값 허용.
   index.astro 조회는 `WHERE status='published'` (현재 41-03은 status 무관 전체 조회 → 수정 필요).
2. **price**: `price_model` (필수, 3택: 무료/Freemium/유료) + `price_detail` (선택, 자유텍스트) 둘 다 유지.
   카드 표시 텍스트 = `price_detail || price_model`. 현재 `price TEXT` 단일 컬럼 → 2컬럼으로 교체.
3. **description**: 200자 캡 유지. 실시간 카운터 UI (`42/200` 형식).
   200자 초과 시 카운터 빨간색 + 제출 버튼 비활성화 (현재: 초과 시 400 에러만 → 클라이언트 선방어 추가).
4. **카테고리**: 8개 (7 + 기타). "기타" 선택 시 "희망 카테고리" text input 표시.
   DB에 `category_custom TEXT` 컬럼 추가.
5. **Step 2 추가**: `screenshot_url TEXT` (URL 형식, 선택). DDL + 폼 + API 검증(URL 형식만, 업로드 아님).
   카페 링크 상수 분리: `const CAFE_URL = 'https://cafe.naver.com/gptdohye'` (하드코딩 문자열 대체).
6. **범위**: Phase 2까지만 진행. Phase 3은 시니어 리뷰 후 범위 확정 — R2/my/PUT-DELETE 착수 금지.

## Scope (실행 순서)
- Step 0: `sql/001_tool_submissions.sql` CREATE TABLE 수정 (파일번호 유지 — `004` 아님.
  근거: sql/에 001/network_schema/persona_migration만 존재, 004 번호는 구 플랜 가정이었음.
  기존 테이블이 local/remote에 이미 적용됨 → ALTER TABLE 마이그레이션 필요:
  `price` → `price_model`+`price_detail`, `category_custom` 추가, `screenshot_url` 추가.
  기존 D1 행의 `price` 값 보존 마이그레이션 규칙 포함). 수정 후 스키마 보고 → 코드 진행.
- Step 1: submit.ts — price_model 필수 3택 검증, price_detail 선택, category_custom(기타 선택 시),
  screenshot_url URL 검증, description 200 캡 유지.
- Step 2: submit.astro — price_model 라디오 + price_detail input, 기타→희망카테고리 input 토글,
  description 카운터+초과 비활성화, screenshot_url input, CAFE_URL 상수.
- Step 3: index.astro — `WHERE status='published'`, 카드 표시 `price_detail || price_model`.
- Step 4: [id].astro — 동일 표시 규칙 + 숨김 섹션 유지. 빌드 + E2E curl 검증.

## Known current state (Phase 41 실측)
- `sql/001_tool_submissions.sql`: price TEXT 단일, category_custom 없음, screenshot_url 없음,
  status DEFAULT 'published' (결정 1과 일치, hidden 미사용 중).
- index.astro: status 무관 전체 조회 (결정 1 위반 → WHERE 추가 필요).
- submit.ts: price 단일 필드, 카테고리 화이트리스트 7+기타 (결정 4와 일치).
- description 200자 서버 검증 존재 (결정 3 서버측 일치, 클라이언트 카운터/비활성화 없음).

## Out of scope
- Phase 3 일체 (R2 업로드 API, 로고/스크린샷 업로드, /my/tools, PUT/DELETE).
- 승인 프로세스 (pending/approved/rejected 없음 — published/hidden만).
- 마크다운 도구·자동수집 파이프라인 (기존 금지 유지).
- ROADMAP Phase 1-40 회귀 없음.
