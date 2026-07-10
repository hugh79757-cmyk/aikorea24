import type { APIRoute } from 'astro';

/**
 * POST /api/courses/enroll
 * 강좌 등록 API. 3가지 응답 케이스:
 *   1. 신규 등록 성공 → { ok: true, course_slug, start_date, first_lesson_at }
 *   2. 이미 등록됨     → { ok: false, reason: "already_enrolled", current_day, next_lesson_at }
 *   3. 오류           → { ok: false, reason: "...", error: "..." }
 *
 * Body: { email: string, course_slug?: string }
 */
export const POST: APIRoute = async ({ request, locals }) => {
  const runtime = (locals as any).runtime;
  const db = runtime?.env?.DB;
  const BREVO_API_KEY = runtime?.env?.BREVO_API_KEY;

  if (!db) {
    return new Response(JSON.stringify({ ok: false, reason: 'server_error', error: 'DB not available' }), {
      status: 500, headers: { 'Content-Type': 'application/json' }
    });
  }

  try {
    const body = await request.json();
    const email = body?.email?.trim()?.toLowerCase();
    const courseSlug = body?.course_slug || '7day-starter';

    if (!email || !email.includes('@')) {
      return new Response(JSON.stringify({ ok: false, reason: 'invalid_email', error: '유효한 이메일을 입력해주세요.' }), {
        status: 400, headers: { 'Content-Type': 'application/json' }
      });
    }

    // 1. 강좌 존재 확인
    const course = await db.prepare('SELECT * FROM courses WHERE slug = ?').bind(courseSlug).first();
    if (!course) {
      return new Response(JSON.stringify({ ok: false, reason: 'course_not_found', error: '존재하지 않는 강좌입니다.' }), {
        status: 404, headers: { 'Content-Type': 'application/json' }
      });
    }

    // 2. 기존 user 확인 (이메일 기준) — Brevo 구독자와 중복 방지
    let user = await db.prepare('SELECT id, name FROM users WHERE email = ?').bind(email).first();

    // 3. 등록 중복 확인
    const existing = await db.prepare(
      'SELECT days_sent, completed FROM enrollments WHERE email = ? AND course_slug = ?'
    ).bind(email, courseSlug).first();

    if (existing) {
      // 이미 등록됨 — 현재 진행 상태 반환
      const nextDay = (existing.days_sent || 0) + 1;
      const sendHour = course.default_send_hour || 18;
      const nowKST = new Date(Date.now() + 9 * 3600 * 1000);
      const todayStr = nowKST.toISOString().split('T')[0];

      let nextLessonAt: string;
      if (existing.completed) {
        nextLessonAt = 'completed';
      } else if (existing.days_sent >= (course.total_days || 7)) {
        nextLessonAt = 'completed';
      } else {
        // 오늘 send_hour가 지났으면 내일, 안 지났으면 오늘
        const currentHour = nowKST.getUTCHours();
        if (currentHour < sendHour) {
          nextLessonAt = `${todayStr}T${String(sendHour).padStart(2, '0')}:00+09:00`;
        } else {
          const tomorrow = new Date(nowKST.getTime() + 86400000);
          nextLessonAt = `${tomorrow.toISOString().split('T')[0]}T${String(sendHour).padStart(2, '0')}:00+09:00`;
        }
      }

      return new Response(JSON.stringify({
        ok: false,
        reason: 'already_enrolled',
        current_day: existing.days_sent || 0,
        next_lesson_at: nextLessonAt,
        completed: !!existing.completed,
      }), { status: 200, headers: { 'Content-Type': 'application/json' } });
    }

    // 4. user가 없으면 생성 (D1에만 저장, Google OAuth와 무관)
    if (!user) {
      const result = await db.prepare(
        "INSERT INTO users (google_id, email, name) VALUES (?, ?, ?)"
      ).bind(`course_${email.replace(/[^a-zA-Z0-9]/g, '_')}`, email, email.split('@')[0]).run();
      const userId = result.meta.last_row_id;
      user = { id: userId, name: email.split('@')[0] };
    }

    // 5. 등록 생성
    const nowKST = new Date(Date.now() + 9 * 3600 * 1000);
    const todayStr = nowKST.toISOString().split('T')[0];
    const sendHour = course.default_send_hour || 18;
    const currentHour = nowKST.getUTCHours();

    // start_date: 현재 시각이 send_hour 이전이면 오늘, 이후면 내일
    let startDate: string;
    if (currentHour < sendHour) {
      startDate = todayStr;
    } else {
      const tomorrow = new Date(nowKST.getTime() + 86400000);
      startDate = tomorrow.toISOString().split('T')[0];
    }

    await db.prepare(
      'INSERT INTO enrollments (user_id, email, course_slug, start_date) VALUES (?, ?, ?, ?)'
    ).bind(user.id, email, courseSlug, startDate).run();

    // 6. Brevo 태그 추가 (선택 — 실패해도 등록은 유지)
    let brevoTagged = false;
    const brevoTag = `course-enrolled-${courseSlug}`;

    if (BREVO_API_KEY) {
      try {
        // Brevo contact 조회/생성
        const contactRes = await fetch(`https://api.brevo.com/v3/contacts/${encodeURIComponent(email)}`, {
          headers: { 'api-key': BREVO_API_KEY }
        });

        if (contactRes.ok) {
          const contact = await contactRes.json();
          const tags: string[] = contact.emailBlacklisted
            ? [brevoTag]
            : [...(contact.tags || []), brevoTag];

          await fetch(`https://api.brevo.com/v3/contacts/${encodeURIComponent(email)}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json', 'api-key': BREVO_API_KEY },
            body: JSON.stringify({
              email,
              tags,
              listIds: [Number(runtime?.env?.BREVO_LIST_ID || 2)],
              updateEnabled: true,
            })
          });
        } else {
          // 새 연락처 생성
          await fetch('https://api.brevo.com/v3/contacts', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'api-key': BREVO_API_KEY },
            body: JSON.stringify({
              email,
              tags: [brevoTag],
              listIds: [Number(runtime?.env?.BREVO_LIST_ID || 2)],
            })
          });
        }
        brevoTagged = true;
      } catch (e) {
        console.error('Brevo tag error:', e);
      }
    }

    // enrollment에 Brevo 태그 완료 표시
    if (brevoTagged) {
      await db.prepare(
        "UPDATE enrollments SET brevo_tag_added = 1 WHERE email = ? AND course_slug = ?"
      ).bind(email, courseSlug).run();
    }

    // 7. 첫 레슨 발송 예정 시각
    const firstLessonAt = `${startDate}T${String(sendHour).padStart(2, '0')}:00+09:00`;

    return new Response(JSON.stringify({
      ok: true,
      course_slug: courseSlug,
      start_date: startDate,
      first_lesson_at: firstLessonAt,
      total_days: course.total_days || 7,
      brevo_tag_added: brevoTagged,
    }), { status: 201, headers: { 'Content-Type': 'application/json' } });

  } catch (e: any) {
    console.error('Enroll error:', e);
    return new Response(JSON.stringify({ ok: false, reason: 'server_error', error: '서버 오류가 발생했습니다.' }), {
      status: 500, headers: { 'Content-Type': 'application/json' }
    });
  }
};
