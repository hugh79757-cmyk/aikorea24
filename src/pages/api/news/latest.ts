import type { APIRoute } from 'astro';

export const GET: APIRoute = async ({ locals }) => {
  const runtime = (locals as any).runtime;
  const db = runtime?.env?.DB;
  if (!db) return new Response(JSON.stringify([]), { headers: { 'Content-Type': 'application/json' } });

  const { results } = await db.prepare(
    `SELECT id, title, link, description, source, category, pub_date 
     FROM news 
     WHERE category IN ('news', 'AI') 
     ORDER BY created_at DESC LIMIT 5`
  ).all();

  return new Response(JSON.stringify(results), { headers: { 'Content-Type': 'application/json' } });
};
