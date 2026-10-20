-- Migration: news.blog_link 추가 (AIK24-PIPE-05 · 2026-10-20)
--
-- 목적: 무료 모델 브리핑 항목의 "원문 보기" 링크를 AIK24 블로그 글로 연결.
--       models.dev 는 제3자 DB라 "원문 보기"로 부적절하고, 표기와 링크가 어긋난다
--       (08:26 이슈). 대표님 결정(2026-10-20): 무료 모델 항목 링크는 항상 AIK24 블로그 URL.
--
-- 규칙: news.link 는 수집기 dedup 키다 (news_collector_v2.save() 가
--       `SELECT link FROM news … LIMIT 3000` 으로 중복 제외). 절대 변경하지 않는다.
--       blog_link 는 링크를 담는 별도 필드 — 기존 행·dedup 로직에 영향 없음.
--
-- 사용: 렌더링 경로에서 COALESCE(n.blog_link, n.link) 로 사용한다.
--       blog_link 가 NULL 이면 기존 link(models.dev 등)로 폴백.

ALTER TABLE news ADD COLUMN blog_link TEXT;
