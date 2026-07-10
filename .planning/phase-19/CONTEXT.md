# Phase 19 Context — MVP-3: 자동 발송

## Phase Goal
7일 강좌의 자동 이메일 발송 시스템 구현. 등록 후 18:00 KST에 하루 한 레슨씩 이메일 발송.

## Scope
- **IN**: Send-daily API, email template, click tracking, launchd cron, Brevo tag progression
- **OUT**: Community gate (Phase 17), retention funnel (Phase 18), completion branching (Phase 20)

## Dependencies
- Phase 17 (schema, enroll API, seed data) — **complete**
- Phase 18 (retention funnel) — **complete**
- No external dependencies beyond existing Brevo + Cloudflare setup

## Existing Assets
- D1 tables: `enrollments`, `course_lessons`, `lesson_clicks`, `courses`
- Seed data: 7 lessons in `posts` + `course_lessons`
- Enrollment API: `src/pages/api/courses/enroll.ts`
- Brevo pattern: `scripts/auto_email_sender.py` (send_email_via_brevo)
- Launchd template: `scripts/threads/threads-publisher.plist.template`
- Install script: `scripts/install_launchd.sh`

## Key Decisions
1. **Workers API for send logic** — consistent with enroll.ts, native D1 binding
2. **Python launchd wrapper** — calls the API endpoint hourly (poll-based)
3. **Click tracking via redirect** — `/api/courses/track` logs click then 302
4. **KST all times** — no timezone conversion complexity
