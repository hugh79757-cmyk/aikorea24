-- Migration v20260710: 강좌 시스템 (Phase 17 MVP-1)
-- 커뮤니티 게이트웨이 패턴: posts가 콘텐츠 본체, course_lessons는 얇은 매핑

-- 1. 기존 posts에 visibility 컬럼 추가
-- public: 기존 일반 글 (누구나)
-- members: 강좌 레슨 (로그인 필요, 구독자 전용)
-- premium: 프리미엄 (추후 유료 전환 시)
ALTER TABLE posts ADD COLUMN visibility TEXT DEFAULT 'public';

-- 2. courses 테이블
CREATE TABLE IF NOT EXISTS courses (
  slug TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  description TEXT DEFAULT '',
  default_send_hour INTEGER DEFAULT 18,
  total_days INTEGER DEFAULT 7,
  created_at TEXT DEFAULT (datetime('now'))
);

-- 3. course_lessons — posts를 가리키는 얇은 매핑 테이블
CREATE TABLE IF NOT EXISTS course_lessons (
  course_slug TEXT NOT NULL,
  day_number INTEGER NOT NULL,
  community_post_id INTEGER NOT NULL,
  teaser_html TEXT NOT NULL,
  email_send_hour INTEGER,  -- NULL이면 courses.default_send_hour 사용
  PRIMARY KEY (course_slug, day_number),
  FOREIGN KEY (course_slug) REFERENCES courses(slug),
  FOREIGN KEY (community_post_id) REFERENCES posts(id)
);

-- 4. enrollments — 수강 신청 + 진행 추적
CREATE TABLE IF NOT EXISTS enrollments (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL,
  email TEXT NOT NULL,
  course_slug TEXT NOT NULL,
  enrolled_at TEXT DEFAULT (datetime('now')),
  start_date TEXT NOT NULL,
  days_sent INTEGER DEFAULT 0,
  completed INTEGER DEFAULT 0,
  brevo_tag_added INTEGER DEFAULT 0,
  UNIQUE(email, course_slug),
  FOREIGN KEY (user_id) REFERENCES users(id),
  FOREIGN KEY (course_slug) REFERENCES courses(slug)
);

-- 5. lesson_clicks — 이메일 클릭 추적 (발송 ≠ 열람)
CREATE TABLE IF NOT EXISTS lesson_clicks (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  enrollment_id INTEGER NOT NULL,
  day_number INTEGER NOT NULL,
  clicked_at TEXT DEFAULT (datetime('now')),
  FOREIGN KEY (enrollment_id) REFERENCES enrollments(id)
);

-- 인덱스
CREATE INDEX IF NOT EXISTS idx_enrollments_email ON enrollments(email);
CREATE INDEX IF NOT EXISTS idx_enrollments_course ON enrollments(course_slug);
CREATE INDEX IF NOT EXISTS idx_lesson_clicks_enrollment ON lesson_clicks(enrollment_id);
CREATE INDEX IF NOT EXISTS idx_posts_visibility ON posts(visibility);
