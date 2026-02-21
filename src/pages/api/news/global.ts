import type { APIRoute } from 'astro';

export const GET: APIRoute = async ({ locals }) => {
  const runtime = (locals as any).runtime;
  const db = runtime?.env?.DB;
  if (!db) return new Response(JSON.stringify([]), { headers: { 'Content-Type': 'application/json' } });

  const { results } = await db.prepare(
    `SELECT id, title, link, description, source, category, pub_date, original_title, country
     FROM news 
     WHERE category = 'global' AND title != original_title
     ORDER BY created_at DESC LIMIT 10`
  ).all();

  return new Response(JSON.stringify(results), { headers: { 'Content-Type': 'application/json' } });
};
