import type { APIRoute } from 'astro';
import { getCollection } from 'astro:content';
import { buildUrlset } from '../lib/sitemap';

export const prerender = false;

export const GET: APIRoute = async () => {
  const base = 'https://aikorea24.kr';
  const terms = await getCollection('glossary');

  const entries = terms.map(term => ({
    loc: base + '/glossary/' + term.id + '/',
    changefreq: 'monthly',
    priority: 0.7,
  }));

  return new Response(buildUrlset(entries), {
    headers: { 'Content-Type': 'application/xml; charset=utf-8' },
  });
};
