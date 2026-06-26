import type { APIRoute } from 'astro';
import { verifySession } from '../../../lib/auth';

const ADMIN_EMAILS = ['twinssn@gmail.com'];

async function requireAdmin(cookies: any, secret: string): Promise<boolean> {
  const session = cookies.get('session')?.value;
  if (!session) return false;
  const user = await verifySession(session, secret);
  return !!user && ADMIN_EMAILS.includes(user.email);
}

export const PUT: APIRoute = async ({ request, locals, cookies }) => {
  if (!(await requireAdmin(cookies, (locals as any).sessionSecret))) {
    return new Response(JSON.stringify({ error: 'Unauthorized' }), { status: 401, headers: { 'Content-Type': 'application/json' } });
  }

  const runtime = (locals as any).runtime;
  const db = runtime?.env?.DB;
  if (!db) return new Response(JSON.stringify({ error: 'DB not available' }), { status: 500, headers: { 'Content-Type': 'application/json' } });

  try {
    const body = await request.json();
    const { briefing_id, intro, items, delete_item_ids } = body;

    if (!briefing_id) {
      return new Response(JSON.stringify({ error: 'briefing_id required' }), { status: 400, headers: { 'Content-Type': 'application/json' } });
    }

    if (intro !== undefined) {
      await db.prepare('UPDATE briefings SET intro = ? WHERE id = ?').bind(intro, briefing_id).run();
    }

    if (delete_item_ids && Array.isArray(delete_item_ids) && delete_item_ids.length > 0) {
      const placeholders = delete_item_ids.map(() => '?').join(',');
      await db.prepare(`DELETE FROM briefing_items WHERE id IN (${placeholders}) AND briefing_id = ?`)
        .bind(...delete_item_ids, briefing_id).run();
    }

    if (items && Array.isArray(items)) {
      for (const item of items) {
        if (!item.id) continue;
        if (item.comment !== undefined && item.sort_order !== undefined) {
          await db.prepare('UPDATE briefing_items SET comment = ?, sort_order = ? WHERE id = ? AND briefing_id = ?')
            .bind(item.comment, item.sort_order, item.id, briefing_id).run();
        } else if (item.comment !== undefined) {
          await db.prepare('UPDATE briefing_items SET comment = ? WHERE id = ? AND briefing_id = ?')
            .bind(item.comment, item.id, briefing_id).run();
        } else if (item.sort_order !== undefined) {
          await db.prepare('UPDATE briefing_items SET sort_order = ? WHERE id = ? AND briefing_id = ?')
            .bind(item.sort_order, item.id, briefing_id).run();
        }
      }
    }

    return new Response(JSON.stringify({ ok: true }), {
      headers: { 'Content-Type': 'application/json' }
    });
  } catch (e: any) {
    console.error('Briefing update error:', e);
    return new Response(JSON.stringify({ error: import.meta.env.DEV ? e.message : 'Internal Server Error' }), { status: 500, headers: { 'Content-Type': 'application/json' } });
  }
};
