import type { APIRoute } from 'astro';
export const GET: APIRoute = async ({ request, redirect, locals }) => {
  const runtime = (locals as any).runtime;
  const clientId = runtime?.env?.KAKAO_CLIENT_ID || import.meta.env.KAKAO_CLIENT_ID;
  const redirectUri = import.meta.env.PROD
    ? 'https://aikorea24.kr/api/auth/callback/kakao'
    : 'http://localhost:4321/api/auth/callback/kakao';

  // redirect_to를 OAuth state 파라미터로 전달 (카카오가 그대로 반환)
  const url = new URL(request.url);
  const redirectTo = url.searchParams.get('redirect_to') || '';
  const state = redirectTo && redirectTo.startsWith('/')
    ? redirectTo
    : '';

  const params = new URLSearchParams({
    client_id: clientId,
    redirect_uri: redirectUri,
    response_type: 'code',
    scope: 'profile_nickname profile_image account_email',
  });

  if (state) {
    params.set('state', state);
  }

  return redirect(`https://kauth.kakao.com/oauth/authorize?${params}`);
};
