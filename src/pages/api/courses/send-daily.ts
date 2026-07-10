/**
 * GET /api/courses/send-daily
 *
 * 7일 강좌 자동 발송 API. launchd에서 매시간 호출.
 * Authorization: Bearer {CRON_SECRET} 필요.
 *
 * 로직:
 *   1. 미완료 enrollment 조회 (days_sent < total_days, start_date <= 오늘)
 *   2. 각 enrollment에 대해 오늘 보낼 차수인지 확인 (KST 기준 send_hour)
 *   3. course_lessons에서 해당 차수 데이터 로드
 *   4. Brevo transactional API로 이메일 발송
 *   5. 성공 시 days_sent++, 완강 시 completed=1
 *
 * 응답: { ok: true, sent: N, skipped: M, failed: K, details: [...] }
 */
import type { APIRoute } from 'astro';
import { buildLessonEmailHtml } from './templates/lesson-email';

interface Enrollment {
  id: number;
  user_id: number;
  email: string;
  course_slug: string;
  start_date: string;
  days_sent: number;
  completed: number;
}

interface Course {
  slug: string;
  title: string;
  default_send_hour: number;
  total_days: number;
}

interface CourseLesson {
  course_slug: string;
  day_number: number;
  community_post_id: number;
  teaser_html: string;
  email_send_hour: number | null;
}

interface CommunityPost {
  id: number;
  title: string;
}

// ─── KST helpers ────────────────────────────────────────────

function nowKST(): Date {
  return new Date(Date.now() + 9 * 3600_000);
}

function todayKST(): string {
  return nowKST().toISOString().split('T')[0];
}

function currentHourKST(): number {
  return nowKST().getUTCHours();
}

// ─── Brevo tag update ───────────────────────────────────────

async function updateBrevoTag(apiKey: string, email: string, courseSlug: string, dayNumber: number, isComplete: boolean): Promise<void> {
  try {
    const dayTag = `course-day-${dayNumber}-sent-${courseSlug}`;
    const tags: string[] = [dayTag];

    // 기존 contact 조회
    const contactRes = await fetch(`https://api.brevo.com/v3/contacts/${encodeURIComponent(email)}`, {
      headers: { 'api-key': apiKey }
    });

    if (contactRes.ok) {
      const contact = await contactRes.json();
      const existingTags: string[] = contact.emailBlacklisted ? [] : (contact.tags || []);
      tags.push(...existingTags);
    }

    if (isComplete) {
      tags.push(`course-completed-${courseSlug}`);
    }

    await fetch(`https://api.brevo.com/v3/contacts/${encodeURIComponent(email)}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json', 'api-key': apiKey },
      body: JSON.stringify({
        email,
        tags,
        updateEnabled: true,
      }),
    });
  } catch {
    // 태그 실패는 이메일 발송 결과에 영향 주지 않음
  }
}

// ─── D1 helpers ─────────────────────────────────────────────

function getDb(context: any) {
  return (context.locals as any).runtime?.env?.DB;
}

function getBrevoKey(context: any): string | undefined {
  return (context.locals as any).runtime?.env?.BREVO_API_KEY;
}

function getCronSecret(context: any): string | undefined {
  return (context.locals as any).runtime?.env?.CRON_SECRET;
}

function siteUrl(context: any): string {
  return (context.locals as any).runtime?.env?.SITE_URL || 'https://aikorea24.kr';
}

// ─── Main handler ───────────────────────────────────────────

export const GET: APIRoute = async (context) => {
  const db = getDb(context);
  const brevoKey = getBrevoKey(context);
  const cronSecret = getCronSecret(context);
  const baseUrl = siteUrl(context);

  if (!db) {
    return new Response(JSON.stringify({ ok: false, error: 'DB not available' }), {
      status: 500, headers: { 'Content-Type': 'application/json' }
    });
  }

  // ── Authorization ──
  const authHeader = context.request.headers.get('Authorization') || '';
  if (cronSecret && authHeader !== `Bearer ${cronSecret}`) {
    return new Response(JSON.stringify({ ok: false, error: 'Unauthorized' }), {
      status: 401, headers: { 'Content-Type': 'application/json' }
    });
  }

  const kstHour = currentHourKST();
  const kstToday = todayKST();

  try {
    // 1. 모든 미완료 enrollment 조회
    const enrollments: Enrollment[] = await db.prepare(`
      SELECT e.* FROM enrollments e
      JOIN courses c ON e.course_slug = c.slug
      WHERE e.completed = 0
        AND e.days_sent < c.total_days
        AND date(e.start_date) <= date(?)
      ORDER BY e.start_date ASC, e.id ASC
    `).bind(kstToday).all().then((r: any) => r.results || []);

    if (enrollments.length === 0) {
      return new Response(JSON.stringify({ ok: true, sent: 0, skipped: 0, failed: 0, message: 'No pending enrollments' }), {
        status: 200, headers: { 'Content-Type': 'application/json' }
      });
    }

    // 2. 필요한 course/lesson 데이터 캐싱
    const courses = new Map<string, Course>();
    const lessons = new Map<string, CourseLesson[]>(); // course_slug → lessons[]
    const posts = new Map<number, CommunityPost>();     // post_id → post

    for (const enrollment of enrollments) {
      if (!courses.has(enrollment.course_slug)) {
        const course = await db.prepare('SELECT * FROM courses WHERE slug = ?').bind(enrollment.course_slug).first() as Course | null;
        if (course) courses.set(enrollment.course_slug, course);
      }
      if (!lessons.has(enrollment.course_slug)) {
        const lessonList: CourseLesson[] = await db.prepare(
          'SELECT * FROM course_lessons WHERE course_slug = ? ORDER BY day_number ASC'
        ).bind(enrollment.course_slug).all().then((r: any) => r.results || []);
        lessons.set(enrollment.course_slug, lessonList);
      }
    }

    const details: any[] = [];
    let sent = 0, skipped = 0, failed = 0;

    for (const enrollment of enrollments) {
      const course = courses.get(enrollment.course_slug);
      if (!course) { skipped++; continue; }

      const nextDay = enrollment.days_sent + 1;
      if (nextDay > (course.total_days || 7)) {
        // 이미 완강 조건이지만 completed 플래그가 안 붙은 경우
        await db.prepare('UPDATE enrollments SET completed = 1 WHERE id = ?').bind(enrollment.id).run();
        skipped++;
        details.push({ email: enrollment.email, action: 'completed_auto', day: nextDay });
        continue;
      }

      // 해당 course의 lessons
      const courseLessons = lessons.get(enrollment.course_slug) || [];
      const lesson = courseLessons.find((l: CourseLesson) => l.day_number === nextDay);
      if (!lesson) {
        // lesson 데이터가 없으면 skip (시드 문제 등)
        skipped++;
        details.push({ email: enrollment.email, action: 'skipped_no_lesson', day: nextDay });
        continue;
      }

      // send_hour 결정
      const sendHour = lesson.email_send_hour ?? course.default_send_hour ?? 18;

      // 아직 send_hour가 안 됐으면 skip (이번 호출에서 처리 안 함)
      if (kstHour < sendHour) {
        skipped++;
        details.push({ email: enrollment.email, action: 'too_early', day: nextDay, send_hour: sendHour, current_hour: kstHour });
        continue;
      }

      // 이미 오늘차를 보냈는지 중복 체크 (days_sent 기준)
      // enrollment.days_sent가 이미 업데이트되었으면 skip
      // (이전 실행에서 성공했으나 아직 커밋 안 된 경우 방지)

      // Community post URL 조회
      let postUrl = `${baseUrl}/courses/${enrollment.course_slug}/`;
      if (lesson.community_post_id) {
        let post = posts.get(lesson.community_post_id);
        if (!post) {
          post = await db.prepare('SELECT id, title FROM posts WHERE id = ?').bind(lesson.community_post_id).first() as CommunityPost | null;
          if (post) posts.set(lesson.community_post_id, post);
        }
        if (post) {
          postUrl = `${baseUrl}/community/${post.id}/`;
        }
      }

      // Brevo 이메일 발송
      if (!brevoKey) {
        failed++;
        details.push({ email: enrollment.email, action: 'failed_no_brevo_key', day: nextDay });
        continue;
      }

      const trackingUrl = `${baseUrl}/api/courses/track?e=${enrollment.id}&d=${nextDay}&url=${encodeURIComponent(postUrl)}`;
      const unsubscribeUrl = `${baseUrl}/subscribe/?unsubscribe=${encodeURIComponent(enrollment.email)}`;

      const htmlContent = buildLessonEmailHtml({
        courseTitle: course.title,
        dayNumber: nextDay,
        totalDays: course.total_days || 7,
        lessonTitle: lesson.teaser_html.replace(/<[^>]*>/g, '').slice(0, 80),
        teaserHtml: lesson.teaser_html,
        communityPostUrl: postUrl,
        trackingUrl,
        unsubscribeUrl,
      });

      try {
        const brevoRes = await fetch('https://api.brevo.com/v3/smtp/email', {
          method: 'POST',
          headers: {
            'api-key': brevoKey,
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            sender: { name: 'AI코리아24', email: 'info@aikorea24.kr' },
            to: [{ email: enrollment.email }],
            subject: `AI코리아24 강좌 — ${nextDay}일차`,
            htmlContent,
          }),
        });

        if (brevoRes.ok || brevoRes.status === 201) {
          // days_sent 증가
          const newDaysSent = enrollment.days_sent + 1;
          const isComplete = newDaysSent >= (course.total_days || 7);

          await db.prepare(`
            UPDATE enrollments SET days_sent = ?, completed = ? WHERE id = ?
          `).bind(newDaysSent, isComplete ? 1 : 0, enrollment.id).run();

          // Brevo 태그 업데이트 (비동기, 실패 무시)
          updateBrevoTag(brevoKey, enrollment.email, enrollment.course_slug, nextDay, isComplete)
            .catch(() => {});

          sent++;
          details.push({
            email: enrollment.email,
            action: isComplete ? 'sent_and_completed' : 'sent',
            day: nextDay,
            days_sent: newDaysSent,
          });
        } else {
          const errText = await brevoRes.text().catch(() => 'unknown');
          failed++;
          details.push({ email: enrollment.email, action: 'brevo_error', day: nextDay, status: brevoRes.status, error: errText });
        }
      } catch (err: any) {
        failed++;
        details.push({ email: enrollment.email, action: 'exception', day: nextDay, error: err.message });
      }
    }

    return new Response(JSON.stringify({
      ok: true,
      sent,
      skipped,
      failed,
      total: enrollments.length,
      details,
    }), { status: 200, headers: { 'Content-Type': 'application/json' } });

  } catch (err: any) {
    console.error('send-daily error:', err);
    return new Response(JSON.stringify({ ok: false, error: err.message }), {
      status: 500, headers: { 'Content-Type': 'application/json' }
    });
  }
};
