import { defineConfig } from 'astro/config';
import mdx from '@astrojs/mdx';
import cloudflare from '@astrojs/cloudflare';
import tailwindcss from '@tailwindcss/vite';
import remarkGfm from 'remark-gfm';

export default defineConfig({
  site: 'https://aikorea24.kr',
  output: 'static',
  adapter: cloudflare({
    // 빌드 중(prerender)에 D1을 조회하는 라우트가 있다. 이 값은 어댑터의 최상위
    // 옵션이어야 한다. platformProxy 안에 넣으면 @astrojs/cloudflare v14 가 통째로
    // 무시하고, @cloudflare/vite-plugin 도 이 키를 못 본다(그래서 빌드 중 miniflare의
    // 빈 로컬 SQLite 를 써서 'no such table: courses' 로 죽는다).
    // Pages 는 프로젝트 바인딩으로 실제 D1 을 썼으므로 동일하게 맞춘다.
    configPath: './wrangler.jsonc',
    remoteBindings: true,
  }),
  // AIK24-MIGRATE-01: Phase 2+3을 대표님 승인으로 합쳐 Astro 7 + Workers로 진행한다.
  // 'single-file'(기본값)은 content 컬렉션 전체를 하나의 JS 청크로 인라인해
  // 24MB 파일을 만든다(Cloudflare Pages 25MiB 한도의 92%).
  // 'chunked'는 각 파트를 독립 청크로 emit한다(실측 최대 1,075KB).
  experimental: {
    collectionStorage: 'chunked',
  },
  trailingSlash: 'always',
  // AIK24-MIGRATE-01 Phase 1: @astrojs/tailwind(v3 전용, Astro 6/7 미지원) → @tailwindcss/vite
  // baseStyles는 global.css가 @import "tailwindcss"로 직접 가져오므로 별도 주입이 필요 없다
  vite: {
    plugins: [tailwindcss()],
  },
  integrations: [
    mdx()
  ],
  markdown: {
    gfm: false,
    remarkPlugins: [[remarkGfm, { singleTilde: false }]],
  },
});
