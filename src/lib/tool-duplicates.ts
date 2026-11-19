/**
 * AIK24-TOOLDUP-NOTICE-01 — 도구 중복 판정기 (admin 검토 큐 노티스용)
 *
 * 목적: 새 제출(pending)이 이미 목록에 있는 도구와 같은 제품인지 화면에서 미리 알려준다.
 * 원칙: 근거가 명확한 것만 'exact', 이름 변형이 의심되는 것만 'likely'. 그 외는 침묵.
 *
 * 판정 규칙 (위에서부터 먼저 맞는 것 하나)
 *  exact
 *    1) 슬러그 동일                       — 같은 URL(/tools/<slug>/)을 덮어쓴다
 *    2) 정규화 이름 동일                  — 공백·기호·대소문자·전각만 다름
 *    3) 접미(AI·App·Pro·Tool 등) 제거 후 이름 동일
 *    4) 도메인 동일 (수집원·플랫폼 도메인 제외)
 *  likely
 *    5) 이름 포함 관계 + 남는 말이 변형어(OSS·Plus·Beta·V2 …)
 *    6) 이름 토큰 Jaccard ≥ 0.8
 *  침묵(일부러 플래그하지 않음)
 *    - 브랜드 단어가 이름 안에 단순 포함된 경우 (예: "Claude" ⊂ "Claude Duet")
 *    - "ChatGPT Work" / "Copilot Fusion" / "Sonnet 5.5" 처럼 별개 제품·버전인 변형
 *      → 접미/변형어·도메인 규칙으로만 잡고, 접두 포함만으로는 잡지 않는다
 *    - 이름이 숫자만 다른 경우(버전 차이)는 규칙 평가 전에 침묵한다
 *    - topai.tools, theresanaiforthat.com 같은 디렉터리 도메인
 */
export type DupLevel = 'exact' | 'likely';

export type ToolEntry = { slug: string; name: string; url?: string | null };
export type IndexEntry = ToolEntry & { source: 'md' | 'submission' };
export type DupHit = {
  level: DupLevel;
  reason: string;
  slug: string;
  name: string;
  url: string;
  source: 'md' | 'submission';
};

/** 같은 도메인이라도 제품 식별에 쓸 수 없는 수집원·플랫폼 도메인 */
export const IGNORED_DOMAINS = new Set([
  'topai.tools',
  'theresanaiforthat.com',
  'futurepedia.io',
  'toolify.ai',
  'aitoolsdirectory.com',
  'toolsforcreators.com',
  'producthunt.com',
  'huggingface.co',
  'github.com',
  'youtube.com',
  'youtu.be',
  'x.com',
  'twitter.com',
  'medium.com',
  'apps.apple.com',
  'play.google.com',
  'openai.com',
  'chatgpt.com',
  'anthropic.com',
  'claude.ai',
  'claude.com',
  'gemini.google.com',
  'google.com',
  'blog.google',
  'x.ai',
  'microsoft.com',
  'notion.so',
]);

/** 이름 끝에 붙는 일반 접미 — 떼고 비교한다 */
const NAME_SUFFIXES = [
  'app', 'application', 'tool', 'tools', 'ai', 'io', 'com', 'hq', 'kr', 'pro', 'plus', 'beta',
  'preview', 'labs', 'inc', 'dev', 'web', 'online', 'site',
];

/** 같은 제품의 다른 배포판·요금제를 가리키는 말 — 이름 포함 관계에서만 사용 */
const VARIANT_WORDS = new Set([
  'oss', 'open', 'source', 'opensource', 'free', 'lite', 'mini', 'nano', 'pro', 'plus', 'max',
  'beta', 'alpha', 'preview', 'app', 'cli', 'api', 'sdk', 'plugin', 'extension', 'addon',
]);
// 버전 표기(v2, 5.5 등)는 별개 제품으로 취급한다 — Sonnet 5 / Sonnet 5.5 를 중복으로 잡으면
// 관리자가 노티스를 무시하게 된다. 그래서 VARIANT_WORDS 에 숫자·vN 을 넣지 않는다.

export function normalizeToolName(name: string | null | undefined): string {
  return String(name ?? '')
    .normalize('NFKC')
    .toLowerCase()
    .replace(/[^0-9a-z\uac00-\ud7a3]+/g, '');
}

export function stripNameSuffix(normalized: string): string {
  let s = normalized;
  let guard = 0;
  while (guard++ < 4) {
    const hit = NAME_SUFFIXES.find((sfx) => s.length > sfx.length + 2 && s.endsWith(sfx));
    if (!hit) break;
    s = s.slice(0, -hit.length);
  }
  return s;
}

export function toolDomain(url: string | null | undefined): string {
  const raw = String(url ?? '').trim().toLowerCase();
  if (!raw) return '';
  let host = raw.replace(/^[a-z]+:\/\//, '').replace(/^www\./, '');
  host = host.split('/')[0].split('?')[0].split('#')[0].split(':')[0];
  if (!host.includes('.')) return '';
  return host;
}

export function nameTokens(name: string | null | undefined): string[] {
  return String(name ?? '')
    .normalize('NFKC')
    .toLowerCase()
    .split(/[^0-9a-z\uac00-\ud7a3]+/)
    .filter((t) => t.length >= 2);
}

function jaccard(a: string[], b: string[]): number {
  if (!a.length || !b.length) return 0;
  const A = new Set(a);
  const B = new Set(b);
  let inter = 0;
  for (const t of A) if (B.has(t)) inter += 1;
  return inter / (A.size + B.size - inter);
}

/** 이름 포함 관계일 때 남는 말이 "같은 제품의 다른 배포판/요금제"인지 */
function isVariantRemainder(longer: string, shorter: string): boolean {
  if (!longer.startsWith(shorter) && !longer.endsWith(shorter)) return false;
  const rest = longer.startsWith(shorter) ? longer.slice(shorter.length) : longer.slice(0, -shorter.length);
  if (!rest) return true;
  return VARIANT_WORDS.has(rest);
}

/**
 * 후보 1건을 인덱스 전체와 비교한다.
 * @param opts.excludeSameSlug 같은 슬러그 = 같은 레코드(md 캐시 ↔ D1 정본). 이미 발행된 항목을 자기 자신과 비교하지 않을 때 true.
 * @param opts.minTokenScore 6번 규칙 임계값(기본 0.8)
 */
export function findDuplicates(
  candidate: ToolEntry,
  index: IndexEntry[],
  opts: { excludeSameSlug?: boolean; minTokenScore?: number } = {}
): DupHit[] {
  const minTokenScore = opts.minTokenScore ?? 0.8;
  const candName = normalizeToolName(candidate.name);
  const candStripped = stripNameSuffix(candName);
  const candDomain = toolDomain(candidate.url);
  const candTokens = nameTokens(candidate.name);
  const hits: DupHit[] = [];

  for (const entry of index) {
    const entryName = normalizeToolName(entry.name);
    const entryDomain = toolDomain(entry.url);
    const sameSlug = entry.slug === candidate.slug;

    if (sameSlug && opts.excludeSameSlug) continue;

    let level: DupLevel | null = null;
    let reason = '';

    if (sameSlug) {
      level = 'exact';
      reason = '슬러그가 동일';
    } else if (candName && entryName && candName === entryName) {
      level = 'exact';
      reason = '이름이 동일';
    } else if (
      candName && entryName
      && candName.replace(/\d+/g, '') === entryName.replace(/\d+/g, '')
    ) {
      // 숫자만 다른 이름 = 버전 차이(Sonnet 5 / 5.5, Copilot 2 / 3). 별개 제품이므로 침묵한다.
      continue;
    } else if (
      candStripped && entryName && candStripped === stripNameSuffix(entryName)
      && candStripped.length >= 4
    ) {
      level = 'exact';
      reason = '접미(AI·App 등)만 다른 동일 이름';
    } else if (
      candDomain && entryDomain && candDomain === entryDomain
      && !IGNORED_DOMAINS.has(candDomain)
      && candDomain.split('.')[0].length >= 3
    ) {
      level = 'exact';
      reason = '도메인이 동일';
    } else if (candStripped && stripNameSuffix(entryName)) {
      const other = stripNameSuffix(entryName);
      const short = candStripped.length <= other.length ? candStripped : other;
      const long = short === candStripped ? other : candStripped;
      if (short.length >= 5 && isVariantRemainder(long, short)) {
        level = 'likely';
        reason = '이름 포함 관계(변형어만 다름)';
      }
    }

    if (!level && candTokens.length >= 2) {
      const score = jaccard(candTokens, nameTokens(entry.name));
      if (score >= minTokenScore) {
        level = 'likely';
        reason = `이름 토큰 유사도 ${Math.round(score * 100)}%`;
      }
    }

    if (level) {
      hits.push({
        level,
        reason,
        slug: entry.slug,
        name: entry.name,
        url: String(entry.url ?? ''),
        source: entry.source,
      });
    }
  }

  const rank = { exact: 0, likely: 1 } as const;
  hits.sort((a, b) => rank[a.level] - rank[b.level] || a.slug.localeCompare(b.slug));
  return hits;
}

/** 같은 슬러그가 md 와 submission 양쪽에 있으면 md 쪽만 남긴다(같은 레코드의 캐시) */
export function dedupeIndex(entries: IndexEntry[]): IndexEntry[] {
  const bySlug = new Map<string, IndexEntry>();
  for (const e of entries) {
    const prev = bySlug.get(e.slug);
    if (!prev || (prev.source === 'submission' && e.source === 'md')) bySlug.set(e.slug, e);
  }
  return [...bySlug.values()];
}
