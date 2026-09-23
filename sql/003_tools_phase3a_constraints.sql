-- Phase 3-A-1: senior checklist 정합 (price_model NOT NULL, difficulty DEFAULT '보통')
-- 적용 시점 local/remote 모두 0행 — rebuild 안전. (001 파일도 동일 정의로 수정됨)
CREATE TABLE tool_submissions_new (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL REFERENCES users(id),
  slug TEXT UNIQUE NOT NULL,
  name TEXT NOT NULL,
  url TEXT NOT NULL,
  category TEXT NOT NULL,
  category_custom TEXT,
  description TEXT NOT NULL,
  price_model TEXT NOT NULL,
  price_detail TEXT,
  screenshot_url TEXT,
  korean_support INTEGER DEFAULT 0,
  difficulty TEXT DEFAULT '보통',
  use_cases TEXT,
  tags TEXT,
  tasks TEXT,
  detail_markdown TEXT,
  status TEXT DEFAULT 'published',
  created_at TEXT DEFAULT (datetime('now')),
  updated_at TEXT DEFAULT (datetime('now'))
);
INSERT INTO tool_submissions_new (id, user_id, slug, name, url, category, category_custom, description, price_model, price_detail, screenshot_url, korean_support, difficulty, use_cases, tags, tasks, detail_markdown, status, created_at, updated_at)
SELECT id, user_id, slug, name, url, category, category_custom, description, price_model, price_detail, screenshot_url, korean_support, difficulty, use_cases, tags, tasks, detail_markdown, status, created_at, updated_at FROM tool_submissions;
DROP TABLE tool_submissions;
ALTER TABLE tool_submissions_new RENAME TO tool_submissions;
CREATE INDEX IF NOT EXISTS idx_tool_submissions_slug ON tool_submissions(slug);
CREATE INDEX IF NOT EXISTS idx_tool_submissions_user ON tool_submissions(user_id);
