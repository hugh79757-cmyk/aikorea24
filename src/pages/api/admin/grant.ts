import type { APIRoute } from 'astro';

const ADMIN_EMAILS = ['twinssn@gmail.com'];

function isAdmin(cookies: any): boolean {
  const session = cookies.get('session')?.value;
  if (!session) return false;
  try {
    const user = JSON.parse(atob(session.split('.')[1] || session));
    return ADMIN_EMAILS.includes(user.email);
  } catch {
    return false;
  }
}

// 권한 부여
export const POST: APIRoute = async ({ request, cookies, locals }) => {
  if (!isAdmin(cookies)) {
    return new Response(JSON.stringify({ error: 'unauthorized' }), {
      status: 403,
      headers: { 'Content-Type': 'application/json' },
    });
  }

  const runtime = (locals as any).runtime;
  const db = runtime?.env?.DB;
  if (!db) {
    return new Response(JSON.stringify({ error: 'db_unavailable' }), {
      status: 500,
      headers: { 'Content-Type': 'application/json' },
    });
  }

  try {
    const body = await request.json();
    const { email, resource_id } = body;

    if (!email || !resource_id) {
      return new Response(JSON.stringify({ error: 'email, resource_id required' }), {
        status: 400,
        headers: { 'Content-Type': 'application/json' },
      });
    }

    await db.prepare(
      'INSERT OR IGNORE INTO access_grants (email, resource_id) VALUES (?, ?)'
    ).bind(email, resource_id).run();

    return new Response(JSON.stringify({ ok: true, email, resource_id }), {
      headers: { 'Content-Type': 'application/json' },
    });
  } catch (e: any) {
    return new Response(JSON.stringify({ error: e.message }), {
      status: 500,
      headers: { 'Content-Type': 'application/json' },
    });
  }
};

// 권한 목록 조회
export const GET: APIRoute = async ({ cookies, locals }) => {
  if (!isAdmin(cookies)) {
    return new Response(JSON.stringify({ error: 'unauthorized' }), {
      status: 403,
      headers: { 'Content-Type': 'application/json' },
    });
  }

  const runtime = (locals as any).runtime;
  const db = runtime?.env?.DB;
  if (!db) {
    return new Response(JSON.stringify([]), {
      headers: { 'Content-Type': 'application/json' },
    });
  }

  const { results } = await db.prepare(`
    SELECT ag.id, ag.email, ag.granted_at, ag.downloaded_at,
           r.id as resource_id, r.title, r.filename
    FROM access_grants ag
    JOIN resources r ON ag.resource_id = r.id
    ORDER BY ag.granted_at DESC
  `).all();

  return new Response(JSON.stringify(results || []), {
    headers: { 'Content-Type': 'application/json' },
  });
};

// 권한 삭제
export const DELETE: APIRoute = async ({ request, cookies, locals }) => {
  if (!isAdmin(cookies)) {
    return new Response(JSON.stringify({ error: 'unauthorized' }), {
      status: 403,
      headers: { 'Content-Type': 'application/json' },
    });
  }

  const runtime = (locals as any).runtime;
  const db = runtime?.env?.DB;
  if (!db) {
    return new Response(JSON.stringify({ error: 'db_unavailable' }), {
      status: 500,
      headers: { 'Content-Type': 'application/json' },
    });
  }

  try {
    const body = await request.json();
    const { grant_id } = body;
    await db.prepare('DELETE FROM access_grants WHERE id = ?').bind(grant_id).run();
    return new Response(JSON.stringify({ ok: true }), {
      headers: { 'Content-Type': 'application/json' },
    });
  } catch (e: any) {
    return new Response(JSON.stringify({ error: e.message }), {
      status: 500,
      headers: { 'Content-Type': 'application/json' },
    });
  }
};
