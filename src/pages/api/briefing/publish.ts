import type { APIRoute } from 'astro';
import { verifySession } from '../../../lib/auth';

const ADMIN_EMAILS = ['twinssn@gmail.com'];

async function requireAdmin(cookies: any, secret: string): Promise<boolean> {
  const session = cookies.get('session')?.value;
  if (!session) return false;
  const user = await verifySession(session, secret);
  return !!user && ADMIN_EMAILS.includes(user.email);
}

export const POST: APIRoute = async ({ request, locals, cookies }) => {
  if (!(await requireAdmin(cookies, (locals as any).sessionSecret))) {
    return new Response(JSON.stringify({ error: 'Unauthorized' }), { status: 401, headers: { 'Content-Type': 'application/json' } });
  }

  const runtime = (locals as any).runtime;
  const db = runtime?.env?.DB;
  if (!db) return new Response(JSON.stringify({ error: 'DB not available' }), { status: 500, headers: { 'Content-Type': 'application/json' } });

  try {
    const body = await request.json();
    const { date, intro, items } = body;

    if (!date || !items || !Array.isArray(items) || items.length < 1) {
      return new Response(JSON.stringify({ error: 'date, intro, items required' }), { status: 400 });
    }

    const existing = await db.prepare('SELECT id FROM briefings WHERE date = ?').bind(date).first();
    if (existing) {
      await db.prepare('DELETE FROM briefing_items WHERE briefing_id = ?').bind(existing.id).run();
      await db.prepare('DELETE FROM briefings WHERE id = ?').bind(existing.id).run();
    }

    const result = await db.prepare(
      `INSERT INTO briefings (date, intro, status, published_at) VALUES (?, ?, 'published', datetime('now'))`
    ).bind(date, intro || '').run();

    const briefingId = result.meta.last_row_id;

    for (let i = 0; i < items.length; i++) {
      const item = items[i];
      await db.prepare(
        'INSERT INTO briefing_items (briefing_id, news_id, sort_order, comment) VALUES (?, ?, ?, ?)'
      ).bind(briefingId, item.news_id, i, item.comment || '').run();
    }

    return new Response(JSON.stringify({ ok: true, briefing_id: briefingId, items_count: items.length }), {
      headers: { 'Content-Type': 'application/json' }
    });
  } catch (e: any) {
    console.error('Briefing publish error:', e);
    return new Response(JSON.stringify({ error: import.meta.env.DEV ? e.message : 'Internal Server Error' }), { status: 500 });
  }
};


export const DELETE: APIRoute = async ({ request, locals, cookies }) => {
  if (!(await requireAdmin(cookies, (locals as any).sessionSecret))) {
    return new Response(JSON.stringify({ ok: false, error: 'Unauthorized' }), { status: 401, headers: { 'Content-Type': 'application/json' } });
  }

  const runtime = (locals as any).runtime;
  const db = runtime?.env?.DB;
  if (!db) return new Response(JSON.stringify({ ok: false, error: 'no db' }), { headers: { 'Content-Type': 'application/json' } });

  try {
    const body = await request.json() as { date: string };
    const date = body.date;
    if (!date) return new Response(JSON.stringify({ ok: false, error: 'no date' }), { headers: { 'Content-Type': 'application/json' } });

    const existing = await db.prepare('SELECT id FROM briefings WHERE date = ?').bind(date).first();
    if (!existing) {
      return new Response(JSON.stringify({ ok: false, error: 'no briefing found' }), { headers: { 'Content-Type': 'application/json' } });
    }

    await db.prepare('DELETE FROM briefing_items WHERE briefing_id = ?').bind(existing.id).run();
    await db.prepare('DELETE FROM briefings WHERE id = ?').bind(existing.id).run();

    return new Response(JSON.stringify({ ok: true }), { headers: { 'Content-Type': 'application/json' } });
  } catch (e: any) {
    console.error('Briefing DELETE error:', e);
    return new Response(JSON.stringify({ ok: false, error: import.meta.env.DEV ? e.message : 'Internal Server Error' }), { headers: { 'Content-Type': 'application/json' } });
  }
};
