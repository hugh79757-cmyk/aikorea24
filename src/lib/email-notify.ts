// Brevo 단일 수신자 이메일 발송 (승인/반려 알림 전용)
// 기존 src/pages/api/briefing/send-email.ts:300 의 Brevo 호출 방식을 참고하되,
// 배치(100명)가 아닌 단일 수신자용으로 작성.

const BREVO_URL = 'https://api.brevo.com/v3/smtp/email';
const SENDER = { name: 'AI코리아24', email: 'info@aikorea24.kr' };
const BASE_URL = 'https://aikorea24.kr';

export interface ToolNotifyParams {
  to: string;           // 제출자 이메일
  toolName: string;     // 도구명
  toolSlug: string;     // URL용 slug
  status: 'approved' | 'rejected';
  reason?: string;      // 반려 사유 (rejected일 때만)
}

function escapeHtml(s: string): string {
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function approvedHtml(params: ToolNotifyParams): { subject: string; html: string } {
  const name = escapeHtml(params.toolName);
  const slug = escapeHtml(params.toolSlug);
  return {
    subject: `[AI코리아24] ${name} 등록이 승인되었습니다`,
    html: `
<div style="font-family:system-ui,Arial,sans-serif;max-width:640px;margin:0 auto;padding:24px;color:#1f2937;">
  <h2 style="font-size:20px;margin:0 0 16px;">등록이 승인되었습니다</h2>
  <p style="margin:0 0 16px;line-height:1.6;">
    등록하신 <strong>${name}</strong>이(가) 검토를 통과하여 디렉토리에 공개되었습니다.
  </p>
  <p style="margin:0 0 24px;font-size:14px;color:#6b7280;">
    수정이 필요하시면 info@aikorea24.kr로 회신해주세요.
  </p>
  <a href="${BASE_URL}/tools/${slug}/" style="display:inline-block;background:#3b82f6;color:#fff;padding:12px 20px;border-radius:8px;text-decoration:none;font-weight:600;font-size:14px;">
    등록 페이지 보기 →
  </a>
  <hr style="margin:32px 0;border:none;border-top:1px solid #e5e7eb;">
  <p style="margin:0;font-size:12px;color:#9ca3af;">AI코리아24 · 이 메일은 도구 등록 승인 알림을 위해 발송되었습니다.</p>
</div>`,
  };
}

function rejectedHtml(params: ToolNotifyParams): { subject: string; html: string } {
  const name = escapeHtml(params.toolName);
  const reason = escapeHtml(params.reason || '');
  return {
    subject: `[AI코리아24] ${name} 등록 검토 결과 안내`,
    html: `
<div style="font-family:system-ui,Arial,sans-serif;max-width:640px;margin:0 auto;padding:24px;color:#1f2937;">
  <h2 style="font-size:20px;margin:0 0 16px;">등록 검토 결과 안내</h2>
  <p style="margin:0 0 16px;line-height:1.6;">
    등록하신 <strong>${name}</strong>이(가) 아래 사유로 공개되지 않았습니다.
  </p>
  <div style="background:#fef2f2;border:1px solid #fecaca;border-radius:8px;padding:16px;margin:0 0 16px;">
    <p style="margin:0 0 4px;font-size:13px;font-weight:600;color:#b91c1c;">사유</p>
    <p style="margin:0;font-size:14px;color:#7f1d1d;white-space:pre-wrap;">${reason}</p>
  </div>
  <p style="margin:0 0 24px;line-height:1.6;font-size:14px;">
    수정 후 다시 제출하신 수 있습니다.
  </p>
  <a href="${BASE_URL}/tools/submit/" style="display:inline-block;background:#3b82f6;color:#fff;padding:12px 20px;border-radius:8px;text-decoration:none;font-weight:600;font-size:14px;">
    등록 페이지로 이동 →
  </a>
  <hr style="margin:32px 0;border:none;border-top:1px solid #e5e7eb;">
  <p style="margin:0;font-size:12px;color:#9ca3af;">AI코리아24 · 이 메일은 도구 등록 반려 알림을 위해 발송되었습니다.</p>
</div>`,
  };
}

export async function sendToolNotification(
  params: ToolNotifyParams,
  apiKey: string
): Promise<{ success: boolean; error?: string }> {
  if (!apiKey) {
    return { success: false, error: 'BREVO_API_KEY not configured' };
  }
  if (!params.to || !params.to.includes('@')) {
    return { success: false, error: 'invalid recipient email' };
  }

  const template = params.status === 'approved' ? approvedHtml(params) : rejectedHtml(params);

  try {
    const res = await fetch(BREVO_URL, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'api-key': apiKey,
      },
      body: JSON.stringify({
        sender: SENDER,
        to: [{ email: params.to }],
        subject: template.subject,
        htmlContent: template.html,
      }),
    });

    if (!res.ok) {
      const text = await res.text().catch(() => '');
      return { success: false, error: `Brevo HTTP ${res.status}: ${text.slice(0, 200)}` };
    }
    return { success: true };
  } catch (e: any) {
    return { success: false, error: e?.message || 'fetch failed' };
  }
}