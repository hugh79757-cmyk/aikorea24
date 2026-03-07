import type { APIRoute } from 'astro';
import { buildIndex } from '../lib/sitemap';

export const prerender = false;

export const GET: APIRoute = async () => {
  const base = 'https://aikorea24.kr';
  const now = new Date().toISOString().split('T')[0];

  const xml = buildIndex([
    { loc: base + '/sitemap-blog.xml', lastmod: now },
    { loc: base + '/sitemap-tools.xml', lastmod: now },
    { loc: base + '/sitemap-briefing.xml', lastmod: now },
    { loc: base + '/sitemap-pages.xml', lastmod: now },
  ]);

  return new Response(xml, {
    headers: { 'Content-Type': 'application/xml; charset=utf-8' },
  });
};
