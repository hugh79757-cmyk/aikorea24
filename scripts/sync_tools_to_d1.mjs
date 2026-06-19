/**
 * sync_tools_to_d1.mjs
 * src/content/tools/*.md → D1 tools 테이블 INSERT SQL 생성
 * 
 * 사용법:
 *   node scripts/sync_tools_to_d1.mjs > /tmp/insert_tools.sql
 *   npx wrangler d1 execute aikorea24-db --remote --file=/tmp/insert_tools.sql
 */

import { readFileSync, readdirSync, existsSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const TOOLS_DIR = join(__dirname, '..', 'src', 'content', 'tools');

// Gray-matter 스타일 frontmatter 파서
function parseFrontmatter(content) {
  const match = content.match(/^---\n([\s\S]*?)\n---\n/);
  if (!match) return {};
  
  const yaml = match[1];
  const fm = {};
  
  for (const line of yaml.split('\n')) {
    const kv = line.match(/^(\w+):\s*(.*)$/);
    if (!kv) continue;
    
    let key = kv[1];
    let val = kv[2].trim();
    
    // 불리언 처리
    if (val === 'true') val = true;
    else if (val === 'false') val = false;
    // 배열 처리 - useCases, tags, tasks 등은 무시 (D1에 없음)
    else if (val.startsWith('[') || val.startsWith('- ')) continue;
    // 인용부호 제거
    else val = val.replace(/^["']|["']$/g, '');
    
    fm[key] = val;
  }
  
  return fm;
}

function escapeSql(val) {
  if (val === null || val === undefined) return 'NULL';
  return "'" + String(val).replace(/'/g, "''") + "'";
}

const files = readdirSync(TOOLS_DIR).filter(f => f.endsWith('.md'));

let insertCount = 0;
const inserts = [];

for (const file of files) {
  const slug = file.replace(/\.md$/, '').toLowerCase();
  const content = readFileSync(join(TOOLS_DIR, file), 'utf-8');
  const fm = parseFrontmatter(content);
  
  if (!fm.name) {
    console.error(`-- SKIP: ${file} - no name in frontmatter`);
    continue;
  }
  
  const name = fm.name;
  const tagline = fm.description || '';
  const category = fm.category || '';
  const price = fm.price || '';
  const koreanSupport = fm.koreanSupport === true ? 1 : 0;
  const difficulty = fm.difficulty || '';
  const url = fm.url || '';
  const featured = fm.featured === true ? 1 : 0;
  
  inserts.push(
    `INSERT OR REPLACE INTO tools (name, slug, tagline, category, price, korean_support, difficulty, url, featured) VALUES (${escapeSql(name)}, ${escapeSql(slug)}, ${escapeSql(tagline)}, ${escapeSql(category)}, ${escapeSql(price)}, ${koreanSupport}, ${escapeSql(difficulty)}, ${escapeSql(url)}, ${featured});`
  );
  insertCount++;
}

// 트랜잭션으로 묶기
console.log('BEGIN TRANSACTION;');
console.log('');
for (const sql of inserts) {
  console.log(sql);
}
console.log('');
console.log('COMMIT;');

console.error(`-- ✅ 총 ${insertCount}개 도구 INSERT SQL 생성 완료`);
