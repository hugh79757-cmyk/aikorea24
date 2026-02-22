import type { APIRoute } from 'astro';

export const GET: APIRoute = async ({ url, locals }) => {
  const runtime = (locals as any).runtime;
  const db = runtime?.env?.DB;
  if (!db) return new Response(JSON.stringify(null), { headers: { 'Content-Type': 'application/json' } });

  const date = url.searchParams.get('date');

  let briefing;
  if (date) {
    briefing = await db.prepare(
      "SELECT * FROM briefings WHERE date = ? AND status = 'published'"
    ).bind(date).first();
  } else {
    briefing = await db.prepare(
      "SELECT * FROM briefings WHERE status = 'published' ORDER BY date DESC LIMIT 1"
    ).first();
  }

  if (!briefing) {
    return new Response(JSON.stringify(null), { headers: { 'Content-Type': 'application/json' } });
  }

  const { results: items } = await db.prepare(
    `SELECT bi.sort_order, bi.comment,
            n.id as news_id, n.title, n.link, n.description, n.source, n.category, n.country, n.pub_date
     FROM briefing_items bi
     JOIN news n ON bi.news_id = n.id
     WHERE bi.briefing_id = ?
     ORDER BY bi.sort_order`
  ).bind(briefing.id).all();

  return new Response(JSON.stringify({ briefing, items }), {
    headers: { 'Content-Type': 'application/json' }
  });
};
