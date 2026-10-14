export const prerender = false;

import { env } from 'cloudflare:workers';
import type { APIRoute } from 'astro';

export const GET: APIRoute = async ({ locals }) => {

  const db = env.DB;
  if (!db) return new Response(JSON.stringify([]), { headers: { 'Content-Type': 'application/json', 'Cache-Control': 'public, max-age=300, s-maxage=300' } });

  const { results } = await db.prepare(
    `SELECT id, title, link, description, source, category, pub_date, original_title, country
     FROM news 
     WHERE category = 'global' AND title != original_title
     ORDER BY created_at DESC LIMIT 10`
  ).all();

  return new Response(JSON.stringify(results), { headers: { 'Content-Type': 'application/json', 'Cache-Control': 'public, max-age=300, s-maxage=300' } });
};
