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
  const { title, content, visibility, category } = body;

  if (!title || !content) {
    return new Response(JSON.stringify({ error: 'Title and content are required' }), { status: 400 });
  }

  const db = locals.runtime?.env?.DB;
  if (!db) {
    return new Response(JSON.stringify({ error: 'DB not available' }), { status: 500 });
  }

  const allowedVisibility = ['public', 'members', 'premium'];
  const newVisibility = allowedVisibility.includes(visibility) ? visibility : undefined;

  if (newVisibility && category) {
    await db.prepare(
      `UPDATE posts SET title = ?, content = ?, visibility = ?, category = ?, updated_at = datetime('now') WHERE id = ?`
    ).bind(title, content, newVisibility, category, id).run();
  } else if (newVisibility) {
    await db.prepare(
      `UPDATE posts SET title = ?, content = ?, visibility = ?, updated_at = datetime('now') WHERE id = ?`
    ).bind(title, content, newVisibility, id).run();
  } else if (category) {
    await db.prepare(
      `UPDATE posts SET title = ?, content = ?, category = ?, updated_at = datetime('now') WHERE id = ?`
    ).bind(title, content, category, id).run();
  } else {
    await db.prepare(
      `UPDATE posts SET title = ?, content = ?, updated_at = datetime('now') WHERE id = ?`
    ).bind(title, content, id).run();
  }

  return new Response(JSON.stringify({ ok: true }), {
    headers: { 'Content-Type': 'application/json' },
  });
};
