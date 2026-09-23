import type { APIRoute } from 'astro';
import { getSessionUser } from '../../lib/auth';

const ALLOWED_TYPES: Record<string, string> = {
  'image/jpeg': 'jpg',
  'image/png': 'png',
  'image/webp': 'webp',
  'image/gif': 'gif',
};

const MAX_SIZE = 2 * 1024 * 1024;

export const POST: APIRoute = async ({ request, locals, cookies }) => {
  const r2 = (locals as any).runtime?.env?.R2;
  const db = (locals as any).runtime?.env?.DB;
  if (!r2 || !db) return new Response(JSON.stringify({ error: '스토리지 설정 오류입니다.' }), { status: 500 });

  const user = await getSessionUser(cookies, (locals as any).sessionSecret);
  if (!user) {
    return new Response(JSON.stringify({ error: '로그인이 필요합니다.' }), { status: 401 });
  }

  let userId = (user as any).id;
  if (!userId) {
    try {
      const row = await db.prepare('SELECT id FROM users WHERE email = ?').bind(user.email).first();
      if (row) userId = (row as any).id;
    } catch {}
  }
  if (!userId) {
    return new Response(JSON.stringify({ error: '유효하지 않은 세션입니다.' }), { status: 401 });
  }

  let file: File | null = null;
  try {
    const form = await request.formData();
    const v = form.get('file');
    if (v instanceof File) file = v;
  } catch {
    return new Response(JSON.stringify({ error: '파일을 선택해주세요.' }), { status: 400 });
  }
  if (!file || file.size === 0) {
    return new Response(JSON.stringify({ error: '파일을 선택해주세요.' }), { status: 400 });
  }

  const ext = ALLOWED_TYPES[file.type];
  if (!ext) {
    return new Response(JSON.stringify({ error: '이미지 파일만 업로드할 수 있습니다. (jpg, png, webp, gif)' }), { status: 400 });
  }
  if (file.size > MAX_SIZE) {
    return new Response(JSON.stringify({ error: '파일 크기는 2MB 이하만 가능합니다.' }), { status: 400 });
  }

  const key = `tools/${userId}/${Date.now()}-${Math.random().toString(36).substring(2, 6)}.${ext}`;
  await r2.put(key, file.stream(), { httpMetadata: { contentType: file.type } });

  return new Response(JSON.stringify({ success: true, url: '/api/files/' + key + '/' }), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
  });
};
