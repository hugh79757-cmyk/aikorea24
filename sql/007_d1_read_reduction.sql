-- 007: D1 읽기 절감 인덱스 (AIK24-D1-READ-01, 2026-10-21)
--
-- 목적: SSR 경로의 D1 rows_read 를 줄여 계정 일일 5,000,000행 한도 초과를 해소한다.
-- 배경: 2026-10-20 UTC 4,190,000행(83.6%) 소진. 실측 단가:
--        홈 `/`  = 1,733행/뷰 (briefings 671 + ToolsSection UNION ALL 1,062)
--        `/global/` = 19,218행/뷰 (news 19,350행 중 global 9,857행 → temp b-tree 9,360행)
--   SSR 경로는 scripts/cfnew.py 의 로컬 가드를 거치지 않아 계측 자체가 안 된다.
--
-- 적용(기존 문서와 동일한 방식):
--   wrangler d1 execute aikorea24-db --remote --file=sql/007_d1_read_reduction.sql
--   (계정 7eb1b8cd... · 토큰은 ~/.env.common 의 CF_MIGRATE_TOKEN)
--
-- 주의: CREATE INDEX 는 라이브 테이블에 쓰이지만 파괴적이지 않다(데이터 변경 0).

-- 1) 브리핑 최신 1건 — src/pages/index.astro
--    기존 인덱스 idx_briefings_status_date(status, date DESC) 는 ORDER BY id DESC 를
--    만족하지 못해 published 행 전체(339행)를 temp b-tree 에 넣었다 → 671행.
--    (status, id) 로 바꾸면 status 일치 구간을 id 역순으로 훑어 1건만 읽는다.
CREATE INDEX IF NOT EXISTS idx_briefings_status_id ON briefings(status, id);

-- 2) 사용자 등록 도구 최신순 — src/components/home/ToolsSection.astro
--    tool_submissions 에 status/updated_at 인덱스가 없어 매번 24행 전수 스캔 +
--    정렬 버퍼에 전부 적재됐다. (status, updated_at) 로 published 8건만 읽는다.
CREATE INDEX IF NOT EXISTS idx_tool_submissions_status_updated ON tool_submissions(status, updated_at);

-- 3) 글로벌 뉴스 최신순 — src/pages/global.astro
--    idx_news_category(category) 만으로는 ORDER BY created_at DESC 정렬이 안 돼
--    global 9,857행 전량을 temp b-tree 에 넣었다(19,218행).
--    (category, created_at DESC) 로 정렬까지 인덱스가 맡고 LIMIT 50 에서 멈춘다.
CREATE INDEX IF NOT EXISTS idx_news_category_created ON news(category, created_at DESC);
