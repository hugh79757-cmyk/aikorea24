export const prerender = false;

import { env } from 'cloudflare:workers';
import type { APIRoute } from 'astro';

export const GET: APIRoute = async ({ locals }) => {

  const db = env.DB;
  if (!db) return new Response(JSON.stringify([]), { headers: { 'Content-Type': 'application/json', 'Cache-Control': 'public, max-age=300, s-maxage=300' } });

  const { results } = await db.prepare(
    `SELECT id, title, link, description, source, pub_date 
     FROM news 
     WHERE category = 'policy' 
     ORDER BY created_at DESC LIMIT 3`
  ).all();

  return new Response(JSON.stringify(results), { headers: { 'Content-Type': 'application/json', 'Cache-Control': 'public, max-age=300, s-maxage=300' } });
};
