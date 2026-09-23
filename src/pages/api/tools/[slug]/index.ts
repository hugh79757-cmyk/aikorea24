import type { APIRoute } from 'astro';
import { verifySession } from '../../../../lib/auth';
import { TASKS } from '../../../../config/tasks';

// submit.ts와 동일한 화이트리스트 (validation parity)
const ALLOWED_CATEGORIES = [
  '글쓰기·챗봇',
  '이미지 생성',
  '영상·음성',
  '업무·생산성',
  '코딩·개발',
  '디자인',
  '번역·학습',
  '기타',
];
const PRICE_MODELS = ['무료', 'Freemium', '유료'];

export const PUT: APIRoute = async ({ params, request, locals, cookies }) => {
  const db = (locals as any).runtime?.env?.DB;
  if (!db) return new Response(JSON.stringify({ error: 'DB 없음' }), { status: 500 });

  const session = cookies.get('session')?.value;
  if (!session) {
    return new Response(JSON.stringify({ error: '로그인이 필요합니다.' }), { status: 401 });
  }

  let user: { email: string; name: string } | null;
  try {
    user = await verifySession(session, (locals as any).sessionSecret);
  } catch {
    return new Response(JSON.stringify({ error: '유효하지 않은 세션입니다.' }), { status: 401 });
  }
  if (!user) {
    return new Response(JSON.stringify({ error: '유효하지 않은 세션입니다.' }), { status: 401 });
  }

  const { slug } = params;
  if (!slug) {
    return new Response(JSON.stringify({ error: 'slug가 필요합니다.' }), { status: 400 });
  }

  // users 테이블에서 user_id 역조회 (posts/index.ts 패턴)
  let userId = 0;
  try {
    const userRow = await db.prepare('SELECT id FROM users WHERE email = ?').bind(user.email).first();
    if (userRow) userId = (userRow as any).id;
  } catch {}
  if (!userId) {
    return new Response(JSON.stringify({ error: '유효하지 않은 세션입니다.' }), { status: 401 });
  }

  const row = await db.prepare('SELECT user_id FROM tool_submissions WHERE slug = ?').bind(slug).first();
  if (!row) {
    return new Response(JSON.stringify({ error: '도구를 찾을 수 없습니다.' }), { status: 404 });
  }
  if ((row as any).user_id !== userId) {
    return new Response(JSON.stringify({ error: '권한이 없습니다.' }), { status: 403 });
  }

  try {
    const body = await request.json();
    const { name, url, category, category_custom, description, price_model, price_detail, screenshot_url, korean_support, difficulty, use_cases, tags, tasks, detail_markdown } = body;

    // 필수 4종 검증 (submit.ts parity)
    if (!name?.trim() || !url?.trim() || !category?.trim() || !description?.trim()) {
      return new Response(JSON.stringify({ error: '이름, URL, 카테고리, 설명을 모두 입력해주세요.' }), { status: 400 });
    }

    // 설명 200자 캡 (무음 절단 금지 → 400)
    if (description.trim().length > 200) {
      return new Response(JSON.stringify({ error: '설명은 200자 이내로 입력해주세요.' }), { status: 400 });
    }

    // URL 검증: http(s)만
    try {
      const parsed = new URL(url.trim());
      if (parsed.protocol !== 'http:' && parsed.protocol !== 'https:') {
        return new Response(JSON.stringify({ error: '올바른 URL을 입력해주세요. (http:// 또는 https://)' }), { status: 400 });
      }
    } catch {
      return new Response(JSON.stringify({ error: '올바른 URL을 입력해주세요.' }), { status: 400 });
    }

    // 카테고리 화이트리스트
    if (!ALLOWED_CATEGORIES.includes(category.trim())) {
      return new Response(JSON.stringify({ error: '올바른 카테고리를 선택해주세요.' }), { status: 400 });
    }

    // 가격 모델: 필수 3택 (D-02)
    if (!price_model?.trim() || !PRICE_MODELS.includes(price_model.trim())) {
      return new Response(JSON.stringify({ error: '가격 모델을 선택해주세요. (무료/Freemium/유료)' }), { status: 400 });
    }

    // screenshot_url: 선택, 비어있으면 스킵, 값 있으면 http(s) 또는 /api/files/ 상대경로 허용
    let screenshotUrl: string | null = null;
    if (screenshot_url !== undefined && screenshot_url !== null && String(screenshot_url).trim() !== '') {
      const shot = String(screenshot_url).trim();
      if (shot.startsWith('/api/files/')) {
        screenshotUrl = shot;
      } else {
      try {
        const parsedShot = new URL(shot);
        if (parsedShot.protocol !== 'http:' && parsedShot.protocol !== 'https:') {
          return new Response(JSON.stringify({ error: '올바른 스크린샷 URL을 입력해주세요. (http:// 또는 https://)' }), { status: 400 });
        }
        screenshotUrl = String(screenshot_url).trim();
      } catch {
        return new Response(JSON.stringify({ error: '올바른 스크린샷 URL을 입력해주세요.' }), { status: 400 });
      }
      }
    }

    // tasks: 최대 5개 + TASKS 키 존재 검증
    let taskList: string[] = [];
    if (tasks !== undefined && tasks !== null) {
      if (!Array.isArray(tasks)) {
        return new Response(JSON.stringify({ error: '연관작업 형식이 올바르지 않습니다.' }), { status: 400 });
      }
      if (tasks.length > 5) {
        return new Response(JSON.stringify({ error: '연관작업은 최대 5개까지 선택할 수 있습니다.' }), { status: 400 });
      }
      for (const t of tasks) {
        if (!TASKS[t]) {
          return new Response(JSON.stringify({ error: `알 수 없는 연관작업입니다: ${t}` }), { status: 400 });
        }
      }
      taskList = tasks;
    }

    const tagList = Array.isArray(tags) ? tags.map((t: any) => String(t)) : [];

    // slug immutable: slug 컬럼을 UPDATE하지 않음 (이름이 바뀌어도 slug 유지)
    await db.prepare(
      `UPDATE tool_submissions SET
        name = ?, url = ?, category = ?, category_custom = ?, description = ?,
        price_model = ?, price_detail = ?, screenshot_url = ?, korean_support = ?,
        difficulty = ?, use_cases = ?, tags = ?, tasks = ?, detail_markdown = ?,
        updated_at = datetime('now')
       WHERE slug = ?`
    ).bind(
      name.trim(),
      url.trim(),
      category.trim(),
      category_custom?.trim() || null,
      description.trim(),
      price_model.trim(),
      price_detail?.trim() || null,
      screenshotUrl,
      korean_support ? 1 : 0,
      difficulty?.trim() || null,
      use_cases?.trim() || null,
      JSON.stringify(tagList),
      JSON.stringify(taskList),
      detail_markdown?.trim() || null,
      slug,
    ).run();

    return new Response(JSON.stringify({ success: true, slug }), {
      headers: { 'Content-Type': 'application/json' },
    });
  } catch (e: any) {
    console.error('Tools update error:', e);
    return new Response(JSON.stringify({ error: '수정 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.' }), { status: 500 });
  }
};
