export const prerender = true;
// AIK24-MIGRATE-01 Phase 2: @astrojs/rss 제거 — Astro 7이 번들하는 zod 4에서
// `record(...).returns(...)` 호출이 모듈 최상위에서 실행되며(zod 3 API, 4에서 제거)
// import 자체가 불가능하다. Astro 7 대응 릴리스도 없다(latest 4.0.19 / alpha·beta는 구버전).
// 출력 포맷은 기존 @astrojs/rss 산출물과 동일하게 유지한다.
import { getCollection } from 'astro:content';
import type { APIContext } from 'astro';

// @astrojs/rss와 동일한 이스케이프 규칙: & < > " ' 만 이스케이프한다.
const esc = (s: string) =>
  s
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&apos;');

// RFC 822 형식 (예: Sun, 11 Oct 2026 08:34:28 GMT)
const rfc822 = (d: Date) =>
  d.toUTCString().replace('GMT', 'GMT');

export async function GET(context: APIContext) {
  const posts = await getCollection('blog', ({ data }) => !data.draft);

  const site = context.site ?? 'https://aikorea24.kr';
  const home = new URL('/', site).href;

  const items = posts
    .sort((a, b) => new Date(b.data.date).getTime() - new Date(a.data.date).getTime())
    .map((post) => {
      // link/guid는 기존 산출물과 동일하게 퍼센트 인코딩된 절대 URL을 쓴다.
      const url = new URL(`/blog/${post.id}/`, site).href;
      return (
        '<item>' +
        `<title>${esc(post.data.title)}</title>` +
        `<link>${url}</link>` +
        `<guid isPermaLink="true">${url}</guid>` +
        `<description>${esc(post.data.description ?? '')}</description>` +
        `<pubDate>${rfc822(new Date(post.data.date))}</pubDate>` +
        '</item>'
      );
    })
    .join('');

  const xml =
    '<?xml version="1.0" encoding="UTF-8"?>' +
    '<rss version="2.0">' +
    '<channel>' +
    '<title>AI코리아24</title>' +
    '<description>AI 큐레이션 플랫폼 — 도구 추천부터 바이브코딩 강좌까지</description>' +
    `<link>${home}</link>` +
    '<language>ko</language>' +
    items +
    '</channel>' +
    '</rss>';

  return new Response(xml, {
    headers: { 'Content-Type': 'application/xml; charset=utf-8' },
  });
}
