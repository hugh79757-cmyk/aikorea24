#!/usr/bin/env node
// 승인된 tool_submissions(published) → src/content/tools/<slug>.md 생성
// 목적: tools 페이지를 prerender(정적)로 전환하기 위한 빌드타임 소스 동기화.
//   - 슬러그/URL 불변 (route /tools/<slug>/ 그대로 → 색인 URL 유지)
//   - md가 이미 있으면 건드리지 않음 (수동 편집 우선)
// 사용: node scripts/sync_submissions_to_md.mjs [--dry]
//       (deploy.sh에서 빌드 전 1회 호출)

import { execFileSync } from 'node:child_process';
import { writeFileSync, existsSync, mkdirSync } from 'node:fs';
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
  // CLOUDFLARE_API_TOKEN은 D1 권한이 없는 스코프(7403) → OAuth 프로필 사용
  const env = { ...process.env };
  delete env.CLOUDFLARE_API_TOKEN;
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

function priceModelEnum(pm) {
  const m = String(pm ?? '').trim();
  if (m === '무료' || m === 'Freemium') return m;
  if (/구독/i.test(m)) return '구독';
  if (/일회성|평생/i.test(m)) return '일회성';
  if (/유료|paid/i.test(m)) return '유료';
  return null; // 미묘한 값은 생략 (schema enum 충돌 방지)
}

function buildMd(row) {
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
    if (existsSync(path)) {
      skipped++;
      continue; // 기존 md(수동 편집 포함) 우선 — 덮어쓰지 않음
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
