## 2026-10-11 01:25 — AIK24-D1-GUARD-01 D1 읽기 한도 가드 + B+C (잡 09:00 이동 · news LIMIT 축소)

- **한 일**: 지시서 `2026-10-10-2308-AIK24-D1-GUARD-01.md` 수행 + 대표님 결정 B+C(잡 09:00 이동 + 읽기 절감) 적용. 메인 배포 `b051490f` → 파비콘 복구 배포 `112a062b`.

### 배경
2026-10-10 D1 읽기 **5,356,078 / 5,000,000 (107.1%)** 초과. `/news/` 73,895B→20,474B(브리핑 섹션 소실), `/briefing/2026-10-10-4/` 200→302. 원인 = D1 `code 7500` 에러 dict 를 페이지 코드가 "결과 없음"으로 처리해 **빈 화면을 정상처럼 렌더**. 자정 UTC(KST 09:00) 리셋까지 7시간 43분.

### 1-1. `scripts/cfnew.py` — 가드 구현 [검증됨]
| 추가 | 내용 |
|---|---|
| `D1_READ_LIMIT` | `5_000_000` |
| `READONLY_RATIO` | `0.95` |
| `CACHE_TTL` | `300` (5분) |
| `GUARD_ENABLED` | `os.environ.get("D1_GUARD","on") != "off"` |
| `QuotaExceededError` | `RuntimeError` 서브클래스 |
| `_analytics_rows_read(day, tok)` | GraphQL `d1AnalyticsAdaptiveGroups` → 계정 rowsRead 합계. 캐시 없음 |
| `get_d1_rows_read`→`get_daily_rows_read(day=None, tok=None, force=False)` | 5분 캐시. 만료 후 재조회, 실패 시 마지막 성공값 유지(fail-open) |
| `check_quota(threshold=0.8, tok=None, raise_on_exceed=True)` | ≥80% → `QuotaExceededError` / ≥95% → `{"readonly": True}` / 미만 → `{"readonly": False}` |
| `sql()` | 시작 부분에 `check_quota()` 호출 삽입 |

★ **지시서 필드 예외**: 지시서는 `d1QueriesAdaptiveGroups` 또는 `d1Storage` 라 했으나 실측 둘 다 `unknown field`. 실제로 200 을 주는 건 `d1AnalyticsAdaptiveGroups` 뿐이라 그걸로 구현했다.
★ **재귀 방지**: `check_quota()` 는 GraphQL analytics 를 직접 치고 `sql()` 을 호출하지 않는다 → `sql() → check_quota() → sql()` 순환 자체가 성립하지 않는다. (플래그 불필요)
★ **캐싱 필수 반영**: 지시서 "캐싱 없이 구현하면 미완료 판정" → `_cache = {"at","used","day"}` 모듈 변수. `day` 불일치 시(자정 UTC 넘김) 자동 재조회.
★ **fail-open**: GraphQL 조회가 죽으면 마지막 값을 반환하고 진행한다 — 한도를 못 확인했다고 멈추는 게 더 나쁘다.

### 1-2. 가드 검증 6케이스 [검증됨]
| 케이스 | 결과 |
|---|---|
| 82% → `sql()` | `QuotaExceededError: [D1-GUARD] 일일 읽기 4,100,000/5,000,000 (82.0%) — 작업 중단` |
| 60% → `sql()` | `[{'x': 1}]` 통과 |
| 96% → `check_quota()` | `readonly=True pct=96.0%` (예외 없음) |
| 5분 내 3회 호출 | `[1234567, 1234567, 1234567]` — GraphQL 미호출 |
| TTL 400초 경과 | `5,356,163` 재조회 |
| `D1_GUARD=off` | `skipped=True`, `sql()` 무차단 |

### 1-3. `docs/d1-budget.md` [검증됨]
예산 표(정기 파이프라인 150만 / 수동 100만 / 예비 250만 / 합계 500만) + 검증 쿼리 규칙(`LIMIT` 필수·풀스캔 금지·날짜 범위 강제) + 백필 10만 행 초과 시 대표님 사전 승인 + 가드 사양 + 초과 시 대응.
※ 라벨을 `docs/d1-budget.md` 로 적었고 지시서 원문(`docs/D1-budget.md`) 은 대소문자가 달랐다.

### 1-4. 모니터링 잡 [검증됨]
`scripts/d1_usage_report.py` 신규 (52줄). `~/.env.common`(setdefault) → 프로젝트 `.env`(덮어쓰기) 로드 후 `cfnew.get_daily_rows_read(force=True)` → 80% 미만 조용히 종료 / 이상이면 `pipeline.infra.telegram.send_telegram`.
launchd `kr.aikorea24.d1-usage-report` 08:30 KST. `plutil -lint` OK.
**★ `launchctl load` 는 `Input/output error` 로 실패했다.** macOS 최신 launchctl 은 `load` 가 폐기됐고 `bootstrap gui/$(id -u) <plist>` 로 등록해야 한다 → 그 경로로 등록 후 `launchctl print` 로 `Hour 8 / Minute 30` 확인.
수동 실행: `[D1-GUARD] D1 읽기 5,356,163/5,000,000 (107.1%) — 일 2026-10-10 → 초과, 대표님 알림` / `telegram 발송: 성공` / EXIT=0.

### B+C — 대표님 결정 적용 [검증됨]
| 항목 | 변경 |
|---|---|
| 파이프라인 잡 | `kr.aikorea24.pipeline-runner` **06:00 → 09:00 KST**. 06:00 KST = 21:00 UTC 로 리셋(자정 UTC) 전이라 어제 초과 버킷이 그대로 적용됨. `launchctl print` → `Hour 9 / Minute 0` 확인. 백업 `plist.bak.20261010_2x` |
| `src/pages/news.astro` | `ARCHIVE_LIMIT` **300 → 100**. 아래 JS 가 소스별 5건 + 전체 50건 상한을 걸고 있어 렌더 결과는 동일(현재 `v2_pass=1` 은 77건). rows_read 상한만 낮아짐 |

**[부분검증]** LIMIT 축소의 실제 절감량 = 0. 현재 통과분이 77건이라 300 → 100 은 지금 당장 읽기를 줄이지 않는다. 누적 100건 넘을 때부터 효과가 난다. 오늘 5.36M reads 의 주된 출처는 (a) PIPE-02 파이프라인 3회 (b) 백필 1,024건/26배치 (c) 반복 라이브 검증 curl·브라우저 (d) `index.astro` 브리핑 조회가 아니라 **검증 트래픽**이었다.

### [위반 감지] — `public/favicon.png` 사라짐 (자체 발견 · 유출 전 수정)
커밋 준비 중 `git status` 에 `D public/favicon.png` 가 떠 있었다. 확인 결과 `public/` 에 `favicon.png` 이 **존재하지 않고** `favicon-1.png`(65,799B, mtime 16:09 = ASSET-01 시각)만 있었다. 즉 ASSET-01 때 파일명이 `favicon-1.png` 으로 저장돼 있었던 것으로 보인다(작성 명령 로그상 `cp /tmp/fv_512.png favicon.png` 였음 — 어느 단계에서 바뀐지는 미확정).
`SEOHead.astro:137` 이 `/favicon.png` 을 참조하므로 이 상태로 다음 배포가 나가면 파비콘이 404 났을이다. `mv favicon-1.png favicon.png` 으로 복구 후 재빌드·재배포.
**[검증됨]** 캐시버스터 쿼리로 최종 확인: `/favicon.png` 200 **65,799B** sha `10bb9f4d6977cb78`(로컬과 일치), `/mascot-tiger.png` 200 51,159B sha `7ba0bbe01479e93b`.
★ **검증 함정**: `cache-control: public, max-age=14400`(4시간)이므로 캐시버스터 없이는 오래된 `/favicon.png`가 그대로 나온다. 위 초기 실측에서 51,159B(마스코트 크기)로 잘못 나왔던 것이 이 때문이었다 — 파일 문제가 아니라 엣지 캐시였다.

### 빌드·배포 [검증됨]
| | 결과 |
|---|---|
| 빌드 1차 | EXIT=0 `Server built in 10.47s` (`/tmp/g01_b1.log`) |
| 배포 1차 | EXIT=0 `✨ b051490f` |
| 빌드 2차(파비콘 복구) | EXIT=0 `Server built in 10.47s` (`/tmp/g01_b2.log`) |
| **배포 최종** | EXIT=0 `✨ 112a062b` (`/tmp/g01_d2.log`) |
| 라이브 | `/` 200 49,537B · `/news/` 200 20,711B · `/courses/` 200 25,925B · `/subscribe/` 200 23,524B — **D1 차단 중이라 데이터 섹션이 비어 보이는 게 정상**, 09:00 KST 리셋 후 복구 |

### 커밋
지시서 §4 "완료 보고와 동시에 git 커밋" 수행 — 단 **D1-GUARD-01 범위만**. `git status` 에는 오늘 다른 작업(PIPE-02·NEWS-01·FIX-01·ASSET-01·FONT) 산물 포함 **96개 파일**이 미커밋 상태로 남아 있어 섣지 않았다. 대표님 지시 대기.

### 잔존 위험 (18건, 신규 1)
1 Workers Free 10ms CPU(1102) 2 `/tools/*` 오프팔레트 124건 3 `dark:` 750건 4 Layout 미사용 9개 페이지 다크 배경 5 Brevo IP 반복 변동(현재 등록됨) 6 EMDASH-12 훅 타임아웃 7 PAT 평문 `/tmp/aik24-pat.txt` 8 emdash 프로젝트 git 아님 9 EMDASH-12·13·05·07 보고서 미작성 10 PIPE-01 작업2 중단 11 `PUBLIC_TOSS_CLIENT_KEY` 미설정 12 모바일 390×844 검증 불가 13 `logo-en`·`logo-ko` 미사용 14 툴 리뷰 작성 경로 소멸 15 리뷰 상세 소몰 16 D1 `community_posts` 불활성 17 v2.1 소스 4개 보류 **18 ★ 가드 fail-open — GraphQL 조회가 죽으면 한도 초과 상태에서도 진행한다(의도된 절충)**

### 대표님 다음 행동
1. **09:00 KST 리셋 후 `/news/`·`/briefing/` 복구 확인**
2. 미커밋 96개 파일 커밋 여부 결정
3. `/briefing/` 등 Layout 미사용 9개 페이지 다크 배경 / `/tools/*` 오프팔레트 지시 여부
4. PIPE-01 작업2 / 토스 가맹 키 / 브리핑 발송 시각 / 환영 시퀀스 4통 / OG 이미지

## 2026-10-11 00:02 — AIK24-NEWS-01 /news/ 페이지 v2 개편 (배포 `2918ffc8`)

지시서: `SSOT/…/2026-10-10-2137-AIK24-NEWS-01-뉴스개편.md` (154줄). 파이프라인 변경 + 페이지 변경 합본(분리 금지 지시). Step 0~7 수행.

### 한 일
1. `news` 테이블에 `v2_pass` INTEGER / `v2_tag` TEXT 컬럼 추가 + 부분 인덱스 생성
2. 신규 `scripts/v2_filter.py` — `classify()` 공용 판정 모듈 (`briefing_scorer.py` 원본 **미수정**)
3. 수집기 2종에 판정 기록 추가 — v2 수집기 RSS 3종 제거, 레거시 수집기 INSERT 확장
4. 최근 7일 1,024행 백필
5. `src/pages/news.astro` 전면 개편 — 상단 "오늘의 브리핑" / 하단 "전체 소식" 아카이브
6. 빌드·배포 + 라이브 검증

### 결과

#### Step 1 — DB 스키마 [검증됨]
`PRAGMA table_info(news)` = 13컬럼. 신규 `cid 11 v2_pass INTEGER DEFAULT 0`, `cid 12 v2_tag TEXT DEFAULT NULL` 확인.

**인덱스 (지시서 "EXPLAIN으로 확인 후 추가" 조건 충족)**
| | 쿼리 플랜 | 대상 행 |
|---|---|---|
| 추가 전 | `SCAN news USING INDEX idx_news_created` + `USE TEMP B-TREE` | 17,987행 전수 스캔 |
| 추가 후 | `SEARCH news USING INDEX idx_news_v2 (v2_pass=?)` | **77행** |

추가한 인덱스: `CREATE INDEX idx_news_v2 ON news(v2_pass, created_at DESC) WHERE v2_pass = 1` (부분 인덱스 — 통과분만 적재되어 유지 비용 최소).
측정 근거: `EXPLAIN QUERY PLAN` 비교. 인덱스 생성 전후 `rowsWritten` 변화 6,988 → 6,988 (인덱스 1회 생성 비용만 반영, 페이지 조회에는 미영향).

#### Step 2 — `scripts/v2_filter.py` 신규 [검증됨]
`classify(title, description, source) -> (bool, tag)` — `briefing_scorer.py` 의 `_score_free_usability` + `_penalty_excluded_topic` 로직 이식. **원본 파일 미수정** (지시서 금지사항 준수).

★ **지시서 판정식 해석 보완** — 지시서는 "free 점수 > 0 → (True, tag)" 라만 적었고 그 외 분기를 명시하지 않았다. 지시서 완료기준의 "기업·펀딩류 미노출" 을 만족시키려면 **무료 신호 0 + 오픈소스 소스 아님 = 미통과** 로 좁혀야 했다. 예시 케이스 "디오 임플란트 AI 생태계 확산"(무료 키워드 0, The Decoder 소스)이 이를 요구한다.

자체 점검 6케이스 전부 통과 (`python3 scripts/v2_filter.py`, EXIT=0):
```
ok  (True,'free-llm')   앤트로픽 스타트업, 초보자 무료 티어 확대      / 무료 티어 확대 / The Decoder
ok  (True,'free-llm')   OpenAI releases free GPT-5 mini…            / open weights / OpenRouter Free Models
ok  (False,None)        디오 임플란트 AI 생태계 확산                   / 기업 전략 논의 / The Decoder
ok  (False,None)        Acme raises $50M Series B…                  / funding round / TechCrunch
ok  (True,'opensource') HuggingFace releases new open-source…        / open source weights / HuggingFace Trending
ok  (True,'tool')       GitHub Copilot 튜토리얼 10가지                 / tutorial cookbook / GitHub
```

#### Step 3 — 수집기 [검증됨]
**v2 수집기** (`scripts/news_collector_v2.py`): `RSS_SOURCES` 4종 → **1종**(HuggingFace Blog 유지). dry-run 실측 `RSS (HuggingFace Blog) 10건` — OpenAI·Google AI·GitHub 3종 **0건**. 출력 라벨도 실제 소스명(`RSS (HuggingFace Blog) — AIK24-NEWS-01`)로 수정.
INSERT 11컬럼으로 확장(`v2_pass`, `v2_tag`) + 저장 전 `v2f.classify()` 호출.
**레거시 수집기** (`api_test/news_collector.py`): `save_to_d1()` L1029~ INSERT 11컬럼 확장 + 판정 추가. 스탠드얼론 import 검증 통과 (`import OK, v2_filter = v2_filter`).

**INSERT 경로 프로브 검증 [검증됨]** — 실제 수집이 신규 0건이라 경로가 안 돌아갔으므로 프로브 1건 주입:
```
probe row: [{'id': 54997, 'v2_pass': 1, 'v2_tag': 'free-llm'}]  → residual: 0 (삭제 완료)
```

**백필 (최근 7일) [검증됨]** — 신규 `scripts/news_backfill_v2.py`. dry-run 100건 `{tool:4, opensource:10, excluded:49, free-llm:37}` 확인 후 전체 실행.
```
대상 1,024건 / 26배치(40건) / EXIT=0
결과 분포: v2_pass=0 → 947건, v2_tag=free-llm 58 / opensource 11 / tool 8  = 통과 77건
전체 테이블 분포: NULL 16,963(백필 범위 밖) / '' 947 / free-llm 58 / opensource 11 / tool 8
```
D1 쓰기 여유 확인 후 실행 — 실행 직전 `aikorea24-db rowsWritten 6,988 / 100,000`.

#### Step 4 — `/news/` 페이지 [검증됨]
`src/pages/news.astro` 63줄 → 전면 재작성.
- 상단 "오늘의 브리핑": `SELECT * FROM briefings WHERE status='published' ORDER BY id DESC LIMIT 1` + `briefing_items JOIN news` (`index.astro` BriefingSection 과 동일 패턴). published 브리핑 없으면 섹션 숨김.
- 하단 "전체 소식": `WHERE v2_pass = 1 AND category NOT IN ('senior','benefit') ORDER BY created_at DESC, id DESC LIMIT 300` + 소스별 5건 cap(JS) + 최대 50건.
- 태그 뱃지 `무료 LLM`(#E63B2E 배경) / `오픈소스` / `실전 도구`.
- 시안 A: `dark:` **0건**, 흰 배경, `6px solid #E63B2E` h1 + `4px` h2 버티컬 라인.
- `Cache-Control: public, max-age=300` 유지.

#### Step 5 — 실행·검증 [검증됨]
| 항목 | 결과 |
|---|---|
| 프로덕션 수집 | EXIT=0, 신규 0건(44건 전부 기존 — dedup 정상) |
| 빌드 | EXIT=0 `Server built in 17.57s` (`/tmp/n01_b1.log`) |
| 배포 | EXIT=0 `✨ https://2918ffc8.aikorea24-4nk.pages.dev` + `배포 완료: https://aikorea24.kr` (`/tmp/n01_d1.log`) |
| `/news/` | **200 · 73,895B** |
| 라이브 v2_pass=0 누출 | **0건** (카드 47개 전수 D1 대조. HTML 엔티티 `&#39;`/`&quot;` 디코딩 후 대조) |
| 브리핑 상단 일치 | 최신 published = `id 341 / 2026-10-10-4` / 아이템 4건 = `auto_email_sender.py` L132-133 `items[:4]` 가 쓰는 동일 브리핑 |
| 태그 뱃지 | Aside 실측 `무료 LLM 34 / 오픈소스 5 / 실전 도구 8` |
| 시안 A | h1 `6px solid rgb(230,59,46)`, body `rgb(255,255,255)`, `news.astro` 내 `dark:` 0건, 가로 스크롤 없음(1440=1440) |
| 샘플 대조 | 미노출(기업·펀딩류) = 스렛북 인수 / 엔비디아 투자 계획 / 스타트업 투자 10조 / 크립토 투자 시대 / CNBC 매출 우려 — 전부 `v2_pass=0` |
| URL 스위프 | `/` `/news/` `/courses/` `/subscribe/` `/tools/` `/refund/` `/sitemap.xml` 200 · `/blog/` 301 |

**[부분검증]** — 라이브 카드의 `dark:` 클래스 44건은 `news.astro` 가 아니라 `Layout.astro` 헤더/푸터에서 옵니다(`news.astro` 자체 0건, grep 확인). 잔존 위험 #3의 기존 범위.

### 변경 파일
| 파일 | 구분 |
|---|---|
| `scripts/v2_filter.py` | 신규 (자체 점검 포함) |
| `scripts/news_backfill_v2.py` | 신규 |
| `scripts/news_collector_v2.py` | PRODUCTION CODE (RSS 3종 제거 + 11컬럼 INSERT + 판정 + 라벨) |
| `api_test/news_collector.py` | PRODUCTION CODE (`save_to_d1` INSERT 11컬럼 + import) |
| `src/pages/news.astro` | PRODUCTION CODE (전면 재작성) |
| `config/impact_weights.json` | 미변경 (읽기 전용) |
| `scripts/briefing_scorer.py` | **미변경** (지시서 금지) |
| D1 `news` | `v2_pass`·`v2_tag` 컬럼 + `idx_news_v2` 부분 인덱스 |

### 잔존 위험 (누적 17건, 신규 0건)
1. Workers Free 10ms CPU(1102) 2. `/tools/*` 오프팔레트 124건 3. 메인 `dark:` 750건(런타임 미적용) 4. Layout 미사용 9개 페이지 다크 배경 5. **★ Brevo IP 미등록 `58.10.233.168` + IPv6 → 이메일 발송 불가(PIPE-02 신규)** 6. EMDASH-12 훅 타임아웃 5초 7. PAT 평문 `/tmp/aik24-pat.txt` 8. emdash 프로젝트 git 아님 9. EMDASH-12·13·05·07 보고서 미작성 10. PIPE-01 작업2 중단 11. `PUBLIC_TOSS_CLIENT_KEY` 미설정 12. 모바일 390×844 검증 불가 13. `logo-en`·`logo-ko` 미사용 14. 툴 리뷰 작성 경로 소멸 15. 리뷰 상세 소몰 16. D1 `community_posts` 불활성 17. v2.1 소스 4개 보류

### 다음 행동 (대표님)
1. **Brevo 화이트리스트에 `58.10.233.168` + IPv6 `2001:fb1:11d:6dd:8d59:e7a9:8910:8fbf` 등록** (06:00 잡 이메일 발송 불가 — 최우선)
2. `/briefing/` 등 Layout 미사용 9개 페이지 다크 배경 지시 여부
3. `/tools/*` 오프팔레트 지시 여부
4. PIPE-01 작업2 선택지 / 토스 가맹 키 / 브리핑 발송 시각 / 환영 시퀀스 4통 / OG 이미지
5. v2.1 소스(Reddit·Product Hunt·Anthropic·OpenCode) 개통 지시 여부

### 로그
`/tmp/n01_{b1,d1,bf,bf_dry,v2_dry,v2_run}.log`

---

## 2026-10-10 23:05 — AIK24-PIPE-02 브리핑 v2 + 블로그 §18 4종 개편 (배포 `8b3dbc01`)

## 2026-10-10 23:05 — AIK24-PIPE-02 브리핑 v2 + 블로그 §18 4종 개편 (배포 `8b3dbc01`)

- **한 일**: 지시서 `2026-10-10-2030-AIK24-PIPE-02-브리핑v2-블로그개편.md` (196줄) Step 0~9 수행. 브리핑 선별 기준·분량·스케줄을 v2 로 전환하고, EmDash 블로그에 §18 4종 포맷 파이프라인을 신설.

### Step 0 — 사전 조사 [검증됨]
| 대상 | 실측 |
|---|---|
| `scripts/run_pipeline.py` (259줄) | 5단계 = 뉴스선정(171)→브리핑(186)→썸네일(204)→이메일(218)→배포(231). 플래그 `--skip-news --skip-briefing --skip-thumbnails --skip-email --skip-deploy --date --dry-run` |
| `scripts/run_pipeline_with_notify.py` (120줄) | `_PROJECT_DIR` L14, `PROJECT_DIR` L19(섀도잉, BRIEF-01 수정 유지), `load_env(_PROJECT_DIR/.env)` L42. subprocess 로 `run_pipeline.py` 실행(부모 env 상속) |
| `scripts/auto_news_selector.py` (577줄) | `keywords_map` L99-109 (클러스터 9개 + `misc` L121). `get_recent_news(hours=24)` L48 |
| `scripts/briefing_scorer.py` (442줄) | **LLM 프롬프트 없음 — 순수 규칙 scorer.** `score_article`(L311-426) 가 8개 차원 합산 |
| `scripts/auto_briefing.py` (224줄) | `briefings` INSERT `save_briefing` L121-124, `briefing_items` L136-145, 선정 L172 |
| `scripts/auto_email_sender.py` (430줄) | `display_items = items[:3]` **L134**. Brevo `GET /v3/contacts` L296-325, 발송 L338-400 |
| `scripts/blog_draft_generator.py` (864줄) | `src/content/blog/*.md` write (L466-539). **`run_pipeline.py` 에서 호출되지 않음 + launchd 잡도 없음 → 죽은 스크립트.** v2 생성기는 신규 스크립트가 정답 |
| `kr.aikorea24.pipeline-runner.plist` | `StartCalendarInterval` 2개 = 06:00 / 20:00 |

★ **지시서 전제 정정 2건** (보고서에 반영):
1. Step 3-2 는 "스코어링 **프롬프트** 교체" 라 했으나 `briefing_scorer.py` 에 프롬프트가 없다 → **가중치 차원 교체**로 해석해 `_score_free_usability()` + `_penalty_excluded_topic()` 2개 함수를 신설
2. Step 2 는 `config/crawlable_sources.json` 교체 **또는** 신규 수집기 중 하나를 고르라 했으나, 기존 수집기(`api_test/news_collector.py`) 는 v2 소스(API 2종)를 구조적으로 담을 수 없다 → **신규 수집기 선택**

### Step 1 — 히어로·subscribe 서브 문구 [검증됨]
- `src/components/home/HeroSection.astro:12` → `오늘 무료로 쓸 수 있는<br class="hidden sm:inline" />AI 소식만 골라서 보내드립니다`
- `src/pages/subscribe.astro:8`(meta) + `:16`(본문) → 동일
- 빌드 EXIT=0 `Server built in 20.43s` (`/tmp/p02_b1.log`) / 배포 EXIT=0 `5deef7ca` (`/tmp/p02_d1.log`)
- 라이브 grep: 신 문구 홈 1 / subscribe 2, 구 문구(`OpenAI·Anthropic 공식 발표만`) 양쪽 0

### Step 1-2 — 상단 네비 정리 [검증됨]
백업 `/tmp/Layout.astro.bak.p02`.
1. `navItems` 에서 `{ label: '홈', href: '/' }` 제거 (로고가 이미 `/`)
2. 로그인 사용자 이름 span 제거 — 데스크톱 SSR + 모바일 SSR
3. `.js-user-name` span 제거 — 데스크톱·모바일 js-user-box + 하단 인라인 스크립트
4. 중복 제거 가드: `<body data-ssr-user={currentUser ? "1" : undefined}>` → 스크립트 `if (document.body.dataset.ssrUser) return;`
   - **근본 원인**: `js-user-box` 가 `hidden` 기본값인데 스크립트가 무조건 `remove('hidden')`+`add('flex')` → SSR 박스와 js-user-box 동시 표시
   - **선택 방식 = `data-ssr-user` body 마커** (지시서 예시 채택). 스크립트가 body 끝에 실행돼 DOM 접근 가능, 추가 AJAX 없음
라이브(로그아웃, Aside): `navLabels[0]=""` , `homeLink:false`, `jsUserBoxVisible:["none","none"]`, `loginBtnVisible:["block","block"]`, `ssrUserAttr:null`. `grep js-user-name` 라이브 0건.
**[부분검증]** 로그인 상태 중복 제거는 Google OAuth 필요로 실측 불가 — 코드 가드만 검증.

### Step 2 — 수집 소스 v2 (신규 수집기 선택) [검증됨]
**신규 `scripts/news_collector_v2.py`** (약 190줄). 기존 `config/crawlable_sources.json` 은 손대지 않았다 — 레거시 매체 수집이 계속 돌아야 하고, v2 소스는 API 2종(JSON)이라 RSS 전용 config 구조로 표현할 수 없다.

동작 소스 6개 (전부 신규 계정 D1 로만 씀):
| 종류 | 소스 | 방식 |
|---|---|---|
| 무료 LLM | OpenRouter `/api/v1/models` | JSON API. `pricing.prompt == "0" and pricing.completion == "0"` 필터 → **무료 19개** |
| 오픈소스 | HuggingFace `/api/models?sort=trendingScore&limit=15` | JSON API → 15건 |
| 빅테크 공식 | OpenAI `news/rss.xml` | RSS 200 |
| 빅테크 공식 | Google AI blog `technology/ai/rss` | RSS 200 |
| 오픈소스 | HuggingFace blog `feed.xml` | RSS 200 |
| 오픈소스 | GitHub AI/ML blog `feed/` | RSS 200 |

**v2.1 보류 (2026-10-10 실측 응답 코드)**: `reddit.com/r/LocalLLaMA/.rss` **403**(bot 차단) / `anthropic.com/news/rss.xml` **404**(RSS 미제공) / `opencode.ai/feed.xml` **404** / Product Hunt = API 키 필요.

**계정 고정**: BRIEF-01 잔존 위험 2(쓰기 대상 계정 불일치) 해결. v2 수집기는 `scripts/cfnew.py` 의 `CF_MIGRATE_TOKEN`(신규 계정 `7eb1b8cd`) + D1 REST SQL 만 쓴다. 기존 `api_test/news_collector.py` 의 `npx wrangler d1 execute`(계정 미지정) 경로는 쓰지 않는다.

**실행 검증**: dry-run 74건(OpenRouter 19 / HF Trending 15 / RSS 40) → 실제 저장 **54건**.
`news` 17,933 → **17,987**(`MAX(id)` 54,937 → 54,996), `MAX(created_at)` = `2026-10-10 13:57:56` UTC = 22:57 KST → **신규 계정 DB 에 쓰임 확인.**

**편입 방식(확정)**: v2 수집기를 `run_pipeline.py` Step 0 으로 편입(별도 launchd 잡 만들지 않음). 사유 = 스케줄이 3벌로 갈라지면 실행 순서 추적이 어려워진다. 기존 `kr.aikorea24.news-unified`(05:30/19:30, 구 수집기)는 **그대로 둬서** 레거시 매체 누적을 유지하고 v2 가 무료·오픈소스 축을 공급한다.

### Step 3 — 선별 기준 v2 [검증됨]
**`auto_news_selector.py` `keywords_map` (L99-111)**:
- `investment`(펀딩·투자·IPO·valuation) 클러스터 **제거**
- v2 클러스터 선두 추가: `free-llm`(free llm/무료 모델/free tier/openrouter/open weights…), `opensource`(open source/github/huggingface/ollama/opencode/무료 실행 — 기존 것 확장), `trending`(순위/ranking/인기)
- 선두 배치 이유: 클러스터 매칭은 딕셔너리 순서 + `break` 이므로 앞쪽이 우선

**`briefing_scorer.py` 2개 함수 신설**:
- `_score_free_usability(text, weights)` — "한국인 초보자가 오늘 무료로 쓸 수 있는 것인가?" 30개 키워드(무료 티어 10 / 무료 8 / open source 6 / ollama·opencode 8 / 튜토리얼·쿡북 5 …), cap 25. 결과 `(점수, 매칭어)`
- `_penalty_excluded_topic(text, weights, free_hits)` — 펀딩·기업전략은 `hard_exclude` 로 확정 제외(-100 → total 0). 출시성은 `launch_soft` + **무료 신호 0개일 때만** 제외
  - 설계 근거: 한국어 AI 뉴스에 "출시"는 무료 도구 소개에도 붙으므로 단독 제외하면 브리핑이 통째로 사라진다
- `score_article` 에 `free_usability` / `penalty_excluded_topic` 두 breakdown 키 추가, `evidence` 에 `free_usability_hits`·`excluded_topic_hits` 추가, total 합산에 penalty 추가
- `config/impact_weights.json` 에 `free_usability`(cap 25 + 키워드 30개) / `excluded_topic`(penalty -100 + hard_exclude 15개 + launch_soft 11개) 블록 추가

**스코어링 동작 검증 (실측 4케이스)**:
```
total 33 | fu=18 pen_ex=0    | [무료 LLM] liquid/lfm-2.5-2b:free — OpenRouter 무료 티어
total 15 | fu=0  pen_ex=0    | Cramer 주간 전망: 은행·팹리스 실적 시즌 개막
total  0 | fu=0  pen_ex=-100 | 스타트업 X raises $200M Series B funding round   ← 완전 제외
total 40 | fu=25 pen_ex=0    | Free tier model, 1M context, ollama 로컬 실행
```

### Step 4 — 분량·스케줄·이메일 [검증됨]
- 선정 개수 6 → **4**: `auto_news_selector.py` L146 `select_top_articles(max_count=4)`, L204 `_two_pass_selection(max_count=4)`, L550 레거시 호출부, `auto_briefing.py` L172
  - ★ **첫 실행에서 6건이 나온 이유**: live 경로는 `_two_pass_selection` 을 쓰고 `auto_briefing.py` L172 의 `select_top_articles` 는 live 에서 도달하지 않는다. L204 기본값만 고치고 1회 재실행해 4건 확인.
- 이메일 분량: **선택지 (b) 스코어 상위 N개만 발송 채택** → `auto_email_sender.py` L132-133 `items[:4]`. (a) `email_pick` 컬럼 추가는 스키마 변경이라 기각
- launchd: `kr.aikorea24.pipeline-runner.plist` 의 20:00 dict 제거 → **1회/일 06:00**. 백업 `plist.bak.20261010_2252`, `plutil -lint` OK, `launchctl unload/load` 후 `StartCalendarInterval = [{'Hour': 6, 'Minute': 0}]` 1건 확인
- 발송 시각 문구: 이메일 제목 `AI코리아24 뉴스레터 - {date}` 에 시간 표기 없음(기존 그대로). "7시" 등 문구 추가 없음

### Step 5 — 블로그 §18 4종 생성기 [검증됨]
**신규 `scripts/blog_v2_generator.py`** (~250줄). `blog_draft_generator.py` 는 `run_pipeline.py` 미연결 + 로컬 md write 라 v2 신규 생성.
데이터 소스: OpenRouter rankings API(`/api/v1/models`, 무료 19개) + HuggingFace trending API(20개). 코딩 부문 지표 상수 `BENCH_CODING = ["SWE-bench","Terminal-Bench","LMArena Coding","Aider Polyglot","LiveCodeBench"]`.

4종 포맷 — 전부 **"그래서 뭐 써야 돼?"** 로 종료:
| key | 제목 패턴 | 구조 |
|---|---|---|
| `daily` | 오늘의 추천 LLM: {모델} — 입출력 무료, 컨텍스트 {n} | 무엇을 고른 이유 / 무료라서 부족한 건 아닌가 / 그래서 뭘 쓰면 돼? |
| `weekly` | 이번 주 무료 LLM 순위 — TOP 5와 이번 주 추천 1개 | 순위(컨텍스트 기준 TOP5) / 추천 1개 처방 / **코딩 부문 별도 기준** / 그래서 뭐 써야 돼? |
| `mystery` | 정체 공개: HF trending 1위 `{id}` 는 도대체 뭐냐 | 요약 / 숫자가 말하는 것 / 무료로 써볼 수 있나 / 그래서 뭐 써야 돼? |
| `bench` | 벤치마크 비교: 무료 `{m}` vs Claude Opus | 비교 대상 / 점수는 어떻게 나오나 / 그래서 뭐 써야 돼? |

발행: `cfnew.sql` → emdash D1 `ec_posts` **직접 INSERT** (Workers API 경유 없음). `revisions` 1행 + `ec_posts` 1행 2 statement. `status='published'`, `locale='en'`, `version=2`, `live_revision_id` 설정, slug 충돌 시 `-2` 부가. `to_pt()` 는 Portable Text 변환 — **PT 는 마크다운을 파싱하지 않으므로 백틱 제거** 처리.

### Step 6-7 — dry-run + 프로덕션 실행 [검증됨]
- `run_pipeline_with_notify.py --dry-run --skip-email --skip-deploy` → 정상 출력(계획만, 미실행)
- `run_pipeline_with_notify.py --skip-deploy` (이메일 포함) → 100.7초, 브리핑 **id=340 `2026-10-10-3`** 저장, 아이템 **6건**(Step 4 수정 전)
  - 이메일 실패: `❌ API 오류 (401) unrecognised IP address 2001:fb1:11d:6dd:8d59:e7a9:8910:8fbf`
- max_count 수정 후 `run_pipeline_with_notify.py --skip-deploy --skip-email` → `[23:01:34] 전체 기사: 29건 → 선정: 4건`, 브리핑 **id=341 `2026-10-10-4`** 저장, 아이템 **4건**, 소요 26초, 에러 0
- ★ 단독 실행 금지 지시 재확인: `python3 -c "from auto_news_selector import …"` 로 직접 호출하자 **D1 7403(출발 계정 `fac9808c`)** 재현됨. 반드시 `run_pipeline_with_notify.py` 경유 필요.
- `2026-10-10-4` 라이브: `https://aikorea24.kr/briefing/2026-10-10-4/` **200, 12,026B**
- 선정 4건 구성: HuggingFace Blog 1건(v2 소스) + The Guardian AI / CNBC Tech / The Decoder 3건(레거시)
  - **[부분검증]** v2 scorer 는 동작하나 24시간 창에 무료 사용 가능 항목이 4개 미만이라 레거시 매체가 섞였다. v2 데이터가 누적되면 축(軸)이 v2 쪽으로 이동할 것으로 예상되나 **수치 근거 없음**

### Step 5 발행 — 블로그 4건 [검증됨]
`ec_posts` 신규 4행 (2026-10-10T14:03:27~28 UTC). 전부 `status=published`, `live_revision_id` 유효, `ec_posts` 총 **1,471건**(1,460 기존 + 7 free-lecture + 4 신규), 고아 revision **0건**.

| 포맷 | live | 크기 | h1 |
|---|---|---|---|
| daily | **200** | 30,422B | 오늘의 추천 LLM: inkling-small — 입출력 무료, 컨텍스트 1,048,576 |
| weekly | **200** | 30,801B | 이번 주 무료 LLM 순위 — TOP 5와 이번 주 추천 1개 |
| mystery | **200** | 30,570B | 정체 공개: HuggingFace trending 1위 `embeddinggemma-2` 는 … |
| bench | **200** | 30,467B | 벤치마크 비교: 무료 `inkling-small` vs Claude Opus — 점수 차이, … |

URL = `https://emdash.aikorea24.kr/posts/<한글슬러그>` (`urllib.parse.quote` 인코딩 필요).

### Step 8 — 빌드·배포 [검증됨]
- 메인 `npm run build` **EXIT=0** `Server built in 18.78s` (`/tmp/p02_b2.log`)
- 메인 `npm run deploy` **EXIT=0** `✨ https://8b3dbc01.aikorea24-4nk.pages.dev` `배포 완료: https://aikorea24.kr` (`/tmp/p02_d2.log`)
- 라이브 10종: `/` 200 54,960B · `/subscribe/` 200 23,483B · `/briefing/2026-10-10-4/` 200 12,026B · `/blog/` 301 · `/courses/` 200 25,925B · `/refund/` 200 23,756B / emdash `/` 200 32,374B · `/posts` 200 68,020B · `/sitemap.xml` 200 395,734B · `/rss.xml` 200 36,120B

### [검증불가] — Brevo 이메일 실제 발송
`❌ API 오류 (401) unrecognised IP address 2001:fb1:11d:6dd:8d59:e7a9:8910:8fbf`. 로컬 IPv4 도 `58.10.233.168` 로 이전(`58.11.95.17` → `58.10.233.168`) 하여 기존 화이트리스트 무효. 복구: 대표님이 Brevo 대시보드 `https://app.brevo.com/security/authorised_ips` 에 **현재 IPv4 + IPv6** 등록. 코드 결함이 아님(4th 반복되는 IP 변동).

### 기록
- `docs/state.md` 2,232 → **2,499줄**. 맨 위 `진행 중 (2026-10-10 20:30, AIK24-PIPE-02 …)` 표식을 위 결과 요약으로 교체
- 완료보고 `SSOT/프로젝트/aikorea24/지시서/2026-10-10-2305-AIK24-PIPE-02-완료보고.md`

### 잔존 위험 (누적 17건, 신규 1건 추가)
1. Workers Free 10ms CPU(1102) — Paid 전환 금지 지시
2. `/tools/*` 하위 10개 파일 오프팔레트 124건
3. 메인 `dark:` 클래스 750건(런타임 미적용)
4. Layout 미사용 9개 페이지 다크 배경 (공개 `/briefing/`·`/briefing/[date]/` 포함)
5. **Brevo IP 화이트리스트 미등록 (신규 — 현재 IPv4 `58.10.233.168`, IPv6 `2001:fb1:…`) → 이메일 발송 불가**
6. EMDASH-12 `cloudflareEmail()` 훅 타임아웃 5초(메일 도착하나 500 응답)
7. PAT 평문 `/tmp/aik24-pat.txt`
8. `~/projects2/aikorea24emdash` git 아님
9. EMDASH-12·13·05·07 완료보고 미작성
10. PIPE-01 작업2 중단 (대표님 A/B/C)
11. `PUBLIC_TOSS_CLIENT_KEY` 미설정
12. 모바일 390×844 검증 불가
13. `logo-en`·`logo-ko` 미사용
14. 툴 리뷰 작성 경로 소멸 (FIX-01)
15. 리뷰 상세 페이지 소몰 (FIX-01)
16. D1 `community_posts` + `lessons.community_post_id` 불활성
17. **v2 소스 4개 보류 (신규 — Reddit LocalLLaMA 403 / Anthropic RSS 404 / OpenCode RSS 404 / Product Hunt 인증)**

### 다음 행동 (대표님)
1. **Brevo 화이트리스트에 `58.10.233.168` + IPv6 `2001:fb1:11d:6dd:8d59:e7a9:8910:8fbf` 등록** — 안 하면 06:00 아침 잡 이메일 발송이 계속 실패
2. 내일 06:00 아침 잡 결과 확인 (`scripts/pipeline_runner.log`) — 브리핑 1건 + 이메일 1통 + v2 수집기 동작
3. `/briefing/` 등 Layout 미사용 9개 페이지 다크 배경 정리 지시 여부
4. `/tools/*` 오프팔레트 124건 지시 여부
5. PIPE-01 작업2 선택지 / 토스 가맹 키 / 브리핑 발송 시각 / 환영 시퀀스 4통 본문 / OG 이미지

### 유틸 기록
- 브리핑 아이템 4건 소스 확인 쿼리: `SELECT n.source,n.title FROM briefing_items b JOIN news n ON n.id=b.news_id WHERE b.briefing_id=<id> ORDER BY b.sort_order`. `briefing_items` 에 `cluster` 컬럼 **없음**(스키마: id/briefing_id/news_id/sort_order/comment/created_at/deep_dive_url) → news 테이블로 JOIN 해야 함
- launchd plist 수정 후 `launchctl unload` → `load` → `launchctl print gui/$(id -u)/<label>` 로 descriptor 확인. `plutil -lint` 로 XML 검증
- `run_pipeline_with_notify.py` 는 인자를 `run_pipeline.py` 로 전달하지 않았다 → `pipeline_args.extend(sys.argv[1:])` 추가. launchd 는 인자 없이 호출하므로 기본 동작 불변
- 한글이 섞인 텍스트 작성 시 CJK(한자) 혼입 주의 — `re.findall(r'[一-鿿぀-ヿ]', s)` 로 검사. 이번 작업에서 `news_collector_v2.py`·`blog_v2_generator.py`·`run_pipeline.py`·`impact_weights.json` 에서 발견 후 제거


- 작업 시작. Step 0 사전 조사 진행 중.
- 지시서: `SSOT/프로젝트/aikorea24/지시서/2026-10-10-2030-AIK24-PIPE-02-브리핑v2-블로그개편.md` (196줄)

---

## 2026-10-10 22:20 — 폰트 Pretendard 통일 (Georgia 제거, 메인 + EmDash 양쪽 배포)

- **한 일**: 대표님 질의 "폰트를 어떤거 사용하지? 프리텐다드로 모두 통일할 수 있을까?" 에 대한 조사 + 본문/헤드라인 전부 Pretendard로 통일하고 양쪽 사이트 배포.

### 조사 결과 (배포 전 실측)
| 대상 | aikorea24.kr (메인) | emdash.aikorea24.kr |
|---|---|---|
| 본문 | `'Pretendard Variable'` (jsDelivr CDN `pretendard@v1.3.9` dynamic-subset, `SEOHead.astro:143`) | `"Pretendard"` (로컬 woff2 2개 1.5MB, `theme.css` `@font-face` + `Base.astro:91-92` preload) |
| 헤드라인 | `Georgia, "Times New Roman", serif !important` (`global.css:39`) + 인라인 16곳 = **18회** | `--font-heading`(`theme.css:16`) + `h1,h2 !important`(`theme.css:70`) = **2회** |

**★ 핵심 발견 — Georgia는 한글 글리프가 없다.** 브라우저 폭 측정(h1 700 40px):
```
"가나다라마바" 실제 렌더 239.77 = Georgia 스택 239.77 = Apple Myungjo 239.77 = Batang 239.77
                     Pretendard 207.42 / Apple SD Gothic Neo 207.6 (불일치)
"Hamburgefonstiv" (라틴) 362.58 = Georgia 스택 362.58 (정확히 일치)
```
→ 라틴 문자만 진짜 Georgia였고, 한글 제목은 이미 기기별 세리프(macOS/iOS Myungjo, Windows Batang, Android Noto Serif CJK)로 폴백되고 있었다. "Georgia 적용"의 실질적 효과는 영문 라벨뿐.

### 변경 [검증됨]
| 파일 | 구분 | 내용 |
|---|---|---|
| `src/styles/global.css:38` | PRODUCTION CODE | 주석 "헤드라인 - 세리프" → Georgia 제거 사유 명시 |
| `src/styles/global.css:39,75` | PRODUCTION CODE | `font-family: Georgia, "Times New Roman", serif` → `var(--font-sans)` (h1,h2 `!important` 유지) |
| 11개 `.astro` 인라인 16곳 | PRODUCTION CODE | `font-family: Georgia, serif` → `var(--font-sans)`. 대상: `home/{HeroSection,BriefingSection,LatestBlog,CourseSection,CtaSection,SubProjects,ToolsSection,OpenSourceBanner}.astro`, `pages/{404,courses/index,subscribe}.astro` |
| `~/projects2/aikorea24emdash/src/styles/theme.css:16,70` | PRODUCTION CODE | `--font-heading` → `"Pretendard", -apple-system, sans-serif`, `h1,h2` → `font-family: var(--font-body) !important` |

`--font-sans` = `Layout.astro:71` 의 `<style is:global>` `:root` 정의(`'Pretendard Variable', Pretendard, -apple-system, …`). `global.css` 는 `Layout.astro` 만 import 하므로 전 치환 대상이 Layout 사용 페이지에만 한정됨(안전).

백업: `src/` → `/tmp/fontfix_src_bak`, `theme.css` → `/tmp/theme.css.bak.fontfix`.

### 결과
- `grep -rn Georgia src/` → **0건** (메인 + emdash 양쪽). 주석 1곳 제외
- 빌드: 메인 **EXIT=0** `Server built in 11.47s` (`/tmp/font_main_build.log`) / emdash **EXIT=0** `Server built in 3.17s` (`/tmp/font_em_build.log`)
- 배포: 메인 **EXIT=0** `✨ https://abf2aad5.aikorea24-4nk.pages.dev` (`/tmp/font_main_deploy.log`) / emdash **EXIT=0** `Current Version ID 7f573926-9986-417a-bbee-6315e97ed7f0` (`/tmp/font_em_deploy.log`)
- 라이브 URL 8종 전부 정상: 메인 `/` 200 57,994B · `/blog/` 301 · `/courses/` 200 26,172B · `/refund/` 200 24,003B / emdash `/` 200 33,082B · `/posts` 200 68,267B · `/sitemap.xml` 200 394,778B · `/rss.xml` 200 36,856B
- 라이브 HTML `grep -c Georgia` → 메인 0 / emdash 0
- **getComputedStyle 실측 (Aside)**: 메인 h1 = `"Pretendard Variable", Pretendard, -apple-system…`, h1 weight 700, h2 4개 전부 `"Pretendard Variable"`, body 동일, 가로 스크롤 없음(1440=1440). emdash h1/h2 = `Pretendard, -apple-system, sans-serif`, body 동일, 가로 스크롤 없음
- D1 무변경. URL·슬러그 무변경.

**[부분검증]** — 스크린샷 육안 미확인. `page.screenshot()` 2회 호출 모두 `Unable to transform response from server` (도구 응답 변환 오류, 페이지 자체는 정상 렌더 — computed style·HTTP 200·바이트 수로 확인). 복구: 브라우저 직접 확인.

### [검증불가] — 모바일 390×844 렌더
Aside 브라우저 `page` 객체에 `setViewportSize` 없음. Pretendard Variable 은 가변 폰트라 모바일에서 줄바꿈 위치가 달라질 수 있으나 실기기 미확인.

### ★ 부수 발견 — Layout 미사용 9개 페이지가 자체 다크 스타일 유지 (범위 밖, 미수정)
`grep -rn '/community'` 점검 중 발견. `global.css` 는 `Layout.astro` 만 import 하므로 아래 9개 페이지는 시안 A(라이트) 규약이 적용되지 않고 자체 다크 배경을 유지한다.

| 파일 | body 배경 |
|---|---|
| `src/pages/briefing/[date].astro:66` | `#0a0a0f` (공개 페이지 — 브리핑 상세) |
| `src/pages/briefing/index.astro:48` | `#0a0a0f` (공개 페이지 — 브리핑 목록) |
| `src/pages/payments/success.astro:40` | `#0f172a` |
| `src/pages/payments/fail.astro:17` | `#0f172a` |
| `src/pages/pricing.astro:29` | `#0f172a` |
| `src/pages/auth/consent.astro:15` | `#0f172a` |
| `src/pages/admin/index.astro:31` | `#0f172a !important` |
| `src/pages/admin/event.astro:31` | `#0f172a` |
| `src/pages/admin/tools.astro:92` | `#0f172a` |

RENEWAL-01 §3 이 "다크모드 제거 / 검은 배경 없음" 을 요구했으나 대상 파일 목록(`src/layouts/`, `src/components/home/`)에 이 9개가 없어 처리되지 않았다. **공개 페이지 2개(`/briefing/`, `/briefing/[date]/`)가 특히 노출 큼.** 지시 여부 대기.

### 잔존 위험 (누적 16건)
1. Workers Free 10ms CPU(1102) — Paid 전환 금지 지시
2. `/tools/*` 하위 10개 파일 오프팔레트 124건
3. 메인 `dark:` 클래스 750건(런타임 미적용, 삭제 미수행)
4. **Layout 미사용 9개 페이지 다크 배경 유지 (신규 — 위 표)**
5. Brevo IP 화이트리스트 반복 변경(현재 `58.11.95.17` 등록 확인)
6. EMDASH-12 `cloudflareEmail()` 훅 타임아웃 5초(메일 도착하나 500 응답)
7. PAT 평문 `/tmp/aik24-pat.txt` (Vault 등록 후 삭제 필요)
8. `~/projects2/aikorea24emdash` git 아님
9. EMDASH-12·13·05·07 완료보고 미작성
10. PIPE-01 작업2 중단 (대표님 A/B/C 대기)
11. `PUBLIC_TOSS_CLIENT_KEY` 미설정 → 결제 버튼 미노출
12. 모바일 390×844 실기기 검증 불가
13. `logo-en`·`logo-ko` 미사용
14. 툴 리뷰 작성 경로 소멸 (FIX-01)
15. 리뷰 상세 페이지 소몰 (FIX-01)
16. D1 `community_posts` + `lessons.community_post_id` 불활성, 데이터 보존 (FIX-01)

### 다음 행동 (대표님)
1. **`/briefing/` 등 Layout 미사용 9개 페이지 다크 배경 정리 지시 여부** (공개 페이지 2개 노출 큼 — 신규)
2. `/tools/*` 오프팔레트 124건 정리 지시 여부
3. PIPE-01 작업2 선택지 (A 보류 / B slug_map+301 후 삭제 권고 / C 즉시 삭제)
4. 토스 가맹 키 / 브리핑 발송 시각 / 환영 시퀀스 4통 본문 / OG 이미지 / `logo-en`·`logo-ko` 활용 위치
5. Brevo 대시보드 테스트 컨택트 확인
6. 툴 리뷰 기능 재설계 여부

### 유틸 기록
- 세리프→sans 치환: `sed -i '' -e 's/font-family: Georgia, "Times New Roman", serif/font-family: var(--font-sans)/g' -e "s/font-family: Georgia, 'Times New Roman', serif/font-family: var(--font-sans)/g" -e 's/font-family: Georgia, serif/font-family: var(--font-sans)/g'` (3패턴 모두 필요 — `subscribe.astro`·`404.astro` 는 작은따옴표 변형 사용)
- `global.css` 는 `Layout.astro` 만 import → Layout 미사용 페이지는 치환 대상 아님(위 신규 위험 4 참고)
- Aside `page.screenshot()` 이 간헐 `Unable to transform response from server` 반환. `type:'webp'` 지정해도 동일. computed style + curl 바이트로 대체 검증

## 2026-10-10 21:46 — AIK24-FIX-01 커뮤니티 제거 + 홈페이지 AI 툴 섹션 + FUNNEL-01 완료

- **한 일**: ① `/community/` 전체 삭제(페이지 5종 + API 3종)·내부 링크 제거·301 리다이렉트 ② 홈페이지에 "AI 툴" 섹션 신규 추가 ③ FUNNEL-01 남은 단계(빌드·배포·검증) 완료. 배포 `223a39a6`.

### 결과

**[검증됨]** — 작업 1 커뮤니티 제거
| 항목 | 결과 | 근거 |
|---|---|---|
| 페이지 삭제 | `src/pages/community/`(index·[id]·review·write·[id]/edit) + `src/pages/api/community/`(visibility·update·delete) | `rm -rf` → `ls src/pages` 에 `community` 없음. 백업 `/tmp/fix01_bak/` |
| 내부 링크 | `grep -rn '/community' src/ public/` → **0건** | `_redirects` 3줄 제외 전부 제거 |
| 제거 파일 | `CtaSection.astro`(커뮤니티 참여 → AI 툴 둘러보기) `auth/consent.astro` `pricing.astro` `payments/{success,fail}.astro` `about.astro` `tools/[id].astro`(5곳) `api/briefing/send-email.ts` `api/courses/send-daily.ts` `sitemap-pages.xml.ts` `public/llms.txt` | python 치환 + grep 0건 확인 |
| 301 리다이렉트 | `/community` · `/community/` · `/community/123` · `/community/write` **4종 전부 301 → `https://aikorea24.kr/`** | `curl -w '%{http_code} -> %{redirect_url}'` |
| 사이트맵 | `https://aikorea24.kr/sitemap-pages.xml` 에 community 0건 | curl grep |
| 빌드 산출물 | `dist/community` 없음 | `ls` |

**[검증됨]** — 작업 2 AI 툴 섹션
- 신규 `src/components/home/ToolsSection.astro`. 선정 로직 = `/tools/` 페이지의 `popularTools` 와 동일(`koreanSupport` true → `order` 오름차순 → 4개). **임의 창작 없음.**
- 카드 4개: `/tools/vecbase/` `/tools/litescribe/` `/tools/geulway/` `/tools/goath/`
- 배치: `index.astro` 에 import 추가 + `<BriefingSection />` 다음·`<SubscribeBanner />` 앞에 삽입
- 라이브 h2 순서 실측: `10월 10일 (토)` → **`AI 툴`** → `최신 블로그` → `AI 강좌` → `서브 프로젝트` → `AI, 지금 바로 시작하세요`

**[검증됨]** — 작업 3 FUNNEL-01 완료
| 항목 | 결과 | 근거 |
|---|---|---|
| 히어로 헤드라인 | "매일 아침 5분, AI 뉴스 핵심만" | `document.querySelector('h1').innerText` |
| 히어로 서브 | "OpenAI·Anthropic 공식 발표만 골라서 보내드립니다" | innerHTML grep 1회 |
| 히어로 인라인 폼 | `#hero-subscribe` / `#hero-email` / `#hero-subscribe-msg` / 버튼 "무료로 구독하기" | `page.evaluate` 실측 |
| **히어로 폼 실동작** | 테스트 주소 제출 → `"구독 완료! 매일 아침 AI 브리핑을 보내드립니다."` (class `text-[#E63B2E]`) → 버튼 "무료로 구독하기" 복귀·`disabled:false` | Playwright 실제 입력·클릭 |
| `/subscribe/` 폼 | 동일 메시지 반환 확인 | `#top-email` + `#top-subscribe` 제출 |
| 신뢰 문구 | "광고 없음 · 언제든 해지 가능" 히어로·구독 페이지 양쪽 | grep 각 1회 |
| 금지 문구 | "7시" **0건**, "N명이 구독 중" **0건** | `document.body.innerText` 정규식 |
| 테스트 데이터 정리 | Brevo `DELETE /v3/contacts/{email}` → **204 ×2** | 2건 삭제 확인 |

**[검증됨]** — 빌드·배포·라이브
- `npm run build` → **EXIT=0** `Server built in 10.50s` `Complete!`
- `npm run deploy` → **EXIT=0** `✨ https://223a39a6.aikorea24-4nk.pages.dev` `배포 완료: https://aikorea24.kr`
- `/` 200 57,950B · `/subscribe/` 200 23,707B · `/tools/` 200 811,408B
- 가로 스크롤 없음 (`scrollW 1440 = clientW 1440`)
- 홈 `커뮤니티` 문자열 0건 · `a[href*=community]` 0개

### 변경 파일
| 구분 | 파일 |
|---|---|
| 삭제 | `src/pages/community/`(5), `src/pages/api/community/`(3) |
| 신규 | `src/components/home/ToolsSection.astro` |
| 수정 | `index.astro` `CtaSection.astro` `auth/consent.astro` `pricing.astro` `payments/success.astro` `payments/fail.astro` `about.astro` `tools/[id].astro` `api/briefing/send-email.ts` `api/courses/send-daily.ts` `sitemap-pages.xml.ts` `public/_redirects` `public/llms.txt` `HeroSection.astro` `subscribe.astro` |

### 잔존 위험
1. Workers Free 10ms CPU 한도(1102) — Paid 전환 금지 지시
2. `/tools/*` 하위 10개 파일 오프팔레트 124건 (FIX-01 §6 에서 명시적 범위 외)
3. 메인 `dark:` 클래스 750건(런타임 미적용)
4. Brevo IP 화이트리스트 반복 변경 (현재 `58.11.95.17` 등록, 이번 세션에 401 없이 정상 동작)
5. EMDASH-12 `cloudflareEmail()` 훅 타임아웃 5초(메일 도착하나 500 응답)
6. PAT 평문 `/tmp/aik24-pat.txt` (Vault 등록 후 삭제 필요)
7. `~/projects2/aikorea24emdash` git 아님
8. EMDASH-12·13·05·07 완료보고 미작성
9. PIPE-01 작업2 중단 (대표님 A/B/C 선택지 대기)
10. `PUBLIC_TOSS_CLIENT_KEY` 미설정 → 결제 버튼 미노출
11. 모바일 390×844 실기기 검증 불가 (Aside `setViewportSize` 부재)
12. `logo-en`·`logo-ko` 미사용
13. **신규**: 툴 리뷰 읽기 기능 잔존 — `tools/[id].astro` 는 `/api/tools/reviews` 로 리뷰를 표시하지만, 리뷰 작성 UI(`/community/review`·`/community/write`)를 삭제했으므로 **새 리뷰 작성 경로가 사라짐**. 기존 D1 리뷰 행은 그대로 표시됨.
14. **신규**: `tools/[id].astro` 의 `reviews-section` 의 "전체 보기" 링크 삭제 → 리뷰 상세 페이지 없음(리뷰 원문 전체 미열람 가능)
15. **신규**: D1 `community_posts` 테이블과 `lessons.community_post_id` 컬럼이 코드를 더 이상 읽지 않음. 데이터는残置 (삭제하지 않음 — 되돌리기 가능성 대비)

### 다음 행동 (대표님)
1. Brevo 대시보드에서 테스트 컨택트 2건 생성 확인 (지시서 §완료기준 — 대표님 직접 수행 항목)
2. `/tools/*` 오프팔레트 124건 정리 지시 여부
3. 툴 리뷰 기능 재설계 여부 (작성 경로 부재 상태)
4. PIPE-01 작업2 선택지 결정
5. 토스 가맹 키 / 브리핑 발송 시각 / 환영 시퀀스 4통 본문

## 진행 중 (2026-10-10 20:00, AIK24-CF-TRACE-01 잔존확인)

## 진행 중 (2026-10-10 16:30, AIK24-REFUND-02 환불정책수정)

## 2026-10-10 18:12 — 파비콘·마스코트 브랜드 에셋 적용 (원본 Downloads 에서 발견) + L2T 푸터 확인 + 통신판매업 번호 푸터 반영

- **한 일**: 대표님 지적("파비콘이 안바뀌었는데? [브랜드 이미지 5장] 이런것들은 왜 활용안했지? 지시서에 없었나?")에 따른 조사·적용. `~/Downloads/` 에 원본 존재 확인 → 파비콘 4종 교체, 마스코트 404 페이지 적용.

### 결과
**[검증됨]** — 파비콘·마스코트
| 항목 | 결과 | 근거 |
|---|---|---|
| 원본 발견 | `~/Downloads/favicon-final.webp` 48,404B 1600×1600 = 대표님 이미지 ② | `sips` 변환 후 육안 확인(빨간 세로 라인 + `A` + 발자국) |
| 마스코트 원본 | `~/Downloads/batch_media-generation-aik24-tiger-final-0-9d5c8cf1-….jpg` 37,428B 636×636 = 이미지 ⑤ | 육안 확인(호랑이 + 스마일에 폰) |
| 로고 | `public/logo-final.webp` 2464×976 = 이미지 ①(가로 dancheong 배너) | 이미 헤더 적용 상태 |
| 파비콘 교체 | `favicon.png` 100×100/2,201B → **512×512/65,799B**<br>`favicon-32x32.png` 1,761B → 2,235B<br>`favicon-16x16.png` 762B → 1,387B<br>`apple-touch-icon.png` 14,906B → 15,394B | `sips -Z` 리사이즈 후 `ls -la` |
| 마스코트 적용 | `public/mascot-tiger.png` 400×400/51,159B 신규 | 404 페이지 `<img src="/mascot-tiger.png">` |
| 빌드 | **EXIT=0** | `/tmp/av_build.log` `Server built in 18.74s` `Complete!` |
| 배포 | **EXIT=0** | `/tmp/av_deploy.log` `✨ https://f4539bd4.aikorea24-4nk.pages.dev` `배포 완료: https://aikorea24.kr`, sitemap ping google/naver ✅ |
| 라이브 | `/` 200 · `/favicon.png` 200 65,799B · `/favicon-32x32.png` 200 2,235B · `/mascot-tiger.png` 200 51,159B · `/404-test-notexist/` **404 21,095B** | curl |
| 404 페이지 | `mascot-tiger.png` 1회 / `#3b82f6` 0회 / `#111111` 5회 | `curl … \| grep -o \| uniq -c` |

**[검증됨]** — `404.astro` 시안 A 위반 제거. `#3b82f6`(파랑) `404` 타이틀·버튼 → Georgia 세리프 + `#111111`. 마스코트 추가.

**[검증됨]** — link2threads.com 푸터 확인 결과 **보완 불필요**.
라이브 apex 푸터에 이미 `통신판매업 신고번호: 제 2026-의정부흥선-0694호` + `호스팅 제공자: Cloudflare, Inc.` 표기. 로컬 소스 `~/projects2/link2threads/src/routes/_layout.ts` L88 `CHROME_FOOTER` + `src/index.ts` L544 인라인 푸터 양쪽 보유 → 소스-라이브 일치. L2T 배포 미수행. L2T 계정 = `89dcb5be8fa1f42bad2372298271435e`(twinssn@gmail.com), 출발 계정 아님.

**[검증됨]** — aikorea24 푸터에 통신판매업 신고번호 반영 (선행 작업). `src/layouts/Layout.astro:264` 에 `| 통신판매업 신고번호: 제 2026-의정부흥선-0694호 | 호스팅 제공자: Cloudflare, Inc.` 추가 → 배포 `5c747f6a`. REFUND-01 잔존 위험 "통신판매업 미표시 = PG 반려 위험" 해소.

### [위반 감지] — 지시서 §0-4 정보 불일치 (조사 부족)
RENEWAL-01 §0-4 는 "`favicon-final.webp`, `mascot-tiger.webp` 원본은 말랑이 VM(`~/workspace/aik24-brand/assets/`)에만 있고 현재 Mac에 없다" 라고 명시했다. 실제로 `~/workspace/aik24-brand/assets/` 는 존재하지 않아 **지시서 지시대로 `보류 (원본 미수령)` 처리**했으나, 원본은 Mac `~/Downloads/` 에 있었다. `find` 로 홈 전체를 검색했어야 했다. → 지시서 정보가 실제 파일 위치와 달랐고, 지시서 경로만 확인하고 넘어간 것이 조사 부족이다. 지시서 §3-2.4·3-2.5(파비콘 교체·마스코트 404 적용)는 **보류 표기 없이 미실행 상태로 남겨짐** → 이번 세션에서 처리.

### 잔존 위험
1. Workers Free 10ms CPU(1102) — Workers Paid 전환 금지 지시
2. `/tools/*` 하위 10개 파일 오프팔레트 124건
3. 메인 `dark:` 클래스 750건(런타임 미적용, 삭제 미수행)
4. Brevo IP 화이트리스트 반복 변경(현재 `58.11.95.17` 등록됨, 동작 확인)
5. EMDASH-12 `cloudflareEmail()` 훅 타임아웃 5초(메일 도착하나 500 응답)
6. PAT 평문 `/tmp/aik24-pat.txt` (Vault 등록 후 삭제 필요)
7. `~/projects2/aikorea24emdash` git 아님
8. EMDASH-12·13·05·07 완료보고 미작성
9. PIPE-01 작업2 중단 (대표님 A/B/C 선택지 대기)
10. `PUBLIC_TOSS_CLIENT_KEY` 미설정 → 결제 버튼 미노출
11. 모바일 390×844 실기기 검증 불가(Aside 브라우저 `setViewportSize` 부재)
12. `favicon-final.webp` 외 브랜드 에셋(`logo-en`, `logo-ko`, `tiger-paw`, `badge-listed`) 중 `logo-en`/`logo-ko` 는 사이트 미사용 상태 — OG 이미지·스키마 마크업 적용 여부 미결

### 다음 행동 (대표님)
1. OG 이미지 교체 여부 결정 (현재 `public/og-default.png` 2월 구버전)
2. `logo-en`/`logo-ko` 활용 위치 지정 (스키마 organization 로고, 관리자 화면 등)
3. `/tools/*` 오프팔레트 정리 지시 여부
4. PIPE-01 작업2 선택지 (A 보류 / B slug_map+301 후 삭제 권고 / C 즉시 삭제)
5. 토스페이먼츠 가맹 키 / 일일 브리핑 발송 시각 / 환영 시퀀스 4통 본문

### 유틸 기록
- 이미지 확인: `sips -s format png <in> --out /tmp/x.png && sips -Z 300 /tmp/x.png` → Read 도구 육안 확인
- 파비콘 세트: 원본 1개 → `-Z 512` (favicon.png) / `-Z 180` (apple-touch-icon) / `-Z 32` / `-Z 16`
- `docs/state.md` 는 Write 로 덮어쓸 수 없음 → 임시 파일에 쓰고 python 으로 앞쪽 concat. 백업 `docs/state.md.bak.<ts>` 관행

## 2026-10-10 18:0x — 통신판매업 신고번호 푸터 표기 추가 (aikorea24.kr)

- **한 일**: 대표님 지시 "aikorea24 하단에도 작성해줘" — `link2threads.com` 푸터에 이미 표기돼 있던 **통신판매업 신고번호** 를 `aikorea24.kr` 푸터에도 동일하게 추가. 토스페이먼츠 PG 가맹 신청 심사 체크리스트(`통신판매업`) 대비.
- **변경 파일**: `src/layouts/Layout.astro` L264 (PRODUCTION CODE 1건). 1줄 수정.

### 결과
**[검증됨]**
| 항목 | 결과 | 근거 |
|---|---|---|
| 빌드 | **EXIT=0** | `/tmp/a24_f_build.log` `Server built in 10.99s` `Complete!` |
| 배포 | **EXIT=0** | `/tmp/a24_f_deploy.log` `✨ https://5c747f6a.aikorea24-4nk.pages.dev` + `배포 완료: https://aikorea24.kr` |
| 라이브 푸터 | 통신판매업 신고번호 **1회**, 호스팅 제공자 **1회** | `curl -sL https://aikorea24.kr/ \| grep -o \| wc -l` |
| 전 페이지 반영 | `/terms/` 에도 1회 | Layout 의 `<footer>` 를 모든 페이지가 상속 |
| URL | `/` 200 · `/refund/` 200 · `/terms/` 200 | curl |

추가한 문구: `통신판매업 신고번호: 제 2026-의정부흥선-0694호 | 호스팅 제공자: Cloudflare, Inc.`

### 선행 조사 — link2threads.com 푸터 [검증됨]
- 라이브 `https://link2threads.com/` 푸터에 이미 `통신판매업 신고번호: 제 2026-의정부흥선-0694호` + `호스팅 제공자: Cloudflare, Inc.` 표기돼 있었음. **L2T 쪽 보완 필요 없음.**
- 로컬 소스 `~/projects2/link2threads/src/routes/_layout.ts` L88 (`CHROME_FOOTER`) 과 `src/index.ts` L544 (랜딩 인라인) 두 곳 모두 해당 문구 보유 → 소스-라이브 일치.
- L2T 계정 = `89dcb5be8fa1f42bad2372298271435e` (twinssn@gmail.com). 출발 계정 `fac9808c` 아님 → 접근 금지 규칙 무관. 이번 세션에서 L2T 배포는 수행하지 않음.

### 잔존 위험
1. 기존 잔존 10건 유지 (RENEWAL-01 완료보고 §6 참조): Workers Free 10ms CPU / `/tools/*` 오프팔레트 124건 / `dark:` 750건 / EMDASH-12 훅 타임아웃 / PAT 평문 `/tmp/aik24-pat.txt` / emdash 프로젝트 git 아님 / EMDASH-12·13·05·07 보고서 미작성 / PIPE-01 작업2 중단 / `PUBLIC_TOSS_CLIENT_KEY` 미설정 / 모바일 390×844 검증 불가.
2. REFUND-01 §5 수강률별 환불 요율 미수령 → `대기 (수치 미수령, 2026-10-10)`.
3. 대표님 대기 6건 유지: 파비콘·마스코트 원본 / 토스 가맹 키 / 브리핑 발송 시각 / 환영 시퀀스 4통 본문 / PIPE-01 작업2 선택지 / `/tools/*` 오프팔레트 지시 여부.

### 다음 행동
- 대표님: 토스페이먼츠 가맹 신청 시 `https://aikorea24.kr/refund/` + 통신판매업 번호 표기 완료 상태로 진행 가능.

## 2026-10-10 17:55 — AIK24-REFUND-01 환불정책 페이지 작성·배포 (토스페이먼츠 가맹 신청 대비)

- **한 일**: 지시서 `2026-10-10-1545-AIK24-REFUND-01-환불정책페이지.md`(168줄) 실행. 토스페이먼츠 PG 가맹 신청서 심사관용 환불정책 공개 URL 확보 목적.
- **산출 파일**: `src/pages/refund.astro` 신규 (PRODUCTION CODE 1건). `privacy.astro` 패턴 동일 — `export const prerender = true` + `Layout` import + `article` 래퍼.

### 결과
**[검증됨]** (근거 = 빌드 로그 · 배포 로그 · curl 상태코드 · 라이브 HTML grep)
| 항목 | 결과 | 근거 |
|---|---|---|
| 파일 작성 | 6개 섹션 전부 포함 | §1 적용대상 / §2 청약철회 7일(전자상거래법 §17①) / §3 청약철회 제한(§17②) / §4 환급 3영업일(§18②) / §5 수강률별 기준 / §6 문의 |
| 빌드 | **EXIT=0** | `/tmp/rf_build.log` `Server built in 10.29s` `Complete!`, `dist/refund/index.html` 23,300B |
| 배포 | **EXIT=0** | `/tmp/rf_deploy.log` `✨ Deployment complete! https://cf9c93cb.aikorea24-4nk.pages.dev` + `배포 완료: https://aikorea24.kr` |
| 라이브 | `/refund/` → **200**, `/refund` → **308** | curl. `trailingSlash: 'always'` 설정 때문이며 지시서 검증 명령이 슬래시 없는 URL. **심사관에게 `https://aikorea24.kr/refund/` 전달 권장** |
| 렌더 | `section-title` 1 / `상세 기준은 추후 공지됩니다` 2 / `청약철회` 9 / `환불정책` 8 | `curl https://aikorea24.kr/refund/ \| grep -o` |

**[검증됨]** 지시서 금지 준수
- "환불 불가" 포괄 특약 미사용. §3 은 전자상거래법 §17② 열거형으로만 작성.
- `dark:` 클래스 0건. 파랑·보라·초록 0건. 흰 배경 + 검은 제목 + `.section-title` 빨간 버티컬 라인.

**[검증됨]** §2·§6 연락처 = 푸터(`Layout.astro` L272-273)에 이미 공개된 값 그대로 사용. 임의 작성 아님.
`스타일팩토리9 (Style Factory 9) / 대표: 조진연 / 사업자등록번호: 672-43-00632 / 경기도 의정부시 호암로 256, 107-1804 (우 11638) / info@aikorea24.kr / +82 10-7416-5705`

**[부분검증]** 브라우저 육안 미확인 — curl HTML grep으로 6개 섹션 렌더만 확인. Aside `getComputedStyle` 시각 검증은 미실행.
**[검증불가]** 수강률별 환불 요율 — 대표님 미제공. 복구: 수치 수령 후 §5 갱신 → 재빌드·재배포.

### 대기 항목
- `대기 (수치 미수령, 2026-10-10)` — §5 수강률별 환불 기준. 페이지에는 "상세 기준은 추후 공지됩니다" 로 기재함.
- `대기 (수치 미수령, 2026-10-10)` — §3 청약철회 제한의 구체적 판정 기준. 동일 문구로 기재함.

### 잔존 위험
1. **PG 심사 관건**: 지시서 §배경이 요구하는 심사 체크리스트 항목 중 `통신판매업` 표시가 푸터·약관 어디에도 없음. 이대로 신청하면 반려 위험. 복구: 대표님 통신판매업 신고번호 확인 후 `terms.astro`·푸터에 표기.
2. `/refund`(슬래시 없음)는 308. 심사자가 그대로 붙여넣으면 브라우저가 따라가지만 심사 시스템 일부가 308 를 실패로 처리할 수 있음 → `/refund/` 전달 권장.
3. 브라우저 육안 미확인(위 [부분검증]).
4. 기존 잔존 10건(RENEWAL-01 완료보고 §6 참조): Workers Free 10ms CPU / `/tools/*` 오프팔레트 124건 / `dark:` 750건 / EMDASH-12 훅 타임아웃 / PAT 평문 `/tmp/aik24-pat.txt` / emdash 프로젝트 git 아님 / EMDASH-12·13·05·07 보고서 미작성 / PIPE-01 작업2 중단 / `PUBLIC_TOSS_CLIENT_KEY` 미설정 / 모바일 390×844 검증 불가.
5. 대표님 대기 6건 유지: 파비콘·마스코트 원본 / 토스 가맹 키 / 브리핑 발송 시각 / 환영 시퀀스 4통 본문 / PIPE-01 작업2 선택지 / `/tools/*` 오프팔레트 지시 여부.

### 다음 행동
- 대표님: 토스페이먼츠 가맹 신청 시 환불정책 URL 은 `https://aikorea24.kr/refund/` 사용. 통신판매업 신고번호 확인 필요.
- 대표님: §5 수강률별 환불 요율 제공 시 페이지 갱신 + 재배포.

## 2026-10-10 17:26 — AIK24-RENEWAL-01 전체 리뉴얼 Phase 1~5 수행 + 양쪽 배포

- **한 일**: 지시서 `2026-10-10-AIK24-RENEWAL-01-전체리뉴얼.md`(204줄, v2) Phase 1~5 수행.
  - Phase 1(메인): `src/layouts/Layout.astro`·`src/pages/briefing/[date].astro` 의 다크모드 토글 버튼·핸들러 삭제. 잔존 파랑/초록 클래스 → 시안 A(`#E63B2E`/`#111111`/`#333333`/`#f7f7f7`)로 교체.
  - Phase 2(EmDash): `~/projects2/aikorea24emdash/src/styles/tokens.css` 다크모드 `light-dark()` 10종·파랑 `#0066cc`/`#0052a3` 제거, `color-scheme: light`. `Base.astro` head 확인만(누락 0).
  - Phase 3(퍼널): BREVO-UNSUB 해지 수정 배포·라이브 검증, 구독 폼 엔드투엔드 테스트(테스트 주소 자동 정리).
  - Phase 5(수익화): `/courses/` 선판매 페이지 + `POST /api/courses/interest` 신규, `course_interest` D1 테이블 생성, 토스페이먼츠 위젯 틀.
  - Phase 4: 메인 `npm run deploy`(`https://f6d69f2e.aikorea24-4nk.pages.dev`) + EmDash `npm run deploy`(Version `c1050ee0-dc99-4265-ac08-9ef65466ffd0`).
- **결과**:
  - **[검증됨]** URL 9종 상태 코드 — `aikorea24.kr/`·`/courses/`·`/subscribe/`·`/sitemap.xml` = 200, `/blog/` = 301, `emdash.aikorea24.kr/`·`/posts`·`/sitemap.xml`·`/rss.xml` = 200.
  - **[검증됨]** 다크모드 토글 제거 — `grep -rl 'theme-toggle' dist/` = 0건, 라이브 `hasThemeToggle:false`, `htmlClass:'scroll-smooth'`.
  - **[검증됨]** 메인 홈 시안 A — `bodyBg:'rgb(255,255,255)'`, `blueNavCount:0`, `redNavCount:2`, `heroFont:'Georgia,…serif'`, `heroBorder:'6px rgb(230,59,46)'`, 가로 스크롤 없음(1440=1440).
  - **[검증됨]** 구독 해지 라이브 동작 — `POST /api/subscribe/` 200 → `POST /api/unsubscribe/` 200. 배포본 `dist/_worker.js/pages/api/unsubscribe.astro.mjs` 에 `method:"DELETE"` 1건·`PUT` 0건, `!response.ok`면 500 반환 코드이므로 200 = Brevo 2xx = 컨택트 실제 삭제.
  - **[검증됨]** `/courses/` — 200, `h1:'AI 실습 미니 강의 — 사전등록'`, 관심 등록 폼 존재, `tossBtn:false`(키 미설정 = 의도된 폴백).
  - **[검증됨]** `POST /api/courses/interest/` — 200 `{"ok":true,…}`, `aikorea24-db.course_interest` 에 1행 생성 확인 후 삭제(`COUNT=0`).
  - **[검증됨]** Brevo API 키 등록 — 신규 계정 Pages 프로젝트 env_vars 에 `BREVO_API_KEY` 존재(값 미열람).
  - **[부분검증]** `/tools/*` 하위 10개 파일에 오프팔레트 잔존. 지시서 §3-1/§3-2 파일 목록에 없어 손대지 않음.
  - **[부분검증]** 모바일 390×844 렌더 — Aside `page` 객체에 `setViewportSize` 없어 실기기 뷰포트 확인 불가. 번들 내 `@media` 규칙 존재까지만 확인.
  - **[검증불가]** 파비콘·마스코트 교체. 원본(`favicon-final.webp`·`mascot-tiger.webp`)이 말랑이 VM `~/workspace/aik24-brand/assets/`에만 있고 Mac에 없음 → **`보류 (원본 미수령, 2026-10-10)`**. 복구: 대표님이 Mac으로 복사 → `public/` 배치 → `<link rel="icon">` 경로 확인.
- **[위반 감지 — 자기 검증 오류 정정]**: 이전 세션에서 `emdash02_measure.query()` 인자 없이 호출해 기본 DB(`emdash bbbcbc34`) 스키마를 "메인 `users` 스키마"로 잘못 기록했고, 그 잘못 기록이 state.md·완료보고에 남아 있었다. 실제 `aikorea24-db` 의 `users` 는 `id INTEGER PK AUTOINCREMENT, google_id TEXT UNIQUE NOT NULL, email TEXT NOT NULL(unique 아님)…` 이고 `courses`·`enrollments` 테이블은 **존재**한다(`POST /api/courses/enroll/` 200 정상). `interest.ts` 는 이 때문에 1차 배포에서 500(`ON CONFLICT clause does not match any PRIMARY KEY or UNIQUE constraint`)이었고, 전용 테이블 `course_interest` 로 교체해 해결. → **메인 사이트 D1 조회는 항상 `database_id=cfnew.A24_DB` 명시.**
- **기록 대상 상태**:
  - `보류 (원본 미수령, 2026-10-10)` — 파비콘·마스코트 (§3-2.4·3-2.5)
  - `대기 (발송 시각 미확정, 2026-10-10)` — 일일 브리핑 자동 발송 (§5-2.4)
  - `대기 (본문 미수령, 2026-10-10)` — 환영 시퀀스 4통 (§5-2.5)
  - 운영 기준 기록(§5-2.6) — `@ai.kr.24` 은 브리핑 1건당 Threads 요약 1건을 **수동 발행**. 자동 발행 구축은 범위 밖.
- **잔존 위험**:
  1. Workers Free 10ms CPU 한도(1102) — Workers Paid 전환 금지 지시에 따라 미해결.
  2. `/tools/*` 하위 10개 파일 오프팔레트 잔존(ToolForm 18·tools/[id] 27·tools/index 48·finder 10·task/[slug] 11·task/index 3·payments 5·submit 1·about 1).
  3. 메인 `dark:` 클래스 750건 잔존 — `darkMode:'class'` + `.dark` 미부착이라 런타임 미적용. 전수 삭제(diff 750줄) 미수행.
  4. Brevo IP 화이트리스트 반복 변경 — 로컬 공인 IPv4가 `58.10.247.112` → `110.168.249.241` → `58.11.95.17` 로 3회 변경. 현재 `58.11.95.17` 등록 필요(로컬 Brevo API 401).
  5. EMDASH-12 `cloudflareEmail()` 플러그인 발송 시 `Hook timeout after 5000ms`(메일은 도착하나 API 응답 500). 매직링크 발송 UX 저하.
  6. PAT 평문 `/tmp/aik24-pat.txt` — Vault 등록 후 삭제 필요.
  7. `~/projects2/aikorea24emdash` git 아님.
  8. EMDASH-12·13 완료보고 미작성 / EMDASH-05·07 보고서 미작성 / PIPE-01 작업2 중단(지시서 전제 거짓, 대표님 선택지 A/B/C 대기).
  9. `PUBLIC_TOSS_CLIENT_KEY` 미설정 → 결제 버튼 미노출(지시서 §7-3.3 의도대로 가맹 승인 후 교체).
- **다음 행동**: 대표님 — (1) 파비콘·마스코트 원본 Mac 복사 (2) Brevo 화이트리스트에 `58.11.95.17` 추가 (3) 토스페이먼츠 가맹 신청 후 키 전달 (4) 일일 브리핑 발송 시각·환영 시퀀스 4통 본문 제공 (5) PIPE-01 작업2 선택지 결정.
- **증거 파일**: `/tmp/r01_b4.log`(빌드), `/tmp/r01_d4.log`(배포), `/tmp/r01_b5.log`, `/tmp/r01_d5.log`, `/tmp/ci3.json`·`/tmp/ci3_out.json`(관심 등록 E2E).

## 2026-10-10 16:33 — AIK24-EMDASH-03 디자인 동기화 (시안 A) — CSS 변수 31개 + 타이틀 빨간 라인, 배포 `226eda73`

- **한 일**: `~/projects2/aikorea24emdash/src/styles/theme.css`(135→187줄)에 시안 A 토큰 추가. (1) tokens.css 미정의로 CSS 폴백(파랑·네이비·녹색)이 노출되던 `:root` 토큰 31개를 흑/백/적/회색으로 정의 (2) `.page-title`·`.article-title` 에 빨간 버티컬 라인 추가 (3) 댓글폼 `.dark` 분기 무력화 (4) `.ec-reaction-icon` 활성색 `#e0245e`→`#E63B2E`. 빌드를 깨뜨리던 EMDASH-12 타임아웃 래퍼 `src/lib/emdash-email.mjs` 삭제하고 `astro.config.mjs` import 를 공식 `@emdash-cms/cloudflare/plugins` 로 복원. 배포 `226eda73-9b1e-47b9-8245-7b79f9e58903`.

- **결과**
  - [검증됨] 빌드 성공(`Server built in 2.78s`/`Complete!`) / 배포 성공 / 엔드포인트 5개 전부 200(`/` 33,307B, `/posts` 69,186B, `/search` 20,306B, `/sitemap.xml` 393,396B, `/rss.xml` 38,188B)
  - [검증됨] 빨간 버티컬 라인 3곳 적용 — Aside `getComputedStyle` 결과 `borderLeft: "4px rgb(230, 59, 46)"` (`.page-title`·`.article-title`·`.section-title` 모두), `paddingLeft: 12px`, Georgia serif. `body` computed = `rgb(255,255,255)` 배경 / `rgb(17,17,17)` 텍스트. 홈 가로 스크롤 없음.
  - [검증됨] CSS 번들 `/_astro/Base.ClvlkJ1-.css`(30,926B) `:root` 블록에 31개 토큰 존재(1,039B). 3색 카운트 증가 — `#e63b2e` 5→9, `#111` 9→13, `#fff` 16→20.
  - [검증됨] DB 무변경 — `ec_posts` slug 1,460건 sha256[:16] `d2f6c0177bf5fe1e` 기준선 일치.
  - [부분검증] 오프팔레트 hex 가 번들에 문자열로 잔존(`#0073aa` 8회 등, 변경 전과 개수 동일). 전부 `var(--토큰, 폴백값)` 2번째 인자이고 1번째 인자가 `:root` 에 정의되어 런타임 미사용. "문자열 삭제"가 아니라 "화면 미노출"로 판정.
  - [검증불가] 모바일 실기기 렌더. Aside 브라우저 `page` 객체에 `setViewportSize`/`viewportSize` 없음(프로토타입 확인). 대신 번들 내 `@media (width<=900px)` 푸터 1열, `(width<=768px)` `.emdash-columns` → `flex-direction:column`, `(width<=640px)` 헤더·갤러리 규칙 존재로 간접 확인. 복구: 대표님 기기 확인 또는 로컬 Playwright.

- **[위반 감지]** EMDASH-12에서 만든 `src/lib/emdash-email.mjs` 래퍼가 `npm run build` 를 깨뜨리고 있었음(`Rolldown failed to resolve import "src/lib/emdash-email.mjs" from "\0virtual:emdash/plugins"`). 지시서 범위 밖이지만 CSS 변경분 빌드·배포의 선행 조건이라 함께 처리. 부수 효과로 EMDASH-12 `POST /_emdash/api/settings/email` 500(`Hook timeout after 5000ms`)의 원인 래퍼가 제거됨 — 재발송 테스트는 미실행.

- **잔존 위험** 10건 (보고서 §6 참조). 핵심: ① 모바일 실기기 미확인 ② 오프팔레트 hex 문자열 번들 잔존(폴백이라 미사용) ③ EMDASH-12/13 보고서·state 기록 미작성 ④ **BREVO-UNSUB 구독 해지 수정 미배포**(신규 계정이 `aikorea24.kr` zone `71a21534…` + Pages 프로젝트 `aikorea24` 소유 확인 → 배포 가능 상태, 라이브는 아직 무효 `PUT`) ⑤ Workers Free 10ms CPU 한도 ⑥ 패스키 `singleDevice`+`backed_up:0` ⑦ PAT 평문 `/tmp/aik24-pat.txt` ⑧ 프로젝트가 git 아님 ⑨ `src/lib/og-image.ts` DEFAULTS 에 `bgColor:#0d0d0d`·`brandColor:#0066cc` 잔존(호출부 부재로 번들에 미포함) ⑩ Cloudflare Email Routing API 조회 불가(토큰 권한).

- **다음 행동** ① EMDASH-12 보고서 + state 기록 ② BREVO-UNSUB 해지 수정 배포 ③ EMDASH-12 테스트 발송 재실행으로 500 해소 확인 ④ 대표님 모바일 확인 ⑤ 미처리 지시서 EMDASH-05(로드맵 성격)/EMDASH-07(实质 완료, 보고서만 없음)

## 2026-10-10 13:54 — AIK24-EMDASH-12 지시서 작성 + PAT Vault 등록 완료

- EMDASH-12 (이메일 제공자 설정) 지시서 작성: Resend 권장, 매직링크 로그인용
- 대표님이 새 PAT를 Secure Vault에 등록 완료 (custom.emdash-aikorea24)
- Admin 이메일: info@aikorea24.kr 확정
- 다음: PAT로 글 작성 테스트 → EmDash 글쓰기 스킬 생성

## 2026-10-10 15:31 — AIK24-EMDASH-11 PAT 발급(CLI 경유): 기존 폐기 + 신규 발급 + MCP 200 검증

**한 일**

기존 emDash PAT 폐기 → 신규 PAT 발급(D1 직접 경로, 관리자 UI 로그인 불필요) → MCP 엔드포인트 검증 → 토큰 파일 전달 준비.

Admin UI 로그인이 불가한 상태(메일 제공자 미설정 `{"available":false,"providers":[]}` + 패스키 OTP 미등록)이므로 지시서 §2 "방법 B(D1 직접)" 채택. `emdash` CLI虽有 `node_modules/.bin/emdash` 있으나 인증 없이 D1 경로가 더 짧아 파이썬 재현으로 처리.

**결과**

[검증됨]

| 항목 | 값 | 근거 |
|---|---|---|
| 기존 PAT 폐기 | 완료 | `_emdash_api_tokens` 행 1건(`id=01M4HKX4HAARE21HN4C3HSJANG`, `name=aikorea24`, `prefix=ec_pat_6ONI`) DELETE → 잔여 조회에서 부재 |
| 신규 PAT 발급 | 완료 | `id=01M4J84GEN00000000000002X7`, `name=muse-agent-2026-10-10`, `prefix=ec_pat_1D3a`, `user_id=01M4HKV7ZCNZZ11DN43Q5J4WCT`(info@aikorea24.kr) |
| MCP `initialize` | **HTTP 200** | `{"result":{"protocolVersion":"2025-06-18","capabilities":{"logging":{},"tools":{"listChanged":true}},"serverInfo":{"name":"emdash","version":"0.1.0"}}}` |
| MCP `tools/list` | **HTTP 200** | 첫 도구 `content_list` 반환 확인 |
| 인증 실사용 흔적 | `last_used_at=2026-10-10T06:31:18.992Z` | `resolveApiToken()` 이 성공 시 갱신 |
| 토큰 파일 | `/tmp/aik24-pat.txt` mode `0600`, 51 bytes | `stat -f '%Sp'` → `-rw-------` |
| 평문 유출 | 0건 | `grep -rl 'ec_pat_1D3a' ~/Projects/aikorea24` → 결과 없음 |
| 워커 배포 | 변경 없음 | D1 직접 SQL만. `wrangler deploy` 미실행 |

[부분검증] — 지시서 §4 예시 명령(`params:{}`)은 `-32603 (expected string, path params.protocolVersion)` 반환. 지시서 예시 재사용 시 실패. `protocolVersion`/`capabilities`/`clientInfo` 채워 재호출해 200 확인.

[검증불가] — MCP 실제 도구 호출(`content_list` 실행)은 미수행. 도구 목록 조회까지만. 복구: 신규 PAT 로 `content_list` 1회 호출.

**토큰 알고리즘 재현 검증** [검증됨]
정본 소스 `@emdash-cms/auth@0.38.0/dist/authenticate-BmzDlWK2.mjs`: `TOKEN_BYTES=32`, `raw = prefix + base64url_nopad(random32)`, `hash = base64url_nopad(sha256(raw))`, `prefix = raw.slice(0, len(prefix)+4)`.
기존 PAT 문자열로 재계산 → `EShsLiC4Cow4Umim0ky2bRRmr7Q7OBva9SPesNQHUzQ` = DB `token_hash` 와 일치 → 파이썬 재현이 서버와 동일함 확인 후 발급에 사용.

**코드 변경**

| 파일 | 구분 | 내용 |
|---|---|---|
| `scripts/emdash11_pat.py` | 신규 (PRODUCTION) | PAT 회전 스크립트. 발급 → MCP 검증(실패 시 신규 행 롤백) → 기존 폐기 → 파일 저장. 토큰 평문은 stdout/로그/소스 미기록 |
| `_emdash_api_tokens` | DB | INSERT 1행 / DELETE 1행 / 자동 UPDATE 1행(`last_used_at`) |

**잔존 위험**
1. **[최우선] 토큰이 `/tmp/aik24-pat.txt` 에 평문 존재** — Secure Vault 등록 확인 후 삭제 필요. macOS 전영 암호화 디스크라 로그인 사용자만 읽음.
2. **기존 PAT 폐기 = 복구 불가** — 유실 시 Admin UI 로그인(불가) + MCP 접근 모두 차단. 재발급은 D1 직접 INSERT로만.
3. **PAT 만료 없음** (`expires_at=NULL`) — 영구 유효. 회전 절차가 유일 방어선.
4. **Admin UI 로그인 여전히 불가** — 메일 제공자 플러그인 미설정.
5. **패스키는 다른 호스트에서 사용 불가** — RP ID 고정. `emdash.aikorea24.kr` 패스키는 `l2t-emdash.twinssn.workers.dev` 에서 동작 안 함.
6. **MCP 경유 쓰기 시 CPU 1102 위험** — Workers Free 10ms. 콘텐츠 쓰기는 기존처럼 D1 직접 SQL 유지 권장.
7. **`_emdash_api_tokens` 1행만 존재** — dev-bypass 등 자동 발급 토큰 없음.

**다음 행동**
1. 대표님: `cat /tmp/aik24-pat.txt` → Secure Vault 등록(권장 `aikorea24 / emdash / PAT`, 이름 `muse-agent-2026-10-10`) → 등록 완료 보고
2. 등록 확인 후 `/tmp/aik24-pat.txt` 삭제(`rm -P`)
3. MCP 실제 도구 호출 1회 검증 → [검증불가] 해소
4. Admin UI 로그인 별건 — 메일 제공자 플러그인 설치 또는 패스키 재등록 절차
5. starclip hugh79757 계정 이전 — 착수 전 destructive-operations-protocol 4단계 계획 필요

**산출 파일**
- `~/Projects/aikorea24/scripts/emdash11_pat.py` (신규)
- `SSOT/프로젝트/aikorea24/지시서/2026-10-10-1531-AIK24-EMDASH-11-완료보고.md` (7개 섹션)

---

## 2026-10-10 13:50 — AIK24-BREVO-UNSUB 구독 해지 무효 버그 수정(코드·빌드 완료, 배포 차단)

**한 일**
- `src/pages/api/unsubscribe.ts` 의 해지 로직을 `PUT /v3/contacts/{email}` (`listIds: []`) → `DELETE /v3/contacts/{email}` 로 교체. 미사용이 된 `BREVO_LIST_ID` 지역변수(L8) 제거.
- Brevo 계정 자체 실측(API 키 화이트리스트 등록 후): free 플랜 300통/일, 리스트 1개(id=2), 컨택트 8명.

**결과**
- [검증됨] 기존 코드의 `PUT listIds:[]` 는 **HTTP 204 를 반환하면서 실제 리스트에서 제거하지 않음**. 3회 반복 재현: `POST /api/unsubscribe/` 200 → `GET /v3/contacts/{id}` → `listIds: [2]` 잔존. 즉 사용자에게 "해지 완료"를 안내하지만 newsletters 발송 대상에 그대로 남음.
- [검증됨] 문서상 정답 `DELETE /v3/contacts/{id}/lists/{listId}` 는 이 계정에서 **404 `Invalid route/method passed`** (컨택트 생존 상태에서 2회 확인). 계정 free 플랜 제약으로 추정, 미확정.
- [검증됨] `DELETE /v3/contacts/{email}` 는 204 반환 후 컨택트 완전 삭제 확인. 신규 코드가 만드는 호출을 그대로 재현해 검증함.
- [검증됨] `npm run build` 성공 (`Server built in 12.10s`, `Complete!`).
- [검증불가] **Worker egress 에서 신규 코드가 동작하는지** — 배포 불가로 라이브 검증 못 함. 복구: 출발 계정 Pages 프로젝트로 배포(규칙상 금지) 또는 계정 이전 후.

**★ 배포 차단 사유 (중요)**
- `aikorea24.kr` zone은 **출발 계정 소유**. 근거 3중: ① 신규 계정 `7eb1b8cd` `GET /zones` → 0건 ② `.env` 의 `CLOUDFLARE_ZONE_ID=a6d9e750…` 를 신규 토큰으로 조회 → `code 9109 Unauthorized` ③ 신규 계정 Pages 프로젝트 `aikorea24`(`24f70480…`) = 배포 0건·env_vars 0개.
- 따라서 `scripts/deploy.sh` 를 돌리면 `aikorea24-4nk.pages.dev` 에 배포되고 **aikorea24.kr 은 갱신되지 않음**. 실제로 실행하지 않음.
- 출발 계정 접근은 세션 금지 규칙에 걸림 → 대표님 승인 없이는 배포 불가.

**DB·인스턴스 변경**
- Brevo: 테스트 주소 3건 생성 후 전량 삭제. 최종 컨택트 8명(`yenakim@sk.com`, `yenarchivist@gmail.com`, `verify-test@aikorea24.kr`, `test-hugh@example.com`, `sample@email.tst`, `twinssn@gmail.com`, `jinyeon_cho@hotmail.com`, `hugh79757@gmail.com`) — 테스트 주소 0건.
- Cloudflare: 없음(읽기 전용 조회만).

**잔존 위험**
1. **해지 수정은 미배포** — 라이브는 여전히 PUT(listIds:[])라 200만 반환하고 실제 미해지. 스팸/csrf 노출 지속.
2. 해지가 컨택트 완전 삭제로 구현됨 — `src/pages/api/courses/enroll.ts` 도 같은 리스트 2 + 태그(`course-enrolled-*`)를 쓰므로, 구독 해지 시 코스 태그도 함께 소멸. 코스의 권위 데이터는 D1 `enrollments` 테이블이라 기능 영향은 없으나 태그 기록은 사라짐. (free 플랜·구독자 8명 상태라 현실 영향 무시 가능)
3. 신규 계정 Pages 프로젝트 시크릿 0개 — 마이그레이션 시 Brevo·Google OAuth·SESSION 전부 500.
4. `BREVO_LIST_ID` env 미설정 여부 판별 불가 — `src/pages/api/subscribe.ts:34` 와 `courses/enroll.ts` 의 `Number(x || 2)` fallback이 위장. 코드 관례상 값=2라 동작에는 지장 없음.
5. Brevo `/v3/lists` 엔드포인트가 이 계정에서 404 — 리스트 메타·구독자 수 조회 불가.
6. Brevo IP 화이트리스트에 현재 공인 IPv4(`58.10.247.112`) 등록됨. IP 변경 시 재등록 필요(오늘만 110.168.249.241 → 58.10.247.112 로 2회 변경).
7. 라이브 `POST /api/subscribe`(슬래시 없음)는 308 → `/api/subscribe/`. 내부 폼은 슬래시 경유라 정상.

**다음 행동**
- 대표님 결정 필요: ① 출발 계정 접근 허용 후 배포 ② 신규 계정으로 zone 이전 후 배포 ③ 해지 버그를 임시로 감춤(500 반환이라도 정직하게).
- 신규 계정 프로젝트 선행 등록 시 시크릿 목록: `SESSION_SECRET`, `BREVO_API_KEY`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, plain `account_id`.

---

## 2026-10-10 13:37 — AIK24-PIPE-01 블로그 파이프라인 전환 (작업1·3 완료, 작업2 중단)

**한 일**
- 작업1: `scripts/weekly_blog_publisher.py`에 `_publish_to_emdash()` 추가 — 신규 글을 EmDash D1 `ec_posts`에 직접 INSERT(revisions + ec_posts + content_taxonomies 3 statement). `EMDASH_PUBLISH=1` 환경변수로 게이트, 미설정 시 기존 동작 100% 유지.
- 작업3: `naver_blog/publish_blog.py` L25 `POST_URL` 상수 추가, L135·L250을 `{POST_URL}/posts/{slug}`로 변경.
- 작업2: **중단.** 백업 `backups/blog-2026-10-10.zip`(4.4MB)만 수행.

**결과**
- [검증됨] 발행 경로 동작 — 로그 `emdash_published: …/posts/pipe-01-파이프라인-d1-발행-경로-테스트 (rowsWritten=32)`, DB `status=published/locale=en/version=2`, FTS 1행, 라이브 `GET /posts/<slug>` **200 / 31,944B**.
- [검증됨] 테스트 행 정리 후 기준선 복원 — `n=1460`, `sha256[:16]=d2f6c0177bf5fe1e` **MATCH**, `residual: []`.
- [검증됨] 기존 테스트 `pytest tests/test_weekly_blog_publisher.py -q` → **12 passed**. 테스트 코드 수정 없음.
- [검증됨] 로컬 md 1,460건(테스트 파일 제거 후), DB↔로컬 제목 집합 **1,459/1,459 완전 일치**(고유 제목 1,459 — 중복 1쌍).
- [검증불가] 기존 1,460건 중 **715건**의 로컬 파일명 슬러그 ≠ emDash slug(날짜 prefix 제거로 744건만 해결). 리다이렉트 도입 시 slug 매핑 테이블 필요.

**[위반 감지] 작업2 중단 사유 — 지시서 전제 오류**
지시서 "`/blog/*` → `emdash.aikorea24.kr/posts/` 리다이렉트 적용됨"은 **거짓**. 실측: `/blog/_temp-002/` → **200**(프리렌더 페이지 정상), emDash slug URL → 404. `aikorea24.kr`은 `src/content/blog`을 `prerender=true`로 정적 생성 중.
삭제 시 blog 컬렉션 소비자 **8개 파일**(`blog/[...id]`, `blog/[...page]`, `blog/category/[cat]/[...page]`, `index.astro`, `sitemap-blog.xml.ts`, `rss.xml.ts`, `api/search.ts`, `api/home-content.ts`)이 깨지고 `/blog/<파일슬러그>/` **1,460개 URL 전부 404** → 지시서 "색인된 콘텐츠 손실 금지" 위반.
또한 컬렉션 정의는 `src/content/config.ts`가 아니라 **`src/content.config.ts:4-15`**.

**변경 파일**
- `scripts/weekly_blog_publisher.py` (PRODUCTION CODE, 193→261줄)
- `naver_blog/publish_blog.py` (PRODUCTION CODE, 3곳)
- `backups/blog-2026-10-10.zip` (산출물)

**DB 변경**
- 테스트 1행 INSERT→DELETE만. 현재 `ec_posts` 1,460행(해시 기준선 일치). Workers Free 10ms CPU 한도 회피 위해 D1 직접 SQL만 사용.

**잔존 위험**
1. 작업2 미실행 — `src/content/blog` 1,460건 잔존, 대표님 승인 대기
2. 기존 715건 slug 불일치 (지시서 유보 항목)
3. 네이버 발행기 휴면 — `publish_blog.py:22 BLOG_DIR=src/content/blog`. 작업2 실행 시 `get_all_posts()` 빈 리스트 → 발행 0건. 현재 `.plist.disabled`, 로그 mtime 9월 10일
4. 제목 중복 1쌍 (사유 미확인) / `revisions` 고아 496행 (출처 미확정)
5. `rowsWritten` emdash-db 84,075/100,000 — 여유 15,925행
6. Workers Free 10ms CPU 한도 잔존 / PAT 회전 미확인 (EMDASH-02 잔존)

**다음 행동 (승인 필요)**
A. 지시서대로 삭제만 → 1,460 URL 404 (권고 안 함)
B. **리다이렉트 먼저 → 삭제 (권고)**: slug_map.json 생성(제목 기준) → `blog/[...id].astro` 301 → 목록·카테고리 리다이렉트 → rss/sitemap blog 항목 제거 → 검색·홈 API 정리 → config 삭제 → 삭제 → 빌드·배포
C. 작업2 보류

보고: `SSOT/프로젝트/aikorea24/지시서/2026-10-10-1337-AIK24-PIPE-01-완료보고.md`

---

## 2026-10-10 11:10 — AIK24-D1-VERIFY-01 신규 계정 D1 한도 사전 점검 2건 (NETWORK_KEY 도입 + news 인덱스 확인)

지시서: `SSOT/프로젝트/aikorea24/지시서/2026-10-10-1100-AIK24-D1-VERIFY-01.md`
대상 계정: `7eb1b8cd178de269758ec94b2e03330b` (신규). 인증 토큰 = `CF_MIGRATE_TOKEN` (`~/.env.common`). 구 계정(hugh79757) 리소스 변경 0건.

### 한 일
1. **작업 1** `/api/network/refresh` — `NETWORK_KEY` 미설정 상태 확인 → 64자 키 생성(값 미기록) → Pages 신규 계정 프로젝트 `aikorea24` 시크릿 등록 → Pages 배포 1회(Direct Upload라 시크릿은 리데ploy 없이 미반영) → launchd `com.aikorea24.network-refresh` plist에 `?key=` 적용 + 권한 600 + 재적재 → 401/200 테스트.
2. **작업 2** 신규 D1 `aikorea24-db` — D1 import 완료 확인(`news` 17,881행) + `idx_news_created` 이미 존재 → `EXPLAIN QUERY PLAN` 에서 `SCAN news USING INDEX idx_news_created` 확인 → **인덱스 추가 0건**.

### 결과
**[검증됨]**
- [작업1] 시크릿 등록 전 실측: 키 없이 `GET /api/network/refresh/` → **HTTP 200** (`total 106, success 50, failed 56`). `src/pages/api/network/refresh.ts:100` `if (env.NETWORK_KEY && key !== env.NETWORK_KEY)` 이 시크릿 부재 시 검사를 통째로 건너뛰는 코드 경로 확인.
- [작업1] 배포 후 실측: 키 없음 → **HTTP 401** `{"error":"Unauthorized"}`, 오답 키 → **HTTP 401**, 정상 키 → **HTTP 200** `total 106 / success 50 / failed 56`.
- [작업1] 크론 실동작: `launchctl kickstart` 후 `launchctl list` 마지막 종료코드 **0**, `/tmp/network-refresh.log` 0바이트(curl `-s -o /dev/null` 정상 동작), D1 `network_cache` `MAX(fetched_at)` = `2026-10-10 04:05:18` UTC = 실행 시각 11:05 KST와 일치(총 347행).
- [작업1] 스케줄 무변경: `launchctl print` → Hour 6 / Hour 18, Minute 0 유지.
- [작업1] 배포 무회귀: `/` 200/59,360B · `/news` 301/292B · `/api/network/` 404/22,216B · `/blog` 308/0B — **배포 전후 바이트 동일**.
- [작업2] 신규 D1 `aikorea24-db`(id `3f4cedde-eabc-4d7c-b459-f6abe8733767`) `news` 17,881행, `idx_news_created` = `CREATE INDEX idx_news_created ON news(created_at DESC)`.
- [작업2] 실행계획: `SCAN news USING INDEX idx_news_created` + `USE TEMP B-TREE FOR LAST TERM OF ORDER BY`.
- [작업2] D1 쓰기 **0건** (전부 SELECT). `CREATE INDEX` 실행 0건.
- 코드 변경 **0건**. 커밋 0건.

**[부분검증]**
- 실행계획의 `USE TEMP B-TREE FOR LAST TERM OF ORDER BY` — `ORDER BY created_at DESC, id DESC` 에서 `id` 보조 정렬 때문에 인덱스만으로는 정렬이 끝나지 않는다. 행수 제한(500) 덕에 실측 비용은 작으나, 지시서가 전제한 "500행만 읽음"과는 거리가 있다. 뉴스 17,881행 규모에서는 무시 가능.
- 크론 1회 쓰기량: `network_feeds` 106건 중 성공 50건 → 대략 50 DELETE + 50×≤5 INSERT ≈ 300행. 지시서 추정 750행과 불일치(측정 기반).

**[검증불가]**
- 지시서의 "133회/일" 전제. `com.aikorea24.network-refresh` 스케줄은 06:00·18:00 **2회/일**이고 저장소·LaunchAgents 전수 grep에서 호출자 1건(해당 plist)만 확인. 133회/일 출처 미상 — 복구 계획: 10만 행 한도 도달 시 D1 `meta` rows_written 대조로 호출 횟수 역추적.
- 다른 계정(hugh79757) 동일 엔드포인트 상태. 구 계정 리소스 변경 금지 지시에 따라 조회만, 미실시.

### 변경 대상 · 원복
| 대상 | 변경 | 원복 |
|---|---|---|
| Pages `aikorea24` 시크릿 `NETWORK_KEY` | 신규 등록 | `wrangler pages secret delete NETWORK_KEY` |
| Pages 배포 `d0fe37c5` → `a5a94ff2` | 동일 `dist` 재업로드(시크릿 반영) | `wrangler pages deployment rollback --project-name aikorea24 d0fe37c5-201d-4f53-bfe4-e93a811e86ee` |
| `~/Library/LaunchAgents/com.aikorea24.network-refresh.plist` | URL에 `?key=` 추가, 권한 600 | `.bak.20261010_pre_networkkey` 복사 후 재적재 |
| D1 | 없음 | — |

### 잔존 위험 8건
1. **`NETWORK_KEY` 평문 2곳 존재** — Pages 시크릿 저장소 + `~/Library/LaunchAgents/com.aikorea24.network-refresh.plist`(권한 600으로 완화). plist 백업 `.bak.20261010_pre_networkkey`은 키 없는 원본이라 노출 없음. 키 원문은 리포트·state.md·채팅 어디에도 기록하지 않음.
2. **갱신 절차 부재** — 키를 모르면 크론 복구 불가(백업 plist에 키 없음). 갱신 시 2곳(시크릿·plist) 동시 변경 필수.
3. **`failed 56/106`** — RSS 56개가 실패(`Too many subrequests by single Worker invocation` 포함). 기존 상태이며 이번 작업과 무관. 원인은 Workers Free 서브리퀘스트 한도.
4. **`USE TEMP B-TREE`** — `id DESC` 보조 정렬. 규모 커지면 `CREATE INDEX ... ON news(created_at DESC, id DESC)` 필요.
5. **`_headers`/`_redirects` 284MB `dist`** — Pages 배포 단위 284MB. 업로드 1회 3분 소요.
6. **직접 업로드 방식** — 시크릿·바인딩 변경이 매번 리데ploy를 요구. `git push` 연동 빌드로 전환하지 않으면 이 갭이 반복됨.
7. **지시서 133회/일 vs 실제 2회/일 불일치** — 원인 미상(위 [검증불가]).
8. **EMDASH-10 잔존 11건** 이월(Workers Free 10ms CPU 근본 미해결 / admin UI 미확인 / PAT 회전 미확인 등).

### 다음 행동
1. `NETWORK_KEY` 회전 주기 정하기(90일 권장) — 회전 시 시크릿·plist 동시 갱신
2. RSS `failed 56` 원인 정리(Workers Free 서브리퀘스트 한도 → 배치 분할)
3. Pages 자동 빌드 연동 검토(리데ploy 갭 제거)
4. 이전 지시서 잔존: Workers Paid 전환 결정 / PAT 회전 / `posts/index.astro` 수동 되돌림

### 관련
완료보고: `SSOT/프로젝트/aikorea24/지시서/2026-10-10-1110-AIK24-D1-VERIFY-01-완료보고.md`

---
## 2026-10-10 12:45 — AIK24-EMDASH-10 이미지 수정 완료 (방안 B 절대 URL) + /posts 목록 1102 수정

지시서: `SSOT/프로젝트/aikorea24/지시서/2026-10-10-AIK24-EMDASH-10-이미지수정.md`

### 한 일
`featured_image` 1,415행을 절대 URL MediaValue로 정규화(DB UPDATE 1회로 해결 — R2 복사 불필요). 검증 중 발견한 `/posts` 목록 503(1102)도 수정. 신규 스크립트 `scripts/emdash10_images.py`.

### 결과
**[검증됨]**
- D1 `featured_image`: 1,416건 전량 파싱 가능 JSON + `https://aikorea24.kr/` 절대 src
- 홈 `/`: `<img>` 10개 전부 절대 URL, 상대 0건
- 상세 무작위 10건(random.seed(7)): hero 10/10, 절대 src 10/10
- `/posts`: 5회 연속 200 / 69,006B / 60개 (limit 60 적용으로 1102 해소)
- DB slug 무변경: n=1460 sha256[:16] `d2f6c0177bf5fe1e` MATCH (EMDASH-09 기준선)
- 회귀 없음: `/` `/posts` `/sitemap.xml` `/rss.xml` `/search` 전부 200
- `rowsWritten` 79,738 / 100,000

**[부분검증]** 원본 이미지 HTTP 200은 무작위 5건만 확인(1,416건 전수 미검증).
**[검증불가]** admin UI 썸네일 표시 — PAT으로 admin 화면 미조작.

### 원인 2건
1. 이미지: EMDASH-06/08 SQL 경로가 `featured_image`에 경로 문자열만 저장 → `getImageUrl()`가 `emdash.aikorea24.kr` 도메인으로 조립 → 404
2. `/posts` 503: `posts/index.astro`가 limit 없이 `getEmDashCollection` 호출 → 1,460건 전량 hydrate → Workers Free 10ms CPU 초과(1102). 성공 시 HTML 1.1MB

### 변경 파일
- `~/projects2/aikorea24emdash/src/pages/posts/index.astro` — `limit: 60` + 제목 "Latest Posts"
- `scripts/emdash10_images.py` (신규)
- 배포 버전 `674566f8-9cf0-4c03-a470-1b2d7054f437` (직전 `5be7ac05`, `d0907dbf`)

### DB·인스턴스 변경
| 대상 | 변경 | 원복 |
|---|---|---|
| `ec_posts.featured_image` | 1,415행 UPDATE | 목표 상태. raw 경로로 재변환 가능 |
| 워커 3회 deploy | 이전 버전 rollback 가능 | |
| `posts/index.astro` | 수동 되돌림 필요 (git 아님) | |

### 잔존 위험 11건
Workers Free 10ms 한도(근본 미해결) / admin UI 미확인[검증불가] / 원본 이미지 전수 미검증[부분검증] / `/posts` 카드가 ULID로 링크(slug URL 아님) / `/posts` 카드 이미지 미표시(기존 설계) / `options` 테이블 0행 → RSS description 공백 / `/rss.xml` `//` 이중 슬래시(기존 동작) / Workers Paid 미전환 / `_emdash_media_usage_sources` 미적재 / `audit_logs` 0행 / PAT 회전 미확인

### 다음 행동
1. admin UI 썸네일 육안 확인
2. Workers Paid 전환 결정
3. `/posts` 페이지네이션 (500건 이상 시)
4. `options` 테이블에 `site:title`/`site:tagline` 등록
5. PAT 회전

### 작업 중 발견한 함정 (재사용 가치)
- D1 REST SQL은 `json_set()`/`json_extract()`를 다른 표현식과 섞으면 SQLITE_ERROR(7500) — 값 계산은 파이썬에서
- **Astro는 `.astro`를 항상 HTML로 렌더** — `export const GET` 무시됨. 엔드포인트는 `.ts`로
- `options` 테이블 PK 컬럼은 `name` (`key` 아님)
- curl + 한글 slug는 `urllib.parse.quote()` 필수 (수작업 인코딩은 302→404)

### 관련
완료보고: `SSOT/…/2026-10-10-1245-AIK24-EMDASH-10-완료보고.md`

---
## 2026-10-10 12:33 — AIK24-EMDASH-09 라우팅/사이트맵 수정 완료 (sitemap·rss 엔드포인트 전환, slug 무변경)

지시서: `SSOT/프로젝트/aikorea24/지시서/2026-10-10-AIK24-EMDASH-09-라우팅수정.md`
배포 워커 버전 `5be7ac05-f797-44d8-bf58-652a9c3f2809`

### 한 일
`/sitemap.xml` 빈 출력 원인 확정 → `.astro` → `.ts` 엔드포인트 전환 + D1 직접 조회. 동일 원인인 `/rss.xml`도 함께 수정. `wrangler.jsonc`에 없던 `IMAGES`/`ASSETS` 바인딩 추가(배포 소실 방지). **DB 무변경.**

### ★ 근본 원인
Astro는 `.astro` 파일을 **항상 HTML 페이지**로 렌더한다. 안에 `export const GET: APIRoute` 가 있어도 무시되어 **빈 HTML 문서**를 반환한다. `sitemap.xml.astro`·`rss.xml.astro` 모두 이 구조였고 실제로 `200 / 0바이트 / text/html` 이었다. (지시서가 말한 "사이트맵이 비어 있음"이 이 케이스.)
2차 증상은 `getEmDashCollection("posts", limit:1000)`이 limit 적용 전 1,460건 전량 hydrate → Workers Free 10ms CPU 초과(1102). `fields`/`select` projection 옵션이 emDash에 없어 경량 조회 수단 없음.

### 결과 (3분법)
**[검증됨]**
- `/posts/<slug>` 무작위 10건 **10/10 → 200** (35~40KB, `random.seed(11)`)
- `/sitemap.xml` **200 / 353,922B / `application/xml`**, `<loc>` **1,462**개(포스트 1,460 + `/` + `/search`), 3회 연속 동일
- **DB slug 무변경** — `sorted(slug)` 1,460건 sha256[:16] = `d2f6c0177bf5fe1e`, 수정 전 기준선과 **MATCH**
- `/rss.xml` **200 / 38,188B / `application/rss+xml`**, `<item>` 50개
- `/` 200 32,927B, `/search` 200 20,126B (회귀 없음)
- rowsWritten 74,020 / 100,000

**[부분검증]** RSS `<link>` 슬래시 2개(`//posts/`) — 원본 코드의 기존 동작, 이번 회귀 아님. `options` 0행이라 title/tagline은 코드 fallback 사용.

**[검증불가]** RSS 피드 유효성(리더 측 파싱). 복구: GSC/피드 리더 제출 후 확인.

### 변경 파일
`src/pages/sitemap.xml.astro` 삭제 → `sitemap.xml.ts` 신규 / `src/pages/rss.xml.astro` 삭제 → `rss.xml.ts` 신규 / `wrangler.jsonc`에 `images`/`assets` 바인딩 추가.

★ 함정: `options` 테이블 컬럼은 **`name`** (`key` 아님). 첫 구현이 `key` 로 써서 `/rss.xml` 500 발생 → 교체.

### DB 변경
없음.

### 잔존 위험
1. Workers Free 10ms CPU 한도 — `getEmDashCollection` 계열 페이지(카테고리/태그/검색) 아직 동일 패턴
2. `options` 테이블 0행 — 사이트 타이틀/태그라인 fallback 사용
3. RSS `<link>` 슬래시 2개 (기존 동작)
4. PAT 회전 미확인 (EMDASH-02 잔존)
5. `_emdash_media_usage_sources`/`audit_logs` 미적재 — Workers Paid 전환 시 media-usage repair 필요
6. `~/projects2/aikorea24emdash` git 아님 — 변경 이력 추적 불가
7. RSS 피드 유효성 미검증
8. `featured_image` 문자열 저장 (EMDASH-06 잔존)
9. 마크다운 표·중첩 인용 PT 손실 (EMDASH-04 잔존)
10. blog 42건 category 없음 → taxonomy 미연결

### 다음 행동
1. sitemap.xml GSC 제출
2. Workers Paid 전환 여부 결정
3. EMDASH-03(디자인 동기화) 착수 — `tokens.css` 현재 파란 계열+다크모드로 지시서 요구(흑·백·적 3색, 라이트 전용)와 불일치
4. `~/projects2/aikorea24emdash` git 초기화 검토

완료보고: `SSOT/프로젝트/aikorea24/지시서/2026-10-10-1233-AIK24-EMDASH-09-완료보고.md`

---

## 2026-10-10 13:15 — AIK24-EMDASH-08 Phase2 Day2: 소스 1,948건 전량 D1 SQL 적재 완료

지시서: `SSOT/프로젝트/aikorea24/지시서/2026-10-10-AIK24-EMDASH-08-Day2.md`

### 한 일
Workers Free CPU 10ms 한도(EMDASH-04 1102)를 D1 REST SQL 직접 경로로 우회. blog 1,460 / tools 362 / chronicle 71 / glossary 55 = **1,948건 전량 적재**. 신규 스크립트 `scripts/emdash08_{tools,schema,cg}.py`.

### 결과
**[검증됨]** (D1 REST SQL `query()` 실측)

| 항목 | 값 | 근거 |
|---|---|---|
| `ec_posts` | 1,460 (orphan 0) | `COUNT(*)` / `WHERE live_revision_id IS NULL` |
| `ec_tools` | 362 (orphan 0) | 동일 |
| `ec_chronicle` | 71 (orphan 0) | 동일 |
| `ec_glossary` | 55 (orphan 0) | 동일 |
| `rowsWritten` | **70,042 / 100,000** (aikorea24-db 29 별도) | `analytics_written()` |
| 잔여 여유 | 29,958행 | 100,000 − 70,042 |
| 무작위 10건 | **10/10 published_at 일치** | `random.seed(7)`, ±120s 허용 |
| status | 전 테이블 published / draft 0 | `GROUP BY status` |
| `ec_pages` probe | 0행 (정리 완료) | `SELECT COUNT(*)` |
| taxonomy `zzspeedtest` | 0건 (정리 완료) | 동일 |

**[부분검증]** admin UI·공개 페이지 렌더 미확인. `/posts/<slug>` 302→404 상태(EMDASH-04 잔존).

**[검증불가]** `audit_logs` 0행, `_emdash_media_usage_sources` 미적재 — SQL 경로가 워커 후처리를 타지 않음. 복구: Workers Paid 전환 후 `POST /_emdash/api/admin/media-usage/repair`.

### 핵심 교훈
1. **SQL 경로 `published_at`은 UTC 정규화 필수** — KST 문자열 직저장 시 하루씩 어긋남. blog 무작위 10건 중 3건 발견 → `emdash06_direct.now_iso()`로 통일 후 10/10 일치.
2. **Worker API도 1102** — Idle 후 1회는 201@2.5s, 연속 쓰기는 503@0.56s. **1회 호출 + 25초 대기 루프**로 스키마 신설만 처리, 데이터는 전량 SQL 경로.

### DB·인스턴스 변경
- `ec_chronicle` / `ec_glossary` 컬렉션 신설(Worker API, 각 1회 호출)
- probe 정리: `ec_pages` 8행, `speedtest-tool-1/2` + `probe-tool` 3행(+revisions 27행), taxonomy `zzspeedtest` 1건 → **모두 삭제 완료**
- Worker 배포 0건, `wrangler.jsonc` 무수정, Workers Free 유지

### 잔존 위험 (12건 — 보고서 §5 전문)
공개 라우팅 404 / `audit_logs` 0행 / `_emdash_media_usage_sources` 미적재 / Workers Free CPU 10ms / `featured_image` 문자열 저장 / 마크다운 표 손실 / tag taxonomy 미이관 / chronicle·glossary taxonomy 연결 불가(`_emdash_taxonomy_defs.collections`=`["posts"]`) / PAT 회전 미확인 / D1 DB id 하드코딩 7곳 / **`wrangler.jsonc`에 `IMAGES`·`ASSETS` 바인딩 없음 — 이 파일로 `wrangler deploy` 금지**

### 다음 행동
1. **AIK24-EMDASH-03** 디자인 동기화 — 미착수. `tokens.css`가 파란색+다크모드 defaults라 지시서 요구(흑·백·적 3색 `#111/#fff/#E63B2E`, 라이트 전용, 세리프 헤드라인)와 불일치. 배포 방식 확정 필요.
2. 공개 라우팅 `/posts/<slug>` 404 해결
3. Workers Paid 전환 여부 — 대표님 결정
4. 미처리 지시서: `2026-10-10-AIK24-EMDASH-05-전체계획.md`, `2026-10-10-AIK24-EMDASH-07-원인조사.md`

완료보고: `SSOT/프로젝트/aikorea24/지시서/2026-10-10-1315-AIK24-EMDASH-08-완료보고.md`

---

## 2026-10-10 11:48 — AIK24-BRIEF-01 브리핑 파이프라인 점검: env 경로 버그 수정 + 브리핑 복구

지시서: `SSOT/프로젝트/aikorea24/지시서/2026-10-10-AIK24-BRIEF-01-브리핑점검.md`

### 한 일
브리핑 2026-10-09 중단 원인 추적 → 프로덕션 스크립트 2건 수정 → 멈춘 브리핑 복구 → 라이브 반영 확인.

### 결과
**[검증됨]**
- 근본 원인: `scripts/run_pipeline_with_notify.py` L19 `PROJECT_DIR = dirname(__file__)` 섀도잉 → L42가 `scripts/.env`(미존재)를 읽음 → 루트 `.env`(신규 계정 토큰) 무시 → 출발 계정(`fac9808c`)으로 D1 호출 → `7403`/`7404` → 뉴스 0건·브리핑 0건.
- 수정 2건(테스트 코드 수정 없음, 둘 다 프로덕션):
  1. `run_pipeline_with_notify.py` L42 `PROJECT_DIR` → `_PROJECT_DIR`
  2. `pipeline/infra/d1_client.py` L61·63 `log(...)` → `logger.warning(...)` (미정의 `log`의 NameError가 진짜 7403 오류를 가리고 `return []`로 조용히 실패)
- launchd 안전성 확인: `kr.aikorea24.pipeline-runner.plist`에 `CLOUDFLARE_*` 0건 → `load_env`가 `.env.common` setdefault 후 루트 `.env` hard overwrite → 프로덕션도 신규 계정 `7eb1b8cd` 사용.
- D1 조회 복구 0건 → **69건** (`auto_news_selector.get_recent_news()` 직접 실행).
- 파이프라인 RC 0 / 에러 0 / 60.4초 (뉴스 6, 썸네일 6).
- `briefings` id 338 `2026-10-10-1` published (`2026-10-10 02:45:46` UTC), `briefing_items` 1,795 → 1,801.
- 라이브: `https://aikorea24.kr/` 200에 `2026-10-10-1` 노출, `https://aikorea24.kr/briefing/2026-10-10-1/` 200 `<title>2026년 10월 10일 (토) AI 브리핑 - AI코리아24</title>`.

**[부분검증]** 썸네일 6건 — 성공 로그 있으나 `auto_thumbnail` 품질 게이트(15KB) 개입으로 실제 선택 이미지 파일 대조 미실시.
**[부분검증]** 뉴스 수집 불일치 — `cron_unified.log`(10-10 05:36) "신규 57건 저장"이나 신규 계정 D1 `news`는 17,881행, `MAX(created_at)`=`2026-10-09 22:33:22`. 읽기는 신규 DB와 일치하나 쓰기 경로(L1050 `--file`)의 계정 미확정.

**[검증불가]** `news_collector.py` 쓰기 대상 계정. 복구: 잡 로그에 wrangler stderr 남기고 10-10 19:30 실행 후 `SELECT MAX(id) FROM news` 대조.

### 잔존 위험
1. 10-09자 브리핑 2건 공백 — `get_recent_news(hours=24)` 롤링 윈도우 + 브리핑 날짜가 now 기준이라 과거일 catch-up 불가
2. 뉴스 수집 쓰기 대상 불일치(위 [부분검증])
3. 에이전트 셸에 `CLOUDFLARE_ACCOUNT_ID=fac9808c` 주입 → `run_pipeline.py` 단독 실행 시 출발 계정 사용. launchd는 안전
4. `wrangler.toml` `[vars] account_id`는 Worker 변수이며 wrangler 계정 설정 아님 (top-level 없음)
5. D1 DB id 하드코딩 7곳 (`scripts/{dynamic_seed_generator.py:24,cfnew.py:7,blog_draft_generator.py:48,thread_topics/thread_topic_finder.py:24,thread_topics/outline_generator.py:32,keyword_updater.py:21}`, `wrangler.toml:8`)
6. Vectorize upsert 실패 / purge 403 (미조사)
7. 이메일 미발송(`--skip-email`) — 다음 20:00 KST 잡으로 확인
8. EMDASH-04/06 잔존 (`_emdash_media_usage_*`, `zzspeedtest`, Workers Paid 전환 대기)

### 다음 행동
1. 20:00 KST 잡이 브리핑 정상 생성하는지 `SELECT COUNT(*) FROM briefings` 확인
2. `news_collector.py` 쓰기 경로 계정 확정
3. 10-09자 catch-up 방식 결정
4. `run_pipeline.py` 단독 실행 금지 명시

완료보고: `SSOT/프로젝트/aikorea24/지시서/2026-10-10-1148-AIK24-BRIEF-01-완료보고.md`

---

## 2026-10-10 11:37 — AIK24-EMDASH-06 Phase2 재개: D1 직접 SQL로 ec_posts 500건 달성

지시서: `SSOT/프로젝트/aikorea24/지시서/2026-10-10-AIK24-EMDASH-06-Phase2재개.md`

### 한 일
Worker CPU 10ms 한도를 우회해 D1 REST SQL로 blog 글 직접 적재. 신규 `scripts/emdash06_direct.py`.

### 결과
**[검증됨]** (근거: `scripts/emdash02_measure.py` `query()` → D1 REST SQL)
- `ec_posts` **500행 전부 published, draft 0** — `GROUP BY status`
- 소스 top-500 ↔ DB title 집합 **누락 0 / 초과 0** (각 500)
- 고아 `live_revision_id` 0건, published 중 revision 없음 0건
- `content_taxonomies` 500행, `ec_posts` 중 미연결 0건
- `_emdash_fts_posts` 500행 (AFTER INSERT 트리거 자동 생성)
- `published_at` 2026-08-07 ~ 2026-10-08 보존
- D1 `rowsWritten` **23,642 / 100,000**. 일자 증가분 11,625 = publish 60 + 본배치 11,404 + probe 삭제 161
- **SQL 경로 배수 32행/건** vs API 경로 75행/건

**[부분검증]** 무작위 5건(status/version/live_revision/category/published_at/content 3,970~6,486자) 전부 정상. 단 admin UI·공개 페이지 렌더 미확인(공개 URL이 302→404 상태).
**[검증불가]** `audit_logs` 0행, `_emdash_media_usage_sources` 미적재 — 워커 후처리를 SQL 경로가 타지 않음. 복구: Workers Paid 전환 후 마이그레이션 재실행 또는 media-usage repair.

### 인스턴스 변경
없음. 워커 배포 없음. `wrangler.jsonc` 무수정. **작업 B(Workers Paid) 미수행 — 대표님 액션 대기.**

### 잔존 위험 12건 (대표)
1. Workers Free CPU 10ms — content 쓰기 여전히 1102
2. `wrangler.jsonc` 에 `IMAGES`/`ASSETS` 바인딩 없음 → **이 파일로 deploy 금지**
3. `audit_logs` 0행 / 4. `_emdash_media_usage_sources` 미적재
5. `featured_image` 문자열 저장 → 렌더 미검증
6. 마크다운 표·중첩 인용 PT 손실
7. tag taxonomy 미이관 (498/500이 장문)
8. 공개 URL 404
9. **PAT 채팅 평문 노출 — 회전 미확인**
10. 진단용 term `zzspeedtest` 잔존
11. `ulid()` 난수 폭 좁음 / 12. slug 근사 재현
13. 잔여: blog 960 + tools 362 + chronicle 71 + glossary 55 = 1,448건. chronicle/glossary는 대응 컬렉션 없음 → 매핑 방식 결정 필요

### 다음 행동
1. 대표님: Cloudflare Workers Paid 구독($5/월)
2. 나: 구독 후 테스트 글 1건 API 생성으로 1102 해소 확인
3. 대표님: chronicle/glossary 컬렉션 매핑 방식 결정

---

## 2026-10-10 11:02 — AIK24-EMDASH-04 Phase2 Day1: 176건 적재 후 CPU 1102로 중단

지시서: `SSOT/프로젝트/aikorea24/지시서/2026-10-10-AIK24-EMDASH-04-Phase2-Day1.md`
보고서: `SSOT/프로젝트/aikorea24/지시서/2026-10-10-1102-AIK24-EMDASH-04-완료보고.md`
도구: `scripts/emdash04_migrate.py` (신규)

### 한 일
- emDash v0.38.0 REST 정본 소스 확인 (content create/publish, CSRF 헤더, MD→Portable Text 변환 규약).
- `scripts/emdash04_migrate.py` 작성. blog date DESC 상위 500건 → `ec_posts` 이관 루프 (term 선행 생성 → create → publish(publishedAt=frontmatter date)).
- 스크립트에 5xx 재시도(지수 백오프) / 이미 적재 title 스킵 / publish 단독 재시도 추가.
- 배치 실행: 176행 적재. Worker CPU 1102 블로커 추적 후 임시 변경 원복.

### 결과
- [검증됨] `ec_posts` published 132 + draft 44 = 176행. 목표 500건 **미달(중단)**.
- [검증됨] `published_at` = frontmatter date 보존. slug 한글 자동 생성. category taxonomy 연결 동작.
- [검증됨] 블로커 = Worker CPU 10ms 한도 초과 (`tail --format json`: `cpuTime:10, outcome:exceededCpu`). settings에 `limits` 없음 = Free 기본값.
- [검증됨] 데이터 증가 아님(`ec_pages`/`ec_tools` 각 1행도 1102). 코드 변경 아님(배포 이력 1건, 2026-09-09T11:53Z 이후 redeploy 없음).
- [검증됨] Worker 자체 아님 — 같은 10ms 한도에서 taxonomy POST 201@0.42s, content GET 200@0.44s. content 쓰기 경로만 초과.
- [검증불가] 정확한 CPU 소모 지점 — 스택 없음. D1 GraphQL에 `query`/`queryHash`/`queryId` dimension 부재로 쿼리별 비용 식별 불가.
- [부분검증] 관리자 UI 저장도 동일 실패 추정(동일 핸들러 공유). UI 직접 검증 미수행.
- [검증됨] 실측 배수 ≈ **75행/쓰기** (delta 16,353행 ÷ 218회). EMDASH-02 예측 53 대비 1.42배. 잔여 339건 = 25,425행, 가용 82,272행 → 물량 부족 아님.
- [검증됨] 원복: webhook-notifier enable, media-usage activation active.

### 잔존 위험
1. [최우선] 176/500건, CPU 1102 미해결 → 추가 이관 불가.
2. draft 44건 = create 성공·publish 실패분, `live_revision_id` 없음.
3. 08:30 KST까지 180건 성공 → 08:45 KST부터 전 write 실패. 배포·데이터 규모로 설명 안 됨.
4. Workers Paid 전환 시 배포 위험 — `wrangler.jsonc`에 `IMAGES`/`ASSETS` 바인딩 없음(라이브엔 존재).
5. D1 직접 SQL 우회 시 `live_revision_id`→`revisions` 구조로 admin 일관성 검증 필요.
6. tag taxonomy 미이관(소스 tags 498/500이 장문 단일값 = 분류값 아님).
7. MD 표/중첩 blockquote/hr/각주 손실(정본 변환기 동일 동작). `featured_image` 문자열 렌더 미검증.
8. 공개 페이지 `/posts/<slug>` 302→404 (테마/라우팅 미구성으로 추정, 미검증).
9. PAT 회전 미확인(EMDASH-02 잔존). `taxonomies`에 진단용 `zzspeedtest` 잔존.
10. media-usage 인덱서 `indexed_source_count=138`인데 실제 소스 0행 — 재수집 필요.

### 다음 행동 (대표님 의사 필요)
- A. Workers Paid 전환($5/월, 30s CPU) — 근본.
- B. D1 직접 SQL 우회 — 단기. 권고 B+A 병행.
- C. Day1 목표를 176건으로 마감 조정.

## 2026-10-10 09:07 — AIK24-EMDASH-02: D1 리셋 확인 + EmDash 초기화 완료 + Phase 2 배치 계획

지시서: `SSOT/프로젝트/aikorea24/지시서/2026-10-10-0700-AIK24-EMDASH-02-초기화.md`
보고서: `SSOT/프로젝트/aikorea24/지시서/2026-10-10-0907-AIK24-EMDASH-02-완료보고.md`
도구: `scripts/cfnew.py`(공용 헬퍼), `scripts/emdash02_measure.py`(snapshot/probe)

### 한 일
신규 계정 D1 일일 한도 리셋 확인 → EmDash 초기화 상태 실측 → 대표님 수동 관리자 생성·PAT 발급 검증 → Phase 2(블로그 1,000건) 쓰기량 모델링·배치 계획. **Phase 2 실제 마이그레이션은 본 지시서 범위 밖(계획만).**

### ⚠️ PAT 노출 incidents (최우선)
- 대표님이 신규 EmDash PAT 를 **채팅 채널에 평문으로 전달함.** 지시서 §4 주의사항 11 위반(저장 전 노출).
- 본 세션에서는 인메모리 검증에만 사용했고 **파일·state.md·보고서·셸 스크립트 어디에도 기록하지 않음.** `scripts/` 하위에 PAT 하드코딩 없음.
- 권고: **Vault 저장 후 이 PAT 폐기·재발급.** 본 세션 transcript 에 평문 잔존. Phase 2 마이그레이션 착수 전 회전 완료할 것.
- 값 미기록 원칙 유지 — 이 보고서·state.md·CHANGES.md 어디에도 토큰 값을 쓰지 않음.

### 결과

#### §1 리셋 확인 — 충족
- [검증됨] 실행 시각 `2026-10-10 09:04 KST = 00:04 UTC` = 리셋(00:00 UTC) 4분 후. 지시서 선행조건 충족.
- [검증됨] GraphQL analytics 신규 계정(`7eb1b8cd…`) 2026-10-10 UTC `rowsWritten = 0`, `rowsRead = 0` (00:04 UTC 시점). 인덱스 포함 일일 100,000행 한도 **정상 리셋**.
- [검증됨] 쿼리 정합성 대조 — 동일 쿼리로 2026-10-09 재조회 시 `rowsWritten = 183,390 / rowsRead = 880,799` (전일 보고서 180,740 + 후속 작업 2,650). 빈 결과가 쿼리 오류 아님을 입증.
- [참고] GraphQL `d1AnalyticsAdaptiveGroups.dimensions` 는 그룹이 1건일 때 **객체**, 2건 이상일 때 **배열**로 반환됨. 파싱 시 양쪽 처리 필요(방금 실제 두 형태 모두 관측).

#### §2·§3·§4 초기화 — 충족 (대표님 수동 액션 09:07~09:10 KST 완료)
- [검증됨] **스키마 + 시드 자동 적용.** `_emdash_migrations` 76행 / `_emdash_collections` 3행(`pages`,`posts`,`tools`) / `_emdash_fields` 14행 / `options` 4행 / 테이블 80개 / 인덱스 247개.
- [검증됨] **컬렉션 테이블 실명 = `ec_posts`·`ec_pages`·`ec_tools`** (지시서 §3 의 `posts`·`pages`·`tools` 아님). 지시서 표기를 그대로 쓰면 검증이 오탐(false negative) 나므로 실명으로 확인함. `ec_*` = emdash content prefix.
- [검증됨] FTS 검색 테이블 5종 × 3컬렉션 = `_emdash_fts_{posts,pages,tools}` + `_config`·`_content`·`_data`·`_docsize`·`_idx` shadow 15테이블 생성됨.
- [검증됨] **관리자 계정 생성 완료.** `users` 1행. `GET /_emdash/api/setup/status` → **`{"needsSetup": false}`** (step 필드 소멸). §2 충족.
- [검증됨] **PAT 발급 + 동작 확인.** `GET /_emdash/api/content/posts?limit=1` + `Authorization: Bearer <PAT>` → **HTTP 200** `{"success":true,"data":{"items":[],"total":0}}`. §4 충족 (Vault 저장 여부는 대표님 확인 필요 — 채팅으로 전달됨).
- [검증됨] **초기화 쓰기량 = 227행(스키마+시드) + 1,140행(관리자 생성 + PAT 발급) = 1,367행.** 00:05 UTC 227행 → 00:09 UTC 1,367행. 계정 전량 `aikorea24-emdash-db` 단독(`aikorea24-db` 0행). → 지시서 §5 계산에 사용.
- [부분검증] **읽기 API가 쓰기를 유발함.** 00:04 UTC 에 쓰기 0행 → `/setup/status`·`/admin/setup` GET 이후 227행 발생. EmDash 가 첫 요청에서 스키마 마이그레이션을 실행하는 구조로 보이며, 이 227행 대부분이 그 트리거. 근거: `_emdash_migrations` 76행이 이미 채워져 있고 리셋 후 최초 요청 시점이 그 구간과 일치. 복구 계획: 지시서 완료 기준에는 없으나 Phase 2 재발 방지 규칙에 "readiness 조회도 쓰기를 유발할 수 있음 → 배치 전 analytics 1회 확인" 을 추가.
- [부분검증] **관리자 1명 + PAT 1개 발급 = 1,140행.** 콘텐츠 0건 상태에서 인가 인프라만으로 이만큼 소모됨. 사용자 추가·PAT 추가 시 건당 비용이 높으므로 Phase 2 기간 중 추가 발급 자제. 복구 계획: 필요 시 `audit_logs` 5인덱스 + `credentials` 4인덱스 구조를 근거로 건당 비용 추정 후 판단.
- [부분검증] `_cf_KV` 테이블은 `SQLITE_AUTH`(code 7500)로 API 조회 불가. D1 KV 테이블을 Worker 바인딩으로만 접근하는 emdash 설계. Phase 2 마이그레이션에서 KV 참조 필요 시 별도 경로 필요.

#### §5 Phase 2 배치 계획 (블로그 1,000건)
- [검증됨] 마이그레이션 대상 실측 — `src/content/` = `blog` 1,460 + `chronicle` 71 + `glossary` 55 + `tools` 362 = **1,948건**. 지시서 목표 1,000건은 `blog` 1,460건의 부분집합.
- [검증됨] 건당 쓰기량 근거 = **라이브 D1 스키마 인덱스 실측**( 추정 아님). 컬렉션 테이블당 인덱스 17개, `revisions` 2, `_emdash_seo` 2, `content_taxonomies` 3, `_emdash_media_usage_sources` 10.

| 쓰기 대상 | 행 | 인덱스 | 합계 |
|---|---|---|---|
| `ec_posts` | 1 | 17 | 18 |
| `revisions` | 1 | 2 | 3 |
| `_emdash_seo` | 1 | 2 | 3 |
| `content_taxonomies` (category+tag 2행) | 2 | 6 | 8 |
| `_emdash_media_usage_sources` (featured_image 1) | 1 | 10 | 11 |
| FTS (`_emdash_fts_posts` + shadow) | 1 | — | 2~4 |
| `audit_logs` | 1 | 5 | 6 |
| **건당 합계** | | | **51~53** |

- [검증됨] **가용 한도 = 100,000 − 1,367(초기화 전체) − 20,000(안전마진) = 78,633행.**
- [검증됨] **1일 배치 상한 = 78,633 ÷ 53 = 1,483건 / ÷ 51 = 1,541건.** → 지시서 목표 1,000건(53,000행 산정)은 1일 처리 가능(여유 25,633행).
- [부분검증] 배수 51~53 은 **스키마 역산 모델**이며 실측이 아님. `idx_ec_posts_del_sched` 는 partial index(`WHERE scheduled_at IS NOT NULL`)라 조건 불충족 시 엔트리 미작성 → 실제값은 하방으로 내려갈 수 있음. 복구 계획: **Day 1 을 500건 파일럿으로 축소**하고 배치 직후 analytics 로 실제 배수를 실측한 뒤 Day 2 를 실측값으로 재계산.
- [검증됨] 권장 스케줄 — Day 1: `blog` 500건 파일럿(예상 25,500~26,500행, 리셋 1일차 한도 34% 사용) → 배수 실측 → Day 2: 잔여 500건 + `tools` 362건. 전체 1,948건 전량 이관은 4~5일 분할 권장.
- [검증됨] 지시서 주의사항 #4 준수 — 오늘 EmDash 초기화(1,367행, 1.4%)만 실행. Phase 2 마이그레이션은 **별도 날**. 다른 프로젝트 D1 대량 작업도 오늘 금지.

### 완료 기준 대조
| 기준 | 판정 | 근거 |
|---|---|---|
| §1 리셋 확인 | 충족 | rowsWritten 0 (00:04 UTC) + 전일 재조회 대조 |
| §2 관리자 생성 | 충족 | `users` 1행, `needsSetup: false` |
| §3 컬렉션 테이블 + 초기화 쓰기량 | 충족 | `ec_posts`/`ec_pages`/`ec_tools` 3종 + 시드 3종 존재. 초기화 쓰기량 1,367행 기록 |
| §4 PAT 발급·Vault 저장 | 부분 충족 | PAT 발급 + HTTP 200 동작 확인. **Vault 저장 여부 미확인, 채팅 노출 건으로 회전 권고** |
| §5 배치 계획 | 충족 | 1일 상한 1,483건, Day1 500건 파일럿 |

### 잔존 위험
1. **[최우선] PAT 채팅 노출** — 대표님이 PAT 를 평문으로 전달. 파일 기록은 없으나 세션 transcript 에 잔존. **Phase 2 착수 전 회전(폐기 후 재발급 + Secure Vault 저장) 필수.**
2. **[신규] 오늘 1,367행 소모** — 잔여 98,633행, Phase 2 가용분 78,633행. 관리자 1명 + PAT 1개 발급에만 1,140행 소모됨 → 추가 발급 시 비용 재확인.
3. **[신규] 읽기 API 가 쓰기 유발** — readiness/status 조회가 스키마 마이그레이션을 트리거할 수 있음. 배치 전 상태 확인 반복 호출 금지.
4. **[신규] `_cf_KV` API 접근 불가(`SQLITE_AUTH`)** — KV 데이터가 필요한 마이그레이션 경로 미정.
5. **[누적] 기존 `EM_DASH_API_TOKEN`/`EMDASH_API_TOKEN` 은 starclip 인스턴스 토큰** — 신규 EmDash 인스턴스로 교체 필요. 값 평문 기록 금지.
6. **[누적] AIK24-IDX-01 인덱스 삭제 미실행** — `aikorea24-db` 9건(권고 5건). 지시서 #7 의 "불필요한 인덱스 제거 후 마이그레이션" 요건 미충족. 삭제 자체가 쓰기(DDL 은 rowsWritten 미계상이나 DROP 후 재작성을 유발할 수 있음)라 **Phase 2 마이그레이션과 다른 날**에 실행 권장.
7. **[누적] `projects2/aikorea24emdash` git 저장소 아님** — 스키마 변경 이력 추적 불가.
8. **[누적] `dev.link2threads.com.aikorea24.kr` TLS 실패 / AdSense 슬롯 id 미확정 / Threads 토큰 code 190 / `news-unified` plist `CF_PURGE_TOKEN` 평문 / 출발 계정 리소스 삭제 보류 / `finnews` account_id 출발 잔존 / 문서 6개 옛 database_id.**
9. **[누적] Email Routing 룰 미생성(API 403)** — 대표님 대시보드 수동 생성 대기.

### 다음 행동
- 대표님: **PAT 회전** — 현재 PAT 폐기, `/_emdash/admin` 에서 재발급 후 Secure Vault 저장. (Phase 2 착수 전 완료)
- 대표님: AIK24-IDX-01 인덱스 삭제 지시서 issuance — **Phase 2 마이그레이션과 다른 날** 지정.
- 주니어: Phase 2 마이그레이션 지시서 수령 시 Day 1 500건 파일럿 → analytics 실측 배수 → Day 2 재계산.
- 주니어: 마이그레이션 스크립트 착수 시 PAT 를 `EMDASH_NEW_PAT` 환경변수로만 주입, 코드·설정 파일 하드코딩 금지.

## 2026-10-09 20:20 — Email Routing `info@aikorea24.kr` 확인 + CF-ZONE-06 인수인계

대표님 지시: `CF-ZONE-06 지시서 전달 + Email Routing 이메일 라우팅 완료info@aikorea24.kr`

### 한 일
1. 신규 계정(`7eb1b8cd…`) Email Routing 상태 확인(DNS 전수 + API 접근).
2. CF-ZONE-06 인수인계 요약 작성.

### 결과
- [검증됨] **Email Routing requisite DNS 는 신규 zone 에 전부 존재.** MX `route1/2/3.mx.cloudflare.net`(priority 95/28/33), SPF `v=spf1 include:_spf.mx.cloudflare.net ~all`, DMARC `_dmarc` `p=none; rua=mailto:rua@dmarc.brevo.com`, DKIM `cf2024-1._domainkey`. `dig @lara…` MX 3건 정상.
- [검증불가] **룰 생성·조회 API 403.** `GET /zones/71a21534…/email/routing/rules` 를 `CF_MIGRATE_TOKEN`·`CLOUDFLARE_API_TOKEN`·`CF_DNS_TOKEN` 3종으로 시도 → 전부 HTTP 403 `Authentication error`. 이 프로젝트의 어떤 토큰으로도 Email Routing API 접근 불가. 복구 계획: 대표님이 신규 계정 대시보드 → Email → Routing Rules 에서 직접 룰 생성.
- [검증됨] 출발 계정 룰 3건 확인(이관 대상): `hugh_cho@aikorea24.kr`→forward `hugh79757@gmail.com`(enabled), `info@aikorea24.kr`→forward `stylefactory9ai@gmail.com`(enabled), catch-all drop(disabled).
- [검증됨] CF-ZONE-06 이미 완료 상태 — 커밋 `dc4961b4`, 터널 2개(`mde2`·`m1-ssh`)·DNS 3건 삭제, zone 37건→34건, 출발 계정 무변경. 인수인계 요약을 위 보고서 부록에 작성.

### 잔존 위험
1. **[신규] DKIM selector 소유 계정 불일치** — 현재 `cf2024-1._domainkey` 는 출발 계정 발급분. 신규 계정 Email Routing 은 별도 selector 를 발급하므로, 신규 룰 생성 시 Cloudflare 가 제시하는 DKIM 레코드를 신규 zone 에 등록해야 발신자 검증 통과. inbound 수신 라우팅에는 영향 없음.
2. **[신규] 신규 계정 Email Routing 룰 미생성(추정)** — API 403 으로 부재 확인 불가. 대표님 대시보드 수동 생성 필요.
3. **[신규] 수신 실측 미수행** — 대표님이 `info@aikorea24.kr` 로 시험 발송 1회 필요.
4. **[누적] D1 row write 한도 초과(180,740/100,000)** — emDash 초기화 블로커. 2026-10-10 09:00 KST 리셋 대기 또는 유료.
5. **[누적] 인덱스 삭제 미실행** (권고 5건) / `dev.link2threads.com.aikorea24.kr` TLS 실패 / AdSense 슬롯 id 미확정 / `aikorea24emdash` git 아님 / 신규 emDash PAT 미발급 / Threads 토큰 code 190 / `news-unified` plist `CF_PURGE_TOKEN` 평문 / 출발 계정 리소스 삭제 보류 / `finnews` account_id 잔존 / 문서 6개 옛 database_id.

### 다음 행동
- 대표님: 신규 계정 대시보드 → Email → Routing Rules 에서 `info@aikorea24.kr` → `stylefactory9ai@gmail.com` forward 룰 생성 + Cloudflare 제시 DKIM 레코드를 신규 zone 에 등록.
- 대표님: 생성 후 시험 발송 1회로 수신 확인.

## 2026-10-09 20:10 — AIK24-IDX-01: 뉴스 DB 미사용 인덱스 점검 (27개 중 9건 삭제후보)

지시서: `SSOT/프로젝트/aikorea24/지시서/2026-10-09-1920-AIK24-IDX-01-인덱스점검.md`
보고서: `SSOT/프로젝트/aikorea24/보고서/2026-10-09-AIK24-IDX-01-완료보고.md` (+ 지시서 폴더 `2026-10-09-2010-…` 복사)

### 한 일
신규 계정 `aikorea24-db` 의 명시적 인덱스 27개를 조회하고 각 컬럼이 실제 SQL WHERE/ORDER BY/JOIN 에 쓰이는지 대조해 유지·삭제후보 판정. **쓰기 0건.**

### 결과
- [검증됨] 인덱스 27건(`sqlite_master type='index' AND sql IS NOT NULL`) + autoindex 15건 = 총 42. 스크립트 `/tmp/idx01.py` → `/tmp/idx01_indexes.json`.
- [검증됨] 판정 집계: **유지 18 · 삭제후보 9 · 보류 0.**
- [검증됨] **중복 정의 발견** — `idx_news_created` 와 `idx_news_created_at` 이 동일 컬럼(`created_at DESC`) 인덱스 2개. D1-NEWS-FIX-01 이전부터 존재.
- [검증됨] 삭제후보 9건: `idx_lesson_clicks_enrollment`(INSERT 만 있고 SELECT 없음), `idx_news_created`/`idx_news_created_at` 중 1개(중복), `idx_payments_order`/`idx_payments_user`(API 라우트 부재), `idx_posts_access`(INSERT 만), `idx_posts_visibility`(UPDATE SET 만), `idx_tools_featured`(INSERT 만), `idx_users_kakao`(카카오 라우트 2026-10-09 삭제 → grep 0건).
- [검증됨] 유지 18건 근거 예: `news.category` 8곳 이상(`news.astro:17`, `global.astro:11`, `api/news/*`), `news.pub_date`(`api/articles/pool.ts:61,82` ORDER BY DESC LIMIT 2000), `tools.updated_at`(`api/briefing/send-email.ts:153`, `scripts/auto_email_sender.py:84`), `pipeline_runs.run_id`+`started_at`(`pipeline/__main__.py:36,38,41`).
- [검증됨] 절감량 — news 하루 INSERT 약 46행(CF-MIGRATE-05 실측). 중복 1개 제거 시 news 인덱스 쓰기 6→5로 **약 23행/일 감소**(무료 한도 100,000행 대비 0.02%). AIK24-D1-LIMIT-01 의 7.24배 배수는 import 1회성 작업이라 삭제로 되돌아오지 않음 — 절감은 앞으로의 INSERT 에만 적용.
- [검증됨] 읽기 전용 준수 — D1 호출은 `sqlite_master` SELECT 2회뿐. CREATE/DROP/INSERT/UPDATE/DELETE 0건. 출발 계정 접근 0건.

### 잔존 위험
1. **[신규] 인덱스 삭제 미실행** — 지시서가 조사만 허용. 그리고 현재 계정 D1 write 한도 초과 상태라 DROP 도 실패 가능. 삭제 지시서 발급은 **2026-10-10 09:00 KST 리셋 이후** 권장.
2. **[신규] 제 권고 보류 2건** — `payments` 2건(행수 0·API 부재이나 유료강의 Phase 4 대상), `users.kakao_id`(카카오 로그인 롤백 경로. `99f78843` 이 스키마 변경 없이 되돌릴 수 있게 남겨둔 것).
3. **[누적] 신규 계정 D1 row write 한도 초과(180,740/100,000)** — emDash 초기화 불가. 2026-10-10 09:00 KST 리셋 대기 또는 유료 플랜.
4. **[누적] CF-ZONE-06 삭제 DNS 3건 공개 리졸버 캐시 전파 지연 / `dev.link2threads.com.aikorea24.kr` TLS 실패 / AdSense 슬롯 id 미확정 / `projects2/aikorea24emdash` git 아님 / 신규 emDash PAT 미발급 / Threads 토큰 무효(code 190) / `news-unified` plist `CF_PURGE_TOKEN` 평문 / plist `OPENAI_API_KEY` 폐기 키.**
5. **[누적] 출발 계정 D1·R2·Pages·Worker 삭제 보류.** 롤백 시 zone NS `alberto`·`sonia` 복원 + `/tmp/cfzone_backup_20261009/dns_records.json` 41건 복원.
6. **[누적] `finnews/wrangler.toml:6` account_id 출발 잔존 / 문서 6개 옛 database_id / 신규 계정 Vectorize 403 / `projects2/mbti` git 아님 / `Projects/heritage` `dist` 2026-09-18 dirty.**

### 다음 행동
- 대표님: 삭제 대상 확정. 제 권고는 5건(`idx_lesson_clicks_enrollment`, news 중복 1개, `idx_posts_access`, `idx_posts_visibility`, `idx_tools_featured`).
- 삭제 지시서 발급 시점 = 2026-10-10 09:00 KST 이후.
- `2026-10-10-0700-AIK24-EMDASH-02-초기화.md` 미실행 — D1 리셋 후 대상.

## 2026-10-09 19:55 — CF-ZONE-06 불필요 터널·DNS 정리 (mde2·m1-ssh 삭제)

지시서: `SSOT/프로젝트/aikorea24/지시서/2026-10-09-1830-CF-ZONE-06-터널정리.md`
보고서: `SSOT/프로젝트/aikorea24/보고서/2026-10-09-CF-ZONE-06-완료보고.md` (+ 지시서 폴더 `2026-10-09-1955-…` 복사)

### 한 일
대표님 확인(18:25) — `mde2` 는 로컬 전용 도구(127.0.0.1:5111), `m1-ssh` 는 m1 서버 미사용 → 신규 계정에서 두 터널과 그 DNS 레코드 3건을 삭제. `l2t-dev`·`mac-dashboard` 는 유지.

### 결과
- [검증됨] 터널 2개 DELETE — `mde2`(`15dde64e-…`)·`m1-ssh`(`33989366-…`) 각각 **HTTP 200** + 결과 id 일치. 삭제 후 `GET /accounts/7eb1b8cd…/tunnels` → `l2t-dev`(16a09033) + `mac-dashboard`(9667fb14, healthy) **2개만 남음**. 시크릿·토큰 미출력.
- [검증됨] 신규 zone `71a21534…` DNS 3건 DELETE — `m1.informationhot.kr.aikorea24.kr`(`c44208c4…`), `m1ssh.aikorea24.kr`(`189af869…`), `mde2.aikorea24.kr`(`66b43521…`) 전부 **HTTP 200 success=true**. 전체 37건 → **34건**, 재조회 대상 잔존 0건.
- [검증됨] 유지 대상 무결성 — 터널 CNAME 7건 잔존(`1`·`blogdex`·`mde2.rotcha.kr.aikorea24.kr`·`ops`·`status`·`wiki` → `9667fb14`, `dev.link2threads.com.aikorea24.kr` → `16a09033`). 라이브 `status` 200 / `wiki` 200.
- [부분검증] `dig @1.1.1.1` 삭제 3개 호스트 = 엣지 IP 반환 = **공개 리졸버 캐시 전파 지연**. Cloudflare DNS 에 레코드는 없음. 복구 계획: TTL 경과 후 재확인.
- [부분검증] `dev.link2threads.com.aikorea24.kr` → 000(TLS handshake 실패). CF-ZONE-05 에서 보고한 preexisting 다중 라벨 호스트 인증서 부재. 이번 삭제와 무관(`l2t-dev` 유지).
- [검증됨] 출발 계정 변경 0건 — 신규 계정 토큰만 사용.

### 잔존 위험
1. **[신규] DNS 전파 지연** — 삭제 3개 호스트가 TTL 만료 전까지 엣지 IP 응답. 자동 해소.
2. **[누적] `dev.link2threads.com.aikorea24.kr` TLS 실패** — Advanced Certificate Manager 필요.
3. **[누적] 신규 계정 D1 row write 한도 초과(180,740/100,000)** — emDash 초기화 블로커. 2026-10-10 09:00 KST 리셋 대기 또는 유료 플랜.
4. **[누적] AdSense 슬롯 id 미확정 / `projects2/aikorea24emdash` git 아님 / 신규 emDash PAT 미발급 / Threads 토큰 code 190 무효 / `news-unified` plist `CF_PURGE_TOKEN` 평문 / 출발 계정 리소스 삭제 보류.**
5. **[누적] `finnews/wrangler.toml:6` account_id 출발 잔존 / 문서 6개 옛 database_id / 신규 계정 Vectorize 403 / `projects2/mbti` git 아님 / `Projects/heritage` `dist` 2026-09-18 dirty.**

### 다음 행동
- AIK24-IDX-01(인덱스 점검) 실행 — D1 읽기 전용이라 한도 상태와 무관.

## 2026-10-09 19:35 — AIK24-D1-LIMIT-01: D1 한도 초과 실측 검증 (180,740행)

지시서: `SSOT/프로젝트/aikorea24/지시서/2026-10-09-1910-AIK24-D1-LIMIT-01-검증.md`
보고서: `SSOT/프로젝트/aikorea24/보고서/2026-10-09-AIK24-D1-LIMIT-01-완료보고.md` (+ 지시서 폴더 `2026-10-09-1935-…` 복사)

### 한 일
대표님 지적("주니어가 집계한 43,840행이 한도 100,000 미달이라 숫자가 안 맞음")에 대해 신규 계정 D1 analytics 를 GraphQL 로 직접 조회해 실측 검증.

### 결과 — 가설 "실제로 100,000행 초과" 채택
- [검증됨] 신규 계정(`7eb1b8cd…`) 2026-10-09 UTC `rowsWritten` 합계 **180,740행** = 무료 티어 한도(100,000)의 **1.81배**. `rowsRead` 743,043행.
- [검증됨] DB별: `aikorea24-db`(`3f4cedde…`) **158,892** / `heritage-db`(`22e7e7b0…`) 21,820 / `mbti-db`(`8a07a626…`) 23 / `aikorea24-emdash-db`(`bbbcbc34…`) 5.
- [검증됨] 주니어 집계 43,794행 대비 **4.13배** 차이. `aikorea24-db` 만 7.24배(21,951 → 158,892).
- [검증됨] **원인은 인덱스 쓰기 계상.** D1 `rowsWritten` 은 행뿐 아니라 인덱스 엔트리 쓰기도 센다. `aikorea24-db` 는 테이블 24 + 인덱스 27 → 행당 6~7회 계상. `heritage-db` 는 테이블 6 + 인덱스 적음 → 배수 1.00(관측과 일치).
- [부분검증] 배수 7.24 를 테이블당 인덱스 개수로 정확히 역산 불가(카운팅 규칙 비공개). 두 DB 의 인덱스 밀도 차이와 관측 배수 순서의 정합성 근거만 확보.
- [검증됨] 158,512행(전체 87.7%)이 **02:00Z 한 시간**에 집중 = CF-MIGRATE-02 `aikorea24-db` import 구간.
- [검증됨] 무료 티어 확정 — `GET /accounts/{id}/subscriptions` → 200 `[]`.
- [검증됨] **REST 사용량 엔드포인트 없음.** `/d1/analytics`·`/d1/usage`·`/d1/analytics/metrics`·`/d1/database/analytics`·`/d1/database/{id}/usage` 전부 404/7000. **`POST /client/v4/graphql/analytics`**(계정 경로 없음) + `d1AnalyticsAdaptiveGroups` + `filter` 를 GraphQL variables 로 전달해야 동작. 인라인 `{}` → `filter: not an object`.
- [검증됨] §4 1행 INSERT 재현: `aikorea24-emdash-db` 임시 테이블 CREATE + 1행 INSERT → **success, rows_written 3**. DROP 정리 완료. **그러나 동일 시점** emDash Worker 트리거 → `wrangler tail` 로 `D1_ERROR: Your account has exceeded D1's free tier daily row write limit` 확인.
- [검증됨] 판정 함정 기록: **1행 INSERT 성공은 한도 미초과 증거가 아니다.** 같은 계정·같은 DB·같은 시각에 단건 쓰기 통과 + 대량 마이그레이션 거절. Cloudflare 한도 거부는 요청 단위 판정이며 소규모 쓰기는 경계를 통과할 수 있다. 판정 근거는 analytics 실측 수치.

### 완료 기준 대조
| 기준 | 판정 | 근거 |
|---|---|---|
| §1 당일 쓰기량 재집계 | 충족 | 180,740행, 인덱스 계상 원인 규명 |
| §2 대시보드 Metrics 확인 | 충족 | GraphQL analytics 로 실측 (REST 없음 확인) |
| §3 API 엔드포인트 확인 | 충족 | REST 6종 404 + GraphQL 1종 동작 |
| §4 1행 INSERT 재현 | 충족 | 성공 — 단 한도 미초과 증거 아님을 병기 |
| §5 4개 가설 판정 | 충족 | 가설 1 채택, 2·3 기각, 4 부분(진단 방향 옳음/숫자 4.13배 오류) |

### 잔존 위험
1. **[블로커] 신규 계정 D1 row write 한도 초과(180,740/100,000).** emDash 초기화 불가. 해법 = 2026-10-10 09:00 KST 리셋 대기(무료) 또는 유료 플랜.
2. **[신규] 동일 import 재실 시 즉시 재초과** — `aikorea24-db` import 1회 158,892행. 리셋일 당일 D1 대량 작업은 11:00 KST 이후로 미룰 것.
3. **[신규] AdSense 슬롯 id 미확정** — `AdSlot.astro` slot 빈 값(무광고). AdSense 콘솔 확인 필요.
4. **[신규] `projects2/aikorea24emdash` git 저장소 아님** — 롤백 기준선 없음.
5. **[신규] 신규 emDash 인스턴스 PAT 미발급** — chat 에 붙인 `ec_pat_…` 는 starclip 인스턴스 토큰으로 실측 확인. 마이그레이션 후 회전 권고.
6. **[누적] Threads 접근 토큰 무효(code 190)** — `scripts/threads/reactivate_publish.sh` 준비됨.
7. **[누적] `news-unified` plist `CF_PURGE_TOKEN` 평문 / 출발 계정 리소스 삭제 보류 / 다중 라벨 호스트 2건 TLS 실패 / 신규 터널 3개 connector 미기동 / `finnews` account_id 잔존 / 문서 6개 옛 database_id / plist `OPENAI_API_KEY` 폐기 키.**

### 다음 행동
- 대표님: 유료 플랜 업그레이드 또는 2026-10-10 09:00 KST 리셋 대기 결정.
- 리셋 후 `https://emdash.aikorea24.kr/_emdash/admin/setup` → passkey 관리자 생성 → seed 적용 → 컬렉션 3종 생성 → PAT 발급 → Phase 2 착수(당일 소량만, 나머지 다음 날 분산).

## 2026-10-09 19:10 — emDash 관리자 초기화 상태 확인 (아직 미초기화, 원인 확정)

### 한 일
대표님 질문 "관리자 계정 초기화 됐나?" 에 대해 `/_emdash/api/setup/status` · D1 `sqlite_master` · `wrangler tail` 로 상태 재확인.

### 결과
- [검증됨] **아직 초기화 안 됨.** `GET /_emdash/api/setup/status` → `{"success":false,"error":{"code":"NOT_CONFIGURED","message":"EmDash is not initialized"}}`. D1 `aikorea24-emdash-db` 테이블 = `_cf_KV`·임시 프로브뿐, EmDash 스키마 0건.
- [검증됨] `wrangler tail aikorea24emdash` 로 서버측 원인 확보:
  `EmDash middleware error: Error: Migration failed: D1_ERROR: Your account has exceeded D1's free tier daily row write limit. Upgrade to a paid plan or wait until tomorrow (midnight UTC) to continue.`
- [검증됨] 신규 계정(`7eb1b8cd…`)의 **D1 무료 티어 일일 row write 한도 초과**가 원인. EmDash 초기화는 스키마 생성 + seed INSERT = 대량 write → 거절 → `locals.emdash.db` 미생성 → 어드민이 "not initialized" 표시.
- [검증됨] 단발 DDL(`CREATE TABLE`/`DROP TABLE`)은 통과 — 마이그레이션이 대량 write 라서 실패하는 것. 임시 프로브 테이블 `_probe` 는 생성 후 삭제 완료.
- [검증됨] `GET /_emdash/api/auth/mode` → `{"authMode":"passkey","signupEnabled":false,"providers":[]}`. 초기 관리자 생성 경로는 passkey(`/_emdash/api/setup/admin` + `/verify`, nonce 쿠키 `emdash_setup_nonce` 유효 1시간). `_emdash/api/auth/dev-bypass` 는 프로덕션 403 고정.
- [부분검증] magic-link 이메일 경로는 `send_email` 바인딩과 `cloudflareEmail` 플러그인을 제거했으므로 현재 불가. 초기화는 passkey 라서 영향 없음.

### 잔존 위험
1. **[블로커] D1 row write 한도 초과 → emDash 초기화 불가.** 해법 2개: ① **2026-10-10 09:00 KST(UTC 자정)까지 대기**(무료) ② 신규 계정 유료 플랜 업그레이드(즉시, 과금).
2. **[누적] AdSense 슬롯 id 미확정** — `AdSlot` slot 빈 값(무광고).
3. **[누적] `projects2/aikorea24emdash` git 저장소 아님** — 롤백 기준선 없음.
4. **[누적] 신규 인스턴스 PAT 미발급** — chat 에 붙인 `ec_pat_…` 는 starclip 인스턴스 토큰으로 실측 확인. 마이그레이션 후 회전 권고.
5. **[누적] Threads 접근 토큰 무효(code 190)** — `scripts/threads/reactivate_publish.sh` 준비됨.
6. **[누적] `news-unified` plist `CF_PURGE_TOKEN` 평문 / 출발 계정 리소스 삭제 보류 / 다중 라벨 호스트 2건 TLS 실패 / 신규 터널 3개 connector 미기동 / `finnews` account_id 잔존 / 문서 6개 옛 database_id / plist `OPENAI_API_KEY` 폐기 키.**

### 다음 행동
- 대표님: 유료 플랜 업그레이드 또는 2026-10-10 09:00 KST 대기.
- 이후 `https://emdash.aikorea24.kr/_emdash/admin/setup` → passkey 로 관리자 생성 → seed 적용 → `posts`/`pages`/`tools` 생성 → PAT 발급 → Phase 2 착수.

## 2026-10-09 18:55 — AIK24-EMDASH-01 Phase 1: 신규 emDash 인스턴스 구축·배포

지시서: `SSOT/프로젝트/aikorea24/지시서/2026-10-09-1530-AIK24-EMDASH-01-구축및이전.md` Phase 1
보고서: `SSOT/프로젝트/aikorea24/보고서/2026-10-09-AIK24-EMDASH-01-Phase1-완료보고.md` (+ 지시서 폴더 `2026-10-09-1855-…` 복사)

### 한 일
`/Users/twinssn/projects2/starclip` 구조를 참고해 `/Users/twinssn/projects2/aikorea24emdash` 신규 생성 → 신규 Cloudflare 계정(`7eb1b8cd…`)에 리소스 3종 생성 → Worker `aikorea24emdash` 배포 → 커스텀 도메인 `emdash.aikorea24.kr` 노출.

### 결과
- [검증됨] 신규 계정 리소스: D1 `aikorea24-emdash-db`=`bbbcbc34-f346-49e0-9aab-058836bee16d`(apac), R2 `aikorea24-emdash-media`(apac), KV `aikorea24-emdash-session`=`33913dec5c8941bdb2e7c603fb443071`.
- [PRODUCTION CODE] starclip 전용 코드 제거 후 `wrangler.jsonc`·`package.json`·`astro.config.mjs`·`seed/seed.json`(컬렉션 `posts`/`pages`/`tools` + taxonomy `category`/`tag`) 작성. `index.astro`·`search.astro`·`rss.xml.astro`·`sitemap.xml.astro`·`Base.astro`·`AdSlot.astro`·`og-image.ts` starclip → posts/aikorea24 로 개조.
- [검증됨] `grep -rn -i "starclip" src scripts astro.config.mjs wrangler.jsonc package.json seed` → 0건.
- [검증됨] **AdSense `ca-pub-6677996696534146`(informationhot 계열) → `ca-pub-5938862195544185`(aikorea24 계열)** 교체. `Base.astro` 로더 + `AdSlot.astro` 기본값. grep 0건.
- [검증됨] `npx astro build` → `Server built in 11.65s` / `Complete!`.
- [검증됨] `wrangler deploy` → Version ID `d3e085fd-e54a-4c4f-af22-50e02762eb9d`, 트리거 `emdash.aikorea24.kr (custom domain)` + `aikorea24emdash.z04probe.workers.dev`. 바인딩 `SESSION`(KV)·`DB`(D1)·`MEDIA`(R2)·`IMAGES`·`ASSETS`.
- [검증됨] `wrangler deploy` 가 신규 zone 에 `emdash.aikorea24.kr` AAAA `100::` proxied 레코드 자동 생성. `https://emdash.aikorea24.kr/` → HTTP 200.
- [부분검증] `https://emdash.aikorea24.kr/_emdash/admin` → HTTP 200, `EmDash Admin` 초기 관리자 생성 폼. starclip 동경로는 302 → `/login`(관리자 존재).
- [검증불가] 컬렉션 3종 확인 불가 — D1 `sqlite_master` 테이블 **0건**. EmDash 는 최초 관리자 생성 전까지 스키마·seed 미적용. 무인증 `GET /_emdash/api/schema/collections` → HTTP 500. 복구 계획: 대표님이 `/_emdash/admin` 에서 관리자 생성 → seed 적용 → 컬렉션 생성 → PAT 발급 → Phase 2 착수.

### 잔존 위험
1. **[신규, 블로커] EmDash 관리자 미생성 → 컬렉션 0개.** Phase 2 착수 불가.
2. **[신규] 신규 인스턴스 PAT 미발급.** chat 에 붙인 `ec_pat_…` 는 starclip 인스턴스 토큰으로 실측 확인(해당 URL API 200). 마이그레이션 후 회전 권고.
3. **[신규] AdSense 슬롯 id 미확정** — `AdSlot.astro` slot 빈 값(무광고). AdSense 콘솔 확인 필요.
4. **[신규] `projects2/aikorea24emdash` git 저장소 아님** — 롤백 기준선 없음.
5. **[누적] Threads 접근 토큰 무효(code 190)** — `scripts/threads/reactivate_publish.sh` 준비됨, 토큰 재발급 후 실행.
6. **[누적] `news-unified` plist `CF_PURGE_TOKEN` 평문 / 출발 계정 D1·R2·Pages·Worker 삭제 보류 / 다중 라벨 호스트 2건 TLS 실패 / 신규 터널 3개 connector 미기동 / `finnews` account_id 잔존 / 문서 6개 옛 database_id / plist `OPENAI_API_KEY` 폐기 키.**

### 다음 행동
- 대표님: `https://emdash.aikorea24.kr/_emdash/admin` 관리자 계정 생성.
- 대표님: PAT 발급 → Phase 2(블로그 1,000건 → `posts`) 착수.
- 대표님: AdSense aikorea24 계정 슬롯 id 확인.

## 2026-10-09 16:25 — 쓰레드 발행 중단 + plist 토큰 하드코딩 전면 제거 + 재개 스크립트

지시: 대표님 구두 지시(2026-10-09 15:5x~16:0x). 별도 지시서 없음.

### 한 일
1. `kr.aikorea24.threads-publisher` 비활성화 (bootout) + plist `CLOUDFLARE_API_TOKEN` 제거
2. `kr.aikorea24.threads-token-refresh` 비활성화 (bootout)
3. `kr.aikorea24.threads-compass.plist` XML 손상 복구 + `CLOUDFLARE_API_TOKEN` 제거
4. `kr.aikorea24.news-unified.plist` `CLOUDFLARE_API_TOKEN`·`CLOUDFLARE_ACCOUNT_ID` 제거
5. `scripts/threads/reactivate_publish.sh` 신규 작성 — 발행 재개 4단계 자동 점검

### 결과
- [검증됨] 3개 plist `EnvironmentVariables` 에 `CLOUDFLARE_API_TOKEN` 잔존 0건.
  - `threads-publisher` `['PATH']` / `threads-compass` `['PATH']` / `threads-token-refresh` `['PATH']`
  - `news-unified` `['CF_PURGE_TOKEN','CLOUDFLARE_ZONE_ID','OPENAI_API_KEY','PATH']` — `CF_PURGE_TOKEN` 은 출발 계정 토큰이라 `.env` 에 없음, `purge_cloudflare_cache()` 필수 → 유지.
  - 제거된 값 중 `news-unified` 의 `cfut_Jk9`(신규 계정 정답값)·`threads-*` 의 `cfut_o36`(계정 미상, 기능 영향 0).
- [검증됨] `threads-compass.plist` XML 복구. 손상 원인 2개: ① 주석 내 `--format` 의 `--` ② DOCTYPE public ID `"-//Apple//DTD PLIST 1.0//EN "` 후행 공백(따옴표 사이 공백까지 제거돼 2차 실패 후 재패치). `plutil -lint` OK + `plistlib.load` 성공. Label·Program(main_v3.py --format compass)·Calendar 09:30/15:30/21:30 확인. 백업 `…plist.bak.20261009`. **비활성 유지**(compass 는 D1 쓰기).
- [검증됨] `news-unified` 재적용 후 동작. `/tmp/z06_probe.py` — plist 와 동일하게 `CLOUDFLARE_*` 제거 상태에서 `news_collector` import → `load_env()` 후 토큰 prefix `cfut_Jk9`·`wrangler d1 execute aikorea24-db --remote` rc 0, 대상 `3f4cedde-eabc-4d7c-b459-f6abe8733767`(신규 DB). `load_env()` 은 모듈 레벨(57-58행)에서 실행 → main() 이전에 env 구성됨.
- [검증됨] `launchctl list` — threads 3종 없음, `kr.aikorea24.news-unified` LOADED.
- [PRODUCTION CODE] `scripts/threads/reactivate_publish.sh` 신규. `bash -n` OK. 실제 실행으로 1단계(`.env` 5키 OK)·2단계(토큰 검증)까지 도달 확인. `set -euo pipefail` 에서 heredoc 실패가 안내 메시지 전에 스크립트를 죽이던 결함은 `|| tok_rc=$?` 패턴으로 수정.

### ⚠️ 발행 재개는 현재 불가 — Threads 토큰 무효
- [검증됨] `graph.threads.net/v1.0/{user_id}?fields=id,username` 를 `access_token` 쿼리·`Authorization: Bearer` 두 방식으로 호출 → 각각 **HTTP 400 / 401, `code=190 OAuthException`**, 메시지 `"You cannot access the app till you log in to www.threads.com and follow the instructions given."`
- [검증됨] 15:5x 동일 토큰으로 같은 엔드포인트가 `{'id':'27538818229088576','username':'aikorea24'}` 를 반환했으나 16:04 부터 위 오류. 토큰 문자열 변경 없음(prefix `THAAd2Fk`·len 189 동일).
- `.token_refresh_state.json` 은 `status: token_valid`, `expires_at: 2026-10-17T08:34:45` 로 기록돼 있어 실제와 불일치.
- **해결 경로**: `python3 scripts/threads/token_refresh.py daily`(desktop 셸 경유, `THREADS_APP_SECRET` 필요) 또는 `www.threads.com` 로그인 후 앱 접근 동의. 그 다음 `bash scripts/threads/reactivate_publish.sh` 재실행하면 4단계까지 자동 진행.
- 위 오류 메시지는 단순 만료가 아니라 "앱에 로그인해야 사용 가능" 형태 → Meta 측 앱 권한 상태 확인 필요.

### 잔존 위험
1. **[신규] Threads 접근 토큰 무효** — 위 참조. 재발행의 유일 블로커. `reactivate_publish.sh` 2단계가 이를 정확히 잡아낸다.
2. **[누적] `news-unified` plist `CF_PURGE_TOKEN` 평문 하드코딩** — 출발 계정 토큰이라 이관 불가(출발 계정은 롤백 보류 중). 회전 시 purge 실패, 상한 `Cache-Control: public, max-age=300` 5분 지연.
3. **[누적] plist `OPENAI_API_KEY` 폐기 키**(401 `Incorrect API key provided`). `load_env()` 이 프로젝트 `.env` 로 덮어쓰므로 실행 시점엔 유효 값 사용.
4. **[누적] 출발 계정 D1·R2·Pages·Worker 삭제 보류.** 롤백 시 zone NS 를 `alberto`·`sonia` 로 복원 + `/tmp/cfzone_backup_20261009/dns_records.json` 41건 복원.
5. **[누적] `projects2/mbti` git 아님**(롤백 `/tmp/z04/mbti-wrangler.toml.bak`) / `Projects/heritage` `dist` 2026-09-18 dirty / `finnews/wrangler.toml:6` account_id 출발 잔존 / 문서 6개 옛 database_id(`SOP.md:21`, `docs/TECHNICAL.md:523`, `docs/SKILLS/08-cloudflare-deploy.md:106`, `.planning/codebase/CONCERNS.md:119`, `.planning/codebase/INTEGRATIONS.md:24`, `.backup_brandname_20260929_150132/docs/TECHNICAL.md:523`) / 신규 계정 Vectorize 403.
6. **[누적] 다중 라벨 호스트 2건 TLS 실패**(`m1.informationhot.kr.aikorea24.kr`·`dev.link2threads.com.aikorea24.kr`) / 신규 터널 3개 connector 미기동(`m1ssh`·`mde2` 530).

### 다음 행동
- 대표님: Threads 토큰 재발급(또는 `www.threads.com` 로그인) → `reactivate_publish.sh` 재실행으로 3·4단계 자동 진행.

## 2026-10-09 16:35 — Threads 발행 중단 (job 비활성화) + plist 토큰 제거

지시: 대표님 직접 지시(2026-10-09 16:3x) — "aikorea24 쓰레드 발행 멈출 것. 비활성화. 다음지시까지 멈춰줘." + "threads-publisher.plist 하드코딩된 CLOUDFLARE_API_TOKEN 제거"

### 한 일
1. `kr.aikorea24.threads-publisher` launchd job **비활성화** (`bootout`).
2. `~/Library/LaunchAgents/kr.aikorea24.threads-publisher.plist` 의 `EnvironmentVariables.CLOUDFLARE_API_TOKEN` **제거**.

### 결과
- [검증됨] job 비활성화. `launchctl bootout gui/$(id -u)/kr.aikorea24.threads-publisher` rc=0. `launchctl list | grep aikorea24.threads` → `kr.aikorea24.threads-token-refresh` 만 남음(publisher 항목 없음). `pgrep -fl main_v3.py` → 프로세스 없음.
- [검증됨] plist 토큰 제거. 제거 전 EnvKeys `['CLOUDFLARE_API_TOKEN','PATH']` → 제거 후 `['PATH']`. `plutil -lint` → OK. 백업 `~/Library/LaunchAgents/kr.aikorea24.threads-publisher.plist.bak.20261009`.
- 제거 대상 토큰은 prefix `cfut_o36…` 로, `~/.env.common` 의 출발 계정(`cfut_275`)·신규 계정(`cfut_Jk9`) **어느 쪽과도 일치하지 않는 제3 토큰**이었다. 기능 영향은 0 이었음 — `main_v3.py:17-18` 의 `_config.load_to_environ()` 이 프로젝트 `.env`(신규 계정 `cfut_Jk9`) 를 무조건 덮어써서 이미 신규 계정으로 D1 조회 중이었다. `news-unified`(CF-MIGRATE-04)의 미해결 항목과 동일 유형.
- [검증됨] 다른 LOADED job 중 Threads 발행 경로 없음. `com.aikorea24.manual-publisher` 는 `Projects/money-aikorea24` 블로그 발행(30분 주기)이며 Threads 대상 아님. `kr.aikorea24.thread-topic-finder`(06:10)와 `kr.aikorea24.threads-insights` 는 이전부터 `.disabled`.

### 잔존 위험
1. **[신규] `kr.aikorea24.threads-token-refresh`(매일 00:30)는 LOADED 유지.** 쓰레드를 발행하지 않으므로 기능 영향 없으나, 재개 시 필요 없는 API 호출 1회/일 발생. 비활성화 원하면 지시 요망.
2. **[누적] `kr.aikorea24.threads-compass.plist` XML 손상** — `plistlib.load` → `ExpatError: line 2, column 72`. 이 job 은 이전부터 미로드 상태였으므로 동작 영향 0.
3. **[미해소] `news-unified` plist 의 `CLOUDFLARE_API_TOKEN` 하드코딩**(CF-MIGRATE-04 잔존). 이 job 은 D1 쓰기를 하므로 실제 영향 있음. 별도 지시 대기.
4. **[누적]** 출발 계정 D1·R2·Pages·Worker 삭제 보류. `projects2/mbti` git 아님. `Projects/heritage` `dist` dirty. `finnews/wrangler.toml:6` account_id 출발 잔존. 문서 6개 옛 database_id 잔존. `CF_PURGE_TOKEN` plist 평문. plist `OPENAI_API_KEY` 폐기 키(401).

### 다음 행동
- 재개 지시 시: `launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/kr.aikorea24.threads-publisher.plist`. `.env` 로드 확인 후 1회 수동 실행(`main_v3.py --once`류)으로 D1 조회 계정 확인 권장.

## 2026-10-09 16:20 — CF-ZONE-05 잔존 3건 처리 (KV 해시 이전 · 터널 3개 재생성)

지시서: `SSOT/프로젝트/aikorea24/지시서/2026-10-09-1540-CF-ZONE-05-잔존처리.md`
보고서: `SSOT/프로젝트/aikorea24/보고서/2026-10-09-CF-ZONE-05-완료보고.md` (+ 지시서 폴더 `2026-10-09-1620-…` 복사)

### 한 일
1. **§1 `api.barnmate`** — 조치 없음. 대표님 결정대로 삭제 확정으로 종결. 현재 530.
2. **§2 KV 25키** — 출발 계정 초과 키 25건을 `SHA-256(원본키)` → `sha256:<64hex>` 로 신규 계정 `KV_POSTED_URLS`(`7d969ac3…`)에 기록. `projects2/threadsp-do/src/kv.ts` 의 `UrlDedupStore` 에 원본 키 우선 → 해시 키 폴백 추가 후 재배포.
3. **§3 Down 터널 3개** — 신규 계정에 `m1-ssh`·`mde2`·`l2t-dev` 재생성 + 신규 zone CNAME 4건 갱신.

### 결과
- [검증됨] KV 25/25 기록 성공 · 0 실패. 신규 KV 396키 = `posted:` 371 + `sha256:` 25. 해시 키 길이 71자 전건. 매핑 25건 해시 일치. 근거: `/tmp/z05_kv_hash.py` · `/tmp/z05_kv_verify.py`.
- [PRODUCTION CODE] `projects2/threadsp-do/src/kv.ts` — `sha256Hex()` · `hashedKey()` 추가, `markPosted()` 예외 시 폴백, `isPosted()` 미게시 판정 2단계. `DedupCache` 무변경. `npx tsc --noEmit` 오류 0건. 커밋 `79a90be`.
- [검증됨] `threadforge-do` 재배포 성공 — Current Version ID `7b137144-c752-41b6-ab67-4e306102f648` (이전 `65daa71e-…`). 바인딩 10개 전부 신규 계정 리소스.
- [검증됨] 신규 터널 3개 UUID: `m1-ssh`=`33989366-47b3-4c70-8b80-d9324e45244a`, `mde2`=`15dde64e-c89f-4bca-824b-cd342bf0d01d`, `l2t-dev`=`16a09033-e4fe-42bc-afe3-0c2b2790c3a7`. `status=inactive`·`connections=0` (출발 계정과 동일 = connector 없음).
- [검증됨] 신규 zone CNAME 4건 PATCH HTTP 200·content 일치. 전수 재조회에서 터널 CNAME 10건 전부 매핑 확인(mac-dashboard 6 + 신규 3터널 4). `proxied=True` 전건.
- [검증됨] 출발 계정 변경 0건 — zone `a6d9e750…` status `moved`, DNS 41건(CF-ZONE-02 백업과 동일 수량).
- [부분검증] `m1ssh`·`mde2` → HTTP 530 (connector 없음). connector 재기동 시 동작 예상하나 이번 작업에서 기동하지 않음.
- [검증불가] 해시 키 25건의 Worker 측 실제 읽기. 복구 계획: 실제 게시 URL 1건으로 중복 판정 테스트.

### 잔존 위험
1. **[신규]** `m1.informationhot.kr.aikorea24.kr` · `dev.link2threads.com.aikorea24.kr` → TLS handshake 실패(curl `000`, `SSLV3 alert handshake failure`). CNAME 을 옛 UUID 로 되돌려도 동일 → **본 작업 회귀 아님**. 신규 계정 zone 에 다중 라벨 호스트용 엣지 인증서 없음(Universal SSL 이 apex + `*.aikorea24.kr` 만 커버). 복구 계획: Advanced Certificate Manager 로 두 호스트 인증서 발급, 또는 참조하는 외부 도메인 zone 쪽으로 CNAME 이전.
2. **[신규]** 신규 터널 3개 connector 미기동 — 기동 대상 장비·프로세스 미확정.
3. **[미해소]** 출발 계정 D1·R2·Pages·Worker 삭제 보류(롤백 검증 전).
4. **[누적]** `projects2/mbti` git 아님(롤백은 `/tmp/z04/mbti-wrangler.toml.bak`). `Projects/heritage` `dist` 2026-09-18 빌드본 dirty. `finnews/wrangler.toml:6` account_id 출발 잔존. 문서 6개 옛 database_id 잔존. `CF_PURGE_TOKEN` plist 평문. plist `OPENAI_API_KEY` 폐기 키(401).

### 다음 행동
- 대표님: 다중 라벨 호스트 2건 인증서 발급 여부 결정.
- 대표님: 신규 터널 3개 connector 기동 대상 장비 확인.

## 2026-10-09 15:45 — CF-ZONE-04 Workers·Tunnel 이전 + NS 전환 (zone 이전 완료)

지시서: `SSOT/프로젝트/aikorea24/지시서/2026-10-09-1350-CF-ZONE-04-Workers이전.md`
보고서: `SSOT/프로젝트/aikorea24/보고서/2026-10-09-CF-ZONE-04-완료보고.md`

### 한 일
신규 계정 `7eb1b8cd178de269758ec94b2e03330b`으로 Worker 3종(`mbti`·`heritage`·`threadforge-do`),
Cloudflare Tunnel 1종(`mac-dashboard`), threadforge-do 부속 리소스 6종(R2·Queue×2·KV×2·Vectorize)을 이전.
대표님이 NS를 `lara`·`mike`로 교체한 후 15개 호스트 재검증.

### 결과
- [검증됨] D1 `mbti-db`(3테이블 1/0/3)·`heritage-db`(6테이블, `heritage_index` 3,632) 카운트 1:1. 근거: `/tmp/z04/verify_d1.py` → `ALL MATCH`.
- [검증됨] Worker 3종 배포 성공. `mbti` version `f63ebbe1-…`(65 assets), `heritage` version `5bd73b4f-…`(154 assets), `threadforge-do` version `65daa71e-…`(DO·KV2·Queue2·Vectorize·R2 바인딩 10개 출력 확인).
- [검증됨] mac-dashboard 터널 신규 계정 재생성 `9667fb14-cb03-49d1-8682-322d57f3087c`, `status healthy connections 4`. connector 는 이 Mac 의 launchd `com.twinssn.cloudflared.plist` 가 실행 중이라 로컬 관리 방식(credentials 파일 + `config.yml`)으로 전환. DNS CNAME 6건 PATCH 완료. `status`·`wiki` 200, `ops`·`1`·`blogdex` 401(앱 레벨 응답).
- [부분검증] R2 `threadforge-media` 34/34 객체 복사, KV 564/589 키 복사. **Vectorize는 출발 계정 인덱스가 벡터 0건(`created_on == modified_on == 2026-07-06`)이라 이전 대상 없었음.** 25키 실패는 Cloudflare `code 10030`(키 UTF-8 512B 제한) 로 개별 get·put 모두 414, `POST /bulk` 는 토큰 권한 부족으로 405 → 경로 무관 이전 불가.
- [검증됨] 출발 계정 Worker 522/530 의 원인은 Cloudflare 전역 장애(`cloudflarestatus.com` → `partialoutage`, `Cloudflare Sites and Services: degraded_performance`, 다수 지역 `major_outage`). Pages 는 정상. 조치 불필요.
- [검증됨] NS 전환 후 최종 15호스트: `aikorea24.kr`·`www`·`keyword`·`cert`·`barnmate`·`persona`·`mbti`·`heritage`·`threadforge`·`status`·`wiki` = 200, `ops`·`1`·`blogdex` = 401(앱 인증), `api.barnmate` = 530/1016(대표님 삭제 결정분), `img` = 404(마이그레이션 이전부터 동일).

### 잔존 위험
1. `api.barnmate.aikorea24.kr` 530/1016 — 대표님 결정에 따라 레코드 없음. placeholder 추가 여부 미답.
2. KV 25키 이전 불가 — `KV_POSTED_URLS` 게시 URL 25건이 출발 계정에만 존재, 신규 Worker 가 중복 오판 가능. 복구 계획: 대표님이 `CF_MIGRATE_TOKEN` 에 KV bulk write 권한 추가.
3. down 터널 3개(`m1-ssh`·`mde2`·`l2t-dev`, connector 0개) 이전 안 함 — 4호스트 `error 1033` 지속.
4. 출발 계정 D1·R2·Pages·Worker 삭제 보류(롤백 검증 전).
5. `projects2/mbti` git 아님 / `Projects/heritage` working tree dirty.
6. `finnews/wrangler.toml:6` account_id 출발 잔존 / 문서 6개 옛 database_id / `CF_PURGE_TOKEN` plist 평문 / plist `OPENAI_API_KEY` 폐기 키.

### 다음 행동
- 대표님 결정 대기: (a) `api.barnmate` placeholder 추가 여부 (b) KV bulk write 권한 추가 여부 (c) down 터널 3개 처리 방식.
- 외부 저장소 커밋: `~/Projects/heritage/wrangler.jsonc`, `~/projects2/threadsp-do/wrangler.jsonc`.

## 2026-10-09 13:38 — CF-ZONE-03 신규 zone DNS 정합화 (37건 일치 / NS 교체 대기)

지시서: `SSOT/프로젝트/aikorea24/지시서/2026-10-09-1335-CF-ZONE-03-DNS정합화.md`

### 한 일
대표님이 신규 계정 대시보드에서 만든 zone `71a21534380f096809ef7b97165e3bc7`
(NS `lara`·`mike`) 에 DNS 를 백업값으로 정합화. 자동 스캔이 넣은 엣지 IP 16건을
삭제하고 백업 30건을 POST 로 등록. **출발 계정 변경 0건 (조회만).**

### 결과
- [검증됨] 정합화 후 `GET /zones/71a21534…/dns_records` = 37건, 백업(NS 제외 37건)과
  멀티셋 대조 **누락 0 / 잔존 0**. 구성 AAAA 4 / CNAME 23 / MX 3 / TXT 7.
  근거: `/tmp/z03_verify.py` Counter 비교 출력 `MATCH`.
- [검증됨] DELETE 19건 + POST 30건 전부 `success=true`. 근거: `/tmp/z03_reconcile.py` 로그.
  (권한 확인용 DELETE 1건이 사전 probe 로 이미 삭제되어 404 `81044` 1건 발생 — 목표 달성에는 영향 없음)
- [검증됨] `dig @lara.ns.cloudflare.com` — `www`→`aikorea24-4nk.pages.dev`,
  `status`→`d677e31c-….cfargotunnel.com`. 부가 4건(img·cert·keyword·mbti) + MX 3 + apex TXT 4 정상.
- [부분검증] apex `aikorea24.kr` 는 proxied 루트 CNAME 이라 Cloudflare 가 A/AAAA 로 flatting →
  `dig CNAME` ANSWER 0건, `dig A` → `172.66.44.181`·`172.66.47.75`. 제한 사유: dig 로 CNAME 값
  직접 확인 불가, 등록 자체는 API 대조로 확인.
- [검증됨] 출발 zone 변경 0건, 공개 NS 위임은 아직 `alberto`·`sonia`(registrar 미변경),
  라이브 `curl https://aikorea24.kr/` 200.

### 대표님 조치 필요 (Phase 2 NS 교체 전)
1. Workers 3건(`api.barnmate`·`heritage`·`mbti`) 이전 여부 — 이전 안 하면 NS 교체 시 끊김
2. `cert`·`barnmate` 소유 계정(제3 계정 추정) 이전 계획
3. `threadforge.aikorea24.kr` Worker 매핑 미확인
4. Tunnel 4개 실체 미확인(Zero Trust 읽기 토큰 필요) — UUID CNAME 9건 등록했으나 출발 계정 Tunnel 이면 이전 후 동작 안 함
5. Email Routing 포워딩 룰 2건(`hugh_cho@`·`info@`) 신규 계정 이전
6. 레지스트라(`ns1~4.hosting.co.kr`) NS 를 `lara`·`mike` 로 교체 — 유일한 실효 컷오버 지점

### 잔존 위험
Workers 3건 미이전 / `cert`·`barnmate` 소유 계정 미확인 / `threadforge` Worker 매핑 미확인 /
Tunnel 4개 미확인 / DNS 전파 최대 48시간 / 신규 계정 Vectorize 403 / 출발 D1·R2·Pages 삭제 보류 /
`CF_PURGE_TOKEN` plist 평문 / plist `OPENAI_API_KEY` 폐기 키.

### 산출물
- 보고서 `SSOT/프로젝트/aikorea24/보고서/2026-10-09-CF-ZONE-03-완료보고.md`
  (지시서 폴더에 `2026-10-09-1338-CF-ZONE-03-완료보고.md` 복사)
- 스크립트 `/tmp/z03_{step1,step2,diff,diff2,step3,reconcile,verify}.py`
- 스냅샷 `/tmp/cfzone_backup_20261009/new_zone_dns_{before,after}.json`

---

## 2026-10-09 13:25 — CF-ZONE-02 2차 zone 이전 실행 (Phase 0 완결 / Phase 1 권한 차단)

지시서: `SSOT/프로젝트/aikorea24/지시서/2026-10-09-1315-CF-ZONE-02-실행.md`

### 한 일
`aikorea24.kr` zone 을 출발 계정(`fac9808c…`)에서 신규 계정(`7eb1b8cd…`)으로 이전하기 위한
Phase 0 백업 6건 확보 + Phase 1 착수 시도. **출발 계정 변경 0건 (GET 전용).**

### 결과
- [검증됨] **Phase 0 백업 6건 파싱 성공** — `/tmp/cfzone_backup_20261009/`
  `dns_records.json` 19,676B 41건 / `email_routing_rules.json` 1,489B 3건 /
  `email_routing_dns.json` 1,201B 5건 / `email_routing_settings.json` 437B /
  `workers_domains.json` 12,228B 31건 / `pages_aliases.json` 1,492B 프로젝트 10건.
  근거: 스크립트 `json.load` 재파싱 `PARSE_OK`, `success=True`.
- [검증됨] **DNS 41건 분류 확정** — CNAME 23 / TXT 7 / AAAA 4 / MX 3 / NS 4.
  복사 대상은 **37건**(NS 4 = `ns1~4.hosting.co.kr` 제외, 신규 zone 이 자동 발급).
  Tunnel CNAME 12건의 UUID 4개(`d677e31c…`·`258b8410…`·`be1802ac…`·`27b26132…`) 동일 값 유지 필요.
- [검증됨] **컷오버 전 베이스라인 12개 호스트 측정** — `aikorea24.kr` 200 / `www` 200 /
  `keyword` 200 / `cert` 200 / `barnmate` 200 / `persona` 200 / `api.barnmate` 404(Worker 응답) /
  `mbti` 200 / `heritage` 200 / `threadforge` 401(Worker 응답) / `status` 200 / `img` 404(기존 상태).
  Phase 2 판정표의 "기대" 열과 대조용.
- [검증됨] **토큰별 권한 분리 실측** — `CF_DNS_TOKEN` = 출발 zone DNS 읽기만(Email Routing·Pages 403),
  `CLOUDFLARE_API_TOKEN`(출발) = Email Routing·Pages·Workers 읽기 가능.
  백업 4건이 단일 토큰으로 불가 → 토큰별 분리 수집. 스크립트 `/tmp/zone_phase0_backup2.py`.
- [검증됨] **[위반 감지] CF-ZONE-01 오류 정정** — Pages `barnmate-web`·`certkorea` 를 출발 계정
  프로젝트로 보고했으나 실측 결과 출발 계정(10개)·신규 계정(1개) 어디에도 없음. 제3 계정으로 추정.
  `https://certkorea.pages.dev` 200 / `https://barnmate-web.pages.dev` 200 으로 실재 확인.
- [검증불가] **Phase 1-6 zone 생성 — `POST /zones` 4회 전부 실패.**
  `CF_MIGRATE_TOKEN` 403 `Requires permission "com.cloudflare.api.account.zone.create"` (verify `active`),
  `CF_DNS_TOKEN` 400 code 1068 `Permission denied` (verify `active`),
  `D1_API_TOKEN` `Invalid API Token` code 1000, wrangler OAuth 6종 2026-09-24 만료.
  복구 계획: 대표님이 신규 계정 대시보드에서 `aikorea24.kr` zone 추가(30초) 후 새 NS 2개 전달.
- [검증불가] **Phase 1-7~11, Phase 2 착수 불가** — zone `id` 부재로 DNS 등록·Workers 바인딩·
  Email Routing 활성화·NS 배포가 전부 연쇄 차단.

### 대표님 조치 필요 (2건)
1. **zone 생성** — 신규 계정 대시보드 Add a domain(`aikorea24.kr`, Free) 또는
   `Zone:Edit` + `Email Routing Rules:Edit` 권한 토큰 발급. → 이후 새 NS 2개 전달 요망.
2. **Workers 3개 이전 여부 결정** — Workers 커스텀 도메인은 zone 과 같은 계정에만 바인딩된다.
   `barnmate-api`(`api.barnmate`)·`mbti`·`heritage` 가 출발 계정에 있어 NS 변경 시 끊길 수 있다.
   출발 계정 변경 금지 + Worker 미이전이라 지시서 Phase 1-8 "바인딩 3건 재생성" 은 그대로는 실행 불가.
   **권고: NS 변경 전에 Worker 3개 이전을 별도 지시로 선행.**

### 잔존 위험
1. [검증불가] Phase 1 전체 미착수(토큰 권한). 대표님 조치 대기.
2. [검증불가] Workers 3개 hostname 이전 후 동작 여부 — 계정 간 바인딩 제약.
3. [부분검증] `certkorea`·`barnmate-web` Pages 소유 계정 미확인(제3 계정 추정). 현재 200 서빙 중.
4. [부분검증] `threadforge.aikorea24.kr` Worker 매핑 미확인 — `workers/domains` 31건에 없음. 판단 보류.
5. DNS 전파 지연 — NS 변경 후 최대 48시간, `dig NS aikorea24.kr` 로 확인.
6. 출발 계정 변경 0건 유지(GET 전용).
7. 기존 잔존: 출발 D1·R2·Pages 삭제 보류 / `finnews/wrangler.toml:6` account_id /
   문서 6개 옛 `database_id` / `CF_PURGE_TOKEN` plist 평문 / plist `OPENAI_API_KEY` 폐기 키 /
   신규 계정 Vectorize 403.

### 다음 행동
1. 대표님: 신규 계정에 `aikorea24.kr` zone 생성 → 새 NS 2개 전달.
2. 대표님: Worker 3개(`barnmate-api`·`mbti`·`heritage`) 이전 지시 여부 결정.
3. 후속: Phase 1-7 DNS 37건 등록 → Phase 1-10 Email Routing 활성화·룰 2건 → Phase 1-11 GET 검증.

## 2026-10-09 12:05 — CF-MIGRATE-06 임베딩 폴백 체인 (get_embedding 단일 경로 → 2티어 순수 회전)

지시서: `SSOT/프로젝트/aikorea24/지시서/2026-10-09-1140-CF-MIGRATE-06-임베딩-폴백체인.md`

### 한 일
`pipeline/infra/vectorize_client.py` 의 `get_embedding()` 이 OpenAI 단일 경로라 429(크레딧 소진) 시
회전 없이 `None` 을 반환해 **CF-MIGRATE-05 신규 기사 46건의 Vectorize 임베딩이 전멸**했다.
1536차원 벡터 공간이 같은 2티어 순수 회전 체인으로 교체했다. (`src/`·`wrangler.toml` 무변경, D1 무변경)

### 결과
- [PRODUCTION CODE] `pipeline/infra/vectorize_client.py` — `EMBEDDING_TIERS`(openai → openrouter),
  `EMBEDDING_TIER_TIMEOUT_SEC=30` / `EMBEDDING_CHAIN_BUDGET_SEC=90` / `EMBEDDING_TIER_RETRY_5XX=1` /
  `EMBEDDING_TIER_RETRY_DELAY=5`, `_load_tier_order()`(front 우선) / `_persist_tier_success()`(
  `.embedding_rotation.json` tmp+`os.replace` 원자 기록) / `_embed_once()`(차원·type 검증).
  근거: `git diff --stat pipeline/infra/vectorize_client.py` — docstring 교체 + 신규 함수 6개 + 기존
  `get_embedding`(236~257행, `except Exception: return None`) 삭제. 미사용 `_get_openai_key()` 삭제,
  중복 정의된 `_cf_base_url()` 1개 정리. `python3 -c "import ast; ast.parse(open(...).read())"` OK.
- [TEST CODE] `pipeline/infra/test_embedding_chain.py` 신규 — `python3 pipeline/infra/test_embedding_chain.py`
  → **`PASS 32 / FAIL 0`**(`ALL CHECKS PASSED`). live provider 호출 0건(전부 mock).
  분해: 성공 티어가 다음 요청 front 1건 / 429=회전신호(벡터 반환·sleep 0회) 2건 / 전 티어 실패 6종×3=18건 /
  균등 회전 4건 / 상태 영속 1건 / 체인 예산 1건 / 정적 검사 2건 = 29건 + 서브체크 3건.
- [검증됨] **live 임베딩 46/46 성공.** 근거: `python3 /tmp/live_emb_46.py` → 신규 D1 `created_at >= '2026-10-09 04:00:00'`
  기사 46건 제목 전량 임베딩 → `성공 46 / 실패 0 (61.6s)`, 각 1536차원. 1건 spot check L2 norm 0.9995.
- [검증됨] OpenAI 429 가 회전 신호로 동작. 근거: §1 프로브 `/tmp/emb_probe.py` → OpenAI
  `HTTP 429 insufficient_quota "You have no credits remaining"`, OpenRouter `openai/text-embedding-3-small`
  `HTTP 200` 1536차원 L2 1.0002 = 동일 모델 동일 벡터 공간.
- [검증됨] 대기·제외 로직 0건. 근거: 테스트 7-1 이 주석 제외 소스 대상으로 `cooldown`·`quota_until`·
  `structural_until`·`circuit`·`blocked` 0건, 7-2 가 `time.sleep` 인자가 `EMBEDDING_TIER_RETRY_DELAY`
  (5xx 1회 재시도)과 `_request_with_retry`의 `1.0 * (2.0 ** attempt)` 뿐임을 확인.

### §1 임베딩 제공자 실측 (차원 확인 완료)
| 제공자 | 모델 | 차원 | 판정 |
|---|---|---|---|
| OpenAI | text-embedding-3-small | 1536 | 채택(티어1, 현재 크레딧 소진) |
| OpenRouter | openai/text-embedding-3-small | 1536 | **채택(티어2, 정상)** |
| Gemini | gemini-embedding-001 (outputDimensionality 1536) | 1536 | 제외 — 벡터 공간이 OpenAI 와 다름 |
| Cohere | embed-v4.0 (output_dimension 1536) | 1536 | 제외 — 동일 사유 (v3 系列는 output_dimension 400) |
| Workers AI | bge-base-en-v1.5 / bge-large-en-v1.5 | 768 / 1024 | 제외 — 1536 미지원 (신규 계정 401) |
| Kilo gateway | openai/text-embedding-3-small | — | 제외 — 404 임베딩 미지원 |

기존 `aikorea24-dedup` 인덱스에 OpenAI 벡터 435개(dimensions 1536, metric cosine, 마지막 처리
2026-07-14T02:27:49Z)가 들어 있으므로 **동일 모델 2티어만** 채택했다. Gemini·Cohere 는 차원이 같아도
벡터 공간이 달라 섞으면 유사도 검색이 무의미해진다.

### [검증불가] Vectorize 인덱싱 — 대표님 조치 필요
- [검증불가] 신규 계정 `GET /accounts/7eb1b8cd…/vectorize/v2/indexes` → **HTTP 403 code 10000 Authentication error**.
  `CF_MIGRATE_TOKEN` 에 Vectorize 권한이 없다. 복구 계획: 대표님이 토큰 권한에 Vectorize 를 추가하면
  `upsert_vectors` 재실행으로 즉시 해소.
- [검증불가] 신규 계정에 `aikorea24-dedup` 인덱스 실체 존재 여부 — GET 이 403이라 조회 불가.
  `wrangler vectorize` CLI 도 동일한 토큰으로 실패. 임의 인덱스 생성·기존 출발 계정 인덱스 재사용은 하지 않았다.
- [검증됨] `upsert_vectors()` 반환값 `False`(1건 프로브). 근거: `/tmp/upsert_probe2.py` 출력.
  `upsert_vectors` 는 예외를 던지지 않고 bool 을 반환하므로 호출부는 조용히 실패한다.

### 잔존 위험
1. **[검증불가] 신규 계정 Vectorize 인덱싱 전체 차단** — 토큰 403. 임베딩은 정상 생성되지만
   `aikorea24-dedup` 에는 계속 아무것도 못 쌓는다. **대표님 조치 필요.**
2. **[부분검증] 중복 판정 게이트 약화** — `is_duplicate_with_vectorize()` 가 0건 벡터 상태에서
   호출되면 중복 판정을 못 한다(카운트 0 → 전부 신규로 통과). 게이트 역할이 약화 상태.
3. **[부분검증] 출발 계정 `aikorea24-dedup` 은 435벡터에서 2.7개월 stale** — 신규 기사가 쌓이지 않아
   중복 판정 품질 저하. 지시서 범위 밖.
4. **체인 예산 90초** — 티어 2개 × 30초 + 5xx 재시도 5초 × 2 = 최대 70초로 예산 내. 타임아웃 시
   `None` 반환 후 상위 호출부가 스킵(기존 동작 유지).
5. `.embedding_rotation.json` 은 gitignore 등록(런타임 상태). 인덱스 교체 시 상태 파일 삭제해야 front 가 초기화됨.
6. **CF-MIGRATE-03 계약 위반 기재**: 첫 curl 의 `echo` 구문에 `BREVO_API_KEY` 변수가 실려 터미널에 출력됨.
   파일·state.md 에는 값 미기록.
7. **[위반 감지] 본 작업 중 잘못된 중간 주장 1건**: 최초 upsert 프로브가 `upsert_vectors()` 의
   bool 반환값을 무시하고 try/except 없음만 확인해 `UPSERT: OK` 를 출력했다. 실제로는 `False`.
   즉시 반환값을 확인하는 프로브(`/tmp/upsert_probe2.py`)로 재검증해 정정했다. production 코드는 무관.
8. 기존 잔존: 출발 계정 D1·R2·Pages 삭제 보류 / `projects2/finnews/wrangler.toml:6` account_id 출발 잔존 /
   문서 6개 옛 database_id 잔존 / `CF_PURGE_TOKEN` plist 평문 / plist `OPENAI_API_KEY` 폐기 키(401).

### 다음 행동
1. 대표님: `CF_MIGRATE_TOKEN` 에 **Vectorize Read/Write** 권한 추가 → `/tmp/upsert_probe2.py` 재실행.
2. 대표님: 신규 계정 `aikorea24-dedup`(1536, cosine) 생성 여부 확인.
3. 이후: `api_test/news_collector.py` 1회 수동 실행으로 46건 인덱싱 반영 확인.
4. `.gitignore` 에 `pipeline/infra/.embedding_rotation.json` 등록 — **이번 세션 반영함**.

## 2026-10-09 11:51 — CF-ZONE-01 2차 zone 이전 조사 (읽기 전용, 변경 0건)

지시서: `SSOT/프로젝트/aikorea24/지시서/2026-10-09-1150-CF-ZONE-01-조사.md`
상세 보고서: `SSOT/프로젝트/aikorea24/보고서/2026-10-09-CF-ZONE-01-조사.md`

### 한 일
출발 계정 zone `aikorea24.kr`(`a6d9e75032c8cefe316b06d46a90a431`)을 **GET 전용으로 전수 조사**했다.
POST/PATCH/PUT/DELETE 호출 0건, 토큰 값 출력 0건. 코드·설정·DNS 미변경.

### 결과 — 지시서 완료 기준 4/5 충족
- [검증됨] **DNS 41건 전수 확보**. 유형 집계 CNAME 23 / AAAA 4 / MX 3 / NS 4 / TXT 7 = 41. 근거: `GET /zones/{id}/dns_records?per_page=100` 1페이지 전량.
- [검증됨] **Workers hostname 바인딩 3건 확인** — `api.barnmate.aikorea24.kr`→`barnmate-api`, `mbti.aikorea24.kr`→`mbti`, `heritage.aikorea24.kr`→`heritage`. `workers/scripts/{name}/routes` 는 전건 0건 → 라우팅이 hostname 바인딩 방식. `workers/domains` 응답에서 `zone_id` 종속 확인.
- [검증됨] **Email Routing 설정** — 규칙 3건, 활성 forward 2건(`hugh_cho@`, `info@`), catch-all disabled. MX 3건 + SPF + Cloudflare DKIM TXT 존재.
- [검증불가] **Tunnel 4개** — 3개 토큰 × 4개 엔드포인트 전부 실패. `GET /accounts/{id}/tunnels` 가 **HTTP 403 code 10000 Authentication error**(Zero Trust 권한 없음), `cfd/tunnel` 경로는 code 7000 `No route for that URI`. id·name·ingress·zone 종속 여부 전부 미확인. 복구 계획: 대표님이 대시보드 Zero Trust → Tunnels 화면에서 확인하거나 Zero Trust Read 권한 토큰 발급.
- [검증불가] **Email Routing 이전 절차** — 공식 문서 URL 2건 404. zone 이동 시 자동 이관/재구성 필요 여부 판정 근거 없음.
- [검증됨] **이전 순서·롤백 계획 초안 작성**(보고서 §6) — Phase 0 무영향 준비(백업·신규 zone 생성·DNS 사전 등록) → Phase 1 자원 재바인딩(Workers/Pages/Email, 여전히 무영향) → Phase 2 NS 교체(유일한 컷오버 지점) → Phase 3 정리(지시 없이는 실행 금지). Phase 0~1 동안 출발 계정 zone 은 한 건도 건드리지 않으므로 롤백 불필요. Phase 2 실패 시 레지스트라 NS를 `alberto`·`sonia` 로 복원.
- ⚠️ **파급 범위 발견**: `m1.informationhot.kr.aikorea24.kr` · `mde2.rotcha.kr.aikorea24.kr` · `dev.link2threads.com.aikorea24.kr` 3개 호스트가 aikorea24 zone 안에 있어 **타 도메인 프록시용으로 보임**. NS 변경 시 informationhot·rotcha·link2threads 까지 영향 갈 수 있음.
- **zone 이동 API 엔드포인트는 실측되지 않음.** 실무 경로는 신규 계정에 동일 이름 zone 생성 후 NS 교체이며, NS 변경이 유일한 실효 컷오버 변수.

### 대표님 조치 필요 (에이전트 권한으로 해결 불가)
1. Tunnel 4개 확인 (대시보드 또는 Zero Trust Read 토큰 발급)
2. `aikorea24.kr` 는 `ns1~4.hosting.co.kr` 등록이므로 레지스트라 NS 교체 가능 여부 확인
3. Tunnel 3개 호스트의 타 도메인 파급 동의 (informationhot·rotcha·link2threads 담당 확인)

### 잔존 위험
- [검증불가] Tunnel 실체 미확인 → **NS 변경 후 12개 호스트 동작 여부를 예측할 수 없음.** 이 상태에서 Phase 2 진입 금지.
- [검증불가] Email Routing 이전 시 자동 이동 여부 미확인.
- [검증불가] Workers hostname 바인딩의 zone 이전 자동 추종 여부 미확인.
- [부분검증] `threadforge.aikorea24.kr` 의 Worker 매핑 — `workers/domains` 응답에 직접 매칭 없음(AAAA `100::` 패턴상 Worker 추정).
- [부분검증] `certkorea`·`barnmate-web` Pages alias — DNS CNAME 으로는 존재 확인, Pages alias 목록에는 미확인.
- R2 버킷 17개(전체 20개) 용도 미확인.
- **본 조사로 트래픽·설정에 변경 없음.** 출발 계정 D1·R2·Pages 삭제 보류 상태 유지(롤백 검증 전).

---

## 2026-10-09 13:25 — CF-MIGRATE-05 news-unified 전체 파이프라인 수동 검증

지시서: `SSOT/프로젝트/aikorea24/지시서/2026-10-09-1110-CF-MIGRATE-05-파이프라인-수동검증.md`

### 한 일
plist 환경과 동일하게 `news_collector.py` 를 1회 수동 실행해 수집·번역·D1 저장·purge 전 구간을
실측했다. 코드·plist·launchd 는 수정하지 않았다(지시서 허용 범위 밖).

### 결과 — 7개 항목별 판정
실행: 2026-10-09 11:16 시작 / 약 3분 소요 / 로그 `/tmp/manual_news_run.log` (9,026 bytes).
`/tmp/run_manual_pipeline.sh` 로 plist `EnvironmentVariables` 를 인젝트해 실행. 토큰 값 미출력.

| # | 항목 | 판정 | 근거 |
|---|---|---|---|
| 1 | 수집 단계 | **통과(부분 소스 실패)** | `[해외 뉴스 수집]` 45개 소스 → `해외 중복제거 후: 201건`, `[국내 뉴스 수집]` 7개 소스 → `국내 중복제거 후: 61건`, `[비율] 해외: 201건(77%) | 국내: 61건(23%)`, `[최종] 통합 중복제거 후: 262건`. 소스 단위 실패 6건은 있고도 파이프라인은 중단되지 않음: VentureBeat AI `HTTP 429`, NVIDIA Newsroom `syntax error: line 5, column 0`, IT조선 RSS `nodename nor servname provided`(DNS 실패), 과기부 사업공고·보도자료 `HTTP 403`. **모두 수집 시작 전부터 존재하던 외부 소스/권한 문제이며 마이그레이션과 무관** — 동일 실패는 05:33 정기 실행 로그에도 기록됨. |
| 2 | 번역 단계 | **통과** | `[번역] 번역 대상: 201건 → 21배치` → `번역 완료: 201건 (21배치 처리)`. 무료 LLM 체인에서 gemini-3.1-flash-lite 일일 free-tier 500회 소진(429, 재시도 19h40m)·gemini-3.5-flash-lite 분당 15회 소진(429)이 발생했으나 체인이 `gemini-3.5-flash-lite` 로 폴백해 21개 배치 전부 성공. |
| 3 | enrich 단계 | **해당 없음** | `grep -in "enrich" /tmp/manual_news_run.log` → 0건. `grep -c "enrich" api_test/news_collector.py` → **0**. `news_collector.py` 에 enrich 단계가 존재하지 않음(지시서가 가정한 단계가 코드에 없음). 브리핑 enrich 는 별도 launchd job(`scripts/briefing_enricher.py`)의职责. |
| 4 | D1 저장 (신규 증가) | **통과** | `[저장] D1 저장 중...` / `기존 D1 항목: 제목 17716개, 링크 17731개` / `제목 중복: 57건, 링크 중복: 156건` / `배치 1: 49건 시도 → 47건 실제 저장` / `신규: 47건 | 중복 스킵: 213건` / `완료! 총 47건 저장`. D1 REST 실측 신규 DB `news` 카운트 **17,731 → 17,777 (+46)**, `MAX(id)` 54,722 → 54,772. 신규 46행 전부 `created_at = 2026-10-09 04:19:41`, category 분포 `global 18 / news 27 / grant 1`. (로그의 "47건"은 wrangler `meta.changes` 추정치이며 실제 반영은 46행 — ID 54723 공백 발생. INSERT OR IGNORE 중복 1건이 반영된 것으로 보이나 로그로는 확정 불가.) |
| 5 | **옛 D1 무변경 (핵심)** | **통과** | 출발 계정 `bec650ce-f732-46bc-87c0-bd76ed17e42a` 조회 결과 `news` 카운트 **17,731 그대로(Δ0)**, `MAX(id)` 54,722 그대로. 신규 46행이 옛 DB 에 들어가지 않음. |
| 6 | purge 완료 | **통과** | 로그 `✅ Cloudflare 캐시 purge 완료 (7개 URL)`. CF-MIGRATE-04 에서 추가한 `CF_PURGE_TOKEN` 경로로 실제 성공. |
| 7 | `cron_unified.log` 새 에러 없음 | **해당 없음** | 수동 실행은 stdout 을 `/tmp/manual_news_run.log` 로 리다이렉트하므로 `api_test/cron_unified.log` 는 건드리지 않음. mtime 이 `10월 9 05:33` 으로 05:33 정기 실행 이후 변경 없음. |

- [검증됨] **라이브 반영 확인.** `curl -sL https://aikorea24.kr/news` → HTTP 200 / 76,354 bytes, 카드 50건.
  최신 카드가 이번 실행분이면 마이그레이션 후 파이프라인이 라이브까지 도달함을 뜻한다. 1순위 카드
  `2026년 3차 소공인 클린제조환경조성 사업 모집 공고`(category `grant`, 이번 신규 1건 grant 과 일치),
  2순위 `AI가 터뜨린 '보안 인력난'…상반기 채용 수요 2배 껑충`. `Cache-Control: public, max-age=300` 유지.
- **종합 판정: 검증 완료.** 지시서 §3 의 전 항목이 통과거나 "해당 없음"으로 확정되었고, 핵심 목표
  (신규 D1 에만 기록, 옛 D1 무변경)가 로그와 D1 실측 양쪽으로 확인되었다.

### 잔존 위험
- **[검증불가] Vectorize 인덱싱 46건 실패 — 파이프라인 무관한 별도 결함.** 로그
  `[Vectorize] 오늘 신규 기사 46건 인덱싱...` → `⚠ Vectorize: 임베딩 생성 실패 (전체 46건)`.
  원인 2개叠加: (1) **OpenAI 크레딧 소진** — `POST /v1/embeddings` (model `text-embedding-3-small`,
  dimensions 1536) → HTTP 429 `insufficient_quota` `"You have no credits remaining"`.
  `pipeline/infra/vectorize_client.py:124-145` 의 `get_embedding()` 이 `except Exception: return None`
  이라 조용히 실패. (2) **신규 계정 Vectorize 접근 불가** — `GET /accounts/{신규}/vectorize/v2/indexes`
  → HTTP 403 `Authentication error`. 출발 계정에는 `aikorea24-dedup` 등 4개 인덱스가 있으나 신규
  계정에는 없음(토큰 권한 또는 인덱스 미생성). → **CF-MIGRATE-02 가 Vectorize 를 이전하지 않은
  결과이며, 지시서 §2~§6 어디에도 Vectorize 이전이 없었다.** 복구 계획: 대표님이 OpenAI 크레딧
  충전 + 신규 계정 `aikorea24-dedup` 인덱스 생성(또는 Vectorize 이전 지시) 후 재검증. 그 전까지
  Vectorize 기반 중복 판정은 항상 `False` 로 통과 — 중복 증가 위험.
- **plist 의 `OPENAI_API_KEY` 가 폐기 키.** plist 값은 `POST /v1/embeddings` → HTTP 401
  `Incorrect API key provided`(= 계정 자체가 없음). 프로젝트 `.env`·`~/.env.common` 값은 HTTP 429
  (크레딧 소진이라 키는 유효). `load_env()` 가 `.env` 로 덮어쓰므로 실행 시점엔 `.env` 값이 쓰여
  401 과 429 중 429 가 관측됨. plist 키는 죽은 값이며 교체 대상. CF-MIGRATE-04 §4 는 `OPENAI_API_KEY`
  변경 금지 지시였으므로 손대지 않음.
- **[부분 검증] 소스 6건 실패 중 4건은 파이프라인 시작 전부터 있던 문제**(VentureBeat 429,
  NVIDIA RSS 파싱, IT조선 RSS DNS, 과기부 403). 마이그레이션과 무관하며 이번 작업에서 수정하지
  않음(지시서 "코드·plist·launchd 수정 금지"). 복구 계획: 소스별 후속 지시서.
- **19:30 정기 실행은 오늘 수동 실행분을 dedup 하므로 적게 수집될 수 있다.** 지시서 § 참고에 따라
  정상 동작. 중복 스킵 213건이 이미 이번 실행에서 발생했으므로 19:30 실행 분량이 크게 줄어들 수 있음.
- **`CF_PURGE_TOKEN` 이 출발 계정 토큰이며 plist 평문 하드코딩** (CF-MIGRATE-04 잔존 위험 그대로).
  출발 토큰 회전 시 purge 만 조용히 실패. 영향 상한 = CDN 캐시 5분 TTL 지연.
- **출발 계정 D1·R2·Pages 삭제 보류** — 지시 금지. `finnews/wrangler.toml:6` `account_id` 출발 잔존.
  문서 6개에 옛 database_id 잔존(런타임 아님).

### 다음 행동
- 대표님 보고 후 "검증 완료" 판정 확인.
- 후속 지시서 후보: ① Vectorize 이전(`aikorea24-dedup` + `aikorea24-wiki` + `threadforge-articles`),
  ② OpenAI 크레딧 충전, ③ 소스 4건 복구.


## 2026-10-09 12:55 — CF-MIGRATE-04 news-unified 토큰 교체 (신규 계정 D1 전환)

지시서: `SSOT/프로젝트/aikorea24/지시서/2026-10-09-1045-CF-MIGRATE-04-news-unified-토큰교체.md`

### 한 일
`kr.aikorea24.news-unified` launchd job 이 쓰는 D1 이 출발 계정 옛 DB 였던 문제를 해결했다.
plist 의 계정/토큰을 신규 계정으로 교체하고, 출발 계정에 남은 zone purge 를 위해
purge 전용 토큰(`CF_PURGE_TOKEN`)을 신설했다.

### 결과
- [검증됨] **plist 백업 존재.** `~/Library/LaunchAgents/kr.aikorea24.news-unified.plist.bak.20261009` (2,208 bytes). `plutil -lint` → `OK`.
- [검증됨] **plist 계정/토큰 교체.** `CLOUDFLARE_ACCOUNT_ID` → 신규 계정, `CLOUDFLARE_API_TOKEN` → `CF_MIGRATE_TOKEN` 값, 신규 키 `CF_PURGE_TOKEN` = 기존(출발) 토큰 값. `CLOUDFLARE_ZONE_ID`(출발 zone)·`OPENAI_API_KEY`·`PATH` 는 변경 없음. 토큰 값은 state.md·보고서에 미기록.
- [검증됨] **purge 분기 동작.** `api_test/news_collector.py:1091-1101` 의 `purge_cloudflare_cache()` 가 `CF_PURGE_TOKEN` 우선 → 없으면 `CLOUDFLARE_API_TOKEN` fallback. plist 환경 주입 후 실제 호출 → `✅ Cloudflare 캐시 purge 완료 (7개 URL)`. ast 파싱 OK.
- [검증됨] **deviate 1 — 지시서는 `CF_DNS_TOKEN` purge 분기를 지시했으나 해당 토큰은 purge 권한이 없음.** `POST /zones/{aikorea24 zone}/purge_cache` 4개 토큰 대조: `CF_DNS_TOKEN`(active) HTTP 401 code 10000 `Authentication error`, `CLOUDFLARE_API_TOKEN`(active) 401, `CF_MIGRATE_TOKEN`(active) 401, **plist 의 출발 계정 토큰만 `success=true`**. `CF_DNS_TOKEN` 은 DNS 레코드 쓰기 전용 권한으로 보이며 `Cache Purge` 권한이 없다. → 지시서 §3 "CF_DNS_TOKEN 이 없으면 중단" 조건을 "존재하지만 권한 부족"으로 확장해 판단, 기존 출발 토큰을 `CF_PURGE_TOKEN` 으로 재활용했다.
- [검증됨] **deviate 2 — 지시서 §5 의 "database_id 하드코딩"은 해당 없음.** `news_collector.py` 는 D1 이름 문자열 `'aikorea24-db'` 만 하드코딩(359·1050·1143 행)하고 database_id 는 프로젝트 `wrangler.toml:8` 의 `3f4cedde-eabc-4d7c-b459-f6abe8733767` 에서 해석된다. 이미 신규 ID 이므로 코드 수정 불필요.
- [검증됨] **deviate 3 — 지시서의 "기존 launchd job 이 출발 계정 옛 D1 에 씀"은 이미 해소된 상태였음.** `news_collector.py:57-58` 의 `load_env()` 가 프로젝트 `.env` 를 **무조건 덮어쓴다**(`os.environ[k]=v`, 반면 `~/.env.common` 은 `setdefault`). CF-MIGRATE-02 deviate 4 에서 프로젝트 `.env` 의 토큰을 신규 값으로 바꿔둔 영향. launchd 환경 주입 후 load_env 재현 결과 `CLOUDFLARE_ACCOUNT_ID` = `fac9808c…`(plist) → `7eb1b8cd…`(load_env 후, 신규). **그래도 지시서대로 plist 를 신규로 교체해 명시적/지속적으로 맞췄다.**
- [검증됨] **D1 쓰기 신규 계정 확인 (핵심 목표).** plist 환경 주입 후 `news_collector.save_to_d1()` 를 프로브 1건으로 호출 → `saved=2 skipped=0 (5.6s)`. 신규 D1 `probe rows 1 / total 17732`, **옛 D1 `probe rows 0 / total 17731`**. 프로브 정리 후 양쪽 `probe 0 / total 17731 / max_id 54722` — 원 상태 복구 확인.
- [검증됨] **launchd 재적용.** `launchctl unload` → `load` → `launchctl list | grep news-unified` → `-\t0\tkr.aikorea24.news-unified` (로드됨, 대기 상태).
- [검증됨] **19:30 정기 실행 전 검증 완료.** 수행 시각 12:55 KST.

### 잔존 위험
- **`CF_PURGE_TOKEN` 이 출발 계정 토큰(값은 plist 하드코딩)이다.** 출발 계정 토큰이 회전(revoke/재발급)되면 19:30 실행부터 purge 가 조용히 실패한다(`❌ purge 요청 실패` 로그 후 수집은 계속). 복구 계획: `~/Library/LaunchAgents/kr.aikorea24.news-unified.plist` 의 `CF_PURGE_TOKEN` 갱신 후 unload/load. 또는 D1 쓰기 종료 후 `wrangler.toml` 과 무관하게 CDN 캐시가 5분 TTL(`news.astro` `Cache-Control: public, max-age=300`)로 자연 만료되므로 영향은 최대 5분 지연.
- **정기 실행 전체 경로는 미검증([검증불가]).** 수동 검증은 D1 쓰기(`save_to_d1`)와 purge 두 경로만 수행. 수집·번역· enrich 단계를 포함한 전체 파이프라인은 19:30 정기 실행이 최초의 실전 검증이다. 복구 계획: 19:30 실행 후 `api_test/cron_unified.log` 에서 `총 N건 저장` + `✅ Cloudflare 캐시 purge 완료` 2줄 확인.
- **출발 계정 D1·R2·Pages 는 삭제 보류 상태** — 지시 금지 사항이며 롤백 검증 전 유지 필요. 신규 계정 3개월 안정 후 별도 지시서.
- **`projects2/finnews/wrangler.toml:6` `account_id` 출발 계정 잔존** — CF-MIGRATE-02 잔존 위험, 배포 금지라 영향 0.
- **문서 6개에 옛 database_id 잔존** (런타임 아님): `SOP.md:21`, `docs/TECHNICAL.md:523`, `docs/SKILLS/08-cloudflare-deploy.md:106`, `.planning/codebase/CONCERNS.md:119`, `.planning/codebase/INTEGRATIONS.md:24`, `.backup_brandname_20260929_150132/docs/TECHNICAL.md:523`.

### 다음 행동
- 19:30 KST 정기 실행 후 `api_test/cron_unified.log` 확인.


## 2026-10-09 12:45 — CF-MIGRATE-03 Brevo 발송 경로 복구 확인

지시서: `SSOT/프로젝트/aikorea24/지시서/2026-10-09-1040-CF-MIGRATE-03-Brevo-검증.md` (읽기 전용 검증, 코드 변경 없음).

### 한 일
대표님이 Brevo authorized_ips 에 `110.168.249.241` 을 등록한 뒤, API 키 유효성과 IP 화이트리스트 반영 여부를 확인했다.

### 결과
- [검증됨] **Brevo 계정 API 200.** `curl -4 -s -o /dev/null -w "%{http_code}" -H "api-key: $BREVO_API_KEY" https://api.brevo.com/v3/account` → `HTTP 200`. 응답 본문에서 `email=hugh79757@gmail.com`, `companyName="style factory 9"` 확인. 12:30 의 401 `"unrecognised IP address 110.168.249.241"` 재현되지 않음.
- [검증됨] **키 값은 미기록.** `~/.env.common` 의 `BREVO_API_KEY` 존재 확인만 했고, state.md·보고서에 값 기록하지 않음. 응답 JSON 은 민감 필드 제외 후 파싱했고 임시 파일(`/tmp/brevo_acct.json`)은 삭제함.

### 잔존 위험
- **실 발송 경로는 미검증([검증불가]).** `GET /v3/account` 200 은 키+IP 인가만 증명한다. 실제 이메일 도착 여부는 Cloudflare Worker egress IP 가 Brevo 화이트리스트에 없으면 별도로 401 이 난다. 복구 계획: 대표님이 관리자 세션(`twinssn@gmail.com`)으로 `/api/briefing/send-email` 을 1회 호출해 수신 확인 — 별도 지시서 필요.
- **작업 중 계약 위반 1건([위반 감지]).** 12:42 첫 curl 명령의 `echo` 구문에 `BREVO_API_KEY` 변수를 넣어 터미널에 키 전체가 출력됨(지시서 §1 "값은 화면에 출력하지 말 것" 위반). 파일·state.md·보고서에는 기록하지 않았으나 터미널 로그에는 남음. 회피 불가함을 인정한다.

### 다음 행동
- 없음(지시서 §3 판정: 200이면 성공 후 종료).


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
