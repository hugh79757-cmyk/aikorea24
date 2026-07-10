-- 관리자 역할 컬럼 추가
ALTER TABLE users ADD COLUMN role TEXT DEFAULT 'member';

-- twinssn@gmail.com 관리자 지정
UPDATE users SET role = 'owner' WHERE email = 'twinssn@gmail.com';
