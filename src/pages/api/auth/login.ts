export const prerender = false;

import { env } from 'cloudflare:workers';
import type { APIRoute } from 'astro';
import { sanitizeReturnTo } from '../../../lib/redirect';

export const GET: APIRoute = async ({ request, redirect, locals }) => {

  const clientId = env.GOOGLE_CLIENT_ID || import.meta.env.GOOGLE_CLIENT_ID;
  
  const redirectUri = import.meta.env.PROD
    ? 'https://aikorea24.kr/api/auth/callback/google'
    : 'http://localhost:4321/api/auth/callback/google';

  // redirect_to를 OAuth state 파라미터로 전달 (Google이 그대로 반환).
  // relative 경로와 허용 origin(emdash.aikorea24.kr 등) 의 절대 URL만 통과(개방 리다이렉트 방지).
  const url = new URL(request.url);
  const state = sanitizeReturnTo(url.searchParams.get('redirect_to') || '');

  const params = new URLSearchParams({
    client_id: clientId,
    redirect_uri: redirectUri,
    response_type: 'code',
    scope: 'openid email profile',
    access_type: 'offline',
    prompt: 'consent',
  });

  if (state) {
    params.set('state', state);
  }

  return redirect(`https://accounts.google.com/o/oauth2/v2/auth?${params}`);
};
