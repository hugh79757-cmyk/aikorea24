-- Phase 5: dofollow/nofollow 수동 전환 기능
-- tool_submissions 테이블에 link_type 컬럼 추가
-- 기본값: nofollow (기존 레코드 모두 nofollow로 초기화)

ALTER TABLE tool_submissions ADD COLUMN link_type TEXT DEFAULT 'nofollow';

-- 기존 레코드 명시적 초기화 (기본값 적용 확인)
UPDATE tool_submissions SET link_type = 'nofollow' WHERE link_type IS NULL;