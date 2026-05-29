import { defineMiddleware } from 'astro:middleware';

const SHORT_SLUGS = new Set([
  'ai', 'lg', '293', 'agi-5', 'openai', 'openai-1220',
  'walkthrough-1-1', 'walkthrough-1-2',
]);

export const onRequest = defineMiddleware(async (context, next) => {
  const url = new URL(context.request.url);
  const path = url.pathname;
  const noSlash = path.endsWith('/') && path !== '/' ? path.slice(0, -1) : path;

  if (noSlash.endsWith('-')) {
    return context.redirect(noSlash.replace(/-+$/g, '') + '/', 301);
  }

  const decoded = decodeURIComponent(path);
  if (decoded.includes('${') || decoded === '/blog/2026-' || path === '/blog/2026-') {
    return new Response('Gone', { status: 410 });
  }

  const blogMatch = noSlash.match(/^\/blog\/(.+)$/);
  if (blogMatch && SHORT_SLUGS.has(blogMatch[1])) {
    return new Response('Gone', { status: 410 });
  }

  return next();
});
