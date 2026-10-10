export const prerender = false;

import type { APIRoute } from 'astro';

/**
 * POST /api/courses/interest
 * 유료 강의 선판매 관심 등록 (AIK24-RENEWAL-01 §7-3).
 * 수집 항목: 이름 · 이메일 (그 외 수집하지 않는다).
 *
 * 저장: D1 `course_interest` 테이블 + Brevo 리스트(태그 `course-interest`).
 * Brevo 실패해도 D1 저장 성공이면 200 — 리드 유실을 막기 위함.
 * (기존 `users` 테이블은 id INTEGER + google_id UNIQUE NOT NULL 라서
 *  이름/이메일만 받는 리드 저장에 재사용하지 않는다.)
 */

const json = (body: unknown, status: number) =>
  new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });

export const POST: APIRoute = async ({ request, locals }) => {
  const runtime = (locals as any).runtime;
  const db = runtime?.env?.DB;
  const BREVO_API_KEY = runtime?.env?.BREVO_API_KEY;
  const BREVO_LIST_ID = runtime?.env?.BREVO_LIST_ID;

  if (!db) return json({ ok: false, error: '서버 오류가 발생했습니다.' }, 500);

  try {
    const { name, email } = await request.json();
    const cleanEmail = String(email ?? '').trim().toLowerCase();
    const cleanName = String(name ?? '').trim().slice(0, 50);

    if (!cleanEmail.includes('@')) return json({ ok: false, error: '유효한 이메일을 입력해주세요.' }, 400);
    if (!cleanName) return json({ ok: false, error: '이름을 입력해주세요.' }, 400);

    // D1 upsert
    await db
      .prepare(
        `INSERT INTO course_interest (name, email) VALUES (?, ?)
         ON CONFLICT(email) DO UPDATE SET name = excluded.name, created_at = datetime('now')`
      )
      .bind(cleanName, cleanEmail)
      .run();

    // Brevo (있을 때만 — 실패해도 리드는 D1에 남는다)
    if (BREVO_API_KEY) {
      try {
        await fetch('https://api.brevo.com/v3/contacts', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'api-key': BREVO_API_KEY },
          body: JSON.stringify({
            email: cleanEmail,
            listIds: [Number(BREVO_LIST_ID) || 2],
            updateEnabled: true,
            attributes: { NAME: cleanName, INTERESTS: 'course-interest' },
            tags: ['course-interest']
          })
        });
      } catch {
        /* Brevo 실패는 무시 — D1에 이미 저장됨 */
      }
    }

    return json({ ok: true, message: '관심 등록되었습니다. 강의 준비되면 먼저 연락드릴게요.' }, 200);
  } catch (error) {
    console.error('course interest error:', error);
    return json({ ok: false, error: '서버 오류가 발생했습니다.' }, 500);
  }
};