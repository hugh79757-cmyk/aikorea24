import type { APIRoute } from 'astro';

export const GET: APIRoute = async ({ request, locals }) => {
  const db = (locals as any).runtime?.env?.DB;
  if (!db) return new Response(JSON.stringify({ reviews: [], avgRating: 0 }), { status: 200 });

  const url = new URL(request.url);
  const toolIndex = url.searchParams.get('tool_index');
  if (!toolIndex) return new Response(JSON.stringify({ reviews: [], avgRating: 0 }), { status: 200 });

  try {
    const reviewResult = await db.prepare(`
      SELECT p.*, u.name as author, u.avatar
      FROM posts p
      JOIN users u ON p.user_id = u.id
      WHERE p.tool_id = ? AND p.category = 'review'
      ORDER BY p.created_at DESC
      LIMIT 10
    `).bind(parseInt(toolIndex)).all();

    const reviews = reviewResult?.results || [];
    const total = reviews.reduce((sum: number, r: any) => sum + (r.rating || 5), 0);
    const avgRating = reviews.length > 0 ? Math.round(total / reviews.length * 10) / 10 : 0;

    return new Response(JSON.stringify({ reviews, avgRating }), { status: 200 });
  } catch (e) {
    console.error('Reviews fetch error:', e);
    return new Response(JSON.stringify({ reviews: [], avgRating: 0 }), { status: 200 });
  }
};
