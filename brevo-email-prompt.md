````markdown
# Brevo 이메일 발송 버튼 추가

## 변경할 파일 (총 2개)

### 1. src/pages/api/briefing/send-email.ts (신규 생성)

POST /api/briefing/send-email

기능:
- 오늘 날짜의 브리핑 조회 (D1 `briefings` 테이블)
- 브리핑 아이템 + 뉴스 상세 조회 (D1 `briefing_items` + `news` 테이블 JOIN)
- Brevo API로 모든 구독자 조회 (`GET /v3/contacts?limit=1000`)
- HTML 이메일 본문 생성 (intro + 각 아이템 제목/코멘트/뉴스 링크)
- Brevo 트랜잭셔널 이메일 발송 (`POST /v3/smtp/email`)
- 구독자가 많으면 100명씩 나눠서 여러 번 발송

```typescript
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

    // 3. HTML 이메일 본문 생성
    let itemsHtml = '';
    for (const item of items.results || []) {
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
              ${item.news_link ? `<tr><td style="padding-top:8px;"><a href="${item.news_link}" style="font-size:12px;color:#2563eb;text-decoration:underline;">원문 읽기 →</a></td></tr>` : ''}
            </table>
          </td>
        </tr>`;
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
              </table>
            </td>
          </tr>
          <tr>
            <td style="padding:24px;text-align:center;color:#9ca3af;font-size:12px;">
              <p style="margin:0;">AI코리아24 · 매일 아침 AI 소식을 전해드립니다</p>
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
          sender: { name: 'AI코리아24', email: 'briefing@aikorea24.kr' },
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
Copy
````

### 2. src/pages/admin/index.astro 수정

수정할 부분:

**A. 상태 표시 줄 바로 아래**, 하단 bot 영역에 발송 버튼 추가:

기존 `bot` div 안에 `pub` 버튼 뒤쪽에 추가:

```html
Copy<button class="pub" id="pub" disabled>브리핑 발행</button>
<button class="email-btn" id="emailBtn" style="display:none;background:#7c3aed;color:#fff;border:none;padding:10px 24px;border-radius:8px;cursor:pointer;font-size:.9rem;font-weight:600;margin-left:8px;">📧 이메일 발송</button>
```

**B. script 안에 있는 checkStatus 함수 수정:**

오늘 브리핑이 있으면 이메일 발송 버튼도 보이게:

```javascript
Copyfunction checkStatus(){
    fetch('/api/briefing/latest/')
      .then(function(r){return r.json()})
      .then(function(d){
        var st = document.getElementById('curStatus');
        var db = document.getElementById('delbtn');
        var eb = document.getElementById('emailBtn');
        if(!st) return;
        if(d && d.briefing && d.briefing.date === today){
          st.innerHTML = '오늘 브리핑 발행됨: <b>'+(d.items?d.items.length:0)+'건</b>';
          st.style.color = '#4ade80';
          if(db) db.style.display = 'inline-block';
          if(eb) eb.style.display = 'inline-block';  // 이메일 버튼 표시
        } else {
          st.textContent = '오늘 발행된 브리핑 없음';
          st.style.color = '#94a3b8';
          if(db) db.style.display = 'none';
          if(eb) eb.style.display = 'none';  // 이메일 버튼 숨김
        }
        var ddBtnEl = document.getElementById('ddBtn');
        if(ddBtnEl) ddBtnEl.style.display = 'inline-block';
      })
      .catch(function(e){ console.log('checkStatus:', e); });
  }
```

**C. 이메일 발송 이벤트 리스너 추가 (script 하단):**

```javascript
Copydocument.getElementById('emailBtn')?.addEventListener('click', function(){
  var btn = this;
  var msg = document.getElementById('msg');
  btn.disabled = true;
  btn.textContent = '발송 중...';
  msg.className = 'msg';
  msg.textContent = '이메일 발송 중입니다...';

  fetch('/api/briefing/send-email/', { method: 'POST' })
    .then(function(r){ return r.json(); })
    .then(function(d){
      btn.disabled = false;
      btn.textContent = '📧 이메일 발송';
      if(d.ok){
        msg.className = 'msg ok';
        msg.textContent = '✅ ' + d.message;
      } else {
        msg.className = 'msg err';
        msg.textContent = '❌ ' + (d.error || '발송 실패');
      }
    })
    .catch(function(e){
      btn.disabled = false;
      btn.textContent = '📧 이메일 발송';
      msg.className = 'msg err';
      msg.textContent = '❌ 에러: ' + e.message;
    });
});
```

### 3. wrangler.toml 확인

```toml
Copy[vars]
BREVO_API_KEY = "xkeysib-..."
BREVO_LIST_ID = "2"
```
