-- users 카카오 확장
ALTER TABLE users ADD COLUMN kakao_id TEXT;
ALTER TABLE users ADD COLUMN provider TEXT DEFAULT 'google';
CREATE UNIQUE INDEX IF NOT EXISTS idx_users_kakao ON users(kakao_id) WHERE kakao_id IS NOT NULL;

-- 페르소나 전용 게시판
CREATE TABLE IF NOT EXISTS persona_posts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL,
  persona_slug TEXT NOT NULL,
  persona_type TEXT NOT NULL,
  region TEXT,
  sex TEXT,
  age TEXT,
  title TEXT NOT NULL,
  content TEXT NOT NULL,
  views INTEGER DEFAULT 0,
  likes INTEGER DEFAULT 0,
  created_at TEXT DEFAULT (datetime('now')),
  updated_at TEXT DEFAULT (datetime('now')),
  FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS persona_comments (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  post_id INTEGER NOT NULL,
  user_id INTEGER NOT NULL,
  content TEXT NOT NULL,
  created_at TEXT DEFAULT (datetime('now')),
  FOREIGN KEY (post_id) REFERENCES persona_posts(id),
  FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS persona_likes (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  post_id INTEGER NOT NULL,
  user_id INTEGER NOT NULL,
  created_at TEXT DEFAULT (datetime('now')),
  UNIQUE(post_id, user_id),
  FOREIGN KEY (post_id) REFERENCES persona_posts(id),
  FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE INDEX IF NOT EXISTS idx_persona_posts_slug ON persona_posts(persona_slug);
CREATE INDEX IF NOT EXISTS idx_persona_posts_created ON persona_posts(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_persona_comments_post ON persona_comments(post_id);
