-- Migration: news.origin_link 추가 (AIK24-PIPE-07 · 2026-10-20)
--
-- 목적: 무료 모델 브리핑 항목의 "원문 보기"를 제공사(OpenCode Zen / OpenRouter /
--       Kilo / NVIDIA NIM)의 모델 페이지로 보낸다. PIPE-05 는 원문 보기를
--       AIK24 블로그(blog_link)로 보냈는데, 그 결과 카드에서 "원문 보기"와
--       "이 뉴스, 더 깊이 읽기"가 같은 블로그로 가는 문제가 생겼다
--       (2026-10-20 대표님 지적).
--
-- 규칙: news.link 는 수집기 dedup 키다 (news_collector_v2.save() 가
--       `SELECT link FROM news … LIMIT 3000` 으로 중복 제외). 절대 변경하지 않는다.
--       origin_link 는 링크를 담는 별도 필드 — 기존 행·dedup 로직에 영향 없음.
--
-- 사용: 렌더링 경로에서 COALESCE(n.origin_link, n.link) 로 사용한다.
--       origin_link 가 NULL 이면 기존 link (비무료 뉴스의 실제 원문) 로 폴백.
--       blog_link 는 남겨두되 "원문 보기"에는 더 이상 쓰지 않는다.

ALTER TABLE news ADD COLUMN origin_link TEXT;
