# Phase 19 Plan — MVP-3: 자동 발송

## Overview
7일 강좌 자동 이메일 발송 시스템. Workers API로 발송 로직 처리, launchd로 정기 실행.

## Plans

### 19-01: Send-Daily Workers API + Email Template

**Goal**: `/api/courses/send-daily` 엔드포인트 구현. enrollment 조회 → 이메일 템플릿 생성 → Brevo 발송 → days_sent 업데이트.

**Files to create/modify**:
- `src/pages/api/courses/send-daily.ts` — 신규 (Workers API)
- `src/pages/api/courses/templates/lesson-email.ts` — 신규 (HTML 템플릿)

**Success criteria**:
1. GET `/api/courses/send-daily`가 `enrollments`에서 `days_sent < total_days`이고 오늘이 발송일인 enrollment 조회
2. 각 enrollment의 오늘 차수(`days_sent + 1`)에 해당하는 `course_lessons` 로드
3. `teaser_html` + community post 링크로 이메일 HTML 생성
4. Brevo transactional API로 발송 (`send_email_via_brevo` 패턴 재사용)
5. 성공 시 `enrollments.days_sent += 1`
6. `days_sent >= total_days`이면 `completed = 1` 설정
7. 실패 시 해당 enrollment 건너뛰고 다음으로 (days_sent 업데이트 안 함)
8. 응답: `{ ok: true, sent: N, skipped: M, failed: K, completed: [...] }`

**Detailed tasks**:
1. Create `src/pages/api/courses/send-daily.ts`
   - Query: `SELECT * FROM enrollments WHERE completed = 0 AND days_sent < (SELECT total_days FROM courses WHERE slug = course_slug) AND date(start_date) <= date('now', '+9 hours')`
   - Group by enrollment, for each: calculate today's day number based on `start_date` + `days_sent`
   - Only send if current KST hour >= course's `default_send_hour` (18)
   - Load `course_lessons` for the day
   - Load community post URL
   - Build email HTML
   - Call Brevo API via `fetch()`
   - Update `days_sent` / `completed`
2. Create email template function (reuse `esc()` pattern from `auto_email_sender.py`)
   - Subject: "AI코리아24 강좌 — {day}일차: {lesson_title}"
   - HTML: header → teaser_html → "전체 내용 보기" 버튼 (→ community post URL) → course progress → unsubscribe footer
3. Authorization: Protect with cron secret header or internal-only access

### 19-02: Click Tracking + Brevo Tag Progression

**Goal**: 이메일 내 링크 클릭 추적 (`lesson_clicks`) + Brevo 태그로 진행 상황 표시.

**Files to create/modify**:
- `src/pages/api/courses/track.ts` — 신규 (클릭 리다이렉트)
- `src/pages/api/courses/send-daily.ts` — 수정 (Brevo 태그 업데이트 추가)

**Success criteria**:
1. 이메일 내 링크가 `/api/courses/track?e={enrollment_id}&d={day_number}&url={encoded_url}` 형식
2. `/api/courses/track`이 `lesson_clicks`에 INSERT 후 302 리다이렉트
3. 5일차 발송 시 Brevo에 `course-day-5-sent` 태그 추가
4. 완강(`completed=1`) 시 Brevo에 `course-completed-7day-starter` 태그 추가
5. `enrollments.brevo_tag_added` 패턴 재사용 (실패해도 발송은 유지)

**Detailed tasks**:
1. Create `src/pages/api/courses/track.ts`
   - Parse `enrollment_id`, `day_number`, `url` from query params
   - Validate enrollment exists and day_number is valid
   - `INSERT INTO lesson_clicks (enrollment_id, day_number) VALUES (?, ?)`
   - `Response.redirect(url, 302)`
2. Modify `send-daily.ts` to wrap community post URLs with track redirect
3. Add Brevo tag update after successful send:
   - `PUT /v3/contacts/{email}` with tags `[..., "course-day-{day}-sent"]`
   - On completion: `course-completed-{course_slug}`
   - Catch errors (tag failure ≠ email failure)

### 19-03: Launchd Cron + Deployment

**Goal**: launchd로 send-daily API를 정기 호출. 배포 및 모니터링.

**Files to create/modify**:
- `scripts/send_course_emails.sh` — 신규 (curl wrapper)
- `scripts/course-email-sender.plist.template` — 신규 (launchd template)
- `scripts/install_course_sender.sh` — 신규 (설치 스크립트)

**Success criteria**:
1. launchd가 매시간 send-daily API 호출 (`StartInterval: 3600`)
2. API 토큰 인증으로 외부 호출 차단
3. 로그: `scripts/course_sender/logs/launchd.log`
4. 배포: `wrangler deploy`로 API 포함

**Detailed tasks**:
1. Create `scripts/send_course_emails.sh`
   - `curl -X GET "https://aikorea24.kr/api/courses/send-daily" -H "Authorization: Bearer $CRON_SECRET"`
   - Log response to stdout/stderr
2. Create `scripts/course-email-sender.plist.template`
   - Label: `kr.aikorea24.course-email-sender`
   - StartInterval: 3600 (1시간)
   - EnvironmentVariables: CRON_SECRET
3. Create `scripts/install_course_sender.sh`
   - Template → plist generation (string.Template)
   - `launchctl load/unload`
4. Add `CRON_SECRET` to wrangler.jsonc / .env
5. Modify `send-daily.ts` to check `Authorization` header against `CRON_SECRET`

## Execution Order

```
Wave 1: 19-01 (Send-Daily API + Email Template)
Wave 2: 19-02 (Click Tracking + Brevo Tags)
Wave 3: 19-03 (Launchd + Deployment)
```

Each wave builds on the previous. Wave 1 is the core — can be tested manually via curl. Wave 2 adds tracking. Wave 3 automates scheduling.
