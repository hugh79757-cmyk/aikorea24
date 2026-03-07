import type { APIRoute } from 'astro';
import { getCollection } from 'astro:content';
import { buildUrlset, toDateStr } from '../lib/sitemap';

export const prerender = false;

export const GET: APIRoute = async () => {
  const base = 'https://aikorea24.kr';
  const posts = await getCollection('blog', ({ data }) => !data.draft);

  const entries = posts.map(post => ({
    loc: base + '/blog/' + post.id + '/',
    lastmod: toDateStr(post.data.date),
    changefreq: 'monthly',
    priority: 0.8,
  }));

  return new Response(buildUrlset(entries), {
    headers: { 'Content-Type': 'application/xml; charset=utf-8' },
  });
};
