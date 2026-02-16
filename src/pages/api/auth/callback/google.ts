import type { APIRoute } from 'astro';

export const GET: APIRoute = async ({ request, redirect, cookies, locals }) => {
  const url = new URL(request.url);
  const code = url.searchParams.get('code');
  if (!code) return redirect('/?error=no_code');

  const runtime = (locals as any).runtime;
  const clientId = runtime?.env?.GOOGLE_CLIENT_ID || import.meta.env.GOOGLE_CLIENT_ID;
  const clientSecret = runtime?.env?.GOOGLE_CLIENT_SECRET || import.meta.env.GOOGLE_CLIENT_SECRET;

  const redirectUri = import.meta.env.PROD
    ? 'https://aikorea24.kr/api/auth/callback/google'
    : 'http://localhost:4321/api/auth/callback/google';

  const tokenRes = await fetch('https://oauth2.googleapis.com/token', {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: new URLSearchParams({
      code, client_id: clientId, client_secret: clientSecret,
      redirect_uri: redirectUri, grant_type: 'authorization_code',
    }),
  });
  const tokenData = await tokenRes.json();
  if (!tokenData.access_token) return redirect('/?error=token_failed');

  const userRes = await fetch('https://www.googleapis.com/oauth2/v2/userinfo', {
    headers: { Authorization: `Bearer ${tokenData.access_token}` },
  });
  const user = await userRes.json();

  const db = runtime?.env?.DB;
  if (db) {
    await db.prepare(
      `INSERT OR IGNORE INTO users (google_id, email, name, avatar) VALUES (?, ?, ?, ?)`
    ).bind(user.id, user.email, user.name, user.picture).run();

    const dbUser = await db.prepare(
      `SELECT id, name, email, avatar FROM users WHERE google_id = ?`
    ).bind(user.id).first();

    const sessionData = btoa(JSON.stringify(dbUser));
    cookies.set('session', sessionData, {
      path: '/', httpOnly: true, secure: import.meta.env.PROD, domain: import.meta.env.PROD ? '.aikorea24.kr' : undefined,
      sameSite: 'lax', maxAge: 60 * 60 * 24 * 7,
    });
  }

  return redirect('/');
};
