import type { APIRoute } from 'astro';
import { getCollection } from 'astro:content';

export const prerender = true;

export const GET: APIRoute = async () => {
  const allPosts = (await getCollection('blog', ({ data }) => !data.draft))
    .sort((a, b) => new Date(b.data.date).getTime() - new Date(a.data.date).getTime());

  const recentPosts = allPosts.filter(p => p.data.category !== 'AI 강좌').slice(0, 3).map(p => ({
    id: p.id,
    slug: p.id,
    data: {
      title: p.data.title,
      description: p.data.description || '',
      category: p.data.category || '',
      tags: p.data.tags || [],
      date: p.data.date instanceof Date ? p.data.date.toISOString() : String(p.data.date),
      thumbnail: p.data.thumbnail || null,
    }
  }));

  const coursePosts = allPosts.filter(p => (p.data.tags || []).includes('바이브코딩')).slice(0, 3).map(p => ({
    id: p.id,
    slug: p.id,
    data: {
      title: p.data.title,
      description: p.data.description || '',
      category: p.data.category || '',
      tags: p.data.tags || [],
      date: p.data.date instanceof Date ? p.data.date.toISOString() : String(p.data.date),
      thumbnail: p.data.thumbnail || null,
    }
  }));

  return new Response(JSON.stringify({ recentPosts, coursePosts }), {
    headers: {
      'Content-Type': 'application/json',
      'Cache-Control': 'public, max-age=300',
    },
  });
};
