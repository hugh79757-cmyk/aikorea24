/**
 * AIK24-TOOLS-NOTIFY-DEDUP-01 — 등록/승인 이메일 중복 발송 방지 계약 테스트
 * 실행: npm run test:js (node --test tests/js/*.test.ts)
 *
 * 2026-11-24 15:31Z·15:33Z에 같은 슬러그로 확인/승인 메일이 2통씩 나간 사건의
 * 재발 방지. 라우트 핸들러는 `cloudflare:workers` 를 import 하므로 Node에서 직접
 * 실행할 수 없어, 소스 계약(가드·condition UPDATE·fetch 경로)을 검증한다.
 */
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

const ROOT = join(import.meta.dirname ?? process.cwd(), '../..');
const read = (rel: string) => readFileSync(join(ROOT, rel), 'utf8');

const review = read('src/pages/api/admin/tools/review.ts');
const submit = read('src/pages/api/tools/submit.ts');
const visibility = read('src/pages/api/tools/[slug]/visibility.ts');
const adminPage = read('src/pages/admin/tools.astro');
const myToolsPage = read('src/pages/my/tools/index.astro');
const toolForm = read('src/components/ToolForm.astro');

test('review: 이미 같은 상태면 UPDATE·메일 없이 already=true 로 돌려준다', () => {
  assert.ok(review.includes('currentStatus === nextStatus'), '같은 상태 조기 반환 가드 없음');
  assert.ok(review.includes('already: true'), 'already 플래그 없음');
  const notifyIdx = review.indexOf('sendToolNotification(');
  const guardIdx = review.indexOf('currentStatus === nextStatus');
  assert.ok(guardIdx > 0 && guardIdx < notifyIdx, '가드가 메일 발송보다 뒤에 있다');
});

test('review: 동시 승인도 한 번만 메일을 보낸다 (조건부 UPDATE + changes 확인)', () => {
  assert.ok(review.includes('WHERE slug = ? AND status <> ?'), '조건부 UPDATE 없음');
  assert.ok(review.includes('meta?.changes'), '변경 행 수 확인 없음');
  assert.equal((review.match(/await sendToolNotification\(/g) || []).length, 1,
    '승인 메일 호출이 2곳 이상이다');
});

test('submit: 5분 내 동일 내용 재제출은 새 행/확인 메일을 만들지 않는다', () => {
  assert.ok(submit.includes("created_at >= datetime('now', '-5 minutes')"), '중복 창 쿼리 없음');
  const dupIdx = submit.indexOf('if (recent)');
  const insertIdx = submit.indexOf('INSERT INTO tool_submissions');
  const mailIdx = submit.indexOf('sendSubmissionConfirmation(');
  assert.ok(dupIdx > 0 && dupIdx < insertIdx && insertIdx < mailIdx,
    '중복 가드가 INSERT/메일보다 뒤에 있다');
});

test('visibility: 같은 상태 재요청은 no-op이고 조건부 UPDATE를 쓴다', () => {
  assert.ok(visibility.includes('currentStatus === status'));
  assert.ok(visibility.includes('WHERE slug = ? AND status <> ?'));
  assert.ok(visibility.includes('already: true'));
});

test('trailingSlash:always — 관리자 승인·公开 전환·등록 fetch 는 끝 슬래시 사용', () => {
  assert.ok(adminPage.includes("fetch('/api/admin/tools/review/'"), '승인 fetch에 끝 슬래시 없음');
  assert.ok(myToolsPage.includes('fetch(`/api/tools/${slug}/visibility/`'), 'visibility fetch에 끝 슬래시 없음');
  assert.ok(toolForm.includes("'/api/tools/submit/'"), 'submit fetch에 끝 슬래시 없음');
  assert.ok(!adminPage.includes("fetch('/api/admin/tools/review'"), '슬래시 없는 승인 fetch 잔존');
  assert.ok(!myToolsPage.includes('fetch(`/api/tools/${slug}/visibility`'), '슬래시 없는 visibility fetch 잔존');
});
