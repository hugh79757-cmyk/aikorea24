import { defineMiddleware } from 'astro:middleware';

const SHORT_SLUGS = new Set([
  'ai', 'lg', '293', 'agi-5', 'openai', 'openai-1220',
  'walkthrough-1-1', 'walkthrough-1-2',
]);

const SECURITY_HEADERS: Record<string, string> = {
  'Content-Security-Policy': "default-src 'self'; script-src 'self' 'unsafe-inline' https://pagead2.googlesyndication.com https://www.googletagmanager.com https://cdn.jsdelivr.net https://static.cloudflareinsights.com; style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://fonts.googleapis.com; img-src 'self' https://lh3.googleusercontent.com https://img.shields.io https://pagead2.googlesyndication.com https://tpc.googlesyndication.com data:; connect-src 'self' https://www.google-analytics.com https://googleads.g.doubleclick.net https://pagead2.googlesyndication.com https://ep1.adtrafficquality.google; font-src 'self' https://fonts.gstatic.com https://cdn.jsdelivr.net; frame-src 'self' https://googleads.g.doubleclick.net https://pagead2.googlesyndication.com",
  'X-Frame-Options': 'DENY',
  'X-Content-Type-Options': 'nosniff',
  'Strict-Transport-Security': 'max-age=31536000; includeSubDomains',
  'Referrer-Policy': 'strict-origin-when-cross-origin',
};

export const onRequest = defineMiddleware(async (context, next) => {
  const runtime = (context.locals as any).runtime;
  context.locals.sessionSecret = runtime?.env?.SESSION_SECRET || '';
  if (!context.locals.sessionSecret) {
    console.warn('[auth] SESSION_SECRET is not configured');
  }

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
