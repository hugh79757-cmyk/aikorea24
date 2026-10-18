export const prerender = false;

import { env } from 'cloudflare:workers';
import type { APIRoute } from 'astro';
import { cleanBriefingComment, cleanBriefingDescription, cleanBriefingTitle } from '../../../lib/briefing-comment';

export const GET: APIRoute = async ({ url, locals }) => {

  const db = env.DB;
  if (!db) return new Response(JSON.stringify(null), { headers: { 'Content-Type': 'application/json' } });

  const date = url.searchParams.get('date');

  let briefing;
  if (date) {
    briefing = await db.prepare(
      "SELECT * FROM briefings WHERE date LIKE ? AND status = 'published' ORDER BY id DESC LIMIT 1"
    ).bind(date + '%').first();
  } else {
    briefing = await db.prepare(
      "SELECT * FROM briefings WHERE status = 'published' ORDER BY id DESC LIMIT 1"
    ).first();
  }

  if (!briefing) {
    return new Response(JSON.stringify(null), { headers: { 'Content-Type': 'application/json' } });
  }

  const { results: items } = await db.prepare(
    `SELECT bi.id, bi.sort_order, bi.comment,
            n.id as news_id, n.title, n.link, n.description, n.source, n.category, n.country, n.pub_date
     FROM briefing_items bi
     JOIN news n ON bi.news_id = n.id
     WHERE bi.briefing_id = ?
     ORDER BY bi.sort_order`
  ).bind(briefing.id).all();

  // AIK24-PIPE-04 §작업2 / AIK24-PIPE-05 §제목 표시 교정:
  // 화면·이메일과 같은 정리 규칙을 이 API 응답에도 적용한다 (웹/이메일/API 표시가 어긋나지 않게).
  //   · title      — 수집기 내부 표식([제외]·[신규 무료]·[무료 LLM])을 문장으로 바꾼다
  //   · comment    — verdict·(a)/(b)·설정 JSON·죽은 텍스트 링크를 걷어낸다
  //   · description— 한 줄 안의 verdict 조각·설정 JSON 조각을 걷어낸다
  const displayItems = (items || []).map((it: any) => ({
    ...it,
    title: cleanBriefingTitle(it.title),
    comment: cleanBriefingComment(it.comment),
    description: cleanBriefingDescription(it.description),
  }));

  return new Response(JSON.stringify({ briefing, items: displayItems }), {
    headers: { 'Content-Type': 'application/json' }
  });
};
