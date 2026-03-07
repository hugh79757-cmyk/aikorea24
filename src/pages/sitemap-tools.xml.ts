import type { APIRoute } from 'astro';
import { getCollection } from 'astro:content';
import { buildUrlset } from '../lib/sitemap';

export const prerender = false;

export const GET: APIRoute = async () => {
  const base = 'https://aikorea24.kr';
  const tools = await getCollection('tools');

  const entries = tools.map(tool => ({
    loc: base + '/tools/' + tool.id + '/',
    changefreq: 'monthly',
    priority: 0.7,
  }));

  return new Response(buildUrlset(entries), {
    headers: { 'Content-Type': 'application/xml; charset=utf-8' },
  });
};
