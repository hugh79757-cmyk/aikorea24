import type { APIRoute } from 'astro';
import { verifySession } from '../../../../lib/auth';

export const PATCH: APIRoute = async ({ params, request, locals, cookies }) => {
  const db = (locals as any).runtime?.env?.DB;
  if (!db) return new Response(JSON.stringify({ error: 'DB 없음' }), { status: 500 });

  const session = cookies.get('session')?.value;
  if (!session) {
    return new Response(JSON.stringify({ error: '로그인이 필요합니다.' }), { status: 401 });
  }

  let user: { email: string; name: string } | null;
  try {
    user = await verifySession(session, (locals as any).sessionSecret);
  } catch {
    return new Response(JSON.stringify({ error: '유효하지 않은 세션입니다.' }), { status: 401 });
  }
  if (!user) {
    return new Response(JSON.stringify({ error: '유효하지 않은 세션입니다.' }), { status: 401 });
  }

  const { slug } = params;
  if (!slug) {
    return new Response(JSON.stringify({ error: 'slug가 필요합니다.' }), { status: 400 });
  }

  let status: string | undefined;
  try {
    const body = await request.json();
    status = body?.status;
  } catch {
    return new Response(JSON.stringify({ error: '요청 본문을 확인해주세요.' }), { status: 400 });
  }
  if (status !== 'published' && status !== 'hidden') {
    return new Response(JSON.stringify({ error: 'status는 published 또는 hidden이어야 합니다.' }), { status: 400 });
  }

  // users 테이블에서 user_id 역조회 (posts/index.ts 패턴)
  let userId = 0;
  try {
    const userRow = await db.prepare('SELECT id FROM users WHERE email = ?').bind(user.email).first();
    if (userRow) userId = (userRow as any).id;
  } catch {}
  if (!userId) {
    return new Response(JSON.stringify({ error: '유효하지 않은 세션입니다.' }), { status: 401 });
  }

  const row = await db.prepare('SELECT user_id FROM tool_submissions WHERE slug = ?').bind(slug).first();
  if (!row) {
    return new Response(JSON.stringify({ error: '도구를 찾을 수 없습니다.' }), { status: 404 });
  }
  if ((row as any).user_id !== userId) {
    return new Response(JSON.stringify({ error: '권한이 없습니다.' }), { status: 403 });
  }

  await db.prepare(
    `UPDATE tool_submissions SET status = ?, updated_at = datetime('now') WHERE slug = ?`
  ).bind(status, slug).run();

  return new Response(JSON.stringify({ success: true, status }), {
    headers: { 'Content-Type': 'application/json' },
  });
};
