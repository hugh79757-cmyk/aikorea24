/**
 * Course Lesson Email Template
 * Brevo-compatible HTML with inline styles.
 */

export interface LessonEmailData {
  courseTitle: string;
  dayNumber: number;
  totalDays: number;
  lessonTitle: string;
  teaserHtml: string;
  communityPostUrl: string;
  trackingUrl: string; // pre-wrapped with /api/courses/track
  unsubscribeUrl: string;
}

function esc(s: string): string {
  return s
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

export function buildLessonEmailHtml(data: LessonEmailData): string {
  const { courseTitle, dayNumber, totalDays, lessonTitle, teaserHtml, trackingUrl, unsubscribeUrl } = data;
  const progress = Math.round((dayNumber / totalDays) * 100);

  return `
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>${esc(lessonTitle)}</title>
</head>
<body style="margin:0;padding:0;background-color:#f4f4f5;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color:#f4f4f5;">
    <tr>
      <td align="center" style="padding:24px 16px;">
        <table role="presentation" width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;">
          <!-- Header -->
          <tr>
            <td style="background:linear-gradient(135deg,#059669,#10b981);padding:32px 24px;border-radius:12px 12px 0 0;text-align:center;">
              <h1 style="margin:0;font-size:20px;font-weight:700;color:#ffffff;letter-spacing:-0.3px;">${esc(courseTitle)}</h1>
              <p style="margin:8px 0 0;font-size:14px;color:#d1fae5;">
                ${dayNumber}일차 / 총 ${totalDays}일
              </p>
            </td>
          </tr>

          <!-- Progress bar -->
          <tr>
            <td style="background-color:#ffffff;padding:0 24px;">
              <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
                <tr>
                  <td style="padding:16px 0 4px;">
                    <div style="background-color:#e5e7eb;border-radius:4px;height:6px;overflow:hidden;">
                      <div style="background:linear-gradient(90deg,#059669,#34d399);width:${progress}%;height:6px;border-radius:4px;"></div>
                    </div>
                  </td>
                </tr>
                <tr>
                  <td style="text-align:right;padding:4px 0 0;font-size:11px;color:#9ca3af;">
                    진행률 ${progress}%
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- Body -->
          <tr>
            <td style="background-color:#ffffff;padding:8px 24px 24px;">
              <h2 style="margin:0 0 16px;font-size:18px;font-weight:600;color:#111827;line-height:1.4;">
                ${esc(lessonTitle)}
              </h2>
              <div style="font-size:15px;line-height:1.7;color:#374151;">
                ${teaserHtml}
              </div>
            </td>
          </tr>

          <!-- CTA Button -->
          <tr>
            <td style="background-color:#ffffff;padding:0 24px 32px;text-align:center;">
              <a href="${esc(trackingUrl)}"
                 style="display:inline-block;background-color:#059669;color:#ffffff;text-decoration:none;
                        font-size:15px;font-weight:600;padding:14px 32px;border-radius:8px;
                        box-shadow:0 1px 3px rgba(0,0,0,0.1);">
                전체 내용 보기 →
              </a>
              <p style="margin:8px 0 0;font-size:12px;color:#9ca3af;">
                커뮤니티에서 전체 강의 내용을 확인하세요
              </p>
            </td>
          </tr>

          <!-- Footer -->
          <tr>
            <td style="background-color:#f9fafb;padding:24px;border-radius:0 0 12px 12px;text-align:center;">
              <p style="margin:0;font-size:12px;color:#9ca3af;line-height:1.6;">
                AI코리아24 · 7일 AI 입문 강좌<br>
                질문이 있다면 커뮤니티에 남겨주세요
              </p>
              <p style="margin:12px 0 0;font-size:11px;color:#d1d5db;">
                <a href="${esc(unsubscribeUrl)}" style="color:#9ca3af;text-decoration:underline;">수신 거부</a>
              </p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>`.trim();
}
