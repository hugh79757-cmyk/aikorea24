import { defineMiddleware } from 'astro:middleware';

const SHORT_SLUGS = new Set([
  'ai', 'lg', '293', 'agi-5', 'openai', 'openai-1220',
  'walkthrough-1-1', 'walkthrough-1-2',
]);

const SECURITY_HEADERS: Record<string, string> = {
  'Content-Security-Policy': "default-src 'self'",
  'X-Frame-Options': 'DENY',
  'X-Content-Type-Options': 'nosniff',
  'Strict-Transport-Security': 'max-age=31536000; includeSubDomains',
  'Referrer-Policy': 'strict-origin-when-cross-origin',
};

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

  const response = await next();

  for (const [key, value] of Object.entries(SECURITY_HEADERS)) {
    response.headers.set(key, value);
  }

  return response;
});
