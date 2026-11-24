-- AIK24-TOOLS-LOGO-01 — 정사각형 로고 업로드 필드
-- 적용: env -u CLOUDFLARE_API_TOKEN /opt/homebrew/bin/wrangler d1 execute aikorea24-db --remote --file=sql/010_tool_submissions_logo_url.sql
-- 검증: ... --command="PRAGMA table_info(tool_submissions);" | grep logo_url
ALTER TABLE tool_submissions ADD COLUMN logo_url TEXT;
