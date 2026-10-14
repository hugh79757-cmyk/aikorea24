## 2026-10-14 12:50 AIK24-EMDASH-04 후속 — /posts 엣지 캐시 적용 시도 + 쿼리 프로파일링 (에지캐시 [검증불가], 원인 특정)

### 한 일
- 지시: 대표님 "EmDash는 200으로 살아있고 1102는 간헐적. 1·2번 하지 말고 3번으로 — /posts* 엣지 캐시 적용 후 /posts 쿼리 프로파일링".
- [PRODUCTION CODE] 없음(이번 항목은 조사만).

### 결과
- **[검증불가] 엣지 캐시 적용 실패 — 토큰 권한 부족.** 존 `aikorea24.kr`(zone_id `76d0599a7e05203168fd8fe1cfae4bd4`) 소유 계정은 `fac9808c757df31d797190c529aaa71a`(Hugh79757). rulesets GET 은 성공하나 POST(Cache Rules, phase `http_request_cache_settings`) 는 `10000 Authentication error`, classic pagerules POST 는 `9109 Unauthorized`. `CF_MIGRATE_TOKEN`/`CF_DNS_TOKEN`/`CLOUDFLARE_EMDASH_D1_TOKEN` 모두 rulesets 읽기부터 실패. 복구 계획: 콘솔에서 Cache Rule 1건 수동 생성(페이로드 `/tmp/cache_ruleset.json` 준비됨) 또는 토큰에 `Zone Rulesets:Edit` 추가.
- [검증됨] /posts 쿼리 프로파일링(EmDash D1, 3회 반복 median):
  - `SELECT * LIMIT 61` = **281 ms / 509.7 KB**
  - `SELECT * LIMIT 12` = 203 ms / 120.2 KB
  - `LIMIT 61` content 컬럼 제외 = **154–162 ms / 43.8 KB**
  - `SELECT COUNT(*)` = 122–146 ms
  - **원인 확정: `SELECT *` 가 `ec_posts.content`(본문 전체 JSON)를 61건 끌어와 509.7 KB. content 제외 시 43.8 KB(11.6배). 목록 카드가 `content` 를 쓰는 곳은 `getReadingTime()` 뿐 → Workers Free CPU 한계 초과(1102)의 원인.**
- [검증됨] 라이브: `/posts` 3/3 = 503(결정적). `/posts?page=2` 3/3 = 503. `/` 간헐(200/503/200). 개별 글·`/rss.xml`·`/sitemap.xml` 3/3 = 200.
- [검증됨] 코멘트 정정: `posts/index.astro` 의 "limit 적용 전 전체 hydrate" 주석은 틀림. `loader-*.mjs:1104` 에서 `LIMIT ${fetchLimit}` 적용됨.

### 잔존 위험
1. EmDash `/posts` 목록 503 지속 — Astro SSR 301 은 정상 동작하나 도착지가 죽어 있어 `aikorea24.kr/blog/` 구간 사실상 중단.
2. 코드를 건드리지 않았으므로 원인(SELECT * )은 그대로. `~/projects2/aikorea24emdash` 소스는 배포 가능한 상태(`CF_MIGRATE_TOKEN` + account `7eb1b8cd178de269758ec94b2e03330b`).
3. Astro 7.3.2 의 `Astro.cache` 는 `astro.config.mjs` 에 `cache` 키가 없어 **죽은 코드**. `@astrojs/cloudflare` 가 cache provider 미제공 → 커스텀 provider 모듈 작성 필요.

### 다음 행동
- 대표님: (a) 콘솔 캐시 규칙 수동 생성, (b) `posts/index.astro` `limit: 60 → 12` + `getReadingTime` 제거 후 `npm run deploy`, (c) 커스텀 Astro cache provider 구현 — 중 택 1.

