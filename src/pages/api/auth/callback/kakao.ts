import type { APIRoute } from 'astro';
export const GET: APIRoute = async ({ request, redirect, cookies, locals }) => {
  const url = new URL(request.url);
  const code = url.searchParams.get('code');
  if (!code) return redirect('/?error=no_code');

  const runtime = (locals as any).runtime;
  const clientId = runtime?.env?.KAKAO_CLIENT_ID || import.meta.env.KAKAO_CLIENT_ID;
  const clientSecret = runtime?.env?.KAKAO_CLIENT_SECRET || import.meta.env.KAKAO_CLIENT_SECRET;
  const redirectUri = import.meta.env.PROD
    ? 'https://aikorea24.kr/api/auth/callback/kakao'
    : 'http://localhost:4321/api/auth/callback/kakao';

  // 토큰 교환
  const tokenRes = await fetch('https://kauth.kakao.com/oauth/token', {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: new URLSearchParams({
      grant_type: 'authorization_code',
      client_id: clientId,
      client_secret: clientSecret,
      redirect_uri: redirectUri,
      code,
    }),
  });
  const tokenData = await tokenRes.json() as any;
  if (!tokenData.access_token) return redirect('/?error=token_failed');

  // 사용자 정보
  const userRes = await fetch('https://kapi.kakao.com/v2/user/me', {
    headers: { Authorization: `Bearer ${tokenData.access_token}` },
  });
  const kakaoUser = await userRes.json() as any;
  const kakaoId = String(kakaoUser.id);
  const email = kakaoUser.kakao_account?.email || `${kakaoId}@kakao.local`;
  const name = kakaoUser.kakao_account?.profile?.nickname || '카카오 사용자';
  const avatar = kakaoUser.kakao_account?.profile?.profile_image_url || null;

  const db = runtime?.env?.DB;
  if (db) {
    // 기존 카카오 계정 확인
    let dbUser = await db.prepare(
      `SELECT id, name, email, avatar FROM users WHERE kakao_id = ?`
    ).bind(kakaoId).first();

    if (!dbUser) {
      // 같은 이메일 구글 계정 있으면 연동, 없으면 신규
      const existing = await db.prepare(
        `SELECT id FROM users WHERE email = ?`
      ).bind(email).first() as any;

      if (existing) {
        await db.prepare(
          `UPDATE users SET kakao_id = ?, provider = 'kakao' WHERE id = ?`
        ).bind(kakaoId, existing.id).run();
      } else {
        await db.prepare(
          `INSERT INTO users (kakao_id, google_id, email, name, avatar, provider) VALUES (?, '', ?, ?, ?, 'kakao')`
        ).bind(kakaoId, email, name, avatar).run();
      }
      dbUser = await db.prepare(
        `SELECT id, name, email, avatar FROM users WHERE kakao_id = ?`
      ).bind(kakaoId).first();
    }

    const sessionData = btoa(JSON.stringify(dbUser));
    cookies.set('session', sessionData, {
      path: '/',
      httpOnly: true,
      secure: import.meta.env.PROD,
      domain: import.meta.env.PROD ? '.aikorea24.kr' : undefined,
      sameSite: 'lax',
      maxAge: 60 * 60 * 24 * 7,
    });
  }
  return redirect('/');
};
