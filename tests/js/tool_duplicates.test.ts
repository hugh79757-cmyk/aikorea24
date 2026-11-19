/**
 * AIK24-TOOLDUP-NOTICE-01 — 중복 판정기 회귀 테스트
 * 실행: node --test tests/js/
 *
 * 케이스 구성
 *  - 실제로 중복이었던 5쌍(2026-11-19 AIK24-TOOLDEDUP-01 에서 삭제한 것) → 반드시 잡아야 한다
 *  - 별개 제품/버전(ChatGPT Work, Copilot Fusion, Sonnet 5.5, Mermaid Flow, Kai Resolve) → 잡으면 안 된다
 */
import test from 'node:test';
import assert from 'node:assert/strict';
import { findDuplicates, dedupeIndex, normalizeToolName, stripNameSuffix, toolDomain, describeApproveWarning } from '../../src/lib/tool-duplicates.ts';
import type { IndexEntry } from '../../src/lib/tool-duplicates.ts';

const md = (slug: string, name: string, url = ''): IndexEntry => ({ slug, name, url, source: 'md' });
const sub = (slug: string, name: string, url = ''): IndexEntry => ({ slug, name, url, source: 'submission' });

const levels = (hits: { level: string }[]) => hits.map((h) => h.level);

test('정규화: 표기 차이는 같은 이름으로 모인다', () => {
  assert.equal(normalizeToolName('Chat PDF GPT'), 'chatpdfgpt');
  assert.equal(normalizeToolName('ChatPDFGPT'), 'chatpdfgpt');
  assert.equal(normalizeToolName('oMLX'), 'omlx');
  assert.equal(stripNameSuffix('freebeataiapp'), 'freebeat');
  assert.equal(stripNameSuffix('freebeatai'), 'freebeat');
  assert.equal(stripNameSuffix('omlxai'), 'omlx');
  assert.equal(stripNameSuffix('kai'), 'kai'); // 3글자는 접미 제거 대상이 아니다
  assert.equal(toolDomain('https://www.edgee.ai/claude-mod'), 'edgee.ai');
  assert.equal(toolDomain('topai.tools#'), 'topai.tools');
  assert.equal(toolDomain('로컬 경로'), '');
});

test('실제 중복 5쌍 — ① oMLX: 접미만 다른 동일 이름', () => {
  const hits = findDuplicates({ slug: 'omlx-ai', name: 'Omlx AI', url: 'https://topai.tools/t/omlx-ai' }, [
    md('omlx', 'oMLX', 'https://omlx.ai'),
  ]);
  assert.deepEqual(levels(hits), ['exact']);
  assert.equal(hits[0].reason, '접미(AI·App 등)만 다른 동일 이름');
  assert.equal(hits[0].slug, 'omlx');
});

test('실제 중복 5쌍 — ② freebeat: App/AI 접미 변형', () => {
  const hits = findDuplicates({ slug: 'freebeat-ai', name: 'freebeat AI', url: 'https://topai.tools#' }, [
    md('freebeat-ai-app', 'Freebeat.ai App', 'https://topai.tools/t/freebeat-ai-app'),
  ]);
  assert.deepEqual(levels(hits), ['exact']);
});

test('실제 중복 5쌍 — ③ Edgee: 도메인 동일', () => {
  const hits = findDuplicates(
    { slug: 'edgee-claude-code-compressor-v2', name: 'Edgee Claude Code Compressor V2', url: 'https://www.edgee.ai' },
    [md('edgee-mod-for-claude-code', 'Edgee Mod for Claude Code', 'https://www.edgee.ai/claude-mod')]
  );
  assert.deepEqual(levels(hits), ['exact']);
  assert.equal(hits[0].reason, '도메인이 동일');
});

test('실제 중복 5쌍 — ④ Make0 Brain: 변형어(OSS)만 다른 포함 관계', () => {
  const hits = findDuplicates({ slug: 'make0-brain-oss', name: 'Make0 Brain OSS', url: '' }, [
    md('make0-brain', 'Make0 Brain', 'https://make0.ai/'),
  ]);
  assert.deepEqual(levels(hits), ['likely']);
  assert.equal(hits[0].reason, '이름 포함 관계(변형어만 다름)');
});

test('실제 중복 5쌍 — ⑤ 슬러그 충돌은 즉시 exact (같은 URL 을 덮어쓴다)', () => {
  const hits = findDuplicates({ slug: 'claude-code', name: 'Claude Code', url: 'https://docs.anthropic.com/x' }, [
    md('claude-code', 'Claude Code (커뮤니티판)', 'https://github.com/x'),
  ]);
  assert.deepEqual(levels(hits), ['exact']);
  assert.equal(hits[0].reason, '슬러그가 동일');
});

test('별개 제품은 침묵한다 — ChatGPT 계열·Copilot Fusion·Sonnet 5.5', () => {
  const index = [
    md('chatgpt', 'ChatGPT', 'https://chatgpt.com'),
    md('github-copilot', 'GitHub Copilot', 'https://github.com'),
    md('claude-sonnet-5', 'Claude Sonnet 5', 'https://www.anthropic.com/claude'),
    md('claude', 'Claude', 'https://claude.ai'),
  ];
  assert.deepEqual(findDuplicates({ slug: 'chatgpt-work', name: 'ChatGPT Work', url: 'https://chatgpt.com' }, index), []);
  assert.deepEqual(findDuplicates({ slug: 'github-copilot-fusion', name: 'GitHub Copilot Fusion', url: '' }, index), []);
  assert.deepEqual(findDuplicates({ slug: 'claude-sonnet-5-5', name: 'Claude Sonnet 5.5', url: 'https://www.anthropic.com/claude-sonnet-5-5' }, index), []);
  assert.deepEqual(findDuplicates({ slug: 'claude-duet', name: 'Claude Duet', url: '' }, index), []);
});

test('이름이 다른 별개 도구는 침묵한다 — Kai / Mermaid Flow', () => {
  const index = [md('kai', 'Kai', 'https://hirekai.ai'), md('mermaid', 'Mermaid', 'https://addmermaid.com/')];
  assert.deepEqual(findDuplicates({ slug: 'kai-resolve-by-gleap', name: 'Kai Resolve by Gleap', url: 'https://www.gleap.ai/kai-resolve' }, index), []);
  assert.deepEqual(findDuplicates({ slug: 'mermaid-flow', name: 'Mermaid Flow', url: '' }, index), []);
});

test('수집원·플랫폼 도메인은 도메인 일치로 보지 않는다', () => {
  const index = [
    md('foo', 'Foo', 'https://topai.tools/t/foo'),
    md('bar', 'Bar', 'https://www.producthunt.com/products/bar'),
  ];
  assert.deepEqual(findDuplicates({ slug: 'baz', name: 'Baz', url: 'https://topai.tools/t/baz' }, index), []);
  assert.deepEqual(findDuplicates({ slug: 'qux', name: 'Qux', url: 'https://producthunt.com/posts/qux' }, index), []);
});

test('자기 자신(md 캐시)은 excludeSameSlug 로 제외한다', () => {
  const index = [md('careops', 'CareOps 마음이', 'https://careops.kr'), sub('careops', 'CareOps 마음이', 'https://careops.kr')];
  const withSelf = findDuplicates({ slug: 'careops', name: 'CareOps 마음이', url: 'https://careops.kr' }, index);
  assert.deepEqual(levels(withSelf).length, 2);
  const withoutSelf = findDuplicates(
    { slug: 'careops', name: 'CareOps 마음이', url: 'https://careops.kr' },
    index,
    { excludeSameSlug: true }
  );
  assert.deepEqual(withoutSelf, []);
});

test('중복 히트는 exact → likely 순으로 정렬된다', () => {
  const hits = findDuplicates({ slug: 'x', name: 'Make0 Brain OSS', url: 'https://make0.ai' }, [
    md('z-likely', 'Make0 Brain', ''),
    md('a-exact', 'Make0 Brain', 'https://make0.ai'),
  ]);
  assert.equal(hits[0].level, 'exact');
  assert.equal(hits[0].slug, 'a-exact');
  assert.ok(hits.some((h) => h.level === 'likely' && h.slug === 'z-likely'));
});

test('승인 확인창 문구: 중복 없음 → 공개 안내', () => {
  const w = describeApproveWarning([]);
  assert.equal(w.level, 'clean');
  assert.equal(w.title, '✓ 기존 목록과 중복 없음');
  assert.ok(w.hint.includes('sitemap'));
});

test('승인 확인창 문구: exact → "이미 중복입니다" + 반려 권고', () => {
  const hits = findDuplicates({ slug: 'omlx-ai', name: 'Omlx AI', url: 'https://topai.tools/t/omlx-ai' }, [
    md('omlx', 'oMLX', 'https://omlx.ai'),
  ]);
  const w = describeApproveWarning(hits);
  assert.equal(w.level, 'exact');
  assert.equal(w.title, '⚠️ 이미 중복입니다');
  assert.ok(w.hint.includes('두 번 노출'), w.hint);
  assert.ok(w.hint.includes('반려'), w.hint);
});

test('승인 확인창 문구: likely → "중복 의심" + 확인 요청', () => {
  const hits = findDuplicates({ slug: 'make0-brain-oss', name: 'Make0 Brain OSS', url: '' }, [
    md('make0-brain', 'Make0 Brain', 'https://make0.ai/'),
  ]);
  const w = describeApproveWarning(hits);
  assert.equal(w.level, 'likely');
  assert.equal(w.title, '⚠️ 중복 의심');
  assert.ok(w.hint.includes('확인'), w.hint);
});

test('dedupeIndex: 같은 슬러그는 md 를 남긴다', () => {
  const out = dedupeIndex([sub('a', 'A', 'https://a.io'), md('a', 'A', 'https://a.io'), sub('b', 'B')]);
  assert.equal(out.length, 2);
  assert.equal(out.find((e) => e.slug === 'a')!.source, 'md');
  assert.equal(out.find((e) => e.slug === 'b')!.source, 'submission');
});
