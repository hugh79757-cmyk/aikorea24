import type { APIRoute } from 'astro';
import { verifySession, isOwner } from '../../../../lib/auth';

export const POST: APIRoute = async ({ params, cookies, locals }) => {
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

  const db = locals.runtime?.env?.DB;
  if (!db) {
    return new Response(JSON.stringify({ error: 'DB not available' }), { status: 500 });
  }

  // Soft delete: set visibility to 'deleted'
  await db.prepare(
    `UPDATE posts SET visibility = 'deleted', updated_at = datetime('now') WHERE id = ?`
  ).bind(id).run();

  return new Response(JSON.stringify({ ok: true }), {
    headers: { 'Content-Type': 'application/json' },
  });
};
