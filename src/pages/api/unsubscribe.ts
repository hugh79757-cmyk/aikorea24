export const prerender = false;

import type { APIRoute } from 'astro';

export const POST: APIRoute = async ({ request, locals }) => {
  const runtime = (locals as any).runtime;
  const BREVO_API_KEY = runtime?.env?.BREVO_API_KEY;

  if (!BREVO_API_KEY) {
    return new Response(JSON.stringify({ error: 'BREVO_API_KEY not set' }), {
      status: 500,
      headers: { 'Content-Type': 'application/json' }
    });
  }

  try {
    const { email } = await request.json();

    if (!email || !email.includes('@')) {
      return new Response(JSON.stringify({ error: '유효한 이메일을 입력해주세요.' }), {
        status: 400,
        headers: { 'Content-Type': 'application/json' }
      });
    }

    // Brevo 구독 해지.
    // PUT listIds:[] 는 204 를 반환하면서 실제 리스트에서 제거하지 않는다(실측).
    // 문서상 정답인 DELETE /contacts/{id}/lists/{listId} 는 이 계정에서 404 라
    // 사용 불가 → 컨택트 자체 삭제가 유일하게 확실히 동작하는 방법(204 확인).
    const response = await fetch(`https://api.brevo.com/v3/contacts/${encodeURIComponent(email)}`, {
      method: 'DELETE',
      headers: {
        'api-key': BREVO_API_KEY
      }
    });

    if (!response.ok) {
      const errorData = await response.json();
      console.error('Brevo unsubscribe API error:', errorData);
      return new Response(JSON.stringify({ error: '구독 해지 처리 중 오류가 발생했습니다.' }), {
        status: 500,
        headers: { 'Content-Type': 'application/json' }
      });
    }

    return new Response(JSON.stringify({ success: true, message: '구독이 해지되었습니다.' }), {
      status: 200,
      headers: { 'Content-Type': 'application/json' }
    });
  } catch (error) {
    console.error('Unsubscribe error:', error);
    return new Response(JSON.stringify({ error: '서버 오류가 발생했습니다.' }), {
      status: 500,
      headers: { 'Content-Type': 'application/json' }
    });
  }
};
