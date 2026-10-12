--
-- 005_submission_status_pending.sql
-- Phase 3-C Wave A: tool_submissions status pending 지원
--
-- 1. rejection_reason 컬럼 추가 (반려 사유 저장)
--    SQLite는 DEFAULT 값 변경을 ALTER로 못 하므로, 코드 레벨에서 INSERT 시 'pending' 기본값 적용.
--    기존 published 행은 그대로 유지 (rejection_reason NULL).
ALTER TABLE tool_submissions ADD COLUMN rejection_reason TEXT;

-- 비고: SQLite는 ALTER TABLE ... ALTER COLUMN ... SET DEFAULT 미지원.
--       status 기본값을 'pending'으로 바꾸는 ALTER는 불가 → 제출 코드(submit.ts)에서
--       INSERT 시 status='pending'으로 명시. 기존 published 행은 이전 마이그레이션 그대로.
--       status 기본값은 001_tool_submissions.sql에서 'pending'으로 지정되어 있음 (기존 DB는 001 재생성 대상 아님; 기존 published 행 유지).
