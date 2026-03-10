import type { APIRoute } from 'astro';
import { getCollection } from 'astro:content';

let cache: string | null = null;

export const GET: APIRoute = async () => {
  if (!cache) {
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

    cache = JSON.stringify(searchData);
  }

  return new Response(cache, {
    headers: {
      'Content-Type': 'application/json',
      'Cache-Control': 'public, max-age=3600',
    },
  });
};
