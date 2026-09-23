import type { APIRoute } from 'astro';

export const GET: APIRoute = async ({ params, locals }) => {
  const r2 = (locals as any).runtime?.env?.R2;
  if (!r2) return new Response('스토리지 설정 오류입니다.', { status: 500 });

  const segments = params.path;
  const path = Array.isArray(segments) ? segments.join('/') : (segments ?? '');
  if (!path) return new Response('파일을 찾을 수 없습니다.', { status: 404 });

  const obj = await r2.get(path);
  if (!obj) return new Response('파일을 찾을 수 없습니다.', { status: 404 });

  const headers = new Headers();
  const contentType = (obj as any).httpMetadata?.contentType || 'application/octet-stream';
  headers.set('Content-Type', contentType);
  headers.set('Cache-Control', 'public, max-age=31536000');
  const etag = (obj as any).httpEtag;
  if (etag) headers.set('ETag', etag);

  return new Response(obj.body as any, { status: 200, headers });
};
