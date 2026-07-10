# Phase 19 Research — MVP-3: 자동 발송

> Generated: 2026-07-10
> Phase: 19 (v2.0 milestone, MVP-3)

---

## 1. What Needs to Be Built

### Goal
Automated daily email delivery for the 7-day starter course. When a user enrolls, they should receive one lesson email per day at 18:00 KST, starting from their `start_date`.

### Scope Boundary
- **IN**: send-daily Workers API, Brevo transactional email template, launchd scheduler, click tracking wiring, Brevo tag progression
- **OUT**: Community gate (Phase 17 done), retention funnel (Phase 18 done), completion branching (Phase 20)

---

## 2. Existing Infrastructure Audit

### 2.1 D1 Schema (deployed via migration `20260710_add_course_system.sql`)
All tables exist and are ready:
- `enrollments` — has `days_sent`, `start_date`, `completed`, `brevo_tag_added`
- `course_lessons` — has `teaser_html`, `email_send_hour`, `community_post_id`
- `lesson_clicks` — table exists but has **no insertion logic yet**
- `courses` — has `default_send_hour` (18), `total_days` (7)

### 2.2 Brevo Integration Pattern
- **API endpoint**: `https://api.brevo.com/v3/smtp/email`
- **Auth**: `api-key` header, key from `BREVO_API_KEY` env var
- **Sender**: "AI코리아24" <info@aikorea24.kr>
- **Existing usage**: `auto_email_sender.py` uses `requests` library, builds HTML, sends to individual email + list broadcast
- **Enroll API pattern**: `enroll.ts` uses native `fetch()` (Workers-compatible) for Brevo contact creation + tag update
- **HTML escaping**: `esc()` function exists in `auto_email_sender.py` for `& < > " '`

### 2.3 Workers API Pattern (from enroll.ts)
- Uses `locals.runtime.env.DB` for D1 binding
- Uses `locals.runtime.env.BREVO_API_KEY` for Brevo key
- Returns typed JSON responses with status codes
- KST timezone handling via `Date.now() + 9 * 3600 * 1000`

### 2.4 Launchd Pattern (from install_launchd.sh)
- `string.Template` generates plist from `.template` file
- `VENV_PYTHON`, `PROJECT_DIR`, `SCRIPT_PATH`, `LOG_DIR` as template variables
- `StartInterval` for periodic execution
- Plist naming: `kr.aikorea24.{service-name}`

### 2.5 Seed Data Status
- `courses` row: `7day-starter` — exists
- `course_lessons`: 7 rows (day 1-7) with `teaser_html` and `community_post_id` — exists
- `posts` (community): 7 posts with `visibility='members'` — exists (from seed script)
- `enrollments`: depends on actual user registrations

---

## 3. Key Design Decisions Needed

### 3.1 Architecture: Workers API vs Python Script
**Two options:**

| Aspect | Workers API | Python Script |
|--------|-------------|---------------|
| D1 access | Native binding | `wrangler d1 execute` subprocess |
| Brevo call | `fetch()` native | `requests` library |
| Scheduling | Workers cron (free tier: 1/min) | launchd |
| Latency | ~200ms | ~2-3s (subprocess overhead) |
| Consistency | Same runtime as enroll.ts | Different runtime |

**Recommendation**: Workers API for the send logic (same runtime as enroll.ts, cleaner D1 access), Python launchd wrapper that calls the API endpoint (separates concerns).

### 3.2 Send Trigger Model
**Recommendation**: Poll-based (launchd calls send-daily API every hour). Simpler than event-driven. The API checks if it's time to send for each enrollment.

### 3.3 Click Tracking
**Recommendation**: Wrap community post URLs with a tracking redirect. Each email link goes through `/api/courses/track?e={enrollment_id}&d={day_number}&redirect={url}` which logs to `lesson_clicks` then 302 redirects.

---

## 4. Risks & Edge Cases

| Risk | Mitigation |
|------|------------|
| Brevo API failure mid-batch | `days_sent` updated only after successful send; failed enrollments retry next cycle |
| Duplicate sends | `days_sent` check + idempotency key on enrollment_id+day_number |
| Enrollment with `start_date` in future | Query only where `start_date <= today` and `days_sent < total_days` |
| Timezone confusion | All times stored/computed in KST; send_hour compared against KST current hour |
| Rate limits | Brevo allows 300 emails/day on free tier; 7-day course × current enrollments is well within limit |
| Unsubscribe | Include unsubscribe link in every email (Brevo handles this automatically for transactional) |
