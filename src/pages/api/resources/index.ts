import type { APIRoute } from 'astro';

export const GET: APIRoute = async ({ cookies, locals }) => {
  const session = cookies.get('session')?.value;
  if (!session) {
    return new Response(JSON.stringify({ error: 'login_required' }), {
      status: 401,
      headers: { 'Content-Type': 'application/json' },
    });
  }

  let user: any;
  try {
    user = JSON.parse(atob(session.split('.')[1] || session));
  } catch {
    return new Response(JSON.stringify({ error: 'invalid_session' }), {
      status: 401,
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

  const { results } = await db.prepare(`
    SELECT r.id, r.title, r.description, r.filename, r.event_code, r.created_at,
           ag.granted_at, ag.downloaded_at
    FROM access_grants ag
    JOIN resources r ON ag.resource_id = r.id
    WHERE ag.email = ?
    ORDER BY ag.granted_at DESC
  `).bind(user.email).all();

  return new Response(JSON.stringify({ email: user.email, resources: results || [] }), {
    headers: { 'Content-Type': 'application/json' },
  });
};
