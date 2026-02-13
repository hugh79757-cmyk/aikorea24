import type { APIRoute } from 'astro';

export const GET: APIRoute = async ({ request, locals }) => {
  const db = (locals as any).runtime.env.DB;
  const url = new URL(request.url);
  const page = Math.max(1, parseInt(url.searchParams.get('page') || '1'));
  const limit = Math.min(50, parseInt(url.searchParams.get('limit') || '20'));
  const category = url.searchParams.get('category') || '';
  const offset = (page - 1) * limit;

  try {
    let whereClause = '';
    const params: any[] = [];

    if (category) {
      whereClause = 'WHERE category = ?';
      params.push(category);
    }

    const countResult = await db.prepare(
      `SELECT COUNT(*) as total FROM posts ${whereClause}`
    ).bind(...params).first<{ total: number }>();
    const total = countResult?.total || 0;

    const posts = await db.prepare(`
      SELECT p.*,
        (SELECT COUNT(*) FROM comments c WHERE c.post_id = p.id) as comment_count
      FROM posts p
      ${whereClause}
      ORDER BY p.created_at DESC
      LIMIT ? OFFSET ?
    `).bind(...params, limit, offset).all();

    return new Response(JSON.stringify({
      posts: posts.results,
      pagination: { page, limit, total, totalPages: Math.ceil(total / limit) }
    }), {
      headers: { 'Content-Type': 'application/json' }
    });
  } catch (e: any) {
    return new Response(JSON.stringify({ error: e.message }), { status: 500 });
  }
};

export const POST: APIRoute = async ({ request, locals, cookies }) => {
  const db = (locals as any).runtime.env.DB;

  const session = cookies.get('session')?.value;
  if (!session) {
    return new Response(JSON.stringify({ error: '로그인이 필요합니다.' }), { status: 401 });
  }

  let user: { email: string; name: string };
  try {
    user = JSON.parse(atob(session.split('.')[1] || session));
  } catch {
    return new Response(JSON.stringify({ error: '유효하지 않은 세션입니다.' }), { status: 401 });
  }

  try {
    const body = await request.json();
    const { title, content, category, access_level, price, preview_content } = body;

    if (!title?.trim() || !content?.trim()) {
      return new Response(JSON.stringify({ error: '제목과 내용을 입력하세요.' }), { status: 400 });
    }

    const allowedCategories = ['free', 'qna', 'news', 'tip', 'project'];
    const cat = allowedCategories.includes(category) ? category : 'free';

    const accessLevels = ['free', 'basic', 'premium'];
    const al = accessLevels.includes(access_level) ? access_level : 'free';
    const p = al !== 'free' ? (parseInt(price) || 0) : 0;
    const pc = al !== 'free' ? (preview_content?.trim()?.slice(0, 500) || '') : '';

    const result = await db.prepare(
      'INSERT INTO posts (title, content, author_email, author_name, category, access_level, price, preview_content) VALUES (?, ?, ?, ?, ?, ?, ?, ?)'
    ).bind(
      title.trim().slice(0, 200),
      content.trim().slice(0, 10000),
      user.email,
      user.name || '익명',
      cat,
      al,
      p,
      pc
    ).run();

    return new Response(JSON.stringify({
      success: true,
      id: result.meta.last_row_id
    }), {
      status: 201,
      headers: { 'Content-Type': 'application/json' }
    });
  } catch (e: any) {
    return new Response(JSON.stringify({ error: e.message }), { status: 500 });
  }
};
