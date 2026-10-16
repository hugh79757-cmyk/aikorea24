// src/lib/redirect.ts — 로그인 후 리다이렉트 대상 URL 안전성 검증 (⑩ EmDash return URL).
// 반환 값은 redirect() 에 그대로 넘길 수 있는 "안전한 URL" (상대 경로 또는 허용된 절대 URL).
// 허용하지 않은 값은 빈 문자열로 떨어뜨려 로그인 후 홈(/) 으로 돌아오게 한다 (개방 리다이렉트 방지).

export const ALLOWED_RETURN_HOSTS = new Set<string>([
  'aikorea24.kr',
  'www.aikorea24.kr',
  'emdash.aikorea24.kr',
]);

export function sanitizeReturnTo(raw: unknown): string {
  if (typeof raw !== 'string') return '';
  const v = raw.trim();
  if (!v) return '';

  // 1. 같은 사이트 상대 경로 (기존 동작, "/" 로 시작하지만 "//" 뒤 무시)
  if (v.startsWith('/') && !v.startsWith('//') && !v.includes('\\')) {
    // 개행·태그·제어 문자가 섞인 경로는 악의적인 redirect로 간주한다.
    if (/[\r\n<>]/.test(v)) return '';
    return v;
  }

  // 2. 허용된 호스트의 절대 URL (예: EmDash 블로그 페이지로부터 로그인 시 복귀)
  try {
    const u = new URL(v);
    if (u.protocol !== 'https:' && u.protocol !== 'http:') return '';
    // http: 는 로컬 개발(http://localhost) 에서만 허용
    if (u.protocol === 'http:') {
      if (u.hostname !== 'localhost' && u.hostname !== '127.0.0.1') return '';
    } else {
      if (!ALLOWED_RETURN_HOSTS.has(u.hostname)) return '';
    }
    // fragment(hash) 는 OAuth state 를 경유할 수 없으므로 버린다.
    return `${u.protocol}//${u.host}${u.pathname}${u.search}`;
  } catch {
    return '';
  }
}

export function isSafeReturnTo(raw: unknown): boolean {
  return sanitizeReturnTo(raw) !== '';
}
