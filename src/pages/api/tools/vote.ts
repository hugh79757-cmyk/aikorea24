import type { APIRoute } from 'astro';

export const POST: APIRoute = async ({ request, locals, cookies }) => {
  const db = (locals as any).runtime?.env?.DB;
  if (!db) return new Response(JSON.stringify({ error: 'DB 없음' }), { status: 500 });

  const session = cookies.get('session')?.value;
  if (!session) return new Response(JSON.stringify({ error: '로그인 필요' }), { status: 401 });

  let userEmail = '';
  try {
    const user = JSON.parse(atob(session.split('.')[1] || session));
    userEmail = user.email;
  } catch {
    return new Response(JSON.stringify({ error: '세션 오류' }), { status: 401 });
  }

  const { tool_id } = await request.json();
  if (!tool_id) return new Response(JSON.stringify({ error: 'tool_id 필요' }), { status: 400 });

  try {
    // 이미 투표했는지 확인
    const existing = await db.prepare(
      'SELECT id FROM tool_votes WHERE tool_id = ? AND user_email = ?'
    ).bind(tool_id, userEmail).first();

    if (existing) {
      // 취소 (토글)
      await db.prepare(
        'DELETE FROM tool_votes WHERE tool_id = ? AND user_email = ?'
      ).bind(tool_id, userEmail).run();
      const count = await db.prepare(
        'SELECT COUNT(*) as cnt FROM tool_votes WHERE tool_id = ?'
      ).bind(tool_id).first();
      return new Response(JSON.stringify({ voted: false, count: count?.cnt || 0 }), { status: 200 });
    } else {
      // 투표
      await db.prepare(
        'INSERT INTO tool_votes (tool_id, user_email) VALUES (?, ?)'
      ).bind(tool_id, userEmail).run();
      const count = await db.prepare(
        'SELECT COUNT(*) as cnt FROM tool_votes WHERE tool_id = ?'
      ).bind(tool_id).first();
      return new Response(JSON.stringify({ voted: true, count: count?.cnt || 0 }), { status: 200 });
    }
  } catch (e: any) {
    return new Response(JSON.stringify({ error: e.message }), { status: 500 });
  }
};

export const GET: APIRoute = async ({ request, locals, cookies }) => {
  const db = (locals as any).runtime?.env?.DB;
  if (!db) return new Response(JSON.stringify({ count: 0, voted: false }), { status: 200 });

  const url = new URL(request.url);
  const tool_id = url.searchParams.get('tool_id');
  if (!tool_id) return new Response(JSON.stringify({ count: 0, voted: false }), { status: 200 });

  const count = await db.prepare(
    'SELECT COUNT(*) as cnt FROM tool_votes WHERE tool_id = ?'
  ).bind(tool_id).first();

  let voted = false;
  const session = cookies.get('session')?.value;
  if (session) {
    try {
      const user = JSON.parse(atob(session.split('.')[1] || session));
      const existing = await db.prepare(
        'SELECT id FROM tool_votes WHERE tool_id = ? AND user_email = ?'
      ).bind(tool_id, user.email).first();
      voted = !!existing;
    } catch {}
  }

  return new Response(JSON.stringify({ count: count?.cnt || 0, voted }), { status: 200 });
};
