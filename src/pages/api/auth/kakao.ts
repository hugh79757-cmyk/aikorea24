import type { APIRoute } from 'astro';
export const GET: APIRoute = async ({ redirect, locals }) => {
  const runtime = (locals as any).runtime;
  const clientId = runtime?.env?.KAKAO_CLIENT_ID || import.meta.env.KAKAO_CLIENT_ID;
  const redirectUri = import.meta.env.PROD
    ? 'https://aikorea24.kr/api/auth/callback/kakao'
    : 'http://localhost:4321/api/auth/callback/kakao';
  const params = new URLSearchParams({
    client_id: clientId,
    redirect_uri: redirectUri,
    response_type: 'code',
    scope: 'profile_nickname profile_image account_email',
  });
  return redirect(`https://kauth.kakao.com/oauth/authorize?${params}`);
};
