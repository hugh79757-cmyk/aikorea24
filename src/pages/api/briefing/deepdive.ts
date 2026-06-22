import type { APIRoute } from 'astro';
import { verifySession } from '../../../lib/auth';

// PATCH /api/briefing/deepdive
// body: { item_id: number, deep_dive_url: string | null }
export const PATCH: APIRoute = async ({ request, locals, cookies }) => {
  // 인증 확인
  const ADMIN_EMAILS = ['twinssn@gmail.com'];
  const session = cookies.get('session')?.value;
  if (!session) return new Response(JSON.stringify({ error: 'Unauthorized' }), { status: 401 });
  try {
    const user = await verifySession(session, (locals as any).sessionSecret);
    if (!user || !ADMIN_EMAILS.includes(user.email)) {
      return new Response(JSON.stringify({ error: 'Forbidden' }), { status: 403 });
    }
  } catch {
    return new Response(JSON.stringify({ error: 'Invalid session' }), { status: 401 });
  }

  const runtime = (locals as any).runtime;
  const db = runtime?.env?.DB;
  if (!db) return new Response(JSON.stringify({ error: 'DB not available' }), { status: 500 });

  try {
    const body = await request.json() as { item_id: number; deep_dive_url: string | null };
    const { item_id, deep_dive_url } = body;

    if (!item_id) {
      return new Response(JSON.stringify({ error: 'item_id required' }), { status: 400 });
    }

    // URL 기본 검증 (null 허용 - 연결 해제용)
    if (deep_dive_url !== null && deep_dive_url !== '') {
      try {
        new URL(deep_dive_url);
      } catch {
        return new Response(JSON.stringify({ error: 'Invalid URL' }), { status: 400 });
      }
    }

    const url = deep_dive_url === '' ? null : deep_dive_url;

    await db.prepare(
      'UPDATE briefing_items SET deep_dive_url = ? WHERE id = ?'
    ).bind(url, item_id).run();

    return new Response(JSON.stringify({ ok: true, item_id, deep_dive_url: url }), {
      headers: { 'Content-Type': 'application/json' }
    });
  } catch (e: any) {
    console.error('Deepdive PATCH error:', e);
    return new Response(JSON.stringify({ error: import.meta.env.DEV ? e.message : 'Internal Server Error' }), { status: 500 });
  }
};

// GET /api/briefing/deepdive?briefing_id=N  (어드민에서 현재 연결 상태 조회용)
export const GET: APIRoute = async ({ url, locals, cookies }) => {
  const ADMIN_EMAILS = ['twinssn@gmail.com'];
  const session = cookies.get('session')?.value;
  if (!session) return new Response(JSON.stringify({ error: 'Unauthorized' }), { status: 401 });
  try {
    const user = await verifySession(session, (locals as any).sessionSecret);
    if (!user || !ADMIN_EMAILS.includes(user.email)) {
      return new Response(JSON.stringify({ error: 'Forbidden' }), { status: 403 });
    }
  } catch {
    return new Response(JSON.stringify({ error: 'Invalid session' }), { status: 401 });
  }

  const runtime = (locals as any).runtime;
  const db = runtime?.env?.DB;
  if (!db) return new Response(JSON.stringify({ error: 'DB not available' }), { status: 500 });

  const briefingId = url.searchParams.get('briefing_id');
  if (!briefingId) return new Response(JSON.stringify({ error: 'briefing_id required' }), { status: 400 });

  const { results } = await db.prepare(
    `SELECT bi.id, bi.sort_order, bi.deep_dive_url, n.title
     FROM briefing_items bi
     LEFT JOIN news n ON bi.news_id = n.id
     WHERE bi.briefing_id = ?
     ORDER BY bi.sort_order`
  ).bind(briefingId).all();

  return new Response(JSON.stringify(results), {
    headers: { 'Content-Type': 'application/json' }
  });
};
