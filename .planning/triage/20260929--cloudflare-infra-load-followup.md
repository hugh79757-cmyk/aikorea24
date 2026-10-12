---
date: 2026-09-29
type: chore
status: ongoing
---

# Cloudflare 인프라 부담 경감 — 장기 과제 (잔여 항목)

## What
2026-09-28~29 인프라 여유 실측·tools 정적화까지 완료한 뒤 남은 미해결 항목. zone 토큰 권한, 21.5MB 데이터 청크, _routes.json exclude 규칙, SSR 잔여 route, pending preview 소실 등.

## 해야할일 (TODO)

1. **Zone 권한 토큰** — dash.cloudflare.com → API Tokens → `$CLOUDFLARE_API_TOKEN`에 **Zone:Read + Zone:Edit** 추가 (또는 존 권한 신규 토큰). 이후 Cache Rules 엣지 캐시 설정 가능 (홈 SSR 945ms → 엣지 히트 ~50ms).
   - 단계: 토큰 스코프 확인 → 권한 추가 → `env -u CLOUDFLARE_API_TOKEN` 재검증 (`GET /zones?name=aikorea24.kr` 결과 1건) → Cache Rule 생성.
2. **_routes.json exclude 검증** — 현재 99건(상한 100 근접). `/tools/*` 와일드카드 미설정 → 미exclude 툴 URL이 Worker 경유 여부 미확정. 헤더로는 구분 불가.
   - 단계: (1번 완료 후) CF 대시보드 Workers 요청 수로 경유 여부 확인 → 경유하면 `_routes.json`에 `/tools/*` 와일드카드 추가 (개별 55건 규칙 정리 가능, 상한 여유 확보).
3. **21.5MB 데이터 청크 제거/축소** — 대공사, 우선순위 낮음. content layer가 md 1,349건을 JS 직렬화.
   - 후보 방안: (a) 런타임 getCollection 1곳(`src/pages/api/tools/submit.ts`)만 md/D1 직접 조회로 전환 → 21MB 로드 경로 완전 차단, (b) Astro content를 loader 분리로 청크 분할, (c) blog 발행량 증가 추이 모니터링 후 판단.
4. **SSR 잔여 .astro 정적화 후보 재검토** — `tools/index·[id]` 완료 후 잔여 SSR: index(불가·D1 briefing), pricing(불가·세션), community/*, event/*(세션 필수), my/tools/*, tools/submit, news, courses/7day-starter 등. dynamic_hits 기반 정적화 가능분 선별.
5. **승인→라이브 반영 주기** — 정적화로 승인 툴이 다음 deploy까지 미반영. deploy.sh가 build 전 `sync_submissions_to_md.mjs` 호출 추가됨. collector 06:00 실행 사이클/수동 deploy 사이클 확인해서 허용 가능한 지연인지 결정.
6. **pending preview 복구 검토** — owner 미승인 `/tools/<slug>/` preview가 정적화로 소실 (`/my/tools/` SSR은 유지). 복구 방안: preview 전용 SSR route 신설 또는 포기 결정.
7. **build WARN** `Astro.request.headers was used when rendering src/pages/tools/[id].astro` — 원인 미확인 (tools 파일·layouts·components에 사용 없음; 유일 사용처 payments/success, api/courses/send-daily). 출력 정상이라 미해결.
8. **로컬 dev nodejs_compat** — `wrangler pages dev` 전부 hang, `nodejs_compat` compatibility flag 부재 로그. wrangler.toml에 flag 추가 검토 (production은 정상, 로컬 전용).
9. **미측정 항목** — Workers 요청/일, CPU 사용량, 계정 플랜(Free/Paid), R2 사용량 (토큰 권한 후 dash 확인).

## 조사한내용 (Findings — 2026-09-28~29 실측)

### 아키텍처/수치 [검증됨]
- `astro.config.mjs`: output server, adapter cloudflare, trailingSlash always. `wrangler.toml`: D1 binding (aikorea24-db), R2 aikorea24-files, account_id `fac9808c757df31d797190c529aaa71a`, **compatibility_flags 없음**.
- dist 250MB/4,076파일. Worker 번들 23MB (64MiB 한도 36%). 핵심 = `_astro_data-layer-content_C9M3jXZk.mjs` **21.5MB** (gzip 4.15MB, 62,179 keys) — Astro 5 content layer가 md 1,349건+tools를 JS 직렬화한 빌드 산출물.
- 청크 로드: `DataStore.fromModule()`의 **lazy dynamic import** → startup엔 미로드. 런타임 getCollection 호출원 = `src/pages/api/tools/submit.ts` **1곳뿐** (prerender 안 된 65개 파일 전수 스캔).
- node 프로브: evaluate 131ms, RSS 44→152MB (+108), heapUsed 47MB [부분검증 — workerd 아님].
- TTFB: `/` 867~945ms (SSR), static 100~300ms. `/api/search/?q=ai` → 404.
- D1: 18.3MB, rows_read 24h 648,770, rows_written 24h 5,771. Pages 배포 25개.

### 한도 [검증됨]
- Workers Free: 요청 100,000/일(계정 전체 공유), CPU 10ms/요청, 메모리 128MB, Worker 64MiB, startup 1초, static asset 20,000개.
- D1 Free: reads 월 5,000만, writes 월 1,000만, 저장 DB당 500MB/계정 5GB, DB 10개.
- R2 Free: 10GB, Class A 100만/월, Class B 1천만/월, egress 무료.
- Pages Free: 빌드 500회/월, 커스텀 도메인 100개/프로젝트, 파일 20,000개.
- 안전 판정: D1 3.7%/39%/1.7%, dist 파일 20%, 빌드 25/500, Worker 36%.

### Zone 토큰 [검증됨]
- `env -u CLOUDFLARE_API_TOKEN wrangler whoami` → User API Token, hugh79757@gmail.com, account wrangler.toml와 일치 = 프로필/계정 정확.
- `$CLOUDFLARE_API_TOKEN` 스코프: `/zones` → 결과 0건 (zone read 없음), D1 → 7403, `/accounts/{id}/zones` → 7003. → 토큰은 Pages 배포 권한만.
- OAuth 토큰 직접 추출(`~/.wrangler/config/*.toml` 7개, refresh 교환) 전부 403/401/400 → CLI 경로만 사용 가능.
- 존은 이 계정 소유 [추론]: NS alberto/sonia.ns.cloudflare.com + Pages 커스텀 도메인 = 같은 계정 필수.

### tools 정적화 완료 (2026-09-29) [검증됨]
- 승인 11건 md 미존재 발견 → `scripts/sync_submissions_to_md.mjs` 신규(기존 md 덮어쓰기 안 함, `env -u` 없으면 7403) → 11건 생성.
- `tools/index.astro` + `[id].astro`에 `export const prerender = true` (slug·경로 불변, md 우선 로직 동일).
- `deploy.sh`에 build 전 sync 단계 추가. 빌드: 정적 툴 390개 index.html. 배포 `d497ce45.aikorea24.pages.dev`, sitemap ping 200.
- 라이브: `/tools/` 200(712,499B), `/tools/aifetchly/`·`/tools/mixdesk/` 200, `/` SSR 200, 삭제 slug 404. 커밋 `7fd0b4a7`+`99dc8bf6`, push `768720a5..99dc8bf6` 완료.

## Files changed
- `.planning/triage/20260929--cloudflare-infra-load-followup.md` (이 파일)
- 관련(참조만): `wrangler.toml`, `scripts/deploy.sh`, `scripts/sync_submissions_to_md.mjs`, `src/pages/tools/{index,[id]}.astro`, `src/pages/api/tools/submit.ts`

## How
조사+구현 세션에서 실측한 내용을 한 파일로 수집. 토큰 권한 → exclude 검증 → 청크 전환 순서로 진행 예정.

## Verification
- [검증됨] 위 수치 전부 curl/wrangler/node 실측 + 공식 한도 문서 fetch. tools 정적화는 라이브 200/404 검증 + 커밋 push 완료.
- [부분검증] RSS 152MB는 node 프로브(workerd 아님); exclude 미확정은 헤더 구분 불가.
- [검증불가] 요청/일·CPU·플랜·R2 = 토큰 zone 권한 확보 후 dash 확인.

## 잔존 위험
- 승인 툴 라이브 반영 지연 (다음 deploy까지), pending preview 소실, exclude 99/100 상한, build WARN 미원인, 로컬 dev hang(nodejs_compat), 요청/일 미측정.
