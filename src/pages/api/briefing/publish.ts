import type { APIRoute } from 'astro';

export const POST: APIRoute = async ({ request, locals }) => {
  const runtime = (locals as any).runtime;
  const db = runtime?.env?.DB;
  if (!db) return new Response(JSON.stringify({ error: 'DB not available' }), { status: 500 });

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
    return new Response(JSON.stringify({ error: e.message }), { status: 500 });
  }
};
