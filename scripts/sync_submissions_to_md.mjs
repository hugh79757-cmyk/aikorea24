#!/usr/bin/env node
// 승인된 tool_submissions(published) → src/content/tools/<slug>.md 생성/갱신
// 목적: tools 페이지를 prerender(정적)로 전환하기 위한 빌드타임 소스 동기화.
//   - 슬러그/URL 불변 (route /tools/<slug>/ 그대로 → 색인 URL 유지)
//   - AIK24-TOOLSYNC-01: **D1 이 정본, md 는 빌드용 캐시다.**
//     D1 updated_at 이 md 파일 mtime 보다 최신이면 md 를 재생성한다.
//     이전 규칙("md 있으면 무조건 스킵")은 편집 화면 저장을 조용히 삼켰다.
//     수동 md 편집은 D1 로 역반영되지 않는 **일방향**이다.
//     재생성 시 md 전용 필드(image)는 기존 md 에서 물려받는다.
// 사용: node scripts/sync_submissions_to_md.mjs [--dry]
//       (deploy.sh에서 빌드 전 1회 호출)

import { execFileSync } from 'node:child_process';
import { writeFileSync, readFileSync, existsSync, mkdirSync, statSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');
const TOOLS_DIR = join(ROOT, 'src/content/tools');
const DRY = process.argv.includes('--dry');

const WRANGLER = '/opt/homebrew/bin/wrangler';
const wrangler = existsSync(WRANGLER) ? WRANGLER : 'wrangler';

function querySubmissions() {
  const sql = `SELECT slug, name, url, category, description, price_model, price_detail,
    korean_support, difficulty, use_cases, tags, tasks, detail_markdown, created_at, updated_at
    FROM tool_submissions WHERE status='published' ORDER BY created_at DESC;`;
  // 2026-10-09 CF-MIGRATE-02: OAuth 프로필은 출발 계정 → env 토큰 사용
  const env = { ...process.env };
  const out = execFileSync(
    wrangler,
    ['d1', 'execute', 'aikorea24-db', '--remote', `--command=${sql}`, '--json'],
    { encoding: 'utf8', maxBuffer: 32 * 1024 * 1024, stdio: ['ignore', 'pipe', 'pipe'], env }
  );
  const json = JSON.parse(out);
  const rows = json[0]?.results ?? [];
  return rows;
}

const yamlStr = (s) => JSON.stringify(String(s ?? '')); // 안전한 quoted scalar
const parseArr = (v) => {
  if (!v) return [];
  if (Array.isArray(v)) return v.map(String);
  try {
    const a = JSON.parse(String(v));
    return Array.isArray(a) ? a.map(String) : [];
  } catch {
    return String(v).split(',').map((s) => s.trim()).filter(Boolean);
  }
};

// AIK24-TOOLSYNC-01: 기존 md frontmatter 에서 스칼라 필드 1개만 꺼낸다(수동 편집 보존용).
const readField = (md, key) => {
  const m = new RegExp(`^${key}:\\s*(.+)$`, 'm').exec(md.split(/^---$/m)[1] ?? '');
  if (!m) return null;
  const v = m[1].trim();
  return v && v !== 'null' ? v : null;
};

function priceModelEnum(pm) {
  const m = String(pm ?? '').trim();
  if (m === '무료' || m === 'Freemium') return m;
  if (/구독/i.test(m)) return '구독';
  if (/일회성|평생/i.test(m)) return '일회성';
  if (/유료|paid/i.test(m)) return '유료';
  return null; // 미묘한 값은 생략 (schema enum 충돌 방지)
}

function buildMd(row, preservedImage = null) {
  const price = String(row.price_detail ?? '').trim() || String(row.price_model ?? '').trim() || '—';
  const useCases = parseArr(row.use_cases);
  const tags = parseArr(row.tags);
  const tasks = parseArr(row.tasks);
  const pm = priceModelEnum(row.price_model);
  const lines = [
    '---',
    `name: ${yamlStr(row.name)}`,
    `description: ${yamlStr(row.description ?? '')}`,
    `category: ${yamlStr(row.category ?? '기타')}`,
    `price: ${yamlStr(price)}`,
    `koreanSupport: ${Number(row.korean_support) === 1 ? 'true' : 'false'}`,
    `difficulty: ${yamlStr(String(row.difficulty ?? '').trim() || '중급')}`,
    `url: ${yamlStr(String(row.url ?? '').trim())}`,
    `useCases: [${useCases.map(yamlStr).join(', ')}]`,
    `tags: [${tags.map(yamlStr).join(', ')}]`,
    `tasks: [${tasks.map(yamlStr).join(', ')}]`,
    // 승인 건은 목록 상단 유지 (기존 d1Tools 우선 정렬과 동일 효과)
    'order: -1',
    `featured: false`,
    `updated: ${yamlStr(String(row.updated_at ?? row.created_at ?? '').slice(0, 10))}`,
    ...(pm ? [`priceModel: ${yamlStr(pm)}`] : []),
    // AIK24-TOOLSYNC-01: screenshot_url 이 NULL 인데 md 에만 썸네일이 있으면 재생성 시 유실된다.
    // D1 값 우선, 없으면 기존 md 에서 물려받은 값을 쓴다.
    ...(row.screenshot_url
      ? [`image: ${yamlStr(row.screenshot_url)}`]
      : preservedImage ? [`image: ${preservedImage}`] : []),
    '---',
    '',
    String(row.detail_markdown ?? row.description ?? '').trim(),
    '',
  ];
  return lines.join('\n');
}

function main() {
  const rows = querySubmissions();
  let created = 0, skipped = 0;
  mkdirSync(TOOLS_DIR, { recursive: true });
  for (const row of rows) {
    const slug = String(row.slug ?? '').trim();
    if (!slug || !/^[a-z0-9-]+$/.test(slug)) {
      console.error(`  [skip] 잘못된 slug: ${JSON.stringify(slug)}`);
      skipped++;
      continue;
    }
    const path = join(TOOLS_DIR, `${slug}.md`);
    // AIK24-TOOLSYNC-01: D1 이 정본, md 는 빌드용 캐시다.
    // D1 updated_at 이 md 파일 mtime 보다 최신이면(= 소유자가 편집 화면에서 저장한 뒤) md 를 재생성한다.
    // 이전에는 "md 있으면 무조건 스킵" 이어서 편집 화면 저장이 조용히 삼켜졌다.
    if (existsSync(path)) {
      const mdMtime = statSync(path).mtimeMs;
      const d1 = Date.parse(String(row.updated_at ?? '').replace(' ', 'T') + 'Z');
      const fresh = Number.isFinite(d1) && d1 > mdMtime;
      if (!fresh) {
        skipped++;
        continue;
      }
      if (DRY) {
        console.log(`  [dry] 재생성 예정(D1 최신): ${slug}.md`);
        created++;
        continue;
      }
      // 재생성으로 날아가면 안 되는 수동 편집 필드(image 등)는 기존 md 에서 물려받는다.
      const prev = readFileSync(path, 'utf8');
      const preserved = readField(prev, 'image');
      const md = buildMd(row, preserved);
      writeFileSync(path, md, 'utf8');
      console.log(`  [update] ${slug}.md (D1 updated_at > md mtime${preserved ? `, image 보존: ${preserved}` : ''})`);
      created++;
      continue;
    }
    if (DRY) {
      console.log(`  [dry] 생성 예정: ${slug}.md`);
      created++;
      continue;
    }
    writeFileSync(path, buildMd(row), 'utf8');
    console.log(`  [create] ${slug}.md`);
    created++;
  }
  console.log(`[sync_submissions_to_md] published=${rows.length} created=${created} skipped(existing/invalid)=${skipped}${DRY ? ' (dry-run)' : ''}`);
}

main();
