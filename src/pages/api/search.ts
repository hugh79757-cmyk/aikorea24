import type { APIRoute } from 'astro';
import { getCollection } from 'astro:content';

export const prerender = true;

export const GET: APIRoute = async () => {
  const posts = (await getCollection('blog', ({ data }) => !data.draft))
    .sort((a, b) => new Date(b.data.date).getTime() - new Date(a.data.date).getTime());

  const searchData = posts.map(post => ({
    title: post.data.title,
    description: post.data.description || '',
    category: post.data.category || '',
    tags: post.data.tags || [],
    slug: post.id,
    date: post.data.date,
  }));

  return new Response(JSON.stringify(searchData), {
    headers: { 'Content-Type': 'application/json' },
  });
};
