import type { APIRoute } from 'astro';

export const GET: APIRoute = async ({ url, locals }) => {
  const runtime = (locals as any).runtime;
  const db = runtime?.env?.DB;
  if (!db) return new Response(JSON.stringify([]), { headers: { 'Content-Type': 'application/json' } });

  const filter = url.searchParams.get('filter') || 'all';
  const limit = Math.min(parseInt(url.searchParams.get('limit') || '100'), 200);

  let where = '1=1';
  if (filter === 'kr') where = "country = 'kr'";
  else if (filter === 'global') where = "country != 'kr' AND title != original_title";
  else if (filter === 'policy') where = "category = 'policy'";
  else if (filter === 'benefit') where = "category = 'benefit'";

  const { results } = await db.prepare(
    `SELECT id, title, link, description, source, category, country, pub_date, original_title, created_at
     FROM news
     WHERE ${where}
     ORDER BY created_at DESC LIMIT ?`
  ).bind(limit).all();

  return new Response(JSON.stringify(results), {
    headers: { 'Content-Type': 'application/json' }
  });
};
