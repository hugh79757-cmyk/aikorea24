import type { APIRoute } from 'astro';
import { verifySession } from '../../../lib/auth';

// Phase 5: dofollow/nofollow 수동 전환 API
// 관리자가 배지 설치 확인 후 링크 타입을 수동 변경

const ADMIN_EMAILS = ['twinssn@gmail.com'];

async function isAdmin(cookies: any, secret: string): Promise<boolean> {
  const session = cookies.get('session')?.value;
  if (!session) return false;
  try {
    const user = await verifySession(session, secret);
    if (!user) return false;
    return ADMIN_EMAILS.includes(user.email);
  } catch {
    return false;
  }
}

export const PATCH: APIRoute = async ({ request, cookies, locals }) => {
  if (!(await isAdmin(cookies, (locals as any).sessionSecret))) {
    return new Response(JSON.stringify({ error: 'unauthorized' }), {
      status: 403,
      headers: { 'Content-Type': 'application/json' },
    });
  }

  const db = (locals as any).runtime?.env?.DB;
  if (!db) {
    return new Response(JSON.stringify({ error: 'db_unavailable' }), {
      status: 500,
      headers: { 'Content-Type': 'application/json' },
    });
  }

  let slug: string | undefined;
  let linkType: string | undefined;
  try {
    const body = await request.json();
    slug = body?.slug;
    linkType = body?.linkType;
  } catch {
    return new Response(JSON.stringify({ error: '요청 본문을 확인해주세요.' }), {
      status: 400,
      headers: { 'Content-Type': 'application/json' },
    });
  }

  if (!slug?.trim()) {
    return new Response(JSON.stringify({ error: 'slug이 필요합니다.' }), {
      status: 400,
      headers: { 'Content-Type': 'application/json' },
    });
  }

  if (linkType !== 'dofollow' && linkType !== 'nofollow') {
    return new Response(JSON.stringify({ error: "linkType은 dofollow 또는 nofollow이어야 합니다." }), {
      status: 400,
      headers: { 'Content-Type': 'application/json' },
    });
  }

  const row = await db
    .prepare('SELECT slug, link_type FROM tool_submissions WHERE slug = ?')
    .bind(slug.trim())
    .first();

  if (!row) {
    return new Response(JSON.stringify({ error: '도구를 찾을 수 없습니다.' }), {
      status: 404,
      headers: { 'Content-Type': 'application/json' },
    });
  }

  const prevType = (row as any).link_type || 'nofollow';
  await db
    .prepare(
      `UPDATE tool_submissions SET link_type = ?, updated_at = datetime('now') WHERE slug = ?`
    )
    .bind(linkType, slug.trim())
    .run();

  return new Response(JSON.stringify({
    ok: true,
    slug: slug.trim(),
    linkType,
    previousLinkType: prevType,
  }), {
    headers: { 'Content-Type': 'application/json' },
  });
};

export const GET: APIRoute = async ({ cookies, query, locals }) => {
  if (!(await isAdmin(cookies, (locals as any).sessionSecret))) {
    return new Response(JSON.stringify({ error: 'unauthorized' }), {
      status: 403,
      headers: { 'Content-Type': 'application/json' },
    });
  }

  const db = (locals as any).runtime?.env?.DB;
  if (!db) {
    return new Response(JSON.stringify({ error: 'db_unavailable' }), {
      status: 500,
      headers: { 'Content-Type': 'application/json' },
    });
  }

  const slug = (query.get('slug') || '').trim();
  if (!slug) {
    return new Response(JSON.stringify({ error: 'slug 파라미터 필요' }), {
      status: 400,
      headers: { 'Content-Type': 'application/json' },
    });
  }

  const row = await db
    .prepare('SELECT slug, link_type FROM tool_submissions WHERE slug = ?')
    .bind(slug)
    .first();

  if (!row) {
    return new Response(JSON.stringify({ error: '도구를 찾을 수 없습니다.' }), {
      status: 404,
      headers: { 'Content-Type': 'application/json' },
    });
  }

  return new Response(JSON.stringify({
    slug: row.slug,
    linkType: row.link_type || 'nofollow',
  }), {
    headers: { 'Content-Type': 'application/json' },
  });
};