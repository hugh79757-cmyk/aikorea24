import type { APIRoute } from 'astro';
import { buildUrlset } from '../lib/sitemap';

export const prerender = false;

export const GET: APIRoute = async ({ locals }) => {
  const base = 'https://aikorea24.kr';
  const runtime = (locals as any).runtime;
  const db = runtime?.env?.DB;

  let entries: any[] = [];

  if (db) {
    try {
      const { results } = await db.prepare(
        "SELECT date FROM briefings WHERE status = 'published' ORDER BY date DESC"
      ).all();

      entries = (results || []).map((row: any) => ({
        loc: base + '/briefing/' + row.date + '/',
        lastmod: row.date,
        changefreq: 'never',
        priority: 0.6,
      }));
    } catch (e) {
      console.error('sitemap-briefing D1 error:', e);
    }
  }

  return new Response(buildUrlset(entries), {
    headers: { 'Content-Type': 'application/xml; charset=utf-8' },
  });
};
