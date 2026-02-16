import { defineConfig } from 'astro/config';
import tailwind from '@astrojs/tailwind';
import mdx from '@astrojs/mdx';
import sitemap from '@astrojs/sitemap';
import cloudflare from '@astrojs/cloudflare';

export default defineConfig({
  site: 'https://aikorea24.kr',
  output: 'server',
  adapter: cloudflare({
    platformProxy: { enabled: true },
  }),
  trailingSlash: 'always',
  integrations: [tailwind(), mdx(), sitemap()],
});
