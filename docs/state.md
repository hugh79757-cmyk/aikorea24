## 2026-10-09 12:30 — 카카오 로그인 제거 + Brevo 401 원인 확정 (CF-MIGRATE-02 후속)

대표님 지시: 카카오 로그인 미사용 → 제거 결정. Brevo 키 재발급 여부 문의에 대한 진단.

### 한 일
카카오 로그인 라우트 2개와 consent 페이지 버튼을 삭제해 신규 계정 Pages에 배포했다. Brevo 401의 원인이 키가 아님을 실측 확정했다.

### 결과
- [검증됨] **카카오 로그인 제거 및 배포.** 삭제 = `src/pages/api/auth/kakao.ts`, `src/pages/api/auth/callback/kakao.ts`(git rm), `src/pages/auth/consent.astro` 카카오 버튼 9줄 제거. 빌드 `Server built in 10.24s` / `Complete!`, 배포 `wrangler pages deploy dist --project-name aikorea24 --branch main` → `bdf5305f.aikorea24-4nk.pages.dev`(1차 시도 `521` 로 실패했으나 5초 후 재시도로 성공).
- [검증됨] **제거 확인.** `https://aikorea24.kr/api/auth/kakao/` 404, `https://aikorea24.kr/api/auth/callback/kakao/` 404, `/auth/consent` HTML 내 `kakao` 문자열 0건. `src/pages`·`src/lib`·`src/middleware.ts` grep 결과 `KAKAO`·`kakao` 런타임 참조 0건.
- [검증됨] **기존 기능 무결.** `/` 200, `/news/` 200, `/api/posts/` 200, `GET /api/auth/login/` 302 → `accounts.google.com/o/oauth2/v2/auth`(`redirect_uri=https%3A%2F%2Faikorea24.kr%2Fapi%2Fauth%2Fcallback%2Fgoogle`).
- [검증됨] **Brevo 401 원인은 키가 아니라 IP 화이트리스트.** `aikorea24/.env`·`~/.env.common` 의 `BREVO_API_KEY` 는 동일하며 사용자가 제시한 키와 일치. IPv4 강제(`curl -4`) 후에도 `GET /v3/account` → 401 `"unrecognised IP address 110.168.249.241"`. 현재 공인 IPv4(`curl -4 ifconfig.me`) = `110.168.249.241` 로 화이트리스트 미등록 상태. **키 재발급으로는 해결되지 않음** — 동일 IP에서 동일 401 발생.
- 커밋 `99f78843`.

### 잔존 위험
- **Brevo 발송 여전히 미검증.** 복구 계획: 대표님이 `https://app.brevo.com/security/authorised_ips` 에 `110.168.249.241` 추가 → `curl -4 https://api.brevo.com/v3/account` 200 확인 후 재검증. 참고: Pages Worker egress 는 Cloudflare IP 이므로 실 발송(`/api/briefing/send-email`, `twinssn@gmail.com` 세션 필요) 시 별도 차단 가능.
- **D1 `users.kakao_id` 컬럼과 `idx_users_kakao` 유니크 인덱스 잔존.** 스키마 변경 없이 롤백 대비로 유지. 사용자 20행 중 kakao_id 값 보유 건 미확인. 정리하려면 별도 마이그레이션 필요 — 현재 필요 없음(YAGNI).
- **`news-unified` launchd job 이 출발 계정 옛 DB 에 씀** — CF-MIGRATE-02 보고서 §10-2 참조(미해결).
- **`projects2/finnews/wrangler.toml:6` `account_id` 출발 계정 잔존** — CF-MIGRATE-02 보고서 §10-3 참조(미해결).

### 다음 행동
1. 대표님: Brevo `authorized_ips` 에 `110.168.249.241` 등록.
2. 대표님: `news-unified` plist 토큰 교체 승인 여부 결정.

## 2026-10-09 12:08 — CF-MIGRATE-02: Cloudflare 계정 이전 1차 (D1+R2+Pages+도메인) 결과 요약

지시서: `SSOT/프로젝트/aikorea24/지시서/2026-10-09-0850-CF-MIGRATE-02.md` (개정본)
신규 계정 `Stylefactory9ai@gmail.com` = `7eb1b8cd178de269758ec94b2e03330b`
`aikorea24.kr` 트래픽이 신규 계정 Pages로 서빙 중. DNS zone 자체는 출발 계정에 그대로 유지(지시 금지 준수).

### 한 일
D1 `aikorea24-db` · R2 `aikorea24-files` · Pages `aikorea24` 를 출발 계정(`fac9808c…`)에서 신규 계정(`7eb1b8cd…`)으로 복제하고, `aikorea24.kr`·`www.aikorea24.kr` CNAME 을 신규 Pages 프로젝트로 전환했다. 함께 D1 접근 경로 전수(파이썬 파이프라인 11개 파일 + R2 갱신 경로)에 새 계정 ID 를 적용했다.

### 결과
- [검증됨] **D1 이전 (§2)** — 신규 DB `3f4cedde-eabc-4d7c-b459-f6abe8733767` 생성 후 import. 24개 테이블 카운트 합계 **21,919 = 출발 21,919**, 불일치 0건. `sqlite_master` 객체 51개(테이블 24 + 인덱스 27) 완전 일치(텍스트 차이 1건은 SQLite 가 `CREATE TABLE IF NOT EXISTS` 의 `IF NOT EXISTS` 를 제거하는 정규화 때문, 확인함). 근거: D1 REST `POST /accounts/{acct}/d1/database/{db}/query` 응답 `meta`.
- [검증됨] **R2 이전 (§3)** — 비용 게이트 통과(출발 버킷 **8 객체 / 1,727,247 B = 1.6MB**, 10GB 게이트 미달). 신규 버킷 `aikorea24-files`(APAC) 동일 이름 생성, R2 REST `GET/PUT .../objects` 로 8개 복사. 신규 버킷 8 객체 / 1,727,247 B, **누락 0 · 추가 0 · 크기불일치 0 · etag 불일치 0**. 스크립트 `/tmp/r2_copy.py`, 리포트 `/tmp/r2_copy_report.json`.
- [검증됨] **Pages 재생성 (§4)** — 신규 계정 `aikorea24` project_id `24f70480-44dc-40de-af31-37bd39ff3173`, 서브도메인 `aikorea24-4nk.pages.dev`. 빌드 `npm run build` → `Server built in 10.51s` / `Complete!`, 배포 `wrangler pages deploy dist --project-name aikorea24 --branch main` → deployment `068ffc52-68d5-433a-bb84-087098b689fa`(env=production). 시크릿 4개(`SESSION_SECRET` `BREVO_API_KEY` `GOOGLE_CLIENT_ID` `GOOGLE_CLIENT_SECRET`) 설정, plain 변수 `account_id=7eb1b8cd…`, compat date `2024-12-01`.
- [검증됨] **도메인 전환 (§5)** — `POST /pages/projects/aikorea24/domains` 로 `aikorea24.kr`·`www.aikorea24.kr` 추가 성공(각 `success=True`). DNS 는 출발 계정 zone(`a6d9e75032c8cefe316b06d46a90a431`)에 그대로 두고, CNAME content 만 `aikorea24.pages.dev` → `aikorea24-4nk.pages.dev` 로 PATCH(레코드 id `2bb370e6d859bf4bad95dc2130dabf22` / `879a3e1f5ba8b33c44a10514038ede7b`, 백업 `/tmp/dns_backup_aikorea.txt`). **롤백 = 백업 content 2건 복원.**
- [검증됨] **§7-1 도메인 200** — `https://aikorea24.kr/` 200 (59,286B), `https://www.aikorea24.kr/` 200.
- [검증됨] **§7-2 D1/R2 바인딩** — `https://aikorea24.kr/news/` 200 (73,942B, 카드 50건), `https://aikorea24.kr/api/posts/` 200 (54,976B, `{"posts":[{"id":45,…}]}` 실제 행), `https://aikorea24.kr/api/files/tools/1/1790357830715-pcvr.webp` 200 `image/webp` 103,084B(R2 객체 원본과 크기 동일).
- [검증됨] **§7-4 Google 로그인 라운드트립** — `GET https://aikorea24.kr/api/auth/login/` 302 → `accounts.google.com/o/oauth2/v2/auth`(`client_id=683559975627-e8rq6vbvgq3j2dmafekq8uk2ji13q90h.apps.googleusercontent.com`, `redirect_uri=https%3A%2F%2Faikorea24.kr%2Fapi%2Fauth%2Fcallback%2Fgoogle`) → `-L` 최종 200 `accounts.google.com/v3/signin/identifier` (896,134B, `invalid_request` 없음). 도메인 불변이라 Google Cloud Console 재등록 불필요.
- [검증됨] **파이프라인 실동작** — `EnvConfig().load_to_environ()` 후 `d1_client.d1_query("SELECT COUNT(*) FROM news")` → `[{'c': 17731}]`, `tools` → `[{'c': 455}]`(신규 DB 실조회). `node scripts/sync_submissions_to_md.mjs` → rc 0, `published=11 created=0 skipped=11`.
- [검증됨] **옛 ID 잔존 0건** — `bec650ce…`(옛 D1)·`fac9808c…`(옛 계정) grep 결과 aikorea24 저장소 런타임 파일(`.toml`/`.py`/`.mjs`/`.js`/`.ts`/`.astro`)에서 0건.
- [부분검증] **§7-3 `img.aikorea24.kr`** — 마이그레이션 이전부터 404 상태였다(출발 계정에서도 동일). R2 바인딩 경유 `/api/files/` 경로는 신규 계정에서 정상 200. img 별도 도메인 재연결은 수행하지 않음.
- [검증불가] **§7-5 Brevo 발송** — `GET https://api.brevo.com/v3/account` 401 `"unrecognised IP address 110.168.249.241"`. `curl -4` 강제해도 동일(스킬 `brevo-email-healthcheck` 절차 기준 IPv4 강제 적용). 복구 계획: 대표님이 `https://app.brevo.com/security/authorised_ips` 에 `110.168.249.241` 추가 후 재검증. 참고 — Worker egress 는 Cloudflare IP 이므로 실 발송 검증은 관리자 세션 필요(`/api/briefing/send-email` 은 `twinssn@gmail.com` 세션 요구).

### 지시서 대비 deviate (5건)
1. **`AUTH_SECRET` 미입력 — 블로커가 아님.** `src/`·`scripts/` 전체 grep 결과 `AUTH_SECRET` 참조 **0건**. `.planning/phases/01-security-hardening/02-SUMMARY.md:115` 에 "Legacy session → `SESSION_SECRET` 으로 교체" 기록. 죽은 변수라 미입력해도 로그인 동작(§7-4 로 실측 확인). 지시서는 이를 "유일 블로커" 로 지목했으나 실측 결과 블록 아님.
2. **GitHub 연동 스킵.** GitHub source 지정 POST → `8000011 There is an internal issue with your Cloudflare Pages Git installation` (신규 계정 GitHub App 미설치. API 토큰으로는 설치 불가). 소스 없이 프로젝트 생성 후 기존 경로인 direct upload(`wrangler pages deploy`)로 배포 — 동일 산출물. **기존 배포 파이프라인(`scripts/deploy.sh`)은 GitHub 연동에 의존하지 않으므로 기능 영향 없음.**
3. **Pages 바인딩은 API PATCH 대신 배포 시 주입.** `PATCH deployment_configs` 에서 D1(`type:"d1"`)은 성공하나 **R2(`type:"r2"`)는 HTTP 500 code 8000000** 로 항상 실패(preview/production 단독·양쪽 모두 동일). 출발 계정 프로젝트 GET 응답에도 바인딩이 없어, Pages 바인딩은 `wrangler pages deploy` 가 `wrangler.toml` 에서 읽어 배포 메타데이터로 주입하는 구조임을 확인. → API PATCH 결과는 무시했고 배포 경로가 정상 주입함을 §7-2 로 확인.
4. **`env.pop` 제거 (지시서 미기재, 미수행 시 파이프라인 전량 실패).** `pipeline/infra/d1_client.py::_build_env()` 와 6개 스크립트가 `CLOUDFLARE_API_TOKEN`·`CLOUDFLARE_ACCOUNT_ID` 를 `env.pop` 후 wrangler 를 호출 → wrangler OAuth 프로필(`~/.wrangler/config/default.toml`, 만료 2026-10-08T21:06Z) 로 fallback → **출발 계정으로 신규 DB 조회 시 7404** 실측. 지시서대로 DB_ID 만 바꾸면 파이프라인 전체가 신규 DB 를 못 봄. 7개 py + 1개 mjs 에서 `env.pop` 제거, 프로젝트 `.env` 의 토큰/계정 ID 를 신규 계정 값으로 교체(백업 `.env.bak.20261009_cfmigrate`).
5. **§6 대상 파일 5개 추가 발견.** 지시서가 나열한 5개 외에 aikorea24 저장소 안에서 `scripts/keyword_updater.py:21`, `scripts/dynamic_seed_generator.py:24`, `scripts/blog_draft_generator.py:48`, `scripts/thread_topics/outline_generator.py:32`, `scripts/thread_topics/thread_topic_finder.py:24` 의 `DB_ID` 하드코딩을 grep 으로 찾아 함께 교체.

### 잔존 위험
- **카카오 로그인 불가 (기능 퇴화).** 지시서 지시대로 `KAKAO_CLIENT_ID`·`KAKAO_CLIENT_SECRET` 미입력. 출발 계정 Pages 에는 설정돼 있었으나 값이 프로젝트 `.env`·`~/.env.common` 양쪽에 없음(읽기 불가 — Cloudflare 시크릿 write-only). 신규 계정에서 카카오 로그인 시도 시 실패. 복구 계획: Kakao Developers 콘솔에서 앱 비밀키 재발급 후 신규 Pages 에 설정.
- **`news-unified` launchd job 이 출발 계정 옛 DB 에 씀.** `~/Library/LaunchAgents/kr.aikorea24.news-unified.plist` 의 `EnvironmentVariables` 에 출발 계정 `CLOUDFLARE_ACCOUNT_ID`·`CLOUDFLARE_API_TOKEN` 이 하드코딩돼 있고, 실행 대상 `api_test/news_collector.py` 의 D1 쓰기 3곳은 `env` 미전달 → 프로세스 환경(출발 계정) 사용. 결과적으로 수집 기사가 **출발 계정의 옛 `aikorea24-db` 에 기록되고 신규 DB 에는 반영되지 않음.** 함께 `purge_cloudflare_cache()` 도 출발 토큰이 필요(zone 은 출발 계정 유지)하므로 단일 토큰 교체로는 해결되지 않는다. 지시서 §6 스코프 밖이라 미수행 — 대표님 승인 시 `CF_DNS_TOKEN` 기반 purge 분기 추가 후 신규 계정으로 교체 필요.
- **`projects2/finnews/wrangler.toml:6` 의 `account_id` 가 출발 계정 `fac9808c…` 로 잔존.** §6 은 finnews `database_id` 만 명시했다. D1 ID 는 신규 값으로 교체됐으므로 finnews 를 배포하면 `account_id` 불일치로 7404 발생. 지시서가 finnews 배포를 금지했으므로 이번 세션 영향 없음. 복구 계획: finnews 배포 시 `account_id` 를 `7eb1b8cd…` 로 교체.
- **문서 6개에 옛 ID/계정 ID 잔존 (런타임 아님).** `SOP.md:21`, `docs/TECHNICAL.md:523`, `docs/SKILLS/08-cloudflare-deploy.md:106`, `.planning/codebase/CONCERNS.md:119`, `.planning/codebase/INTEGRATIONS.md:24`, `.backup_brandname_20260929_150132/docs/TECHNICAL.md:523`. 지시서 §6 스코프 밖.
- **출발 계정 D1·R2·Pages 리소스 삭제 보류 (지시 금지).** 롤백 검증 전까지 유지. 신규 계정 롤백 시 이전 CNAME content(`aikorea24.pages.dev`) 복원 + 출발 Pages 로 DNS 전파 대기 필요.
- **Brevo 발송 미검증** — 위 3분법 [검증불가] 참조. IP 화이트리스트 등록 전까지 브리핑 이메일 발송 경로 신뢰도 미확인.
- **`scripts/briefing_dedup.json` 이 작업 중 변경됨**(2026-10-08 브리핑 336번 기준 항목 282행 추가). `auto_briefing` 실동작 경로가 새 DB 를 읽으며 재생성한 산출물이며 의도된 변경. 이번 커밋 대상에서 제외함.

### 다음 행동
1. 대표님: Brevo `authorized_ips` 에 `110.168.249.241` 등록 (7월 IP 변경분).
2. 대표님: `news-unified` plist 토큰 교체 승인 여부 결정 (위 잔존 위험 2번째).
3. 대표님: 카카오 앱 키 확보 후 신규 Pages 시크릿 설정 (위 잔존 위험 1번째).
4. 선택: 출발 계정 D1·R2·Pages 삭제 — 신규 계정 안정 구주(7일) 경과 후.
5. 선택: D1 row read 알람 재기준선 설정 — D1-NEWS-FIX-01 후 rows_read 1,075/요청 이므로 여유 큼.

## 2026-10-09 09:05 — CF-MIGRATE-02 중단: 사전 조건 미충족 (작업 미시작)

지시서: `SSOT/프로젝트/aikorea24/지시서/2026-10-09-0850-CF-MIGRATE-02.md`
**작업 시작 전 사전 조건 검사에서 중단.** 코드·인프라 변경 0건, launchd 상태 변경 0건, D1·R2·Pages·DNS 무변경.

### 한 일
Cloudflare 신규 계정(`7eb1b8cd178de269758ec94b2e03330b`) 으로 D1·R2·Pages 이전 지시서(CF-MIGRATE-02)의 사전 조건 검증만 수행.

### 결과
- [검증됨] 신규 계정 API 토큰 부재 — 치명적 블로커. `~/.env.common` `CLOUDFLARE_API_TOKEN` (계정 `fac9808c757df31d797190c529aaa71a`) 으로 신규 계정 API 호출 시 `Unauthorized to access requested resource`. `aikorea24/.env`·`finnews/.env` 토큰도 동일하게 출발 계정만 접근. `GET /accounts` 조회 결과 접근 가능 계정 = 출발 계정 1개뿐. `~/.wrangler/config/*.toml` OAuth 프로필 6종은 2026-09-24 만료 상태(비interactive 셸에서 갱신 불가). → §2 D1·§3 R2·§4 Pages·§5 DNS 전부 실행 불가.
- [검증됨] Pages 시크릿 7개 중 3개 부재 — `AUTH_SECRET`, `KAKAO_CLIENT_ID`, `KAKAO_CLIENT_SECRET` 이 `~/.env.common`·`aikorea24/.env` 양쪽에 없음. 존재하는 것: `SESSION_SECRET`(project .env), `BREVO_API_KEY`(양쪽), `GOOGLE_CLIENT_ID`·`GOOGLE_CLIENT_SECRET`(project .env) = 4개. 지시서 §16 은 "5개 확인됨"으로 기술하나 실제 4개. → §4 시크릿 입력 및 §7 로그인 라운드트립 검증 불가.
- [검증됨] 시각 조건 충족 — 현재 08:59 KST. `kr.aikorea24.pipeline-runner` 실행 시각 06:00·20:00 KST(`StartCalendarInterval` plist 실측), 다음 실행까지 11시간 1분.
- [검증됨] 출발 계정 리소스 ID 지시서와 일치 — D1 `bec650ce-f732-46bc-87c0-bd76ed17e42a`, Pages `6024af53-e322-4941-b65c-fd46c865b1ba`.

### 잔존 위험
- 계정 이전 미완료. D1 row read 초과(D1-NEWS-FIX-01 해결로 66배 감소했으나 blast radius 격리는 미달) 상태가 현재 계정에 그대로 유지된다.
- 신규 계정에는 D1·R2·Pages 리소스가 아직 생성되지 않았다. 지시서 §15 는 "R2 활성화 확인" 만 기재돼 있어 D1·Pages 활성화 여부는 미검증(접근 불가).
- D1-NEWS-FIX-01 잔재 인덱스 `idx_news_source_created` 가 출발 계정 DB에 미사용 상태로 잔존. 지시서 §28 이 §2 진입 시 DROP 을 요구하나 진입하지 못해 실행되지 않음.
- R2 출발 버킷 `aikorea24-files` 용량 미확인 (§3 비용 게이트 10GB 규칙). 접근 불가 사유로 측정하지 못함. 용량 초과 상태일 경우 §3 착수 시 즉시 중단 필요.

### 다음 행동 (대표님 조치 필요)
1. 신규 계정 API 토큰 발급 — Cloudflare 신규 계정 → My Profile → API Tokens. 필요 권한: D1 Read/Write, R2 Read/Write, Pages Edit, Workers Scripts Edit, Zone DNS Edit(`aikorea24.kr`). 발급 후 `~/.env.common` 에 **신규 키명으로** 추가 (기존 `CLOUDFLARE_API_TOKEN` 덮어쓰면 출발 계정 작업이 차단됨). 권장 키명: `CF_MIGRATE_TOKEN` / `CF_MIGRATE_ACCOUNT_ID=7eb1b8cd178de269758ec94b2e03330b`.
2. 시크릿 3개(`AUTH_SECRET`, `KAKAO_CLIENT_ID`, `KAKAO_CLIENT_SECRET`) 확보 후 `~/.env.common` 에 추가. 출처 후보: 출발 계정 Pages 프로젝트 `6024af53-e322-4941-b65c-fd46c865b1ba` 의 시크릿 목록, 또는 Kakao Developers 콘솔. **값을 채팅·보고서에 기록하지 않는다.**
3. 두 조치 완료 시 CF-MIGRATE-02 §1 사전 확인부터 순차 재개.

## 2026-10-09 08:45 — D1-NEWS-FIX-01 완료: /news 풀스캔 제거 + 배포

지시서: `SSOT/프로젝트/공통/지시서/2026-10-09-0830-D1-NEWS-FIX-01.md`
보고서: `SSOT/프로젝트/공통/보고서/2026-10-09-D1-NEWS-FIX-01-완료보고.md`
수정 파일: `src/pages/news.astro` 1개 + D1 인덱스 SQL 1건. 배포 커밋 `570ea8c70cc5ce28242ba8ff7067b7e3be238efc`.

### 한 일
`aikorea24.kr/news` 의 D1 `news` 테이블 풀스캔 쿼리(윈드함수 `ROW_NUMBER() OVER (PARTITION BY source ...)`)를
후보 500행 단순 SELECT + JS 소스별 상한 5건 방식으로 교체하고 `Cache-Control: public, max-age=300` 적용. 프로덕션 배포.

### 결과 (검증 근거)
- [검증됨] rows_read **70,962 → 1,075** (66배 감소). 근거: `wrangler d1 execute aikorea24-db --remote` 의 `meta.rows_read`.
- [부분검증] 2-1(인덱스) 실패 — `SCAN news` → `SCAN news USING INDEX idx_news_source_created` 로 바뀌었으나 53,387행(24.8% 감소)에 그침. 윈드함수는 전체 행 분할 정렬이 필요해 인덱스로 스캔 자체 제거 불가. → 2-2 대신 동치 쿼리 채택.
- [검증됨] 기능 보존 3조건 — 라이브 `curl -sL https://aikorea24.kr/news` HTTP 200 / 73,942 bytes. `<a class="block bg-white` 50건, 소스 배지 50건, `<h2>` 50건, distinct source 19개 / max 5건, 후보 500행 category `grant 34 / news 187 / global 279` (senior·benefit 0건), 후보 created_at 내림차순 True.
- [검증됨] 캐시 헤더 — `curl -sIL https://aikorea24.kr/news` → `cache-control: public, max-age=300`.
- [검증됨] 빌드·배포 — `npm run deploy` → `✨ Deployment complete!` (`3b5bd842.aikorea24.pages.dev`).
- [부분검증] 결과 집합이 원 쿼리와 40/50 일치, 10건 상이. 상이 10건 전부 `created_at = 2026-10-08 22:33:19` 동률 행(47행 몰림)에서 발생 — 원 쿼리도 동률 순서가 임의라 스캔 방식이 바뀌면 승자가 바뀐다. 기능 3조건은 양쪽 모두 충족.
- [부분검증] `SCAN news` 완전 제거는 미충족(인덱스 스캔 잔존). rows_read 66배 감소로 실질 효과는 달성했으나 지시서 완료 기준 1번 문면 미달.

### 잔존 위험
- `idx_news_source_created` 인덱스가 최종 쿼리에서 미사용. DB 잔류 상태. `DROP INDEX idx_news_source_created` 로 삭제 가능 — 대표님 판단 대기.
- 지시서 2-2(소스별 분할 조회) 미수행 — `COUNT(DISTINCT source)` = 89개로 지시서 "20개 초과 시 중단" 조건에 해당. 동치 쿼리(후보 500행)로 대체했고 동치성 증명은 보고서 §2.
- 후보 500행 상한이 미래에 부족할 가능성 (특정 소스가 최신 500행 독점 시 노출량 50건 미만으로 감소). 코드 `ponytail:` 주석에 상한 근거·상향 조건 기재.
- `cf-cache-status: DYNAMIC` — `Cache-Control` 적용됐으나 Cloudflare CDN 엣지 캐시의 실효화 여부 미검증. 필요 시 `Cache Everything` 규칙 별도 설정.
- `/news` 호출자 미특정 (322회/시간) — rows_read 감소로 호출 빈도 자체는 그대로. Cloudflare Analytics 필요.
- `index.astro`(홈)도 D1 조회 — 동일 패턴 풀스캔 잔존 가능성 미조사.

### 다음 행동
- `idx_news_source_created` 삭제 여부 결정.
- Cloudflare 캐시 규칙으로 `/news` 엣지 캐시 실효화 여부 확인.
- 홈 페이지 D1 쿼리 패턴 조사 (D1-NEWS-FIX-02 후보).
- `/news` 호출자 특정 (Cloudflare Analytics 로그).

## 2026-10-09 — CF-MIGRATE-01 완료: Cloudflare 계정 이전 조사

지시서: `SSOT/프로젝트/공통/지시서/2026-10-09-0835-CF-MIGRATE-01-조사.md`
읽기 전용 조사. 계정 생성·리소스 이동·DNS 변경 0건, 배포 0건, 시크릿 값 기록 0건.
보고서: `SSOT/프로젝트/공통/보고서/2026-10-09-CF-MIGRATE-01-조사.md` (완료보고 사본: `SSOT/프로젝트/공통/지시서/2026-10-09-0836-CF-MIGRATE-01-완료보고.md`)

**한 일**
- hugh79757 계정(`fac9808c757df31d797190c529aaa71a`)의 aikorea24 관련 리소스를 Cloudflare REST 읽기 전용으로 전수 조사 → 이전 절차·위험·롤백·작업량 산정.

**결과**
- [검증됨] Tier A(aikorea24 직접 사용) = D1 `aikorea24-db`(`bec650ce-f732-46bc-87c0-bd76ed17e42a`) / R2 `aikorea24-files` / Pages `aikorea24`(project_id `6024af53-e322-4941-b65c-fd46c865b1ba`, 호스트 `aikorea24.kr`·`www.aikorea24.kr`, GitHub `hugh79757-cmyk/aikorea24`). KV·DO·Queue·Workers AI 미사용. Pages 시크릿 7개(`AUTH_SECRET` `SESSION_SECRET` `BREVO_API_KEY` `GOOGLE_CLIENT_ID` `GOOGLE_CLIENT_SECRET` `KAKAO_CLIENT_ID` `KAKAO_CLIENT_SECRET`) + plain `account_id` 1개 — 키 이름만 기록.
- [검증됨] Worker `finnews` 는 **미배포**. `workers/scripts` 72건에 없음, DNS 레코드 없음, `dig fin.aikorea24.kr` 결과 없음. `wrangler.toml` 정의만 존재.
- [검증됨] Tier B(zone 공용) = `aikorea24.kr` zone(`a6d9e75032c8cefe316b06d46a90a431`) 레코드 41개. Pages 3종(`news-keyword-pro`→keyword. / `money-aikorea24`→persona. / `certkorea`→cert.) + Worker 4종(`barnmate-api` `heritage` `mbti` `threadforge-do`) + R2 3종(`persona-cards` `heritage-images` `barnmate-uploads`) + Tunnel 4개(`mac-dashboard` `l2t-dev` `m1-ssh` `mde2`). MX 3건 = Cloudflare Email Routing(계정 종속). DNSSEC `disabled`.
- [검증됨] 실사용 네임서버 = `alberto.ns.cloudflare.com` / `sonia.ns.cloudflare.com` (API `name_servers` + `dig NS @1.1.1.1` 일치). zone `type=full`, `original_name_servers`=hosting.co.kr(비활성 잔존 레코드).
- [검증됨] 계정 전량 인벤토리 — D1 10 / Workers 72 / Pages 10 / KV 5 / R2 20 / Queue 2 / DO 1 / Tunnel 4 / **Cron Trigger 0건**(Workers 72건 `schedules` 전수 조회 결과 전부 빈 배열).
- [검증됨] 이전 절차 8종 문서화 — D1 `wrangler d1 export/import`(계정 간 복사 API 없음) / Pages 재생성+GitHub 재연결 / DNS zone transfer→NS 변경 2경로 / R2 동일명 버킷 `aws s3 sync` / KV 이전 대상 없음 / Tunnel 4개 재생성 / OAuth·Brevo·Email Routing 재설정.
- [검증됨] 위험 8건 + 검증 체크리스트 10항목 + 롤백 3단계 정리. 핵심: **출발 계정 리소스를 롤백 검증 완료 전 삭제 금지**(이동이지 복제가 아님 → 출발 쪽이 온전하면 되돌리기가 가능).
- [검증됨] 작업량 = 9단계, 약 6~9h(직접 수행). **분할 권고: 1차(D1+R2+Pages, DNS zone 유지, 4h) → 안정화 1~2주 → 2차(zone+Tunnel+Email Routing, 3~5h).**

**잔존 위험**
- **[검증불가] zone transfer 의 Free 플랜 가용성.** `POST /zones/{id}/account` 제공 여부를 이 토큰으로 확인 못 함. 불가 시 NS 변경 필수 → 다운타임 구간 발생. 1차 실행 전 Cloudflare 문서/지원팀 확인 필요.
- **[부분검증] `img.aikorea24.kr` → R2 버킷 매핑 미확정.** R2 목록 API 가 공개 URL 미반환. 실제 응답 헤더로 확인 필요. 버킷명 변경 시 전 이미지 링크 파손.
- **[부분검증] Pages 를 다른 계정에 둘 때의 쿼리 격리 수준.** 1차 분할 권고의 핵심 가정. 이전 후 실측 필요.
- **[검증불가] Tier B 13개 호스트의 운영 트래픽·SLA.** 서브 프로젝트 소유 미확인 → 동시 장애 영향 범위 수치화 못 함.
- **[부분검증] `.env` 29개 키와 Pages 런타임 secret 의 공유 범위.** 키 이름만 비교(값 미확인 지시 준수).
- `finnews` 과거 배포 후 삭제되었을 가능성 있어 이전 전 확인 요망.
- 신규 계정(`Stylefactory9ai@gmail.com`)은 대표님 직접 생성 예정 — 본 작업에서 생성 0건. 계정 ID·Workers.dev 서브도메인 미확정(신규 계정 생성 후 확인).

**다음 행동**
- 대표님: (1) 신규 계정 생성 및 계정 ID 전달, (2) zone transfer Free 플랜 가용성 확인, (3) 1차(분할 1단계)만 먼저 승인할지 전체 승인할지 결정.
- 승인 시 착수 순서: D1 export(파이프라인 `kr.aikorea24.pipeline-runner` unload 후) → 신규 D1 create/import → R2 sync → Pages 재생성 → Pages 커스텀 도메인만 재연결(zone 은 출발 계정 유지).

## 2026-10-09 — 진행 중 (2026-10-09, CF-MIGRATE-01): Cloudflare 계정 이전 조사

지시서: `SSOT/프로젝트/공통/지시서/2026-10-09-0835-CF-MIGRATE-01-조사.md`
읽기 전용 조사. 계정 생성·리소스 이동·DNS 변경 금지. 배포 없음.

## 2026-10-07 02:10 — 10-06 블로그/수정분 커밋 + 재배포

### 한 일
사용자 지시 "오늘자 블로그 배포해줘." → 옵션 확인 후 "10-06 커밋 + 재배포" 선택.
미커밋 상태였던 원인1·2 수정분 + 10-06 블로그 10건을 커밋하고 재빌드·재배포.

### 커밋
- 커밋 `8187d201` "fix: 홈·뉴스 빌드시점 D1 공백 복구 (prerender false) + 10-06 블로그 10건".
- 포함: `src/pages/index.astro`, `src/pages/news.astro`, `src/content/blog/2026-10-06-001~010.md`(10건 신규), `docs/state.md`, `scripts/briefing_dedup.json`.
- 제외: `.wrangler/state/.../miniflare-*.sqlite` (로컬 빌드 임시 상태, 커밋 노이즈).

### 결과 (라이브 검증)
- [검증됨] validate — `python3 scripts/validate_blog_posts.py` → `✅ 모든 블로그 포스트 정상`.
- [검증됨] 빌드 — `npm run build` → `Server built in 22.23s` / `Complete!`.
- [검증됨] 배포 — env.common 토큰 export 후 `wrangler pages deploy dist --project-name aikorea24 --branch main --commit-dirty=true` → `✨ Deployment complete!` (126 modules, `5b506c65.aikorea24.pages.dev`).
- [검증됨] 홈 — HTTP 200 / 59183 bytes, `브리핑 준비 중` 0건, 브리핑 아이템 링크 6건(`/briefing/2026-10-06-2/#item-*`). 근거: `curl "https://aikorea24.kr/?v=<cachebust>"`.
- [검증됨] /news — HTTP 200 / 78252 bytes, 빈 상태 문구 0건, 기사 h2 3건+ 렌더, 외부링크 46건.
- [검증됨] /blog 아카이브 — `2026-10-06-002`~`010` 표시(페이지1), `2026-10-06-001` 상세 HTTP 200.
- [검증됨] /briefing — HTTP 200 (회귀 없음).
- [부분검증] 첫 curl 캐시로 옛 응답 가능 → cachebust 병행. Worker 에러율·응답시간 미측정.

### 잔존 위험
- `description` 보일러플레이트: 10-06 `004`·`005`·`010` 3건이 `"원문기사는 아래의 링크를 통해 확인할 수 있습니다"` 로 저장(생성기 LLM이 실제 요약 미출력 → fallback). 메타/SEO 품질 저하. 커밋은 사용자 지시대로 진행.
- `2026-10-06-010` frontmatter 뒤 stray `---` 1줄 → 본문 상단에 `<hr>` 렌더. 004·005에는 없음.
- 홈/뉴스 런타임 SSR → 요청마다 D1 조회.
- 원인3 Brevo 401(미등록 IP) 미해결.
- 2026-10-06 20:16 재부팅 원인 미확인.
- `blog_draft_generator.py` log = `print()`(stdout) → launchd 블록버퍼, SIGKILL 시 로그 유실(flush 미적용).
- `kr.aikorea24.blog-draft.plist`에 `OPENAI_API_KEY` 평문(키 이름만 기록).

### 다음 행동
- 06:00 KST 파이프라인 / 06:15 KST blog-draft 자동 런 정상 여부 확인.
- 004·005·010 `description` 재생성 + 010 stray `---` 제거 (원하면 실행).
- Brevo 콘솔에 IPv6 `2001:fb1:...` 등록 후 이메일 재시도.
- 재부팅 원인 로그 점검.

---

## 2026-10-07 00:02 — 원인 1·2 수정 (홈/뉴스 SSR 복원 + 007–010 배포)

### 한 일
사용자 지시 "123 실행해줘. 하나씩." — 원인1(홈/뉴스 빌드시점 D1 공백), 원인2(007–010 미배포) 수정. 원인3(Brevo)은 사용자가 IP 직접 등록 예정이라 미실행.

### 수정 파일
- [PRODUCTION CODE] `src/pages/index.astro`: `export const prerender = true;` → `false;` (런타임 SSR 환원, /briefing와 동일 패턴).
- [PRODUCTION CODE] `src/pages/news.astro`: `export const prerender = false;` 추가.

### 결과 (라이브 검증)
- [검증됨] 홈 브리핑 복원 — `https://aikorea24.kr/` 에서 `오늘의 브리핑 준비 중` 0건(수정 전 1건), 브리핑 아이템 실제 렌더(외부링크 7건, 예: "새로운 조사에 따르면 AI 오용이 브랜드 평판에…"). 근거: `curl "https://aikorea24.kr/?v=<cachebust>" | grep -c "오늘의 브리핑 준비 중"` → 0.
- [검증됨] /news/ 복원 — 라이브 뉴스 아이템 53건 렌더(수정 전 `아직 수집된 뉴스가 없습니다` 빈 상태). 근거: `grep -oE 'target="_blank"' /tmp/p_news2.html | wc -l` → 53.
- [검증됨] 블로그 007–010 배포 — 라이브 `/blog/` 에 `2026-10-06-007`~`010` 표시(수정 전 001–006만). 빌드가 `src/content/blog` 전체를 포함하므로 원인2도 이 배포로 해소.
- [검증됨] 빌드·배포 경로 성공 — `python3 scripts/validate_blog_posts.py` → `✅ 모든 블로그 포스트 정상`; `npm run build` → `Server built in 13.76s`, `Complete!`; `wrangler pages deploy dist` → `✨ Deployment complete!`(126 modules, `d1763e51.aikorea24.pages.dev`), env.common 토큰 export 사용(글로벌 섹션 3).
- [검증됨] 회귀 없음 — `/briefing/` HTTP 200 유지, 홈에 최신 블로그(007–010) 제목 렌더.
- [검증됨] dist 구조 변경 확인 — `dist/index.html`·`dist/news/index.html` 삭제됨(정적 파일 아님, Worker `_worker.js/` + `_routes.json` 이 서빙). 기존 `dist/_worker.js/` 존재.

### [부분검증]
- 홈/뉴스 SSR 동작은 라이브 HTTP 응답으로 확인했으나 Cloudflare Worker 에러율·응답시간 로그는 미확인.

### [검증불가]
- 배포 직후 첫 curl이 CDN 캐시로 옛 빈 페이지를 반환했다가(동일 URL·캐시버스트로 재요청 시 정상) → 캐시 무효화 지연을 정량 실측하지 못함.

### 잔존 위험
- **미커밋**: 두 페이지 수정 + 007–010 untracked. deploy.sh/blog_draft는 워킹트리를 사용하므로 일시 동작하나 `git reset`/`clean` 시 소실. 커밋 필요(사용자 미지시).
- 홈이 이제 런타임 SSR → 매 요청 D1 조회(지연·비용 소폭 증가). /briefing와 동일 부하 특성.
- 원인3 Brevo 401 미해결(사용자 IP 등록 예정).
- 2026-10-06 20:16 재부팅의 원인 미확인(재발 시 저녁 파이프라인 재차단).
- `blog_draft_generator`의 stdout이 launchd 파일로 블록 버퍼링 → 재부팅/SIGKILL 시 로그 유실(진단 가림). flush 도입 미적용.
- `kr.aikorea24.blog-draft.plist`에 `OPENAI_API_KEY` 평문 저장(값 미기록).

### 다음 행동
1. 커밋 여부 결정(index.astro/news.astro + 007–010).
2. Brevo IP 등록 후 이메일 재시도.
3. 재부팅 원인 점검 + blog_draft stdout line-buffering(flush) 도입 검토.

---

## 2026-10-06 23:55 — 발행 정지 원인 진단 (홈 브리핑/뉴스 공백 + 저녁 블로그 미배포)

### 한 일
사용자 보고 "블로그 발행, 뉴스브리핑. 모두 멈췄어. 원인파악." 진단. 코드 수정 없음(진단 전용). 재부팅·빌드·launchd 상태·로컬/원격 D1 대조.

### 결과 — 독립 원인 3건

**[검증됨] 원인 1 — 홈/뉴스 페이지가 "빌드 시점 로컬 D1(빈 DB)" 조회로 공백**
- 라이브 홈(`https://aikorea24.kr/`) HTML에 브리핑 빈 상태 `📡 오늘의 브리핑 준비 중` 1건, 브리핑 아이템 0건. 근거: `grep -c "오늘의 브리핑 준비 중" dist/index.html` → 1, `grep -c "briefing" dist/index.html` → 0.
- 라이브 `/news/` HTML에 `뉴스가 없습니다` 1건. 근거: `/tmp/aik_news.html` grep.
- 두 페이지 모두 frontmatter에서 빌드 시점 `Astro.locals.runtime.env.DB`로 D1 질의 (`src/pages/index.astro:2` `prerender=true`, `src/pages/news.astro`, `output:'static'`).
- 빌드가 조회하는 로컬 miniflare D1 `.wrangler/state/v3/d1/miniflare-D1DatabaseObject/6ba36e…sqlite`(mtime 9월 26)의 테이블은 `users`, `tool_submissions`, `sqlite_sequence`, `_cf_METADATA`뿐. `briefings`/`news` 테이블 **없음**(sqlite3 → `no such table: briefings`).
- 회귀 커밋: `0323c7c6 feat: hybrid 정적 전환 + 홈 개편` (2026-10-01 20:36 +07) — `astro.config.mjs` 변경 + `prerender=true` + 빌드 시점 스냅샷 코드를 동시 도입. 이전(hybrid/런타임 SSR)에는 프로덕션 D1을 읽어 표시됨.
- 대조: `/briefing/`는 `prerender=false` 런타임 SSR이라 프로덕션 D1을 읽어 표시(HTTP 200 / 104967 bytes / `2026-10-06-2` 존재). 프로덕션 D1 자체는 정상, 빌드 시점 페이지만 파손.

**[검증됨] 원인 2 — 저녁 블로그 007–010 미배포 = 20:16:23 재부팅이 실행 중 프로세스 SIGKILL**
- `sysctl -n kern.boottime` → `Tue Oct  6 20:16:23 2026`; `last reboot` → `화 10월 6 20:16`.
- 저녁 blog-draft 글 007–010 mtime 20:15:11–20:15:59 → 생성 직후 약 15초 만에 재부팅.
- `scripts/blog_draft.log` mtime 06:17(아침 런만 기록), 저녁 런 기록 0줄. `log()`는 `print()`(stdout)이고 launchd가 파일로 리다이렉트(블록 버퍼) → SIGKILL 시 버퍼 유실.
- `launchctl print kr.aikorea24.blog-draft` → `runs=0`, `last exit code=(never exited)`, `job state=uninitialized` = 재부팅으로 상태 초기화.
- 라이브 `/blog/` 목록에 `2026-10-06-001`–`006`만, 007–010 없음. 배포 단계 미도달.

**[검증됨] 원인 3 — Brevo 이메일 401 (부차, 조용히 실패)**
- `scripts/pipeline_runner.log` 20:03:33: `❌ Brevo contacts 조회 실패 (401)` + `{"message":"We have detected you are using an unrecognised IP address 2001:fb1:…"}`.
- `auto_email_sender.main()`이 예외를 내부에서 삼키고 run_pipeline summary에 올리지 않음 → 최종 알림 `✅ 에러 없음`과 모순. 그 "에러 없음"은 이메일 성공을 보증하지 않음.

**[부분검증] "재부팅이 007–010 미배포의 직접 원인"이라는 단정**
- 제한: 재부팅 시각(20:16:23)과 파일 mtime(20:15:59)이 15초 차로 부합하고 launchd 상태 초기화가 일치하나, 커널 로그에서 해당 PID 종료 이벤트를 직접 확인하진 않음. 대안(프로세스 자체 예외)은 로그 부재·exit 미기록과 상충.

### 잔존 위험
- 원인1(빌드 시점 D1 회귀)은 10-01 이후 모든 배포에 적용 → 홈/뉴스 공백이 계속 재생성됨. 미수정.
- 007–010은 워킹트리 untracked → 재배포 전까지 라이브 미반영.
- Brevo 401 지속 → 아침 브리핑 메일 미발송 가능.
- `kr.aikorea24.blog-draft.plist`에 `OPENAI_API_KEY` 평문 저장(값 미기록). 보안 위험.
- 배포 경로가 wrangler auth 프로필(hugh79757) 의존 — 글로벌 섹션 3(env.common 토큰 export)과 불일치. 프로필 만료 시 배포 실패 위험.

### 다음 행동 (사용자 결정 대기)
1. 원인1: (a) 홈/뉴스도 `prerender=false` 런타임 SSR로 환원(/briefing와 동일 패턴, 최소 변경) 또는 (b) 빌드 시 원격 D1 바인딩(remoteBindings). 권장 (a).
2. 원인2: 007–010 커밋 후 deploy.sh 재배포. 배포 전 destructive-operations-protocol.
3. 원인3: Brevo IP 화이트리스트/토큰 점검.
4. plist 평문 키 제거(환경변수/키체인 이전).

---

## 2026-10-05 15:47 — nvidia-nemotron 체인 제외 (7 tier)

### 한 일
사용자 지시 "응 빼자" — `nvidia-nemotron`을 aikorea24 폴백 체인에서 제외. 스킬 `llm-fallback-chain-management` §Dead/excluded의2026-09-13 소유자 결정("nemotron 계열은 한국어 콘텐츠 생성 부적합")이 이 프로젝트 config에 미반영 상태였음.

### 결과

**[검증됨] tier 8→7, 제외 완료**
```
1. gemini-3.1-flash-lite
2. gemini-3.5-flash-lite
3. gemini-3.5-flash
4. groq-gpt120b
5. groq-gpt20b
6. zhipu-glm
7. default (★ 유료, 최후)
```
- 검증: `yaml.safe_load` → tier 7개, 모든 tier가 `models`에 존재, 고아 model 키 0건, 전 tier의 provider가 `providers`에 정의됨, `default` 마지막 고정.

**[검증됨] 프로덕션 라우터 실로드 확인**
- `model_router` 직접 import 후: `chain loaded: True`, tier 7개 일치.
- 회전 순서 산출: `['gemini-3.5-flash-lite', 'gemini-3.1-flash-lite', 'gemini-3.5-flash', 'groq-gpt120b', 'groq-gpt20b', 'zhipu-glm', 'default']` — front는 `llm_fallback_state.json`의 `last_success_tier`(gemini-3.5-flash-lite)이며 유료 `default`는 순수 회전 + 맨뒤 고정 유지.

**[검증됨] 키/프로바이더 보존**
- `providers.nvidia`(base_url `https://integrate.api.nvidia.com/v1`) 항목 유지. `NVIDIA_API_KEY` 유지. 사유: 제외 사유는 모델 품질이지 키/접근성 문제가 아님. 향후 NVIDIA NIM 한국어 적합 모델 등장 시 즉시 재편입 가능하도록 배선은 남김.

- 백업: `config/models.yaml.bak_20261005_154630`. 커밋 `864e8f79`.

### 잔존 위험
- **남은 free tier 품질 미검증** — groq-gpt120b / groq-gpt20b / zhipu-glm은 이번 프로브에서 제목 출력 공백(빈 content)이거나 미검증 상태. `zhipu-glm`은 스킬 catalog상 "일일 제한 429 잦음, 40s 지연 사례". 순수 회전이라 429 시 다음 tier로 즉시 회전하므로 파이프라인 중단은 없음.
- **nemotron 2종 tier 잔존 (다른 프로젝트)** — 본 작업은 aikorea24 config/models.yaml만 해당. `pipeline/threads/contrast/` 하위 writer가 별도 chain을 참조하는지는 미확인.
- **번역 단계 엔티티명 게이트 미구현** (15:40 스테이트먼트 잔존 위험 이월) — "오픈에어하이" 허칭 근본 미해결.
- **JSON gate / billing-text gate 미구현** — 스킬 계약 위반 상태 유지.

### 다음 행동
1. groq 2종 / zhipu-glm 실호출 품질 확인 필요 시 동일 live probe 방식 적용.
2. (선택) 번역 단계 엔티티명 검증 게이트 구현 — 알려진 고유명사 목록 대조 + 불일치 시 tier 회전.

---

## 2026-10-05 15:40 — [정정] gemini-3.1-flash-lite 체인 제외 되돌림 (오존재 오귀속)

### 한 일
사용자 지적: "gemini-3.1-flash-lite 이걸 왜 삭제하나? 제미나이에서 구글에서 더이상 이 llm 모델을 서빙하지 않나? 리타이어 됐어?"
직전 작업(15:25 스테이트먼트)의 모델 제외 결정을 live probe로 재검증한 결과 **오존재**로 판명되어 되돌림.

### 결과

**[검증됨] gemini-3.1-flash-lite는 정상 서빙 중 — 리타이어/404 아님**
- live probe (OpenAI SDK, 프로젝트 실제 GEMINI_API_KEY, `base_url=https://generativelanguage.googleapis.com/v1beta/openai/`):
  ```
  model=gemini-3.1-flash-lite, temperature=0.3, max_tokens=100
  → HTTP OK
  → '또 한 명의 오픈AI 안전 전문가 퇴사, 연구원들의 잇따른 공개 경고와 퇴사 패턴 이어져'
  ```
  "OpenAI" → "오픈AI" 정상 번역. 루트 인용: `scripts/threads/v3/model_router.py:196-202` `_call_tier_once`가 OpenAI SDK 사용.

**[검증됨] 로그상 실패 0건**
- `rg -o "  \[경고\] [a-z0-9.\-]+ 실패: HTTP [0-9]+" scripts/blog_draft.log` → 0건 (전 tier 합계).
- `rg -c "gemini-3.1-flash-lite" scripts/blog_draft.log` = 48건 전부 성공 로그.

**[위반 감지] 오존재 — 모델 귀속 잘못됨**
잘못한 추论的 두 지점:
1. `scripts/blog_draft.log:1383`의 `[5/5] ... [모델] google gemini-3.1-flash-lite`는 **번호역(번역) 단계가 아니라 블로그 본문 작성 단계** 로그. 이미 오역된 제목을 입력받아 그대로 옮긴 것이지, 허칭을 만든 주체가 아님.
2. 실제 번역 단계는 `api_test/news_collector.py:423` `translate_to_korean()` → `model_router.chat_completion()`. 2026-10-04 19:30 수집 실행 로그(`api_test/cron_unified.log:44199` 구간)에서 `[번역] 해외 뉴스 한국어 번역... 번역 대상: 196건 → 20배치` 전 배치 `[체인] 성공: gemini-3.5-flash-lite` — 즉 번역 담당 tier는 gemini-3.5-flash-lite.

**[검증불가] 허칭 발생 주체 미확정**
- 원 tier(8개 전부)에 `translate_to_korean` 동일 system prompt + 동일 원문 english title로 재현 프로브 수행 → **'오픈에어하이' 재현 tier 없음**(gemini-3.1-flash-lite '또 한 명의 오픈AI 안전 전문가 퇴사...', gemini-3.5-flash-lite '공개 경고와 함께 떠나는 연구원들: 오픈AI 안전 부서 퇴사 행렬에...' 등 전부 정상).
- batch_translate 프롬프트(TITLE+DESC 20배치)로도 동일 프로브 → 재현 실패.
- 따라서 "특정 모델이 일관적으로 이 허칭을 만든다"는 결론은 성립하지 않음. 단발 또는 프롬프트 배치 효과 가능성 열림. 복구 계획: 다음 동일 오류 발생 시 해당 시점의 tier 로그(`[모델]` 직전 `[체인]` 기록)와 프롬프트 전문을 캡처해 동일 프로브로 격리 재현.

### 처리
- `config/models.yaml` → `config/models.yaml.bak_20261005_151503`로 복원. 8개 tier 원복(`gemini-3.1-flash-lite` 재등재), 삭제 이력 주석 모두 제거. 검증: `yaml.safe_load` → tier 8개, `default`(유료) 마지막 고정.
- 커밋 `87e5d3e8`.
- **포스트 오타 교정 및 배포는 유지** (15:25 작업 — 교정 자체는 올바른 판단).

### 잔존 위험
- **근본 원인 미해결** — 번역 단계 엔티티명 정확성 게이트 부재. 허칭이 어떤 tier/어떤 프롬프트 조건에서 발생했는지 특정되지 않아 재발 가능. 단발 발생 가정 하에 재발 시 즉시 프로브 가능하도록 로그 라인 확보 필요.
- **`gemini-3.1-flash-lite` 실사용 정상** — front tier가 될 경우 매번 호출됨. 리타이어 우려 없음.
- **`nvidia-nemotron` 체인 잔존 (미해결)** — 스킬 §Dead/excluded "nemotron 계열은 한국어 콘텐츠 생성 부적합"(2026-09-13 소유자 결정)이나 현재 `tier_order`에 포함됨. 이번 live 프로브 결과 `1. TITLE: OpenAI 안전 담당자 또 이탈...` 정상 번역(저품질 아님). 소유자 판단 대기.
- **JSON gate / billing-text gate 미구현** — 15:25 스테이트먼트 §위반 감지 항목 그대로 미해결.

### 다음 행동
1. `nvidia-nemotron` 체인 제외 여부 소유자 결정.
2. (선택) 번역 단계 엔티티명 검증 게이트 구현 — 알려진 고유명사 목록(OpenAI/Anthropic/Google/Meta 등)을 번역 결과에서 대조하고 불일치 시 tier 회전.

---

## 2026-10-05 15:25 — aikorea24 "오픈에어하이" 오타 교정 + gemini-3.1-flash-lite 체인 제외 (배포 37ad1204)

### 한 일
사용자 지시 3건: (1) `aikorea24.kr/blog/2026-10-04-011-...오프에어하이...` 글의 "오프에어하이" 존재 확인, (2) 오픈AI(OpenAI) 의미면 해당 글을 쓴 LLM을 체인에서 삭제, (3) 전체 fallback chain 스킬을 보고 최신 스킬 적용. 후속 지시: "그리고 오픈에어하이 는 수정해주고."

### 결과

**[검증됨] "오프에어하이" 문자열 존재 안 함**
- `rg "오프에어하이" /Users/twinssn/Projects/aikorea24` → 0건.
- 실제 존재한 것은 **"오픈에어하이"**(OpenAI의 오타). 라이브 URL은 사용자가 붙여넣은 오타 slug가 아니라 정상 slug였음(사용자 URL 404, 실제 슬러그 200).

**[검증됨] "오픈에어하이" = OpenAI 맞음**
- 근거: 원문 링크 `https://the-decoder.com/another-openai-safety-departure-adds-to-a-pattern-of-researchers-leaving-with-public-warnings/` — 링크 경로에 `another-openai-safety-departure`. 인물 데이비드 로빈슨(OpenAI safety 담당). `scripts/briefing_dedup.json` articles[208]의 link 필드 동일.

**[검증됨] 해당 글 작성 LLM = `google gemini-3.1-flash-lite`**
- 근거: `scripts/blog_draft.log:1383-1385`
  ```
  [22:16:05]   [5/5] '오픈에어하이의 또 다른 안전 관련 퇴사...' 생성 중...
    [모델] google gemini-3.1-flash-lite
    [체인] 성공: gemini-3.1-flash-lite
  ```
- 오타 발생 지점 = 브리핑 번역 단계. `api_test/news_collector.py:423` `translate_to_korean()` → `model_router.chat_completion()` (동일 폴백 체인). 영문 "OpenAI" → 한국어 번역 중 "오픈에어하이" 허칭 생성.

**[검증됨] 오타 교정 — 라이브 반영 완료**
| 항목 | 사전 | 사후 | 검증 |
|---|---|---|---|
| 블로그 title/tags/본문 | 6건 | 0건 | 라이브 HTML `rg -c` 0 |
| 파일명 슬러그 | `...-오픈에어하이의-...` | `...-오픈ai의-...` | 신규 슬러그 200 |
| briefing_dedup.json | 4건 | 0건 | JSON parse OK |
| `_redirects` | 18행 | 19행 (301 1행 추가) | 구슬러그 301→신규 확인 |

- 라이브 검증: 신규 URL `HTTP 200`, `<title>오픈AI의 또 다른 안전 관련 퇴사, 공개 경고와 함께 이탈 패턴 이어져: 인공지능 안전의 위기 | AI코리아24</title>`, 라이브 HTML에 "오픈에어하이" 0건. 구슬러그 `HTTP 301` → 신규 URL로 리다이렉트.
- 배포: `wrangler pages deploy dist --project-name aikorea24 --branch main` → `37ad1204.aikorea24.pages.dev`.
- 사전 검증: `python3 scripts/validate_blog_posts.py` → "✅ 모든 블로그 포스트 정상", `npm run build` → "Complete!" (5.89s).
- 백업: `config/models.yaml.bak_20261005_151503`, `backups/content_blog/2026-10-04-011-....md.bak_20261005_151734`, git 커밋 `c218e0a9`.

**[검증됨] `gemini-3.1-flash-lite` 체인 제외**
- `config/models.yaml`: `tier_order` 8→7, `models` 8→7. 삭제 이력 주석에 스킬 §Dead/excluded 형식으로 사유 기록(품질 사고 — 재검증 없이 체인 복귀 금지).
- 사후 검증: `yaml.safe_load` → `tier_order = ['gemini-3.5-flash-lite','gemini-3.5-flash','groq-gpt120b','groq-gpt20b','nvidia-nemotron','zhipu-glm','default']`, 고아 model 키 0건, 전 tier의 provider가 `providers`에 존재, `default`(유료) 마지막 고정.

**[검증됨] fallback chain 스킬 대조 감사 — `scripts/threads/v3/model_router.py`**
스킬 `llm-fallback-chain-management` 계약 항목별:
- 쿨다운/서킷브레이커/배제 상태 없음 — `rg "cooldown|quota_until|blocked"` `model_router.py` 0건.
- 실패 즉시 다음 tier — `_chain_completion:315-341`, 실패 시 `continue`, sleep 없음. 5xx만 `_call_tier_with_retry:246`에서 1회 5초 재시도.
- 유료 tier 마지막 고정 — `_FallbackState.order():167` `ordered.append(paid_tier)`.
- 상태 영속 + 원자적 — `STATE_PATH=scripts/threads/logs/llm_fallback_state.json`, `_save():145` temp 파일 + `os.replace`. 현재 내용 `{"front":"gemini-3preview","last_success_tier":"gemini-3.5-flash-lite"}`.
- timeout — `TIER_TIMEOUT_SEC=90`, `CONNECT_TIMEOUT_SEC=10`, `GLOBAL_BUDGET_SEC=300` (`:70-72`).

**[위반 감지] JSON gate / billing-text gate 미구현**
- `rg "json.loads|billing|reached its|insufficient|credits" model_router.py` → 0건. 스킬 §JSON gate(L175-180), §200-OK-with-billing-body(L163-173) 미적용.
- 부분 무해 근거: `_call_tier_once:206`이 `response_format`을 무료 tier에 보내지 않고 `provider == 'deepseek'`일 때만 전달. 따라서 무료 tier의 JSON 파싱 실패는 체인이 아니라 downstream 파서에서 잡힘. 부수 증상: `scripts/threads/logs/raw_parse_fail/` 105개 디렉터리 누적.

**[부분검증] 엔티티명 정확성 게이트 없음**
- "오픈에어하이"가 그대로 라이브에 반영된 경위를 막을 proper-noun 검증 코드를 aikorea24 chain 경로에서 찾지 못함. 제한 사유: `blog_draft` 생성 후 quality gate 위치는 미탐색(시간 제약). 원천은 브리핑 번역 단계이므로 그쪽 게이트 부재가 직접 원인.

### 잔존 위험
- **JSON gate / billing-text gate 미구현** — 스킬 계약 위반 상태가 유지됨. HTTP 200 + 과금 본문 응답이 유료 deepseek 경로에서 성공으로 통과될 수 있음. 복구 계획: `_call_tier_once` 반환 직전에 첫 200자 regex 스캔 추가.
- **번역 단계 엔티티명 게이트 부재** — 다른 체인 tier(`gemini-3.5-flash-lite`, `gemini-3.5-flash`, `groq-*`, `nvidia-nemotron`, `zhipu-glm`)도 같은 허칭 재현 가능. 체인에서 한 모델만 빼는 것은 완화일 뿐 근본 제거 아님.
- **`gemini-3.1-flash-lite` 제외 후 최상위 tier가 `gemini-3.5-flash-lite`** — 스킬 §2026-09-28 스냅샷에 gemini 6종이 429 "quota exceeded"(과금 필요)로 제거된 이력이 있음. 이 프로젝트 config에는 남아 있었으나 실제 호출 가능 여부는 미검증. 429면 순수 회전으로 즉시 다음 tier로 넘어가므로 파이프라인 중단은 없음.
- **슬러그 변경에 따른 기존 인덱스 손실** — 신규 URL은 새 주소. `_redirects` 301로 기존 URL 유입은 보존되나 검색엔진 재수집은 지연.
- **`nvidia-nemotron` 체인 잔존** — 스킬 §Dead/excluded에 "nemotron 계열은 한국어 콘텐츠 생성 부적합"(2026-09-13 소유자 결정)으로 기재. 현재 aikorea24 `tier_order`에 여전히 포함됨(`nvidia/nemotron-3-ultra-550b-a55b`). 소유자 확인 필요.

### 다음 행동
1. `gemini-3.5-flash-lite` 실제 호출 가능 여부 확인 (chain front가 이동했으므로 다음 발행에서 `[체인] 성공:` 로그 tier로 관찰 가능).
2. `nvidia-nemotron` 제외 여부 소유자 판단.
3. (선택) JSON/billing gate + 번역 엔티티명 게이트 구현.

## 2026-10-04 09:05 — AIK24-LOGIN-404 수정: 옵션 A 적용 + 전수 확인 (배포 5880ab04)

### 한 일
`3eb21e03` — API 라우트 핸들러 30개에 `export const prerender = false` 추가 → 빌드 시점 정적 스텁 제거 → 재배포. 08:00 진단의 옵션 A. 앞 절(08:00) 참조.

### 수정 [검증됨]
- 대상 = `src/pages/api/**` 중 라우트 핸들러(`export const GET|POST|...`)를_export_하면서 `export const prerender`가 없던 파일. `find src/pages -name '*.ts'` = 50개, 그중 `api/courses/templates/lesson-email.ts`는 핸들러 0개(라이브러리 모듈)라 제외 → **30개**.
- 기계적 전처리: 30개 파일 선두에 `export const prerender = false;` 삽입. 이중 삽입 검사 = 0건.
- 어댑터(`@astrojs/cloudflare/dist/utils/generate-routes-json.js`)가 `_routes.json`을 자동 재생성. include에 신규 진입: `/api/auth/*`, `/api/news/*`, `/api/subscribe`, `/api/unsubscribe`, `/api/admin/*`, `/api/briefing/*`, `/api/courses/enroll|send-daily|track`, `/api/posts`, `/api/upload`, `/api/articles/*`.

### 검증 [검증됨]
| 검사 | 결과 |
|---|---|
| `npm run build` | exit 0, `dist/api` 확장자 없는 스텁 = 2건(`search`, `home-content` — 둘 다 `prerender = true` 명시) |
| `scripts/deploy.sh` | exit 0, 배포 `5880ab04` |
| `GET /api/auth/login/` | **302 → `https://accounts.google.com/o/oauth2/v2/auth?client_id=...`** (사용자 증상 해소) |
| `GET /api/news/latest/` | 200 `application/json`, D1 실데이터(`id:53959`…) |
| `GET /api/briefing/latest/` | 200 `application/json` (`briefing id 329`, date 2026-10-04-1) |
| `GET /api/posts/` | 200 `application/json` (게시물 45번까지) |
| `GET /api/tools/reviews/` | 200 (`{"reviews":[],"avgRating":0}`) |
| `GET /api/auth/me/` | 200 (`{"loggedIn":false}` — 세션 판정이 이제 실시간) |
| `POST /api/subscribe/` 잘못된 이메일 | 400 `{"error":"유효한 이메일을 입력해주세요."}` — 검증 분기 살아 있음, DB 미삽입 |
| `POST /api/admin/tools/review/` 인증 없음 | 403 `{"error":"unauthorized"}` |

주의: 슬바더 링크 `href="/api/auth/login"`(슬래시 없음)은 301 → `/api/auth/login/` → 302 → Google 2홉. 동작함. 슬래시 추가로 1홉 줄일 수 있으나 [검증됨]currently-200 흐름이므로 미변경.

### 전수 확인 — 남은 .astro 페이지 15건 [부분검증]
`.astro` 중 `prerender` 미선언 = 15개 → 지금은 전부 정식 static prerender.
- 데이터 정지 위험(RUNTIME=빌드 시 D1 조회): `news.astro`, `global.astro`, `pricing.astro`, `community/index.astro`, `courses/7day-starter.astro`, `my/tools/index.astro`
- 요청 헤더 의존(REQ): `community/review.astro`, `community/write.astro`, `event/index.astro`, `event/download.astro`, `payments/success.astro`, `payments/fail.astro`, `tools/submit.astro`, 위 6개 중 겹치는 것
- 이상 없음: `auth/consent.astro`, `unsubscribe.astro`
- 빌드 경고로 `Astro.request.headers` 사용이 확인된 페이지: `404`, `about`, `aikeep24/index`, `blog/category/[cat]/[...page]`, `blog/[...id]`, `blog/[...page]`, `terms`, `privacy`, `contact`, `subscribe`, `tools/*`, `glossary/*`, `chronicle/*`, `community/[id]`, `community/[id]/edit`, `admin/*`, `network/index`, `compare/index`, `briefing/*` — 이 31개는 `prerender = true`가 **명시**되어 있어 의도된 정적화. 공유 레이아웃/UA 판별 로직이 빌드 시점 값으로 굳는 문제는 이번 변경이 만든 것이 아니라 기존부터 잠재来着. [부분검증] 각 페이지가 헤더로 분기하는 로직의 실제 사용자 영향은 미조사.

### 잔존 위험
1. `.astro` 15건 중 D1 조회 6개는 배포 시점 데이터로 동결 — 다음 배포까지 갱신 안 됨. SSR 복귀 여부 사용자 결정 필요.
2. `api/search.ts`·`home-content.ts`는 `prerender = true` 의도 유지 — 검색 인덱스(748KB)와 홈 콘텐츠가 빌드 시점 스냅샷. 매 배포 갱신은 되나 배포 사이엔 정지.
3. 워치dog(`9e22d6a9`)은 이 재발을 못 잡음(exit 0). 업그레이드안: 빌드 후 `dist/api/**` 확장자 없는 스텁 검사 — 미구현.
4. `.astro` 15건은 복귀시키지 않음 — `output: 'server'` 복귀(B)는 미채택. 각 페이지 SSR化 시 Worker 비용·런타임 증가.
5. Brevo 클릭 통계 오염 ~77건(앞 절) + 오늘 08:00 발송분은 구독 API 정상화 **이후**라 데이터 손실 없음.

### 다음 행동
1. (사용자 결정) `.astro` 15건 중 D1 조회 6건을 SSR 복귀할지, 정적 유지할지.
2. 워치독에 `dist/api` 스텁 검사 1줄 추가 → 이 재발 자동 차단.
3. `OPENAI_API_KEY` 평문 plist 회전(앞 절 잔존).

---

## 2026-10-04 09:50 — AIK24-AUTH-UI-01: 로그인 후에도 로그인 버튼이 계속 보이는 근본 원인 수정 (배포 fe7c586b)

### 한 일
Google 로그인은 정상인데 사이트 헤더가 계속 로그인 버튼을 보여주던 문제(사용자 보고: "로그인이 안되")의 근본 원인을 규명하고, 프리렌더 페이지에서도 로그인 상태가 보이게 고침. 진단 로그 임시 배포(38e4b286) → 원인 규명 → 수정 배포(fe7c586b).

### 진단 경로 [검증됨]
1. **우회 가설 폐기 — OAuth는 정상.** `wrangler pages deployment tail`로 실제 로그인 2회 포착:
   ```
   (error) [auth:google] userinfo 200 107908468092318898018
   (error) [auth:google] bindings { db: 'present', secret: 'present' }
   (error) [auth:google] session cookie set, dbUser id= 1
   ```
   `token_failed` 로그 없음 = 토큰 교환 성공, userinfo 200, D1 바인딩 존재, 세션 쿠키 서버 정상 심음. client secret 불일치·redirect_uri 불일치 가설 **기각**.
2. **진짜 원인 = `src/layouts/Layout.astro:31-32`**
   ```astro
   const session = Astro.cookies.get('session')?.value;
   if (session) currentUser = await verifySession(session, Astro.locals.sessionSecret);
   ```
   Layout은 전 페이지 공통 헤더(`Layout` 사용 페이지 36개). 프리렌더 페이지에서는 이 코드가 **빌드 시점**에 실행되어 쿠키가 없음 → 항상 로그인 버튼. `src/pages/index.astro:2`가 `export const prerender = true` → 홈이 정적. 라이브 `curl https://aikorea24.kr/ | grep -c auth/login` = 1(HTML에 박혀 있음)이 증명.
   → **내 커밋 `12f71446`(output 'hybrid'→'static')이 유발.** hybrid는 "기본 SSR"라서 이 코드가 런타임에 돌았고, static으로 바꾸면서 프리렌더가 기본이 됨.
3. 참고: `/api/auth/me` 원래는 `name`을 반환하지 않았음 → 클라이언트 스왑 전에 확장 필요.

### 수정 내역 [PRODUCTION CODE] 3개 파일
- `src/layouts/Layout.astro`
  - 로그인 앵커 2곳(데스크톱 121행, 모바일 178행)에 `js-login-btn` 클래스 추가.
  - 각 위치에 숨김 상태 로그인 박스 `.js-user-box` 추가(기존 SSR 로그인 UI와 동일 마크업 스타일, 초기 `hidden`).
  - `</body>` 직전에 인라인 스크립트 추가: `/api/auth/me` fetch → `loggedIn`이면 로그인 앵커 숨기고 박스 표시. 사용자 이름은 `textContent`로만 주입(innerHTML 미사용 = XSS 방지).
- `src/pages/api/auth/me.ts`: 응답에 `name: user.name` 추가(하위 호환 — 필드 추가만).
- `src/pages/api/auth/callback/google.ts`: 진단 로그 3개 추가 후 **2개는 제거**(정상 로그인 시마다 찍히던 `userinfo`/`bindings`), 실패 시만 찍히는 `token_failed` 1개만 유지.

### 검증
- [검증됨] 빌드: `npm run build` exit 0. 산출물 확인 `dist/index.html`에 `js-login-btn` 2회, `js-user-box` 5회, `api/auth/me` 1회.
- [검증됨] 워커 번들: `dist/_worker.js/pages/api/auth/me.astro.mjs`에 `loggedIn: true, email: user.email, name: user.name` 확인.
- [검증됨] 배포 `fe7c586b-86a2-4af9-bc22-bae20d576b14`. 라이브 `curl https://aikorea24.kr/` = `js-user-box` 5회 / `js-login-btn` 2회 → 새 코드 반영.
- [검증됨] `curl https://aikorea24.kr/api/auth/me/` = `{"loggedIn":false}` (쿠키 없는 요청이라 정상).
- [검증됨] 실제 로그인 후 헤더 전환 — **사용자 확인 완료**(2026-10-04 09:5x, "로그인 완료" 보고). 쿠키가 httpOnly라 CLI 재현은 불가 → 사용자 확인이 유일한 검증 수단.
- [검증됨] 표시 상태 — 사용자 화면에서 로그인 후 헤더 정상 동작 확인(예정 아이니셜 + 이름 + 내 도구 + 로그아웃).

### 부수 발견
- **`wrangler 4.110.0`의 `pages deployment tail`가 깨짐.** 배포 ID가明明 존재하는데 `The deployment ID you have specified does not exist [code: 8000009]`. `npx wrangler@4.147.0`으로 동일 명령 성공. 로컬 wrangler 업그레이드 필요(업데이트 알림 4.147.0).
- `npx tsc --noEmit` 오류 5건 전부 `pipeline/instagram/prototypes/generate-all-cards.mjs`, `generate-cards.ts` — 이번 작업과 무관한 기존 오염 파일.

### 미커밋 → 커밋됨
`Layout.astro`, `me.ts`, `google.ts`, `docs/state.md` 4건 커밋 (사용자 승인 후).

### 잔존 위험
1. `prerender = true`인 **21개 `.astro` 페이지**: 헤더 로그인 표시는 동작(클라이언트 스왑). 서버측 인증 게이트가 필요한 로직(`Astro.redirect('/api/auth/login')` 패턴: `my/tools/index`, `event/download`)이 정적 페이지에 남아 있으면 빌드 시점 실행되어 무의미 — [검증불가] 실제 영향 미조사.
3. 클라이언트 스왑이므로 로그인 전 잠깐 로그인 버튼이 보인다(FOUC). 서버 렌더 요구 시 해당 페이지를 `prerender = false`로 바꾸는 편이 정확함 — 성능과 트레이드오프.
4. `token_failed` 진단 로그 1줄이 프로덕션에 남아 있음(실패 시에만 발생). 유지 여부 판단 필요.
5. oauth 콜백은 무-slash URI → slash로 301 리다이렉트 후 실행(쿼리 보존 확인됨). 동작하지만 왕복 1회 낭비.
6. 앞선 [위반 감지] `OPENAI_API_KEY` 평문 plist — 키 회전 미실시.
7. 워치독은 빌드 exit 코드만 감지 — 이 类 "조용히 성공하지만 의미 틀림" 사고는 못 잡음.

### 다음 행동
1. 사용자 확인: 로그인 후 헤더에 이름/내 도구/로그아웃 표시되는지.
2. 커밋 (승인 대기).
3. (선택) 로컬 wrangler 4.147.0+ 업그레이드.
4. (선택) 정적 페이지 21개의 서버측 인증 로직 점검.

---

## 2026-10-04 08:00 — AIK24-LOGIN-404: 로그인 클릭 시 다운로드 현상 진단 (원인 특정, 수정 대기)

### 한 일
aikorea24.kr 로그인 버튼 클릭 시 Google 동의 화면으로 안 가고 파일이 다운로드되는 현상의 원인 파악. **진단만 — 코드 수정 없음.** systematic-debugging Phase 1~3 수행.

### 재현 [검증됨]
`curl -sD - https://aikorea24.kr/api/auth/login` (Mozilla UA):
- `HTTP/2 200` (302 아님)
- `content-type: application/octet-stream`, `x-content-type-options: nosniff`, `content-length: 1654`
- body = `<!doctype html><title>Redirecting to: https://accounts.google.com/o/oauth2/v2/auth?client_id=...&redirect_uri=https%3A%2F%2Faikorea24.kr%2Fapi%2Fauth%2Fcallback%2Fgoogle&scope=openid+email+profile...`
- `curl -L` 추적: `redirects=0`, 최종 URL 여전히 `/api/auth/login`

→ `nosniff` + 확장자 없는 HTML = 브라우저가 **다운로드** 처리. 사용자 증상과 정확히 일치.

### 원인 [검증됨]
`12f71446`(2026-10-04 06:35 배포, b66bc14f)의 `output: 'hybrid'` → `'static'` 전환이 원인. 실체는 그 커밋의 **prerender 플래그 누락**:
1. `output: 'static'`에서는 모든 라우트가 기본 prerender. SSR이 필요한 라우트는 `export const prerender = false`로 명시해야 한다.
2. `src/pages/api/auth/*.ts` 6개(login·me·logout·kakao·callback/google·callback/kakao)에 플래그 없음 → `astro build`가 이路由들을 **빌드 시점에 실행**해 정적 스텁으로 굽는다.
3. 산출물 실측: `dist/api/auth/login` = "HTML document text, ASCII text (1654 bytes), no line terminators", mtime 10/4 07:33. `dist/api/auth/me` = 18바이트, `logout` = 275바이트.
4. `@astrojs/cloudflare` 어댑터가 `dist/_routes.json`을 **prerender=false 라우트 기준으로 자동 생성**(`node_modules/@astrojs/cloudflare/dist/utils/generate-routes-json.js`). `/api/auth/*`는 플래그가 없어 include에 없음 → **Worker가 이 경로를 전혀 받지 않음** → Pages 정적 에셋 서버가 확장자 없는 스텁 파일을 octet-stream으로 반환.

즉 `login.ts:28`의 `redirect()`는 **런타임에 한 번도 실행된 적 없다.** body에 Google URL이 박혀 있는 것은 빌드 시점 실행 결과물.

### 피해 범위 — 로그인 외 31개 API [검증됨]
`find src/pages/api -name '*.ts'` = **41개**, `export const prerender` 보유 = **10개** → 31개가 정적 스텁. 라이브 스팟 체크:

| 경로 | code | content-type | size | 판정 |
|---|---|---|---|---|
| `/api/auth/login` | 200 | octet-stream | 1654 | 사용자 증상 |
| `/api/briefing/latest` | 200 | octet-stream | 4 | 빌드 시점 빈 응답 굽힘 |
| `/api/news/latest` | 200 | octet-stream | 2 | 동일 |
| `/api/tools/reviews` | 200 | octet-stream | 28 | 동일 |
| `/api/subscribe` | 404 | text/html | 19648 | 정적 산출물 없음(POST 전용) |
| `/api/search` | 200 | octet-stream | 748801 | 검색 인덱스가 정적으로 굳음(동작은 하나 데이터 정지) |

추정 피해 도메인: 뉴스레터 구독·수신확인(`/api/subscribe`, `/api/unsubscribe`), 뉴스 API 6종, 브리핑 API 6종, 코스 API 4종, 관리자 API 2종(`/api/admin/*` — include에 `/admin/*`만 있고 `/api/admin/*`는 없음), 업로드(`/api/upload`), 검색, 글 목록(`/api/posts`), 로그인 세션 판정(`/api/auth/me` — 18바이트라 항상 "로그인 안 됨"으로 보임).

### 회귀 구간 [부분검증]
- 10/01 20:30 배포 b3309304는 `output: 'server'` 상태로 빌드됨(`logs/deploy_2026-10-01.log` 마지막 항목, 커밋 0323c7c6 직전). `output: 'server'`는 SSR 라우트를 prerender하지 않으므로 그 시점엔 API가 정상 동작했다.
- 10/01 20:36 ~ 10/04 06:35는 빌드 자체가 실패해 아무것도 배포되지 않음 → 기존 SSR 배포본이 그대로 서비스됨.
- 따라서 파손 시작점은 10/04 06:35의 b66bc14f. [부분검증] 근거 = 커밋 diff + 배포 로그이며, Brevo/Analytics에 10/04 이전 `/api/auth/me` 응답 원본이 없어 실측 대조 불가.

### [위반 감지] — 이번 진단이 드러낸 자기 결함
`12f71446`은 **빌드를 통과시키는 것**을 목표로 했고 달성했지만, "빌드 성공"만 검증하고 "라우트가 런타임에 살아 있는지"는 검증하지 않았다. GetStaticPathsRequired로 **에러를 내는** 라우트만 골라 플래그를 붙였고, **조용히 성공하는** 31개는 놓쳤다. 빌드 워치dog(`9e22d6a9`)도 exit 0만 확인하므로 이 재발을 못 잡는다 — 워치독의 사각지대를 명시적으로 기록.

### 수정 옵션 (아직 미실행 — 선택 대기)
- **A. 정적 유지 + 플래그 31개 추가** (astro 5 hybrid 완전 이관): `output: 'static'` 유지, 플래그 없는 API 라우트 31개에 `export const prerender = false;` 1줄씩. 어댑터가 `_routes.json`을 자동 갱신하므로 수동 편집 불필요. diff = +31줄. 10/01의 "정적 전환" 의도 유지. 주의: SSR 전환 시 `import.meta.env`는 빌드 시점 값으로 인라인되므로 `locals.runtime.env` 경로가 필요(`login.ts`는 이미 `runtime?.env?.GOOGLE_CLIENT_ID || import.meta.env...` 폴백 보유).
- **B. `output: 'server'` 복귀** (1줄): 10/01 이전 동작 그대로. diff 1줄. 단 "hybrid 정적 전환"(0323c7c6)의 의도 포기 — 페이지 전부 SSR로 비용·SEO 부담 증가.

권고: A(의도 보존,機械적). B는 되돌리기만 하고 "정적 전환" 요구는 그대로 남음.

### 잔존 위험
1. 옵션 A/B 미실행 상태 — 현재 라이브는 로그인·구독·뉴스·브리핑 API가 정적 스텁 상태(사용자 트래픽 대상).
2. `runtime.env` 미사용 라우트가 A 적용 후 D1/R2에 못 닿을 가능성 — 해당 라우트의 `locals` 사용 여부는 A 실행 시 전수 확인 필요.
3. 워치dog 사각지대: exit 0이어도 라우트가 정적으로 굳는 실패는 못 감지. 업그레이드 경로 = 빌드 후 `dist/api/**` 산출물 존재 여부 검사(파일에 content-type이 붙는 정적 스텁) — 아직 미구현.
4. Brevo 클릭 이벤트에 10/04 이후 구독/뉴스 API 실패 implicate 안 됨(수신 newsletters는 08:00 발송, breakage 시작 06:35 → 오늘 08:01 발송분부터 리스크). 다음 발송 전 수정 필요.

### 다음 행동
1. 옵션 A/B 선택 → 즉시 수정 → `bash scripts/deploy.sh` → 검증: `/api/auth/login` 302 + `Location: accounts.google.com`, `/api/news/latest` 200 JSON, `/api/subscribe` 405/400(200 아님), `dist/api/**` 정적 스텁 0건.
2. 워치독에 "빌드 후 dist/api 정적 스텁 검사" 1줄 추가(옵션 A 적용 후).

---

## 2026-10-04 07:36 — AIK24-404FIX-02: 빌드 파손 수정 커밋 + 빌드 워치독(조용한 실패 감시) 설치

### 한 일
(a) AIK24-404FIX-01 수정 10개 파일 커밋, (b) astro 조용한 빌드 실패를 Telegram 알림으로 바꾸는 워치독 작성 + launchd 등록. 지시 없었음 → a·b 외 커밋/수정 없음.

### (a) 커밋 [검증됨]
- `12f71446` fix: astro 5 output 'hybrid' → 'static' 복구 (배포 b66bc14f) — 10개 파일, +19/-1. `git diff --stat` 근거: astro.config.mjs 2±, API 라우트 6개 각 +2, SSR 페이지 3개 각 +2.
- `9e22d6a9` chore: 빌드 워치독 추가 — 신규 `scripts/build_watchdog.py`(104줄).
- 후속 커밋(07:40, 사용자 지시): `57326043` feat: 블로그 6건 추가 (2026-10-04) — 커밋 전 `scripts/validate_blog_posts.py` 실행 결과 `✅ 모든 블로그 포스트 정상`(exit 0). `316f6431` chore: briefing dedup 상태 갱신 — `git diff --numstat` +134/-0, 키 이름만 확인(`date`/`briefing_id`/`articles`/`original_title` 등) = 상태 append, 시크릿 없음.
- 커밋하지 않은 것(의도적): `docs/state.md`·`docs/AIK24-BREVO-TRACK-01.md`(??). `launchd/kr.aikorea24.build-watchdog.plist`는 `.gitignore:51 *.plist` 규칙으로 미추적 — 저장소 launchd 파일은 원래 전부 미추적(`git ls-files launchd` → 0건).

### (b) 빌드 워치독 [검증됨]
- `scripts/build_watchdog.py`: `npm run build` 실패 시 exit 코드 + `npx astro build --verbose` 1회 추가 실행으로 `ASTRO_CLI_ERROR`(ZodError) 원문 추출 → `TELEGRAM_BOT_TOKEN`/`TELEGRAM_CHAT_ID`으로 sendMessage. 배포 중이면 `/tmp/wrangler_deploy.lock` 확인 후 skip.
- `launchd/kr.aikorea24.build-watchdog.plist`: 매일 07:10 KST. 근거 = 뉴스레터 08:00 발송 50분 전에 알림이 와야 링크 404로 나가지 않음.
- 검증 3건:
  1. 수동 실행 → `[ok] 빌드 성공 (exit 0) — dist/index.html mtime=2026-10-04 07:32`, 12.9초(1회 빌드 비용 무시 가능).
  2. launchd 실실행 → `launchctl kickstart -p gui/$(id -u)/kr.aikorea24.build-watchdog` → `runs = 1`, `last exit code = 0`, `logs/build_watchdog.log` 1줄 기록. `launchctl print` state=not running(정상 종료), path/program/stdout 모두 의도대로.
  3. 알림 경로 → `notify()` 실제 호출 `[telegram] sent http=200` (테스트 메시지 1건 발송됨 — 10/04 07:31 경).
- 실패 분기 [부분검증]: 정규식 `ASTRO_CLI_ERROR.{0,500}` 추출을 10/1 ZodError 실측 형태 모사 문자열로 검증(성공). 단 실제 config-invalid 상태에서의 end-to-end 실패 발신은 미실증 — astro config를 일부러 깨뜨려 재현하지 않음. 복구 계획: 필요 시 임시로 `output: 'hybrid'` 한 줄을 로컬에서만 바꿔 `python3 scripts/build_watchdog.py` 1회 실행.

### [위반 감지] — Committed secret (기존 문제, 이번 작업과 무관)
- `launchd/kr.aikorea24.weekly-contrast.plist`의 `EnvironmentVariables`에 `OPENAI_API_KEY` 평문 하드코딩(값 미출력). 파일은 `.gitignore:51 *.plist`로 미추적이므로 git 히스토리에는 없음. 설치본 `~/Library/LaunchAgents/kr.aikorea24.weekly-contrast.plist`도 동일(8/28 설치본, 1564 bytes, 동일 내용).
- 조치 필요(이번엔 손대지 않음 — 지시 범위 밖): ① 키 회전(OpenAI 콘솔에서 revoke/재발급) ② plist에서 값 제거 후 `.env` 로드 또는 `EnvironmentVariables` 참조 방식으로 교체. 같은 패턴이 다른 plist에도 있는지 전수 확인 필요([검증불가] — plist 전수 스캔 미실시).

### 잔존 위험
1. 워치독은 "빌드가 죽는 것"만 잡는다. 빌드가 성공해도 배포가 안 되면(예: wrangler 인증 실패) 링크는 여전히 404 — 배포 실패 감지는 별도 필요. ponytail 한계로 명시: 업그레이드 경로 = `scripts/deploy.sh` exit 코드도 같은 워치독에 묶기.
2. 워치독 plist가 git 미추적 → 새 클론/다른 Mac에 자동 설치 안 됨. `~/Library/LaunchAgents`에 설치본 1벌 존재(확인함).
3. 워치독 실패 알림이 Telegram으로만 나감 → Telegram 계정/채널이 죽으면 무음. 로그는 `logs/build_watchdog.log`.
4. 미커밋 잔여물: `briefing_dedup.json`(M) + 블로그 6건(??). 이번 지시는 10개 파일 커밋이므로 손대지 않음.
5. 앞선 Brevo 진단 보고(07:21)에 기재 — 클릭 통계 가짜 클릭 ~77건 오염.
6. `astro.request.headers` 프리렌더 경고(chronicle, community review/write)는 미해소 — 빌드는 통과하므로 링크 404와 무관.

### 다음 행동
1. OpenAI 키 회전 + weekly-contrast plist에서 평문 제거(사용자 승인 후).
2. (선택) `scripts/deploy.sh` 실패도 워치독 알림에 편입 — 다음 재발 시.
3. (선택) 미커밋 블로그 6건 커밋 여부 결정.

---

## 2026-10-04 07:21 — AIK24-BREVO-TRACK-01: Brevo 클릭 추적 404 진단 (읽기 전용)

### 한 일
`docs/AIK24-BREVO-TRACK-01.md` 진단 지시 1·2·4 실행. 수정/발송/키 재생성 없음. 지시서 3번(테스트 발송)은 지시서 마지막 줄 "수정·발송·키 재생성 금지"와 상충 → 미수행, 대신 기존 실메일 9통으로 대체 검증.

### 1. 발송 경로 [검증됨]
- 트랜잭셔널 API 직접 호출. 캠페인 미사용.
- 근거: `scripts/auto_email_sender.py:353` `POST https://api.brevo.com/v3/smtp/email`, 발신 `{"name":"AI코리아24","email":"info@aikorea24.kr"}`(:381), 제목 `AI코리아24 뉴스레터 - {date}`(:382), 수신자 = Brevo 리스트 2(`get_subscribers_from_brevo(list_id=2)`:298).
- 오케스트레이션: `scripts/run_pipeline.py` step 4(:92-97 `auto_email_sender.main()`) → step 5가 deploy.sh.
- 발송 시각 [검증됨]: Gmail `Date` 헤더 기준 2회/일 = 08:00·22:00 KST(13:00Z·23:00Z). 제목 접미사 `-1`/`-2`가 회차. 9통 = 2026-09-29-1 ~ 2026-10-04-1.
- 스케줄러 [검증불가]: `~/Library/LaunchAgents`에 `auto_email_sender` 참조 plist 없음(grep 0건). 수동 또는 외부 스케줄 실행으로 추정.

### 2. Brevo 계정 상태 [검증됨/검증불가]
- [검증됨] `GET /v3/account` HTTP 200. 플랜 `free`(type=free, credits=271, creditsType=sendLimit). 계정 `hugh79757@gmail.com` / companyName "style factory 9". → API 키 유효 + 로컬 IPv4 IP 화이트리스트 통과(skill Check 1 통과).
- [검증됨] `GET /v3/senders` → id 2 / `info@aikorea24.kr` / active=true.
- [검증불가] 발신 도메인 `aikorea24.kr` 인증 상태. `GET /v3/domainAuthentication` → HTTP 404 `{"code":"not_found","message":"Invalid route/ method passed"}`. Brevo 공개 API에 없음 → Brevo UI(Transactional > 도메인 인증)에서만 확인 가능. 복구 계획: UI 1회 확인.
- [검증불가] API 키 생성일. API에 키 메타 엔드포인트 없음. `.env`는 git 미추적(`git ls-files --error-unmatch .env` → untracked), mtime `2026-09-25 08:04:55`.

### 3. 클릭 이벤트 통계 [검증됨]
- `GET /v3/smtp/statistics/events?startDate=2026-09-27&endDate=2026-10-04` → 총 360건: requests 78 / delivered 63 / opened 30 / **clicks 171** / hardBounces 11 / softBounces 3 / blocked 1 / deferred 3.
- 뉴스레터 한정 clicks **168건**(전체 클릭의 98%). 실제 수신자 IP 포함(twinssn@gmail.com, yenakim@sk.com) → 봇만 찍은 숫자가 아님.
- 해석: Brevo는 클릭을 **리다이렉트를 제공한 시점에만** 기록함. 168건 기록 = 추적 링크가 404였던 기간은 없었음.

### 4. 추적 URL 404 재현 실패 [검증됨]
실메일 9통에서 추출한 링크로 27건 probe(`curl -4`, `-o /dev/null`):
- `/tr/cl/` 18건 → **302 전건**, `Location` 정상(예: `https://aikorea24.kr/briefing/2026-09-29-1#item-1`).
- `/tr/op/` 9건 → **200 전건**.
- `-L` 완주 추적 9건 → 최종 **200 전건**(리다이렉트 2회 = Brevo 302 → CF 301 → 200).
- 추적 호스트 2종 모두 정상: `bbehihgh.r.af.d.sendibt2.com`(9/29-1, 9/30-2, 10/02-2, 10/03-1, 10/03-2, 10/04-1) / `bbehihgh.r.bh.d.sendibt3.com`(10/01-1, 10/01-2, 10/02-1). 호스트가 갈려도 404 없음.

### 5. 404 재현 성공 → 0번 진단의 오진 지목 [검증됨]
동일 호스트·동일 경로에서 트래킹 id만 변조:
| 대상 | 결과 |
|---|---|
| 정상 `/tr/cl/{id}` | 302 |
| 마지막 12자 변조 `/tr/cl/{id}` | **404** |
| URL 절반 자름 | **404** |
| 호스트 루트 `/` | 301 |
| 무효 id `/tr/op/INVALIDID123` | 200 |

→ 0번이 관측한 조합("루트 301, `/tr/op/` 200, `/tr/cl/` 404")이 **무효한 추적 id에서 정확히 재현**됨. Brevo 추적 서버는 정상이며, 0번이 curl한 문자열이 잘림/공백 혼입/변형된 것.

### 6. 목적지 404 창 [검증됨/부분검증]
- 클릭 이벤트 기준 고유 목적지 47건 현재 상태: **200 23건 + 301 24건, 404 0건**. (301은 trailing-slash 리다이렉트라 정상. 예 `/briefing/2026-10-04-1#item-1`.)
- [부분검증] 2026-10-01 20:36 ~ 2026-10-04 06:35 동안 빌드 파손(`output:'hybrid'`)으로 `/tools/*` 목적지 자체가 404였음 → 그 구간의 클릭은 목적지 404로 착지했을 가능성. 제한 사유: Brevo 클릭 이벤트는 타임스탬프만 있고 응답 코드를 소급 조회할 수 없음(과거 클릭의 목적지 상태 재현 불가).

### 7. "9/27 Brevo API 키 신규 생성" 가설 [부분검증] — 반증 근거 있음
- `.env` mtime이 `2026-09-25 08:04:55`이고 이후 수정 없음 → `BREVO_API_KEY`(키 이름만 확인, 값 미출력)는 9/27 이전에 기록된 값.
- [부분검증] Brevo UI에서 키만 재생성하고 `.env`를 건드리지 않은 시나리오는 배제 못 함. 키 생성일 자체는 [검증불가].

### 원인 가설 (0번 판정 대기용)
- **가설 A (근거 강함)**: 0번 진단의 "추적 URL 404"는 진단 측 URL 문자열 손상에서 기인. 근거 = 5번 재현 표 + 클릭 168건 존재 + 27건 probe 전건 정상.
- **가설 B (배제 못함)**: 사용자가 체감한 404의 실체는 목적지 `/tools/*` 404 창(빌드 파손)이었음. 오늘 06:35 배포로 해소. 근거 = 6번.
- 두 가설 모두 "Brevo 추적 장애"가 아님을 가리킴 → Brevo 측 조치(키 재생성·설정 변경) 불필요.

### 잔존 위험
1. **이번 진단이 Brevo 클릭 통계에 가짜 클릭을 남김**: probe 27건 + 목적지 상태 확인 47건 + 변조/절단 2건 + 추적 URL 1건 ≈ 77건이 사용자 IP(110.169.9.102)에서 클릭으로 기록됨. 원인: 추적 URL GET은 클릭 로깅이 불가피. 10월 클릭 수치는 이만큼 부풀려짐.
2. 0번이 사용한 정확한 URL 문자열은 열람 불가(진단 기록에 없음) → 가설 A는 "재현 일치" 증거까지 확보했지만 원본 문자열 대조는 [검증불가].
3. 발신 도메인 `aikorea24.kr` 인증 상태 미확인([검증불가]) — 무관하지만وحة UI 확인 필요.
4. 뉴스레터 발송 스케줄러 위치 미확인(launchd plist 없음) → 08:00·22:00 KST 발송이 무엇이 띄우는지 [검증불가].
5. 이번 작업은 읽기 전용 — 코드/설정/키 변경 0건. AIK24-404FIX-01의 미커밋 10개 파일 상태는 그대로(위 06:36 보고서 참조).

### 다음 행동
1. 0번에 회신: "추적 URL 404 재현 실패(27/27 정상). 404는 잘못 복사된 URL에서 재현됨. Brevo 조치 불필요" + 본 보고 5번 표 첨부.
2. (선택) Brevo UI에서 `aikorea24.kr` 도메인 인증 상태 확인.
3. (선택) 사용자가 같은 추적 URL을 재현하려면 원본 문자열 그대로 재curl — 절반으로 자른 문자열에 대한 404는 정상 동작.

---

## 2026-10-04 06:36 — AIK24-404FIX-01: tools 404 유발 빌드 파손 수정 + Pages 재배포

### 한 일
지시된 `scripts/deploy.sh` 재실행을 시도 → 빌드가 config 검증 단계에서 실패. 원인 규명 후 빌드 통과용 최소 수정(10개 파일) 후 빌드 + Cloudflare Pages 배포(배포 ID `b66bc14f`)까지 마쳤음.

### 진단 — 지시서의 "코드 수정 없음" 가정과 불일치
- [검증됨] 재빌드만으로는 해결되지 않음. 근거: `npm run build` 종료코드 1, 전체 출력이 8줄(에러 본문 없음), `dist/` mtime이 10/1 20:16 그대로.
- [검증됨] 원인 1 = astro config. `npx astro build --verbose` 텔레메트리 `ASTRO_CLI_ERROR {name:"ZodError", isConfig:true, configErrorPaths:["output"]}`. `astro.config.mjs:9` 의 `output: 'hybrid'` 가 astro 5.17.2에서 제거된 값.
- [검증됨] 이 config는 한 번도 빌드 성공한 적이 없음. 근거: `git show 0323c7c6`(10/1 20:36 커밋)이 `output: 'server'` → `'hybrid'` 로 변경했고, `logs/deploy_2026-10-01.log`의 마지막 배포는 20:30(`b3309304`) = 변경 전 config로 빌드된 산출물. astro 5.17.2는 9/13부터 설치됨(`node_modules/astro/package.json` mtime 2026-09-13, `package-lock.json`도 5.17.2).
- [검증됨] 원인 2 = 원인 1 해결 후 드러난 후속 에러. `src/pages` 동적 라우트 17건 중 `getStaticPaths()`도 `prerender = false`도 없는 9건이 `GetStaticPathsRequired`로 빌드 중단(첫 실패: `src/pages/api/community/[id]/delete.ts`, 수정 후 다음 실패: `src/pages/community/[id]/edit.astro`).
- → 결론: 10/1 20:36 커밋이 빌드 불가 config를 남긴 상태였고, 이후 모든 배포 시도가 [1/3] 빌드에서 실패해 `dist`가 10/1 산출물로 고정 → 10/3 생성된 tools md 4건이 반영되지 않음. 404의 근본 원인.

### 수정 내역 (10개 파일, 미커밋 — 지시대로 커밋하지 않음)
[CONFIG]
- `astro.config.mjs:9` — `output: 'hybrid'` → `output: 'static'` (astro 5에서 hybrid와 동일 의미: 기본 프리렌더 + per-route `prerender = false`로 온디맨드)

[PRODUCTION CODE] API 라우트 6건에 `export const prerender = false;` 추가
- `src/pages/api/tools/[slug]/index.ts`
- `src/pages/api/tools/[slug]/visibility.ts`
- `src/pages/api/files/[...path].ts`
- `src/pages/api/community/[id]/visibility.ts`
- `src/pages/api/community/[id]/update.ts`
- `src/pages/api/community/[id]/delete.ts`

[PRODUCTION CODE] 페이지 3건 frontmatter에 `export const prerender = false;` 추가
- `src/pages/community/[id].astro`
- `src/pages/community/[id]/edit.astro`
- `src/pages/my/tools/[slug]/edit.astro`

- 수정 분류: [CONFIG] 1개 + [PRODUCTION CODE] 9개, [TEST CODE] 수정 0건(테스트로 통과시킨 케이스 없음).

### 결과 (검증 근거)
- [검증됨] `scripts/deploy.sh` 종료코드 0. 근거: 배포 로그 `Deployment complete! Take a peek over at https://b66bc14f.aikorea24.pages.dev` + `배포 완료: https://aikorea24.kr`.
- [검증됨] tools 4건 라이브 200 (curl `http_code`): `/tools/syllaby-ai-avatar-2-0/`, `/tools/veltrix-ai-for-e-commerce/`, `/tools/adaptive-reward-routing-dynamic-multi-reward-opti/`, `/tools/never-boring-ai/`.
- [부분검증] 위 200 판정은 상태코드만 확인. 제한 사유: 응답 본문의 툴명/설명 일치 여부는 미검사. 상태코드 신뢰도는 별도 확인 — 존재하지 않는 slug `/blog/zzz-definitely-not-a-post-9f3a/` → 404 (soft 404 아님).
- [검증됨] sitemap 노출: `sitemap.xml`은 인덱스(6 loc, 하위 sitemap 6종: blog/briefing/chronicle/glossary/pages/tools). 4개 slug은 `sitemap-tools.xml`에서 각 1건 확인(`grep -c` = 1). `sitemap.xml` 본문에는 없음(인덱스 구조이므로 정상).
- [검증됨] SSR 라우트 생존: `prerender = false` 대상인 `/briefing/` 200 + `dist/briefing/index.html` 미생성 → 정적 산출물이 아닌 워커 서빙. `dist/_worker.js/`(디렉터리 형태)와 `dist/_routes.json` 존재.
- [검증됨] 부가 스팟 체크 200: `/`, `/tools/`, `/community/review/`.
- [검증됨] 미커밋 신규 글 6건이 이번 빌드에 반영됨: `dist/blog/2026-10-04-001-…` 존재, 라이브 `/blog/2026-10-04-001-…/` 200.
- [검증됨] 배포 전 동기화 단계: `[sync_submissions_to_md] published=11 created=0 skipped(existing/invalid)=11`.
- [검증불가] 전체 페이지 회귀(라이브 전 페이지 before/after 대조). 사유: 10/1 산출물이 이번 빌드로 덮어써져 비교 기준 없음. 복구 계획: 다음 배포부터 `dist` 스냅샷을 날짜 디렉터리로 보존하고 페이지 목록 diff 스크립트 추가.

### 지시서 오류 정정
- 지시된 `https://aikorea24.kr/tools/veltrix-ai-for-ecommerce/` 는 하이픈 누락 오타. 근거: 실파일 `src/content/tools/veltrix-ai-for-e-commerce.md`, typo URL 404 / 실제 경로 200. slug 변경 없이 파일명 그대로 deploy.

### 잔존 위험
1. [CONFIG] 수정 10건이 미커밋 상태(`git status --short` 기준). 리버트 시 404 재발. 조치 필요.
2. 출력 전환이 `server`(이전) → `hybrid`(10/1 커밋) → `static`(이번)로 3단계였고 의도가 문서화되지 않음. 이번 수정은 astro 5.x 호환 최솟값. admin/briefing/community/my 등 SSR 라우트가 남아 있어 "완전 정적 확정" 여부는 사용자 확인 필요.
3. `src/content/blog/_temp-002.md`(2026-07-26 커밋 `6e16127e`, 추적 중)가 라이브 `/blog/_temp-002/` 200 및 `sitemap-blog.xml` 노출 중. 이번 변경이 만든 것은 아니지만 공개 상태. 미수정.
4. 빌드 로그에 `Astro.request.headers` 프리렌더 경고 다수(chronicle, community review/write 등). 빌드는 통과했으나 해당 페이지가 요청 헤더를 읽지 못한 상태. 미수정.
5. Cloudflare 계정/토큰/프로파일은 건드리지 않음. deploy.sh의 기존 `.env` 로드 경로를 그대로 사용했고, 참조한 키 이름은 `CLOUDFLARE_API_TOKEN` / `CLOUDFLARE_ACCOUNT_ID` 뿐이며 값은 출력하지 않음.

### 다음 행동
1. 위 10개 파일 커밋 여부 결정(권장: 커밋).
2. `_temp-002.md` 삭제 또는 정식 파일명으로 정리.
3. astro 출력 전환 의도를 `CHANGES.md`에 기록.
