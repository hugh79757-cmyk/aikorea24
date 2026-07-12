# RESEARCH.md — Phase 25: 커뮤니티 레슨 순차 해금 (Community Lesson Unlock)

> Generated: 2026-07-12 by Sisyphus
> Method: 소스 직독 (src/pages/community/[id].astro, enroll.ts, send-daily.ts, track.ts,
>         seed_course_7day_*.py, migrations/20260710_*.sql, subscribe.astro, api/subscribe.ts)

## 1. 현재 콘텐츠 구성 (확인됨)

게이트웨이 패턴: 본문 = `posts`, 매핑 = `course_lessons` (얇은 매핑).

| 항목 | 값 |
|---|---|
| 코스 | `7day-starter` (day 0~7, 8레슨 정의), `7day-infra` (day 8~14, 7레슨) |
| 본문 저장 | `posts` (user_id=1, **category=`free`**, **visibility=`members`**) |
| 매핑 | `course_lessons` (course_slug + day_number → community_post_id + teaser_html) |
| total_days | 둘 다 7 고정 |
| 등록 | `enrollments` (start_date, days_sent=0, completed=0) — 오직 `/api/courses/enroll` 경로 |

## 2. 현재 게이트 동작 + 버그 (community/[id].astro L131-175)

```
visibility='members' 이면 로그인 필요
 ├─ post.category === '강의'  → course_lessons 역조회(lesson)
 │     ├─ lesson 있음 + 비로그인  → gated (preview)
 │     ├─ lesson 있음 + 로그인 + 미등록 → gated (notEnrolled)
 │     └─ lesson 있음 + 로그인 + 등록   → isGated=false (전체 공개, days_sent 체크 없음)
 └─ 그 외(일반 members) → 로그인만 있으면 전체 공개
```

**치명적 불일치**: 시드가 레슨을 **`category='free'`**로 저장하는데, per-course 분기는
**`category==='강의'`**일 때만 진입. → 레슨은 `강의` 분기에 안 들어가고 **일반 members 분기**로 빠짐.
결과: 로그인한 누구나(등록 여부 무관) 레슨 전체 즉시 열람 가능. 일차별 해금 로직 자체가 미동작.

또한 등록된 사용자라도 `days_sent` 체크가 아예 없어(주석 "옵션 X: 등록 즉시 전체 공개") 이메일
드립 진도와 완전히 분리됨.

## 3. 등록 폼 2개 분리 확인 (사용자 확인 요청 → 검증 완료)

- **강좌 폼**: `courses/7day-starter.astro` → `POST /api/courses/enroll` → `enrollments` row 생성 + Brevo `course-enrolled-{slug}` 태그. **유일한 enrollment 생성 경로.**
- **뉴스레터/브리핑 폼**: `subscribe.astro`(`SubscribeBanner`) → `POST /api/subscribe` → Brevo list 추가 **만**. `enrollments` 미생성, 강좌 시스템 무관.

→ 결론: `enrollments`가 단일 진실원. auto-enroll 불필요.

## 4. 설계 결정 (사용자 확정)

- **해금 기준 = `days_sent` (이메일 드립 진도) 미러**.
  레슨 day N 해금 조건: `enrollment.days_sent >= day_number`.
  (크론 OFF 상태에선 days_sent=0 유지 → 콘텐츠 검수 끝날 때까지 전 레슨 잠금. 사용자 승인.)
  크론 켜지면 send-daily가 days_sent를 올리고, 커뮤니티 해금과 자동 동기화(동일 start_date/일정).
- **대상 범위 = auto-enroll 없음**. 강좌 폼으로 등록한 사람만 `enrollments` 보유 → 해금 대상.
  뉴스레터 구독자/순수 커뮤니티 회원은 등록 전까지 잠금(CTA로 강좌 폼 유도).

## 5. 게이트 재설계 (목표 동작)

레슨 판별: `category==='강의'` 가 아니라 **`course_lessons` 역조회 결과(`lesson`) 존재 여부**로.
(시드 category 건드리지 않음 — 콘텐츠 검수 중이므로 데이터 변경 최소화)

```
lesson 존재(=강좌 레슨) 이면:
 ├─ 비로그인        → gated: 로그인 + 강좌 신청 CTA + preview
 ├─ 로그인 + 미등록  → gated: "수강생 전용" + 강좌 신청 CTA + preview
 ├─ 로그인 + 등록:
 │    ├─ days_sent >= day_number → 전체 본문 공개 (unlocked)
 │    └─ days_sent <  day_number → gated: "N일차 잠금 해제 전" + 대기 안내 + preview
 └─ (lesson 없음 일반 members) → 기존 로그인 게이트 유지
```

추가: 잠금 카드 UI(자물쇠 아이콘 + 상태 문구 + CTA), 커뮤니티 인덱스에서 강좌 레슨은
'회원전용' 뱃지 유지(목록은 그대로, 본문만 게이트).

## 6. 부수 발견 (이번 페이즈 범위 외, 기록만)

- **day 0 고아 레슨**: `7day-starter` day 0 정의되나 send-daily는 days_sent+1(=1)부터 발송 → day 0은 이메일로 절대 안 나감. 커뮤니티에선 `course_lessons` 매핑이 있으므로 `days_sent>=0`(항상 참)으로 접근 가능. 동작엔 문제 없으나 의도 확인 필요(별도 이슈).
- **랜딩페이지/시드 불일치**: `7day-starter.astro` 커리큘럼 텍스트가 시드 본문과 다름(하드코딩 "곧 오픈"). 별도 정비 대상.
- **크론 미가동**: Phase 22 plist 미설치. 이번 페이즈에서 건드리지 않음(사용자 지시).
