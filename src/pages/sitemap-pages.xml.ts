import type { APIRoute } from 'astro';
import { buildUrlset } from '../lib/sitemap';

export const prerender = false;

export const GET: APIRoute = async () => {
  const base = 'https://aikorea24.kr';

  const entries = [
    { loc: base + '/',          priority: 1.0, changefreq: 'daily' },
    { loc: base + '/blog/',     priority: 0.5, changefreq: 'daily' },
    { loc: base + '/tools/',    priority: 0.5, changefreq: 'daily' },
    { loc: base + '/briefing/', priority: 0.5, changefreq: 'daily' },
    { loc: base + '/news/',     priority: 0.5, changefreq: 'daily' },
    { loc: base + '/community/',priority: 0.4, changefreq: 'weekly' },
    { loc: base + '/event/',    priority: 0.4, changefreq: 'monthly' },
    { loc: base + '/global/',   priority: 0.4, changefreq: 'weekly' },
    { loc: base + '/about/',    priority: 0.3, changefreq: 'yearly' },
    { loc: base + '/contact/',  priority: 0.3, changefreq: 'yearly' },
    { loc: base + '/privacy/',  priority: 0.3, changefreq: 'yearly' },
    { loc: base + '/terms/',    priority: 0.3, changefreq: 'yearly' },
  ];

  return new Response(buildUrlset(entries), {
    headers: { 'Content-Type': 'application/xml; charset=utf-8' },
  });
};
