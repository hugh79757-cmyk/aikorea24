import type { APIRoute } from 'astro';

// AIK24-EMDASH-03: Astro 블로그가 EmDash 로 이관되어 RSS 항목이 0건이 되었다.
// 구독자가 피드를 계속 받도록 EmDash RSS 로 302 시킨다.
export const prerender = false;

export const GET: APIRoute = async () => {
  return new Response(null, {
    status: 302,
    headers: { Location: 'https://emdash.aikorea24.kr/rss.xml' },
  });
};