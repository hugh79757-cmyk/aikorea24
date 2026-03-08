import type { APIRoute } from 'astro';
import { getCollection } from 'astro:content';
import { buildUrlset } from '../lib/sitemap';

export const prerender = false;

export const GET: APIRoute = async () => {
  const base = 'https://aikorea24.kr';
  const events = await getCollection('chronicle');

  const entries = events.map(ev => ({
    loc: base + '/chronicle/' + ev.id + '/',
    changefreq: 'monthly',
    priority: 0.6,
  }));

  return new Response(buildUrlset(entries), {
    headers: { 'Content-Type': 'application/xml; charset=utf-8' },
  });
};
