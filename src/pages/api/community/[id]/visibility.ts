import type { APIRoute } from 'astro';
import { verifySession, isOwner } from '../../../../lib/auth';

export const POST: APIRoute = async ({ params, request, cookies, locals }) => {
  const { id } = params;
  if (!id) {
    return new Response(JSON.stringify({ error: 'Missing post id' }), { status: 400 });
  }

  const session = cookies.get('session')?.value;
  if (!session) {
    return new Response(JSON.stringify({ error: 'Unauthorized' }), { status: 401 });
  }

  const user = await verifySession(session, locals.sessionSecret);
  if (!isOwner(user)) {
    return new Response(JSON.stringify({ error: 'Forbidden' }), { status: 403 });
  }

  const body = await request.json();
  const { visibility } = body;
  if (!['public', 'members', 'premium'].includes(visibility)) {
    return new Response(JSON.stringify({ error: 'Invalid visibility value' }), { status: 400 });
  }

  const db = locals.runtime?.env?.DB;
  if (!db) {
    return new Response(JSON.stringify({ error: 'DB not available' }), { status: 500 });
  }

  await db.prepare(
    `UPDATE posts SET visibility = ?, updated_at = datetime('now') WHERE id = ?`
  ).bind(visibility, id).run();

  return new Response(JSON.stringify({ ok: true, visibility }), {
    headers: { 'Content-Type': 'application/json' },
  });
};
