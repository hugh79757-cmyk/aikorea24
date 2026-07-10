/**
 * GET /api/courses/track
 *
 * 이메일 내 링크 클릭 추적. lesson_clicks 테이블에 기록 후 원본 URL로 302 리다이렉트.
 *
 * Query params:
 *   e  — enrollment_id
 *   d  — day_number
 *   url — 원본 URL (encoded)
 *
 * 응답: 302 redirect to url (또는 url이 없으면 400)
 */
import type { APIRoute } from 'astro';

export const GET: APIRoute = async (context) => {
  const db = (context.locals as any).runtime?.env?.DB;

  if (!db) {
    return new Response(null, { status: 302, headers: { Location: '/' } });
  }

  try {
    const url = new URL(context.request.url);
    const enrollmentId = url.searchParams.get('e');
    const dayNumber = url.searchParams.get('d');
    const redirectUrl = url.searchParams.get('url');

    // url이 없으면 홈으로
    if (!redirectUrl) {
      return new Response(null, { status: 302, headers: { Location: '/' } });
    }

    // 유효한 파라미터면 클릭 기록
    if (enrollmentId && dayNumber) {
      const eId = parseInt(enrollmentId, 10);
      const dNum = parseInt(dayNumber, 10);

      if (!isNaN(eId) && !isNaN(dNum) && dNum >= 1 && dNum <= 30) {
        // enrollment 존재 확인
        const enrollment = await db.prepare(
          'SELECT id FROM enrollments WHERE id = ?'
        ).bind(eId).first();

        if (enrollment) {
          // INSERT OR IGNORE (중복 클릭 방지)
          await db.prepare(
            'INSERT OR IGNORE INTO lesson_clicks (enrollment_id, day_number) VALUES (?, ?)'
          ).bind(eId, dNum).run();
        }
      }
    }

    // 302 리다이렉트
    const decodedUrl = decodeURIComponent(redirectUrl);
    return new Response(null, {
      status: 302,
      headers: { Location: decodedUrl },
    });

  } catch (err) {
    console.error('track error:', err);
    // 에러 나도 리다이렉트는 보장
    const fallbackUrl = context.url.searchParams.get('url');
    return new Response(null, {
      status: 302,
      headers: { Location: fallbackUrl ? decodeURIComponent(fallbackUrl) : '/' },
    });
  }
};
