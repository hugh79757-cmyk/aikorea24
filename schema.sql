-- 사용자
CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  google_id TEXT UNIQUE NOT NULL,
  email TEXT NOT NULL,
  name TEXT NOT NULL,
  avatar TEXT,
  created_at TEXT DEFAULT (datetime('now'))
);

-- 게시판 글
CREATE TABLE IF NOT EXISTS posts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL,
  title TEXT NOT NULL,
  content TEXT NOT NULL,
  category TEXT DEFAULT 'general',
  views INTEGER DEFAULT 0,
  created_at TEXT DEFAULT (datetime('now')),
  updated_at TEXT DEFAULT (datetime('now')),
  FOREIGN KEY (user_id) REFERENCES users(id)
);

-- 댓글
CREATE TABLE IF NOT EXISTS comments (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  post_id INTEGER NOT NULL,
  user_id INTEGER NOT NULL,
  content TEXT NOT NULL,
  created_at TEXT DEFAULT (datetime('now')),
  FOREIGN KEY (post_id) REFERENCES posts(id),
  FOREIGN KEY (user_id) REFERENCES users(id)
);

-- 뉴스
CREATE TABLE IF NOT EXISTS news (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  title TEXT NOT NULL,
  link TEXT UNIQUE NOT NULL,
  description TEXT,
  source TEXT NOT NULL,
  category TEXT DEFAULT 'AI',
  pub_date TEXT,
  created_at TEXT DEFAULT (datetime('now'))
);

-- 브리핑 (날짜별 큐레이팅)
CREATE TABLE IF NOT EXISTS briefings (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  date TEXT UNIQUE NOT NULL,
  intro TEXT DEFAULT '',
  status TEXT DEFAULT 'draft',
  created_at TEXT DEFAULT (datetime('now')),
  published_at TEXT
);

-- 브리핑 아이템 (뉴스 + 코멘트)
CREATE TABLE IF NOT EXISTS briefing_items (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  briefing_id INTEGER NOT NULL,
  news_id INTEGER NOT NULL,
  sort_order INTEGER DEFAULT 0,
  comment TEXT DEFAULT '',
  created_at TEXT DEFAULT (datetime('now')),
  FOREIGN KEY (briefing_id) REFERENCES briefings(id),
  FOREIGN KEY (news_id) REFERENCES news(id)
);

-- 성능 인덱스
CREATE INDEX IF NOT EXISTS idx_news_created_at ON news(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_news_country ON news(country);
CREATE INDEX IF NOT EXISTS idx_news_category ON news(category);
