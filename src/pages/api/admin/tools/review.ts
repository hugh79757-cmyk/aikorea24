import type { APIRoute } from 'astro';
import { verifySession } from '../../../../lib/auth';

// Phase 3-C Wave B: 관리자 승인/반려 API (approve → published, reject → retired)
// Auth gate: grant.ts와 동일 ADMIN_EMAILS 패턴
const ADMIN_EMAILS = ['twinssn@gmail.com'];

async function isAdmin(cookies: any, secret: string): Promise<boolean> {
  const session = cookies.get('session')?.value;
  if (!session) return false;
  try {
    const user = await verifySession(session, secret);
    if (!user) return false;
    return ADMIN_EMAILS.includes(user.email);
  } catch {
    return false;
  }
}

export const POST: APIRoute = async ({ request, cookies, locals }) => {
  if (!(await isAdmin(cookies, (locals as any).sessionSecret))) {
    return new Response(JSON.stringify({ error: 'unauthorized' }), {
      status: 403,
      headers: { 'Content-Type': 'application/json' },
    });
  }

  const db = (locals as any).runtime?.env?.DB;
  if (!db) {
    return new Response(JSON.stringify({ error: 'db_unavailable' }), {
      status: 500,
      headers: { 'Content-Type': 'application/json' },
    });
  }

  let slug: string | undefined;
  let action: string | undefined;
  let reason: string | undefined;
  try {
    const body = await request.json();
    slug = body?.slug;
    action = body?.action;
    reason = body?.reason;
  } catch {
    return new Response(JSON.stringify({ error: '요청 본문을 확인해주세요.' }), {
      status: 400,
      headers: { 'Content-Type': 'application/json' },
    });
  }

  if (!slug?.trim()) {
    return new Response(JSON.stringify({ error: 'slug가 필요합니다.' }), {
      status: 400,
      headers: { 'Content-Type': 'application/json' },
    });
  }
  if (action !== 'approve' && action !== 'reject') {
    return new Response(JSON.stringify({ error: "action은 approve 또는 reject이어야 합니다." }), {
      status: 400,
      headers: { 'Content-Type': 'application/json' },
    });
  }
  if (action === 'reject' && !reason?.trim()) {
    return new Response(JSON.stringify({ error: '반려 사유를 입력해주세요.' }), {
      status: 400,
      headers: { 'Content-Type': 'application/json' },
    });
  }

  const row = await db
    .prepare('SELECT slug, status FROM tool_submissions WHERE slug = ?')
    .bind(slug.trim())
    .first();
  if (!row) {
    return new Response(JSON.stringify({ error: '도구를 찾을 수 없습니다.' }), {
      status: 404,
      headers: { 'Content-Type': 'application/json' },
    });
  }

  const nextStatus = action === 'approve' ? 'published' : 'retired';
  await db
    .prepare(
      `UPDATE tool_submissions SET status = ?, rejection_reason = ?, updated_at = datetime('now') WHERE slug = ?`
    )
    .bind(nextStatus, action === 'reject' ? reason!.trim() : null, slug.trim())
    .run();

  return new Response(JSON.stringify({ ok: true, slug: slug.trim(), status: nextStatus }), {
    headers: { 'Content-Type': 'application/json' },
  });
};
