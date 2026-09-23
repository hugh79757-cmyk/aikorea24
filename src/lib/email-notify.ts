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
  const badgeDark = `${BASE_URL}/badges/featured-dark.svg`;
  const badgeLight = `${BASE_URL}/badges/featured-light.svg`;

  return {
    subject: `[AI코리아24] ${name} 등록이 승인되었습니다 🎉`,
    html: `
<div style="font-family:system-ui,-apple-system,Arial,sans-serif;max-width:640px;margin:0 auto;padding:24px;color:#1f2937;">
  <div style="text-align:center;margin-bottom:24px;">
    <span style="display:inline-block;background:linear-gradient(135deg,#1E3A5F,#0B1120);color:#fff;font-weight:700;font-size:16px;padding:6px 16px;border-radius:8px;">AI코리아24</span>
  </div>

  <h2 style="font-size:22px;margin:0 0 16px;text-align:center;">등록이 승인되었습니다 🎉</h2>
  <p style="margin:0 0 16px;line-height:1.6;font-size:15px;">
    등록하신 <strong>${name}</strong>이(가) 검토를 통과하여 디렉토리에 공개되었습니다.
  </p>

  <!-- 등록 페이지 링크 -->
  <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:12px;padding:16px;margin:0 0 24px;">
    <p style="margin:0 0 8px;font-size:13px;font-weight:600;color:#475569;">📍 등록 페이지</p>
    <a href="${toolUrl}" style="color:#3b82f6;text-decoration:none;font-size:15px;font-weight:600;">${toolUrl}</a>
  </div>

  <!-- 현재 링크 상태 -->
  <div style="background:#fefce8;border:1px solid #fde68a;border-radius:12px;padding:16px;margin:0 0 24px;">
    <p style="margin:0 0 8px;font-size:13px;font-weight:600;color:#92400e;">ℹ️ 현재 링크 상태</p>
    <p style="margin:0;font-size:14px;color:#78350f;line-height:1.6;">
      현재 귀사 사이트 링크는 <strong>nofollow</strong>로 설정되어 있습니다.
    </p>
  </div>

  <!-- dofollow 전환 안내 -->
  <div style="background:linear-gradient(135deg,#1E3A5F,#0B1120);border-radius:16px;padding:24px;margin:0 0 24px;color:#fff;">
    <h3 style="font-size:16px;margin:0 0 12px;">🔗 dofollow 링크로 전환하세요</h3>
    <p style="margin:0 0 16px;font-size:14px;line-height:1.6;opacity:0.9;">
      아래 배지를 귀사 사이트에 설치하시면 <strong>dofollow</strong> 링크로 전환해 드립니다.
      dofollow 링크는 검색엔진 최적화(SEO)에 도움이 됩니다.
    </p>

    <!-- 배지 미리보기 -->
    <div style="background:#fff;border-radius:12px;padding:16px;margin:0 0 16px;text-align:center;">
      <p style="margin:0 0 12px;font-size:12px;color:#64748B;">배지 미리보기 (어두운 배경)</p>
      <img src="${badgeDark}" alt="Featured on AI코리아24" height="48" style="display:inline-block;">
      <p style="margin:12px 0 0;font-size:12px;color:#64748B;">배지 미리보기 (밝은 배경)</p>
      <img src="${badgeLight}" alt="Featured on AI코리아24" height="48" style="display:inline-block;margin-top:8px;">
    </div>

    <p style="margin:0 0 12px;font-size:13px;font-weight:600;opacity:0.8;">📌 권장 설치 위치</p>
    <ul style="margin:0 0 16px;padding-left:20px;font-size:13px;opacity:0.9;line-height:1.8;">
      <li> 사이트 푸터</li>
      <li> 홈페이지 하단</li>
      <li> 회사 소개 페이지</li>
    </ul>

    <details style="margin:0 0 16px;">
      <summary style="cursor:pointer;font-size:13px;font-weight:600;opacity:0.8;">HTML 설치 코드 보기</summary>
      <pre style="background:rgba(0,0,0,0.3);border-radius:8px;padding:12px;margin:8px 0 0;font-size:12px;overflow-x:auto;white-space:pre-wrap;"><code>&lt;a href="${toolUrl}" rel="dofollow"&gt;
  &lt;img src="${badgeDark}" alt="Featured on AI코리아24" height="48"&gt;
&lt;/a&gt;</code></pre>
    </details>

    <p style="margin:0;font-size:13px;opacity:0.85;line-height:1.6;">
      설치 완료 후 <strong>info@aikorea24.kr</strong>로 알려주시면 확인 후 dofollow로 전환해 드립니다.
    </p>
  </div>

  <div style="text-align:center;margin-top:24px;">
    <a href="${toolUrl}" style="display:inline-block;background:#3b82f6;color:#fff;padding:12px 28px;border-radius:8px;text-decoration:none;font-weight:600;font-size:14px;">
      등록 페이지 보기 →
    </a>
  </div>

  <hr style="margin:32px 0;border:none;border-top:1px solid #e5e7eb;">
  <p style="margin:0;font-size:12px;color:#9ca3af;text-align:center;">AI코리아24 · 이 메일은 도구 등록 승인 알림을 위해 발송되었습니다.</p>
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