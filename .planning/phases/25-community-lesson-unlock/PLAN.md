# PLAN.md — Phase 25: 커뮤니티 레슨 순차 해금 (Community Lesson Unlock)

> Generated: 2026-07-12 by Sisyphus
> Research: RESEARCH.md (same dir)

## Goal
커뮤니티에서 강좌 레슨을 **이메일 드립 진도(`days_sent`)와 동일하게 하나씩 잠금 해제**하도록
게이트를 재구현한다. 현재 버그(시드 category=`free` vs 게이트 분기 `category='강의'` 불일치로
인한 등록 무관 즉시 전체 공개)를 수정하고, 미등록/미로그인/잠금 대기 3상태 UI를 추가한다.

## Scope
- **In scope**: `community/[id].astro` 게이트 로직 재작성(lesson 판별=매핑 기반, days_sent 해금),
  잠금 카드 UI, 미등록/미로그인 CTA.
- **Out of scope**: 시드 category 변경(데이터 건드리지 않음), send-daily/크론 활성화(Phase 22),
  랜딩페이지 커리큘럼 동기화, day 0 고아 레슨 처리, auto-enroll(사용자 지시로 제외).

## Requirements
- REQ-25-1: 강좌 레슨 판별을 `category==='강의'` 가 아닌 `course_lessons` 역조회 결과로 결정
- REQ-25-2: 등록 사용자 레슨 해금 = `enrollment.days_sent >= lesson.day_number`
- REQ-25-3: 미로그인 → 로그인 + 강좌 신청 CTA + preview 게이트
- REQ-25-4: 로그인 + 미등록 → "수강생 전용" + 강좌 신청 CTA + preview 게이트
- REQ-25-5: 로그인 + 등록 + 잠금 대기(days_sent < day) → "N일차 잠금 해제 전" 대기 안내 + preview
- REQ-25-6: 잠금/해금 상태를 시각적으로 구분(자물쇠 아이콘 + 상태 문구 + CTA 버튼)

## Success Criteria
1. 등록+days_sent>=day 사용자: 레슨 전체 본문 노출
2. 등록+days_sent<day 사용자: preview만 + "잠금 해제 전" 안내
3. 미등록 로그인 사용자: preview만 + 수강 신청 CTA
4. 미로그인 사용자: preview만 + 로그인+신청 CTA
5. 일반 members 레슨 아님 게시글: 기존 로그인 게이트 동작 유지(회귀 없음)
6. `course_lessons` 매핑 없는 `members` 글: 기존 동작 유지
7. 빌드 통과(`astro check` 또는 dev 컴파일), 사이트 HTTP 200

## Tasks (Waves)

### Wave 1 — 게이트 로직 재작성 (community/[id].astro)
- **T1**: L131-175 게이트 블록 재작성
  - `post.category === '강의'` 분기 조건 → `lesson`(역조회 결과) 존재 여부로 변경
  - 등록 확인 쿼리 유지: `SELECT id FROM enrollments WHERE user_id=? AND course_slug=?`
  - 등록 시 `unlocked = enrollment.days_sent >= lesson.day_number` 계산
  - 상태 변수: `isGated`, `notEnrolled`, `lockedWaiting`(신규), `previewContent`(기존 splitPreview)
  - 비로그인/미등록/잠금대기 모두 `isGated=true` + 적절한 프래그 세트
- **T2**: 잠금 카드 UI (본문 렌더 영역, L~200 부근)
  - `isGated && courseSlug` 일 때 자물쇠 아이콘 + 상태 문구 분기:
    - `!currentUser` → "로그인 후 수강 신청하세요" + /login, /courses/7day-starter 링크
    - `notEnrolled` → "이 강의는 수강생 전용입니다" + 강좌 신청 CTA
    - `lockedWaiting` → "N일차는 아직 잠금 해제 전입니다 (이메일로 발송될 때까지)" 
  - previewContent 렌더(기존 splitPreview 결과)

### Wave 2 — 검증
- **T3**: 상태별 수동 검증(아래 Verification)
- **T4**: 빌드/사이트 헬스 체크

## Verification
- [ ] 등록+days_sent>=day: 본문 전체 노출 (테스트용 days_sent 강제 세팅으로 확인)
- [ ] 등록+days_sent<day: preview + "잠금 해제 전" 문구
- [ ] 미등록 로그인: preview + 수강 신청 CTA
- [ ] 미로그인: preview + 로그인+신청 CTA
- [ ] 일반 members(레슨 아님) 로그인: 기존대로 전체 노출
- [ ] `npm run build` 또는 `astro check` 통과
- [ ] `curl -s -o /dev/null -w "%{http_code}" https://aikorea24.kr` == 200

## Risks
- 크론 OFF → 운영에서 days_sent=0 → 모든 레슨 잠금 상태(사용자 승인). 검증은 days_sent 강제 세팅으로 우회.
- `splitPreview` 시그니처/동작 미확인 → T1 전 해당 함수 시그니처 확인 필요.
- courseSlug/lockedWaiting 등 신규 변수가 템플릿 하단(CTA 버튼 L~230)에서도 참조되는지 점검.
