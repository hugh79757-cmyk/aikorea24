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
