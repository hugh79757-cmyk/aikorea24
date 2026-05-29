import { defineMiddleware } from 'astro:middleware';

export const onRequest = defineMiddleware(async (context, next) => {
  const url = new URL(context.request.url);
  const path = url.pathname;
  const noSlash = path.endsWith('/') && path !== '/' ? path.slice(0, -1) : path;

  if (noSlash.endsWith('-')) {
    return context.redirect(noSlash.replace(/-+$/g, '') + '/', 301);
  }

  if (path.includes('${') || path === '/blog/2026-') {
    return new Response('Gone', { status: 410 });
  }

  return next();
});
