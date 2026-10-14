import type { APIRoute } from 'astro';

// AIK24-EMDASH-03: Astro 블로그(1,479건)가 EmDash 로 이관되어 이 사이트맵은 비었다.
// 빈 사이트맵을 그대로 두면 검색엔진이 "블로그가 사라졌다"고 판단하므로
// EmDash 사이트맵으로 302 시킨다 (그래야 포스트 URL 목록이 계속 전달된다).
export const prerender = false;

export const GET: APIRoute = async () => {
  return new Response(null, {
    status: 302,
    headers: { Location: 'https://emdash.aikorea24.kr/sitemap.xml' },
  });
};