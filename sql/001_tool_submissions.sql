-- tool_submissions: 사용자 직접 등록 AI 툴 (Phase 41-02)
-- 마크다운 컬렉션(src/content/tools/*.md)은 건드리지 않음. D1에만 저장.
-- user_id 타입: INTEGER NOT NULL REFERENCES users(id) (41-01-REPORT §1.5 실측 확정)
CREATE TABLE IF NOT EXISTS tool_submissions (
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
  status TEXT DEFAULT 'pending',
  created_at TEXT DEFAULT (datetime('now')),
  updated_at TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_tool_submissions_slug ON tool_submissions(slug);
CREATE INDEX IF NOT EXISTS idx_tool_submissions_user ON tool_submissions(user_id);
