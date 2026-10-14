export const prerender = false;

import { env } from 'cloudflare:workers';
import type { APIRoute } from 'astro';

export const GET: APIRoute = async ({ url, locals }) => {

  const db = env.DB;
  if (!db) return new Response(JSON.stringify([]), { headers: { 'Content-Type': 'application/json', 'Cache-Control': 'public, max-age=300, s-maxage=300' } });

  const filter = url.searchParams.get('filter') || 'all';
  const limit = Math.min(parseInt(url.searchParams.get('limit') || '100'), 200);
  const days = Math.min(parseInt(url.searchParams.get('days') || '3'), 30);

  const params: (string | number)[] = [];
  let where = "created_at >= datetime('now', ?) AND category != 'senior'";
  params.push(`-${days} days`);
  if (filter === 'kr') where += " AND country = ?", params.push('kr');
  else if (filter === 'global') where += " AND country != ? AND title != original_title", params.push('kr');
  else if (filter === 'policy') where += " AND category = ?", params.push('policy');
  else if (filter === 'benefit') where += " AND category = ?", params.push('benefit');
  else if (filter === 'startup') where += " AND category = ?", params.push('startup');
  else if (filter === 'grant') where += " AND category = ?", params.push('grant');
  params.push(limit);

  const { results } = await db.prepare(
    `SELECT id, title, link, description, source, category, country, pub_date, original_title, created_at
     FROM news
     WHERE ${where}
     ORDER BY created_at DESC LIMIT ?`
  ).bind(...params).all();

  return new Response(JSON.stringify(results), {
    headers: { 'Content-Type': 'application/json', 'Cache-Control': 'public, max-age=300, s-maxage=300' }
  });
};
