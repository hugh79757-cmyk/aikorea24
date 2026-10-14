## 2026-10-14 13:00 AIK24-EMDASH-04 해결 — B안(limit 12 + getReadingTime 제거) 배포로 /posts 503 해소 [검증됨] / A안 캐시 규칙은 여전히 [검증불가]

### 한 일
- 대표님 지시: "zone 이전 확인됨. B안 먼저 배포하고, A안 캐시 규칙은 /tmp/cache_ruleset.json으로 API 재시도."
- [PRODUCTION CODE] `~/projects2/aikorea24emdash/src/pages/posts/index.astro` 3줄 — `limit: 60 → 12`, `readingTime={getReadingTime(post.data.content)}` 삭제, `getReadingTime` import 삭제. 주석에 프로파일링 수치 근거 기입.
- **주의: 이 프로젝트는 git 저장소가 아니다**(`git stash` → "not a git repository"). 되돌리려면 파일 수동 수정.

### 결과
- [검증됨] **존 이전 확인 — zone_id가 바뀜.** `aikorea24.kr` 신규 zone_id = `71a21534380f096809ef7b97165e3bc7`, 계정 `7eb1b8cd178de269758ec94b2e03330b`(Stylefactory9ai), status `active`. 구 zone `a6d9e75032c8cefe316b06d46a90a431` status `moved`. 기존에 쓰던 `76d0599a7e05203168fd8fe1cfae4bd4` 는 `informationhot.kr`. **`CF_MIGRATE_TOKEN`으로 새 zone 읽기 성공.**
- [검증됨] 배포 성공 — Version `9a0f78e6-b020-4b29-b065-a995c94daa3e`, Worker Startup 22ms, 113 assets.
- [검증됨] **`/posts` 8/8 = 200**(0.34–0.54s, 38,762B, "12 articles"). 홈페이지 **8/8 = 200**. `/rss.xml` 200.
- [검증됨] ego-browser 육안: `title="Latest Posts — aikorea24"`, `h1="최신 글"`, `desc="12 articles"`, 카드 12개, `broken images 0/14`. 스크린샷 `/tmp/posts_after.png` — 썸네일 전부 정상 렌더.
- [검증됨] typecheck 신규 에러 0건 (기존 6건은 `og-image.ts`·`sanitize.ts`·`index.astro` 의 기존 문제).
- **[검증불가] A안 캐시 규칙 — 여전히 스코프 부족.** 새 zone `71a21534380f096809ef7b97165e3bc7` 에 `/tmp/cache_ruleset.json` POST → `CF_MIGRATE_TOKEN`/`CF_DNS_TOKEN`/`D1_API_TOKEN`/`CLOUDFLARE_EMDASH_D1_TOKEN`/`CLOUDFLARE_API_TOKEN` **5개 전부 `10000 Authentication error`**. GET rulesets 도 10000. → 이전은 계정 문제였지만 **지금은 토큰 스코프(Zone Rulesets:Edit) 문제**. 복구 계획: 콘솔 수동 생성 또는 토큰 재생성.

### 잔존 위험
1. `/posts` 가 항상 최신 12편만 표시 — `?page=N` 파라미터 미구현(이번 변경 이전에도 페이지네이션 없었음). 1,481편 중 1,469편은 목록에서 도달 불가.
2. 카드에서 "N분 소요" 표시 사라짐(`readingTime` 미전달).
3. 캐시 미적용 — 트래픽 급증 시 `/posts` 는 여전히 CPU 한계에 노출.
4. `~/projects2/aikorea24emdash` 미커밋(저장소 아님) — 수동 백업 필요.

### 다음 행동
- 대표님: 콘솔에서 Cache Rule 1건 생성(페이로드 `/tmp/cache_ruleset.json`), `/posts` 페이지네이션 지시 여부.

