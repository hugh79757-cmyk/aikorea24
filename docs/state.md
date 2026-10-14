## 2026-10-14 14:05 AIK24-EMDASH-06 완료 — 블로그 표 렌더링 근본 해결(10+1건/19표/147행) → SSOT/프로젝트/aikorea24/지시서/2026-10-14-1405-AIK24-EMDASH-06-완료보고.md (완료 — verify는 시니어2)

### 한 일
- [PRODUCTION CODE] `~/projects2/aikorea24emdash/scripts/fix_tables.py` 신규(331줄). 커밋 `0adc9cc` + `0d4bdda`, GitHub 푸시 완료.
  - **쓰기 경로 = EmDash API**(D1 직접 UPDATE 안 씀 — 렌더 소스가 `revisions.data` 이라 정합성 깨짐): MCP `content_get` → `_rev` 획득 → `PUT /_emdash/api/content/posts/{id}` → `POST .../publish`. D1 은 탐색 전용.
  - 안전장치 지시서 §작업3 3항목 전부 이행: 변환 전 원본 백업(`scripts/logs/table_fix_backup_2026-10-14/`, 10개/212KB) → 애매 파이프 줄은 원본 유지+제외 목록 → dry-run 선행 후 적용.
  - 모드: `--dry` / `--apply` / `--prefix`(백업 원본 재변환) / `--limit`.
- 배포: **미실행** — 지시서 §배포 "D1 데이터 수정이므로 Worker 재배포 불필요", 렌더러 코드 미변경.

### 결과
- [검증됨] **작업1 피해 규모 = 21건**(`ec_posts` content 에 마크다운 구분선 패턴. `content LIKE '%|%'` 55건, `<table` 0건). 목록은 `/tmp/emdash06_targets.json`.
- [검증됨] **작업2 table 스펙**(`node_modules/@emdash-cms/admin/dist/portable-text-table.d.ts`):
  - block `{_type:"table", _key, rows:[TableRow], hasHeaderRow?:bool, markDefs?}`
  - row `{_type:"tableRow", _key, cells:[TableCell]}`
  - cell `{_type:"tableCell", _key, content:[PortableTextSpan], isHeader?:bool, colspan?, rowspan?, colwidth?:number[], textAlign?:"left"|"center"|"right"|"justify", markDefs?}`
  - span `{_type:"span", _key, text, marks?}`
  - 헤더 구분 = 블록 `hasHeaderRow:true` + 헤더행 셀 `isHeader:true`. alignment 은 구분선 행에서 추출(`:---`→left, `:---:`→center, `---:`→right).
- [검증됨] **작업4 변환 적용 11건 / 표 19개 / 행 147**. 재측정 잔여 5건 = 바이브코딩 워크쓰루 5건(아래 참조), 즉 **표로 판정 가능한 글 0건**.
- [검증됨] **작업5 검증 6/6 통과** — 제보 글(구글 플레이스토어) + 무작위 5건 전부 `table≥1 AND th≥1 AND <p>…|…</p> 0건`:
  - 독자 파운데이션 table=5/th=21/td=111 · free-models 2/9/121 · deepseek-v4 1/4 · private-offline 1/4 · 부트캠프란 1/5 · **구글 플레이스토어 1/4/12**.
  - ego-browser(spaceId 4) 제보 글 DOM: `table` 1개, 4행×3열(`이용 자격 / 게시 비용 / 주요 활용 도구 / 앱 공개 범위`), 파이프 문단 0.
- [검증됨] 바이낸스 글(2차 수정분) table=1/th=4/td=12/파이프문단=0.

### 실행 중 발견·수정한 버그 3건
1. `block_text()` 가 span 을 2번 append(중복 텍스트) → 분기 처리.
2. ★ `has_header = (d == 0)` 로 짚어 **헤더행 통째로 유실**(1차 라이브 반영). `d >= 1` 로 수정 후 **백업 원본으로 10건 전량 재적용**(행 124 → 142).
3. ★ 구분선 행의 앞뒤 파이프가 이관 과정에서 잘려 `--- | --- | ---` 로 남는 경우를 `split_row` 가 거부 → 바이낸스 글 1건 변환 누락. 앞뒤 파이프를 강제하지 않도록 수정 후 적용.

### 잔존 위험
1. **바이브코딩 워크쓰루 5건의 파이프 문단 11/10/11/10/11개는 미변환** — 지시서 §작업3-2(애매한 파이프 줄 미변경) 준수. 라이브 확인 결과 `GitHub | Pages | Vercel` 처럼 **링크를 나열한 인라인 목록**이며 표가 아님. 원본 데이터 복구가 필요하면 별도 지시서.
2. 제외 5건(`free-lecture-*` 4 + 무료-llm-인클루전아이 1)은 soft-deleted(`deleted_at` 설정, 라이브 미노출). API 404 로 변환 불가.
3. 1차 변환에서 헤더행 유실 상태가 라이브에 2~3분 노출됨(현재 정상).
4. [검증불가] 표 렌더가 Google 크롤러·네이버 프리뷰에서 동일하게 보이는지 — 사이트 외부 렌더링이라 내부 실측 불가. 수치 데이터는 표로 정확히 표시됨(위 HTML 근거).

### 다음 행동
- 대표님: 바이브코딩 5건의 파이프 나열을 표로 바꿔야 하는지, 아니면 링크 목록 유지가 맞는지 결정.
## 진행 중 (2026-10-14, AIK24-EMDASH-06) — EmDash 블로그 마크다운 표 → table 블록 변환

## 2026-10-14 13:47 AIK24-RENEWAL-02 완료 — 색상 흑백+상징빨강 통일 / 7일 강의 삭제 → SSOT/프로젝트/aikorea24/지시서/2026-10-14-1347-AIK24-RENEWAL-02-완료보고.md (완료 — verify는 시니어2)

### 한 일
지시서: `SSOT/프로젝트/aikorea24/지시서/2026-10-14-1340-AIK24-RENEWAL-02-색상통일+7일강의삭제.md` (47줄). 대표님 결정 ① 색상 전부 흑백, 유일한 예외 상징 빨강 `#E63B2E` ② 7일 강의는 상품이 없으므로 관련 페이지·진입점 전부 삭제.

#### 작업 1 — 색상 (PRODUCTION CODE 1파일)
- [PRODUCTION CODE] `src/pages/chronicle/index.astro`
  - `categoryConfig` 의 `color: "blue"/"green"/"red"/"purple"/"amber"` 5개 필드 **삭제**. 근거: 91행 `cfg.emoji` 만 사용, `cfg.color` 참조 0건(죽은 코드). 타입 `Record<string, { emoji: string }>` 로 축소.
  - `borderColorClass` 5개(`border-l-blue-500`/`green`/`red`/`purple`/`amber-500`) → **전부 `border-l-[#E63B2E]`**.
  - `catColorClass`(정책·규제 빨강 배지)는 지시서 §3에 따라 **미변경**.
  - `src/styles/global.css` 미변경(§4 준수). 카테고리 이모지 5개 유지(§6 준수). `src/auto_poster/` 미변경.

#### 작업 2 — 7일 강의 삭제 (PRODUCTION CODE 4파일 + 삭제 6파일)
- [PRODUCTION CODE] `src/components/home/HeroSection.astro` — 홈 CTA `<a href="/courses/7day-starter/">7일 강좌 시작하기 →</a>` 블록 삭제, 남은 `/about` 링크에 `group` 클래스+`→` 스페인 이관.
- [PRODUCTION CODE] `src/pages/subscribe.astro` — `🔗 강좌 연계` 카드 삭제, grid `sm:grid-cols-3` → `sm:grid-cols-2`.
- [삭제] `src/pages/courses/7day-starter.astro`, `src/pages/api/courses/` 전체(enroll/interest/track/send-daily.ts + templates/lesson-email.ts). 근거: 6파일 전부 7일강의 전용(track=lesson_clicks 테이블, send-daily="7일 강좌 자동 발송", lesson-email="7일 AI 입문 강좌"), `src/` 내 외부 참조 0건, launchd plist 에서 send-daily 호출 0건.

### 결과
- [검증됨] **색상 grep 0건**: `grep -rniE "green|pink|blue|purple|amber|yellow|teal" src/ --include="*.astro" --include="*.css" | grep -v "^src/auto_poster/" | wc -l` → **0**. (수정 전 8건, 전부 `chronicle/index.astro`)
- [검증됨] **7일강의 grep 0건**: `grep -rniE "7day|7-day|7일 ?강좌|7일 ?강의" src/ public/ | grep -v "^public/images/"` → **0**(exit 1).
- [검증됨] 빌드: `npm run build` → **EXIT 0** (`✓ Completed in 6.05s`, `Server built in 10.63s`, `Complete!`).
- [검증됨] 배포: `npm run deploy` → **Current Version ID `19125a64-21a0-406a-aa5d-ef86c0225440`**, `Uploaded 19.19 sec`, sitemap ping `{"google": true, "naver": true}`.
- [검증됨] 라이브 HTTP: `/` 200, `/chronicle/` 200, `/subscribe/` 200, `/courses/` 200, **`/courses/7day-starter/` 404**.
- [검증됨] 라이브 참조 0건: `/`·`/subscribe/`·`/chronicle/` HTML 모두 `7day|7-day|7일 ?강좌` **0건**.
- [검증됨] **chronicle border (ego-browser 실측)**: `class="border-l-[#E63B2E]"` 요소 **67개**, `getComputedStyle` 결과 **전건 `borderLeftColor: rgb(230, 59, 46)`(= #E63B2E) / `borderLeftWidth: 4px` / `solid`**, 4px 아닌 것 **0개**. 라이브 CSS(`/_astro/Layout.Zo4j6TRk.css`)에 `border-left-color:#e63b2e` 존재, 이전 blue/green/purple/amber border CSS **0건**.
- [검증됨] 카테고리 이모지 5개(🤖🏢📜🇰🇷💥) 라이브 chronicle 본문 모두 존재.
- [검증됨] 홈 hero CTA = `더 알아보기 → => /about` 1개, 7일강좌 링크 **0개**.
- [검증됨] `/subscribe/` 카드 = `오늘 쓸 수 있는 소식`, `AI 도구 소개` 2개, `7일|7day` 텍스트 **없음**.
- [검증됨] 깨진 이미지 **0건**(chronicle·홈).
- [부분검증] 스크린샷 육안 — ego-browser `page.screenshot()` 이 `Page.captureScreenshot` CDP 타임아웃으로 **미확보**(3회 시도). 위 computed-style 67/67 확인이 색상 검증의 근거이며, 픽셀 단위 육안은 미수행.

### 1번 grep 결과 목록 (지시서 작업2 §1 첨부)
`grep -rni "7day\|7-day\|7일" src/ public/` (public/images 제외) → 총 24건.
**삭제 대상(7일 강의 관련, 6곳)** — `src/components/home/HeroSection.astro:32-34`, `src/pages/courses/7day-starter.astro`(9·10·11·16·39·43·79·165행), `src/pages/subscribe.astro:38`, `src/pages/api/courses/enroll.ts:29`, `src/pages/api/courses/send-daily.ts:6`, `src/pages/api/courses/templates/lesson-email.ts:104`.
**삭제 금지(무관, 18건 유지)** — `src/content/tools/dailyhelm.md:31·34·56·76`(SaaS "7일 무료 체험"), `src/content/tools/appto.md:31·34`(동일), `src/content/chronicle/2026-07-01-anthropic-fable5-재배포.md:22`(뉴스 본문 날짜), `src/pages/api/articles/pool.ts:54`("최근 7일 news" 주석), `src/pages/refund.astro:21·23`(청약철회 7일, 「전자상거래법」 제17조).

### 잔존 위험
1. **D1 `courses` 테이블에 2행 잔존** — `7day-starter`(삭제된 페이지), `7day-infra`("0원 인프라, 7일", `src/` 참조 0건으로 이미 고아). 지시서 §범위 밖(DB 삭제)이라 **코드/D1 미변경**. 대표님 판단 대기.
2. `src/pages/courses/index.astro` 는 **7일강의 아님**(RENEWAL-01 §7-3 유료 강의 사전등록). 삭제하지 않음 — 유지.
3. 스크린샷 미확보(위 [부분검증]).
4. `docs/state.md` 에 동시 FREE-PIPE-01 진행중 줄 존재(다른 세션 산출물, 미수정).
5. B-3/B-4/B-5/B-7 정량 스펙 부재 → 미착수(지시서 §범위 밖).

### 다음 행동
- 대표님: D1 `courses` 테이블 2행 정리 여부 결정.
- 별도 지시서 대기: B-3/B-4/B-5/B-7(디자인 스펙), A안 콘솔 캐시 규칙.

## 진행 중 (2026-10-14, AIK24-FREE-PIPE-01) — 무료 모델 수집·평가·발행 일일 파이프라인 (model_catalog.py 신규 + diff + 리스트 페이지 + launchd)

## 2026-10-14 13:45 AIK24-RENEWAL-01 B그룹(디자인 7건)현황 감사 — B-1/B-2 이미 적용됨 확인, 잔여 1건 + 스펙 확인 대기

### 한 일
- 지시(원문): "10-11 백로그(B디자인·C버그·D프롬프트·E이관) … 다해줘 / 마무리 하자."
- [PRODUCTION CODE] **없음.** 감사만. 이유 하단.

### 결과 — B그룹 7건 실측
| 항목 | 상태 | 근거 |
|---|---|---|
| B-1 7일강의 배경(검정→흰/검정텍스트) | **[완료]** | `courses/7day-starter.astro:25` `class="bg-white text-[#111111] min-h-screen"`. 검정 배경 아님. |
| B-2 초록/핑크 제거(전제 "25개 파일") | **[사실과 불일치 — 잔여 1건]** | `global.css` 토큰은 이미 흑백+빨강(`--bg-primary:#ffffff`, `--text-primary:#111111`, `--accent-red:#E63B2E`). `grep -rniE "green\|pink" src/` → 웹 UI 에 **2건만**. Tailwind 초록/핑크 21건은 전부 `src/auto_poster/`(Threads 카드, 웹 아님). |
| B-3 타임라인 통일 | **[감사 불가]** | 대상 4파일(`tools/finder`, `compare`, `chronicle/[...id]`) 확인. "통일" 기준이 스펙에 없어 판정 불가. |
| B-4 푸터 통일 | **[감사 불가]** | `src/components/` 에 Footer 컴포넌트 없음 — `layouts/Layout.astro` 인라인. 비교 대상 부재. |
| B-5 EmDash 헤더/푸터 | **[감사 불가]** | EmDash CMS 소스(`~/projects2/aikorea24emdash`) 대상. aikorea24 사이트와 디자인 기준 공유 여부 불명. |
| B-6 블로그 타이포(글자크기·대칭·표→단락·여백) | **[대상 이동]** | Astro 블로그 소스 삭제 완료(EMDASH-04) → 대상이 `~/projects2/aikorea24emdash/src/pages/posts/[slug].astro` 로 옮겨감. |
| B-7 마스코트 배치 | **[감사 불가]** | `mascot` 참조 5파일(`home/HeroSection`, `home/ToolsSection`, `404`, `global`, `unsubscribe`). "배치" 기준 미정의. |

- [검증됨] B-2 잔존 2곳: `src/pages/chronicle/index.astro:17` `color: "green"` — **죽은 필드**(91행에서 `.emoji` 만 사용, `.color` 미사용) / `:37` `border-l-green-500` — `borderColorClass()` 에서 실제 사용됨.
- [검증됨] E그룹(블로그 이관)은 EMDASH-01~05 로 완료. D그룹도 D-1/D-2/D-3 완료. C그룹 5건 완료.

### 잔존 위험
1. **B그룹 잔여 5건(B-3/B-4/B-5/B-6/B-7)을 임의 스펙으로 수정하지 않음** — RENEWAL-01 의 서술은 "통일/대칭/여백" 처럼 정량 기준이 없어 재작업하면 대표님 의도와 어긋날 수 있음.
2. chronicle 의 5개 카테고리는 blue/green/red/purple/amber 색 구분|border-left)이라 "green 만 제거" 하면 5색 중 1개만 빠진 비대칭 상태가 됨.
3. `border-l-green-500` 는 실제 렌더에 영향. 미수정 상태.

### 다음 행동
- 대표님: (a) chronicle 초록 border 색 결정(검정/회색/유지) (b) B-3~B-7 정량 스펙(또는 대상 화면 스크린샷) 제공 시 그 기준으로 재작업.
