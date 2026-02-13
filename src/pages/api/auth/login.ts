import type { APIRoute } from 'astro';

export const GET: APIRoute = async ({ redirect, locals }) => {
  const runtime = (locals as any).runtime;
  const clientId = runtime?.env?.GOOGLE_CLIENT_ID || import.meta.env.GOOGLE_CLIENT_ID;
  
  const redirectUri = import.meta.env.PROD
    ? 'https://aikorea24.kr/api/auth/callback/google'
    : 'http://localhost:4321/api/auth/callback/google';

  const params = new URLSearchParams({
    client_id: clientId,
    redirect_uri: redirectUri,
    response_type: 'code',
    scope: 'openid email profile',
    access_type: 'offline',
    prompt: 'consent',
  });

  return redirect(`https://accounts.google.com/o/oauth2/v2/auth?${params}`);
};
