-- 006: news 인덱스 정합화 문서화 (2026-10-17)
-- 목적: schema.sql 과 운영 DB 의 실제 인덱스를 일치시킨다.
-- ■ 이 파일은 신규 DDL 실행을 만들지 않는다 — 운영 DB에는 아래 인덱스가 이미 존재한다.
--   (2026-10-17 실측: EXPLAIN QUERY PLAN 이 idx_news_pubdate 를 사용하는 것을 확인)

-- [이미 존재 / 이제 schema.sql 에도 수록]
-- 1) pub_date 범위 질의용 — src/pages/api/articles/pool.ts 의
--    "WHERE pub_date >= datetime(?, '-7 days') AND source IN (...) ORDER BY pub_date DESC"
--    에서 SEARCH news USING INDEX idx_news_pubdate (pub_date>?) 로 풀스캔 탈피.
CREATE INDEX IF NOT EXISTS idx_news_pubdate ON news(pub_date);

-- 2) v2 파이프라인 부분 인덱스 — v2_pass=1 통과분만 적재 (유지 비용 최소).
--    10-11 실측: EXPLAIN 17,987행 → 77행.
CREATE INDEX IF NOT EXISTS idx_news_v2 ON news(v2_pass, created_at DESC) WHERE v2_pass = 1;

-- [참고: 관측된 중복 — 미정리]
-- idx_news_created     ON news(created_at DESC)  -- schema.sql 부재, 라이브 존재
-- idx_news_created_at  ON news(created_at DESC)  -- schema.sql 존재, 라이브 존재
-- 두 인덱스는 동일 컬럼 정의로, 뉴스 INSERT 마다 이중 유지 비용이 든다.
-- 정리(DROP) 시 아래 절차를 따를 것:
--   1. 사전 카운트: SELECT name FROM sqlite_master WHERE tbl_name='news' AND type='index';
--   2. 백업: scripts/emdash04_migrate.py 전체 덤프 또는 d1 export
--   3. 대표님 승인 후 (schema.sql 이선 바인딩 유지) DROP INDEX idx_news_created;
--   4. 사후 검증: EXPLAIN QUERY PLAN 로 created_at 질의가 idx_news_created_at 사용 확인.
