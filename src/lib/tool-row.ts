// AIK24-TOOLS-UX-01 — /tools/ 목록과 홈 '오늘의 도구'가 함께 쓰는 행(row) 유틸.
// 1차에서 index.astro 안에 있던 함수들을 그대로 옮겼다(동작 변경 없음).

export const TAGLINE_MAX = 60;

/** 조사· Connection 어미가 끝에 남으면 절단 자국처럼 보인다 — 단어 경계 컷 후 정리. */
const TRAILING_PARTICLE = /(?:은|는|이|가|을|를|와|과|의|에서|으로|로|도|만)$/;

export function deriveTagline(description?: string | null): string {
  let text = String(description ?? '').replace(/\s+/g, ' ').trim();
  if (!text) return '';
  // '[.!?] + 공백'만 문장 경계 → '2.0' 같은 소수점은 자르지 않는다.
  const firstSentence = text.match(/^[\s\S]*?[.!?](?=\s|$)/);
  if (firstSentence) text = firstSentence[0].trim();
  if (text.length > TAGLINE_MAX) {
    const head = text.slice(0, TAGLINE_MAX);
    const space = head.lastIndexOf(' ');
    text = (space > 20 ? head.slice(0, space) : head).trimEnd().replace(TRAILING_PARTICLE, '').trimEnd();
  }
  return text; // 말줄임(…) 붙이지 않음
}

export function faviconDomain(url?: string | null): string {
  const m = String(url ?? '').match(/^https?:\/\/([^/?#]+)/i);
  return m ? m[1].toLowerCase() : '';
}

/** 목록에서는 가격 한 단어 — priceModel 우선, 없으면 price 첫 토큰(필터용 data-price는 전문 유지). */
export function shortPrice(tool: any): string {
  const pm = String(tool?.data?.priceModel ?? tool?.priceModel ?? '').trim();
  const src = pm || String(tool?.data?.price ?? '').trim();
  return src.split(/\s+/)[0] || '—';
}

export function difficultyColor(d: string): string {
  if (d.includes('초보')) return 'bg-gray-100 text-[#111111] border-[#e5e5e5] dark:bg-[#333333]/15 dark:text-[#555555] dark:border-[#e5e5e5]/30';
  if (d.includes('중급')) return 'bg-gray-100 text-[#111111] border-[#e5e5e5] dark:bg-[#333333]/15 dark:text-[#555555] dark:border-[#e5e5e5]/30';
  return 'bg-gray-100 text-[#111111] border-[#e5e5e5] dark:bg-[#333333]/15 dark:text-[#555555] dark:border-[#e5e5e5]/30';
}

export function difficultyLabel(d: string): string {
  if (d.includes('초보')) return '초보자 OK';
  if (d.includes('중급')) return '중급';
  return '고급';
}

const KST_OFFSET_MS = 9 * 60 * 60 * 1000;
const DAY_MS = 24 * 60 * 60 * 1000;

/** 최근 7일 내 등록·갱신 (KST 기준, 지시서의 NEW 배지 규칙 그대로). */
export function isNewTool(t: any): boolean {
  const u = String(t?.data?.updated ?? t?.updated ?? '').slice(0, 10);
  if (!u) return false;
  const nowKst = Date.now() + KST_OFFSET_MS;
  const todayKst = new Date(nowKst).toISOString().slice(0, 10);
  const cutoffKst = new Date(nowKst - 7 * DAY_MS).toISOString().slice(0, 10);
  return u >= cutoffKst && u <= todayKst;
}
