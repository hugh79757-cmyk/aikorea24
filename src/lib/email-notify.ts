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

export interface ApprovalEmailParams {
  to: string;
  toolName: string;
  toolSlug: string;
}

export async function sendToolApprovalEmail(
  params: ApprovalEmailParams,
  apiKey: string
): Promise<{ success: boolean; error?: string }> {
  return sendToolNotification({
    to: params.to,
    toolName: params.toolName,
    toolSlug: params.toolSlug,
    status: 'approved',
  }, apiKey);
}

export interface SubmissionConfirmParams {
  to: string;
  toolName: string;
  toolSlug: string;
}

export async function sendSubmissionConfirmation(
  params: SubmissionConfirmParams,
  apiKey: string
): Promise<{ success: boolean; error?: string }> {
  if (!apiKey) {
    return { success: false, error: 'BREVO_API_KEY not configured' };
  }
  if (!params.to || !params.to.includes('@')) {
    return { success: false, error: 'invalid recipient email' };
  }

  const template = submissionHtml(params);

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

export async function sendToolRejectionEmail(
  params: { to: string; toolName: string; reason?: string },
  apiKey: string
): Promise<{ success: boolean; error?: string }> {
  return sendToolNotification({
    to: params.to,
    toolName: params.toolName,
    toolSlug: params.toolName,
    status: 'rejected',
    reason: params.reason,
  }, apiKey);
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
  const toolUrl = `${BASE_URL}/tools/${slug}/`;

  return {
    subject: `[AIKorea24] ${name} 등록이 승인되었습니다 🎉`,
    html: `
<div style="font-family:system-ui,-apple-system,Arial,sans-serif;max-width:640px;margin:0 auto;padding:24px;color:#1f2937;">
  <div style="text-align:center;margin-bottom:24px;">
    <span style="display:inline-block;background:#0F172A;color:#fff;font-weight:700;font-size:16px;padding:6px 16px;border-radius:8px;">AIKorea24</span>
  </div>

  <h2 style="font-size:22px;margin:0 0 16px;text-align:center;">등록이 승인되었습니다 🎉</h2>
<p style="margin:0 0 8px;line-height:1.6;font-size:15px;">안녕하세요,</p>
<p style="margin:0 0 16px;line-height:1.6;font-size:15px;">
     <strong>${name}</strong>이(가) AIKorea24 AI 도구 디렉토리에 등록되었습니다!
   </p>

  <!-- 등록 페이지 링크 -->
  <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:12px;padding:16px;margin:0 0 24px;">
    <p style="margin:0;font-size:15px;font-weight:600;color:#1f2937;">🔗 등록 페이지: <a href="${toolUrl}" style="color:#3b82f6;text-decoration:none;">${toolUrl}</a></p>
  </div>

  <p style="margin:24px 0 4px;font-size:14px;">감사합니다,</p>
  <p style="margin:0 0 8px;font-size:14px;font-weight:700;">AIKorea24 팀</p>

  <hr style="margin:32px 0;border:none;border-top:1px solid #e5e7eb;">
  <p style="margin:0;font-size:12px;color:#9ca3af;text-align:center;">AIKorea24 · 이 메일은 도구 등록 승인 알림을 위해 발송되었습니다.</p>
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

export interface SubmissionConfirmParams {
  to: string;
  toolName: string;
  toolSlug: string;
}

function submissionHtml(params: SubmissionConfirmParams): { subject: string; html: string } {
  const name = escapeHtml(params.toolName);
  const slug = escapeHtml(params.toolSlug);
  const toolUrl = `${BASE_URL}/tools/${slug}/`;
  const badgeUrl = `${BASE_URL}/badges/featured-light.svg`;

  return {
    subject: `[AIKorea24] ${name} 등록이 완료되었습니다 ✅`,
    html: `
<div style="font-family:system-ui,-apple-system,Arial,sans-serif;max-width:640px;margin:0 auto;padding:24px;color:#1f2937;">
  <div style="text-align:center;margin-bottom:24px;">
    <span style="display:inline-block;background:#0F172A;color:#fff;font-weight:700;font-size:16px;padding:6px 16px;border-radius:8px;">AIKorea24</span>
  </div>

  <h2 style="font-size:22px;margin:0 0 16px;text-align:center;">등록이 완료되었습니다 ✅</h2>
  <p style="margin:0 0 8px;line-height:1.6;font-size:15px;">안녕하세요,</p>
  <p style="margin:0 0 16px;line-height:1.6;font-size:15px;">
    <strong>${name}</strong>이(가) AIKorea24 AI 도구 디렉토리에 등록되었습니다.
    관리자 검토 후 공개됩니다 (보통 24시간 이내).
  </p>

  <!-- 배찌 배지 -->
  <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:12px;padding:20px;margin:0 0 24px;text-align:center;">
    <img src="${badgeUrl}" alt="Featured on AIKorea24" style="max-width:200px;height:auto;margin-bottom:12px;" />
    <p style="margin:0;font-size:14px;font-weight:600;color:#0F172A;">AIKorea24는 신뢰의 상징입니다</p>
    <p style="margin:4px 0 0;font-size:13px;color:#64748B;">이 배지를 사이트에 달아주세요 — 벌써 많은 협력사들이 달았습니다</p>
  </div>

  <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:12px;padding:16px;margin:0 0 24px;">
    <p style="margin:0;font-size:15px;font-weight:600;color:#1f2937;">🔗 등록 페이지: <a href="${toolUrl}" style="color:#3b82f6;text-decoration:none;">${toolUrl}</a></p>
  </div>

  <p style="margin:24px 0 4px;font-size:14px;">감사합니다,</p>
  <p style="margin:0 0 8px;font-size:14px;font-weight:700;">AIKorea24 팀</p>

  <hr style="margin:32px 0;border:none;border-top:1px solid #e5e7eb;">
  <p style="margin:0;font-size:12px;color:#9ca3af;text-align:center;">AIKorea24 · 이 메일은 도구 등록 완료 알림을 위해 발송되었습니다.</p>
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