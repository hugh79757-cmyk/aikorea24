import rss from '@astrojs/rss';
import { getCollection } from 'astro:content';
import type { APIContext } from 'astro';

export async function GET(context: APIContext) {
  const posts = await getCollection('blog', ({ data }) => !data.draft);

  return rss({
    title: 'AI코리아24',
    description: 'AI 큐레이션 플랫폼 — 도구 추천부터 바이브코딩 강좌까지',
    site: context.site ?? 'https://aikorea24.kr',
    items: posts
      .sort((a, b) => new Date(b.data.date).getTime() - new Date(a.data.date).getTime())
      .slice(0, 20)
      .map((post) => ({
        title: post.data.title,
        pubDate: post.data.date,
        description: post.data.description,
        link: `/blog/${post.id}/`,
      })),
    customData: '<language>ko</language>',
  });
}
