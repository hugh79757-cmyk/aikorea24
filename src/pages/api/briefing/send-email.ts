import type { APIRoute } from 'astro';

export const POST: APIRoute = async ({ locals }) => {
  const runtime = (locals as any).runtime;
  const db = runtime?.env?.DB;
  const BREVO_API_KEY = runtime?.env?.BREVO_API_KEY;

  if (!db) return new Response(JSON.stringify({ error: 'DB not available' }), { status: 500 });
  if (!BREVO_API_KEY) return new Response(JSON.stringify({ error: 'BREVO_API_KEY not set' }), { status: 500 });

  try {
    const today = new Date(Date.now() + 9 * 3600 * 1000).toISOString().split('T')[0];

    // 1. 오늘 브리핑 조회
    const briefing = await db.prepare('SELECT * FROM briefings WHERE date = ?').bind(today).first();
    if (!briefing) {
      return new Response(JSON.stringify({ ok: false, error: '오늘 발행된 브리핑이 없습니다.' }), {
        status: 404, headers: { 'Content-Type': 'application/json' }
      });
    }

    // 2. 브리핑 아이템 + 뉴스 조회
    const items = await db.prepare(
      `SELECT bi.*, n.title as news_title, n.description as news_desc, n.link as news_link, n.source as news_source
       FROM briefing_items bi
       LEFT JOIN news n ON bi.news_id = n.id
       WHERE bi.briefing_id = ?
       ORDER BY bi.sort_order ASC`
    ).bind(briefing.id).all();

    // 3. HTML 이메일 본문 생성 (3개만 표시 + 더보기)
    const displayItems = (items.results || []).slice(0, 3);
    const totalCount = items.results?.length || 0;
    let itemsHtml = '';
    for (const item of displayItems) {
      const briefingUrl = `https://aikorea24.kr/news/${today}${item.sort_order ? `#item-${item.sort_order}` : ''}`;
      itemsHtml += `
        <tr>
          <td style="padding:16px 0;border-bottom:1px solid #e5e7eb;">
            <table width="100%" cellpadding="0" cellspacing="0">
              <tr>
                <td style="font-size:14px;color:#2563eb;font-weight:600;padding-bottom:4px;">
                  ${item.news_title || ''}
                </td>
              </tr>
              ${item.comment ? `<tr><td style="font-size:13px;color:#4b5563;padding:4px 0 8px 0;line-height:1.5;">💡 ${item.comment}</td></tr>` : ''}
              ${item.news_desc ? `<tr><td style="font-size:13px;color:#6b7280;line-height:1.5;">${item.news_desc.substring(0, 200)}</td></tr>` : ''}
              <tr><td style="padding-top:8px;">
                <a href="${briefingUrl}" style="font-size:12px;color:#2563eb;text-decoration:underline;">
                  AI코리아24에서 자세히 보기 →
                </a>
              </td></tr>
            </table>
          </td>
        </tr>`;
    }
    if (totalCount > 3) {
      itemsHtml += `
        <tr>
          <td style="padding:16px 0;text-align:center;">
            <a href="https://aikorea24.kr/news/"
               style="display:inline-block;padding:10px 24px;background:#2563eb;color:#ffffff;border-radius:8px;font-size:14px;font-weight:600;text-decoration:none;">
              👉 오늘의 브리핑 ${totalCount}개 전체 보기 →
            </a>
          </td>
        </tr>`;
    }

    // 4. 신규 AI 툴 섹션
    let toolsHtml = '';
    try {
      const tools = await db.prepare(
        `SELECT name, slug, tagline, category, price, korean_support, difficulty
         FROM tools
         WHERE featured = 1 OR updated_at > datetime('now', '-7 days')
         ORDER BY updated_at DESC
         LIMIT 6`
      ).all();

      if (tools.results && tools.results.length > 0) {
        toolsHtml = `
          <tr>
            <td style="padding:24px 0 8px 0;">
              <table width="100%" cellpadding="0" cellspacing="0" style="border-top:2px solid #e5e7eb;padding-top:24px;">
                <tr>
                  <td style="font-size:16px;font-weight:700;color:#1f2937;padding-bottom:16px;">
                    🛠️ 오늘의 신규 AI 도구
                  </td>
                </tr>
                ${tools.results.map(t => `
                  <tr>
                    <td style="padding:8px 0;border-bottom:1px solid #f3f4f6;">
                      <table width="100%" cellpadding="0" cellspacing="0">
                        <tr>
                          <td style="font-size:14px;font-weight:600;color:#111827;">
                            ${t.korean_support ? '🇰🇷 ' : ''}${t.name}
                          </td>
                          <td style="text-align:right;font-size:11px;color:#6b7280;">
                            ${t.price || ''} ${t.category ? '· ' + t.category : ''}
                          </td>
                        </tr>
                        <tr>
                          <td colspan="2" style="font-size:13px;color:#6b7280;padding-top:4px;line-height:1.4;">
                            ${t.tagline || ''}
                          </td>
                        </tr>
                        <tr>
                          <td colspan="2" style="padding-top:6px;">
                            <a href="https://aikorea24.kr/tools/${t.slug}/"
                               style="font-size:12px;color:#2563eb;text-decoration:underline;">
                              AI코리아24에서 자세히 보기 →
                            </a>
                          </td>
                        </tr>
                      </table>
                    </td>
                  </tr>
                `).join('')}
                <tr>
                  <td style="padding:12px 0;text-align:center;">
                    <a href="https://aikorea24.kr/tools/"
                       style="font-size:13px;color:#2563eb;text-decoration:underline;">
                      🔎 모든 AI 도구 보기 →
                    </a>
                  </td>
                </tr>
              </table>
            </td>
          </tr>`;
      }
    } catch (e) {
      console.error('툴 조회 오류:', e);
    }

    const htmlContent = `
      <!DOCTYPE html>
      <html>
      <head><meta charset="utf-8"></head>
      <body style="margin:0;padding:0;background:#f9fafb;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">
        <table width="100%" cellpadding="0" cellspacing="0" style="max-width:600px;margin:0 auto;">
          <tr>
            <td style="padding:32px 24px 16px 24px;background:#1e3a5f;text-align:center;">
              <h1 style="color:#fff;font-size:20px;margin:0;">AI코리아24</h1>
              <p style="color:#94a3b8;font-size:13px;margin:4px 0 0 0;">오늘의 AI 브리핑 — ${today}</p>
            </td>
          </tr>
          ${briefing.intro ? `
          <tr>
            <td style="padding:20px 24px;background:#fff;border-bottom:1px solid #e5e7eb;">
              <p style="font-size:14px;color:#374151;line-height:1.6;margin:0;">${briefing.intro}</p>
            </td>
          </tr>` : ''}
          <tr>
            <td style="padding:0 24px;background:#fff;">
              <table width="100%" cellpadding="0" cellspacing="0">
                ${itemsHtml}
                ${toolsHtml}
              </table>
            </td>
          </tr>
          <tr>
            <td style="padding:24px;text-align:center;color:#9ca3af;font-size:12px;">
              <p style="margin:0;">AI코리아24 · 매일 아침 AI 소식을 전해드립니다</p>
              <p style="margin:4px 0 0 0;">
                <a href="https://aikorea24.kr/community/" style="color:#3b82f6;text-decoration:underline;">💬 커뮤니티</a>에서 오늘의 브리핑에 대한 의견을 나눠보세요
              </p>
              <p style="margin:4px 0 0 0;">
                <a href="https://aikorea24.kr/unsubscribe" style="color:#9ca3af;text-decoration:underline;">구독 해지</a>
              </p>
            </td>
          </tr>
        </table>
      </body>
      </html>`;

    // 4. Brevo 구독자 목록 조회
    let allContacts: string[] = [];
    let offset = 0;
    const limit = 100;

    while (true) {
      const contactRes = await fetch(
        `https://api.brevo.com/v3/contacts?limit=${limit}&offset=${offset}`,
        { headers: { 'api-key': BREVO_API_KEY } }
      );
      if (!contactRes.ok) break;
      const contactData = await contactRes.json();

      for (const c of contactData.contacts || []) {
        if (c.email) allContacts.push(c.email);
      }

      if (contactData.contacts?.length < limit) break;
      offset += limit;
    }

    if (allContacts.length === 0) {
      return new Response(JSON.stringify({ ok: false, error: '구독자가 없습니다.' }), {
        status: 404, headers: { 'Content-Type': 'application/json' }
      });
    }

    // 5. Brevo 이메일 발송 (100명씩 배치)
    let sentCount = 0;
    const batchSize = 100;

    for (let i = 0; i < allContacts.length; i += batchSize) {
      const batch = allContacts.slice(i, i + batchSize);
      const to = batch.map(email => ({ email }));

      const emailRes = await fetch('https://api.brevo.com/v3/smtp/email', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'api-key': BREVO_API_KEY
        },
        body: JSON.stringify({
          sender: { name: 'AI코리아24', email: 'info@aikorea24.kr' },
          to: to,
          subject: `오늘의 AI 브리핑 — ${today}`,
          htmlContent: htmlContent
        })
      });

      if (emailRes.ok) sentCount += batch.length;
    }

    return new Response(JSON.stringify({
      ok: true,
      sent: sentCount,
      total: allContacts.length,
      message: `${sentCount}명에게 발송 완료 (총 ${allContacts.length}명)`
    }), { headers: { 'Content-Type': 'application/json' } });

  } catch (e: any) {
    return new Response(JSON.stringify({ error: e.message }), {
      status: 500, headers: { 'Content-Type': 'application/json' }
    });
  }
};
