import { defineMiddleware } from 'astro:middleware';
import { env } from 'cloudflare:workers';

const SHORT_SLUGS = new Set([
  'ai', 'lg', '293', 'agi-5', 'openai', 'openai-1220',
  'walkthrough-1-1', 'walkthrough-1-2',
]);

// AIK24-RENEWAL-01 C-4: 서브프로젝트(heritage 등) 이미지는 외부 서브도메인이라
// img-src 에 *.aikorea24.kr 추가. 없으면 브라우저가 이미지를 차단해 안 보였다.
// AIK24-ADSBLANK-02 (2026-10-18 실측): script-src 에 fundingchoicesmessages.google.com 이
// 없으면 adsbygoogle.js 가 부르는 동의 메시지 로더가 CSP 로 차단되고, 그 실패가 광고 스택
// 초기화 체인을 끊어 **두 번째 광고 유닛(레이아웃 하단 슬롯)의 /pagead/ads 요청이 아예
// 발생하지 않는다**. 실측: CSP 현행 = 단위 요청 1건(상단 ady=81), fundingchoicesmessages
// 허용 = 단위 요청 2건(ady=81 + 하단 ady=4285). 호스트 1개만 추가하는 최소 수정.
// (ep2.adtrafficquality.google/sodar2.js 는 계속 차단 상태 — 요청 발생과 무관함을 확인했다.)
const SECURITY_HEADERS: Record<string, string> = {
  'Content-Security-Policy': "default-src 'self'; script-src 'self' 'unsafe-inline' https://pagead2.googlesyndication.com https://fundingchoicesmessages.google.com https://www.googletagmanager.com https://cdn.jsdelivr.net https://static.cloudflareinsights.com; style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://fonts.googleapis.com; img-src 'self' https://*.aikorea24.kr https://lh3.googleusercontent.com https://img.shields.io https://pagead2.googlesyndication.com https://tpc.googlesyndication.com data:; connect-src 'self' https://www.google-analytics.com https://googleads.g.doubleclick.net https://pagead2.googlesyndication.com https://ep1.adtrafficquality.google; font-src 'self' https://fonts.gstatic.com https://cdn.jsdelivr.net; frame-src 'self' https://googleads.g.doubleclick.net https://pagead2.googlesyndication.com",
  'X-Frame-Options': 'DENY',
  'X-Content-Type-Options': 'nosniff',
  'Strict-Transport-Security': 'max-age=31536000; includeSubDomains',
  'Referrer-Policy': 'strict-origin-when-cross-origin',
};

export const onRequest = defineMiddleware(async (context, next) => {
  const url = new URL(context.request.url);

  // AIK24-ROT-CLEAN-01: http→https 강제 + www→apex canonical 리다이렉트.
  // http://aikorea24.kr 이 200으로 서브되던 것을 막는다(구글 중복 콘텐츠 방지).
  // dev 서버(localhost)는 제외. 배포되는 Workers 런타임에서 scheme 은 CF가 그대로 전달한다.
  const host = url.hostname;
  const isLocal = host === 'localhost' || host.startsWith('127.') || host.startsWith('192.168.');
  if (!isLocal && (url.protocol !== 'https:' || host === 'www.aikorea24.kr')) {
    const to = new URL(context.request.url);
    to.protocol = 'https:';
    to.hostname = 'aikorea24.kr';
    return context.redirect(to.toString(), 301);
  }

  // Astro 6에서 Astro.locals.runtime이 제거됐다. 어댑터의 createLocals()가
  // writable:false로 정의해 두기 때문에(utils/cf-helpers.js) 미들웨어에서 주입도
  // defineProperty 재정의도 불가능하다. 정식 경로인 'cloudflare:workers'의 env를
  // 각 호출부가 직접 import 하도록 마이그레이션했다.
  context.locals.sessionSecret = env.SESSION_SECRET || '';
  if (!context.locals.sessionSecret) {
    console.warn('[auth] SESSION_SECRET is not configured');
  }

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
