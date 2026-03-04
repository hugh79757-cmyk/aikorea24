import type { APIRoute } from 'astro';

export const GET: APIRoute = async ({ url, cookies, locals }) => {
  const session = cookies.get('session')?.value;
  if (!session) {
    return new Response('로그인이 필요합니다.', { status: 401 });
  }

  let user: any;
  try {
    user = JSON.parse(atob(session.split('.')[1] || session));
  } catch {
    return new Response('세션이 만료되었습니다.', { status: 401 });
  }

  const resourceId = url.searchParams.get('id');
  if (!resourceId) {
    return new Response('리소스 ID가 필요합니다.', { status: 400 });
  }

  const runtime = (locals as any).runtime;
  const db = runtime?.env?.DB;
  const r2 = runtime?.env?.R2;
  if (!db || !r2) {
    return new Response('서버 오류', { status: 500 });
  }

  // 권한 확인
  const grant = await db.prepare(
    'SELECT id FROM access_grants WHERE email = ? AND resource_id = ?'
  ).bind(user.email, resourceId).first();

  if (!grant) {
    return new Response('다운로드 권한이 없습니다.', { status: 403 });
  }

  // 리소스 정보
  const resource = await db.prepare(
    'SELECT r2_key, filename FROM resources WHERE id = ?'
  ).bind(resourceId).first() as any;

  if (!resource) {
    return new Response('리소스를 찾을 수 없습니다.', { status: 404 });
  }

  // R2에서 파일 가져오기
  const object = await r2.get(resource.r2_key);
  if (!object) {
    return new Response('파일을 찾을 수 없습니다.', { status: 404 });
  }

  // 다운로드 기록 업데이트
  await db.prepare(
    "UPDATE access_grants SET downloaded_at = datetime('now') WHERE email = ? AND resource_id = ?"
  ).bind(user.email, resourceId).run();
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
