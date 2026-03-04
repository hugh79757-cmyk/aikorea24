import type { APIRoute } from 'astro';

// 토큰 기반 직접 다운로드 (로그인 불필요)
const VALID_TOKENS: Record<string, number> = {
  'feb2026': 2,  // resource_id = 2 (492개 이벤트 CSV)
};

export const GET: APIRoute = async ({ url, locals }) => {
  const token = url.searchParams.get('t');
  if (!token || !VALID_TOKENS[token]) {
    return new Response('유효하지 않은 링크입니다.', { status: 403 });
  }

  const resourceId = VALID_TOKENS[token];
  const runtime = (locals as any).runtime;
  const db = runtime?.env?.DB;
  const r2 = runtime?.env?.R2;
  if (!db || !r2) {
    return new Response('서버 오류', { status: 500 });
  }

  const resource = await db.prepare(
    'SELECT r2_key, filename FROM resources WHERE id = ?'
  ).bind(resourceId).first() as any;

  if (!resource) {
    return new Response('리소스를 찾을 수 없습니다.', { status: 404 });
  }

  const object = await r2.get(resource.r2_key);
  if (!object) {
    return new Response('파일을 찾을 수 없습니다.', { status: 404 });
  }

  // 다운로드 카운트 증가
  await db.prepare(
    'UPDATE resources SET download_count = download_count + 1 WHERE id = ?'
  ).bind(resourceId).run();

  return new Response(object.body, {
    headers: {
      'Content-Type': 'text/csv; charset=utf-8',
      'Content-Disposition': `attachment; filename="${resource.filename}"`,
    },
  });
};
