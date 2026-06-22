# Mimo v2.5 Work Log

## 작업 날짜: 2026-06-22

---

## 1. 프로젝트 보안 취약점 분석 및 수정

### CRITICAL (즉시 조치)

#### C-1. 세션 인증 전면 교체 (HMAC-SHA256)
- **문제**: 세션이 `base64(JSON)` 인코딩으로 누구나 위조 가능
- **수정**: `src/lib/auth.ts` — `signSession()`, `verifySession()` 함수 추가. HMAC-SHA256 서명/검증
- **수정 대상 파일 (15곳)**:
  - `src/lib/auth.ts` (신규 작성)
  - `src/pages/api/auth/callback/google.ts` — `signSession()` 적용
  - `src/pages/api/auth/callback/kakao.ts` — `signSession()` 적용
  - `src/pages/admin/index.astro` — `verifySession()` 적용
  - `src/pages/admin/event.astro` — `verifySession()` 적용
  - `src/layouts/Layout.astro` — `verifySession()` 적용
  - `src/pages/pricing.astro` — 기존 사용
  - `src/pages/tools/[id].astro` — `verifySession()` 적용
  - `src/pages/community/[id].astro` — `verifySession()` 적용
  - `src/pages/community/index.astro` — `verifySession()` 적용
  - `src/pages/community/write.astro` — `verifySession()` 적용
  - `src/pages/community/review.astro` — `verifySession()` 적용
  - `src/pages/event/index.astro` — `verifySession()` 적용
  - `src/pages/event/download.astro` — `verifySession()` 적용
  - `src/pages/api/posts/index.ts` — `verifySession()` 적용
  - `src/pages/api/tools/vote.ts` — `verifySession()` 적용
  - `src/pages/api/admin/grant.ts` — `verifySession()` 적용
  - `src/pages/api/briefing/deepdive.ts` — `verifySession()` 적용
- **필요 환경변수**: `SESSION_SECRET` (Cloudflare Workers 환경변수에 설정 필요)

#### C-2. 브리핑 API 인증 추가
- **문제**: `publish.ts`, `send-email.ts`에 인증 검증 없음
- **수정**: 두 파일 모두 상단에 관리자 인증 검증 로직 추가. 미인증 시 401 반환
- **수정 파일**:
  - `src/pages/api/briefing/publish.ts` — `requireAdmin()` 함수 + POST/DELETE 핸들러 적용
  - `src/pages/api/briefing/send-email.ts` — `verifySession()` + `ADMIN_EMAILS` 체크

#### C-3. Telegram 토큰 로그 제거
- **문제**: `naver_blog/logs/auto_publish.log`에 Telegram Bot 토큰 평문 노출 (4줄)
- **수정**: `sed -i '' '/8511728557/d'`로 토큰 포함 줄 제거
- **추가**: `.gitignore`에 `naver_blog/logs/`, `scripts/threads/logs/` 추가

### HIGH

#### H-1. XSS 수정 (이메일)
- **문제**: `send-email.ts`에서 DB 값을 HTML 이스케이프 없이 이메일 HTML에 삽입
- **수정**: `escapeHtml()` 함수 추가, 모든 DB→HTML 삽입 위치 적용 (19곳)
- **수정 파일**: `src/pages/api/briefing/send-email.ts`

#### H-2. XSS 수정 (관리자)
- **문제**: `admin/index.astro`에서 innerHTML에 DB 데이터 삽입
- **수정**: `esc()` 함수 추가, innerHTML 모든 DB 데이터 적용
- **수정 파일**: `src/pages/admin/index.astro` (4곳 innerHTML)

#### H-3. SQL 인젝션 수정
- **문제**: `gov_doc_collector.py`에서 `shell=True` + f-string SQL
- **수정**: 리스트형 subprocess + `--file` 방식으로 교체. `shell=True` 제거
- **수정 파일**: `api_test/gov_doc_collector.py` (`get_existing_hashes()`, `insert_to_d1()`)

#### H-4. 에러 메시지 정보 노출 수정
- **문제**: 7개 API 엔드포인트에서 `e.message`를 클라이언트에 직접 반환
- **수정**: 프로덕션에서 "Internal Server Error" 반환, DEV에서만 상세 메시지
- **수정 파일 (7곳)**:
  - `src/pages/api/posts/index.ts`
  - `src/pages/api/tools/vote.ts`
  - `src/pages/api/admin/grant.ts`
  - `src/pages/api/briefing/deepdive.ts`
  - `src/pages/api/briefing/publish.ts`
  - `src/pages/api/network/refresh.ts`
  - `src/pages/api/network/feeds.ts`

### MEDIUM

#### M-1. 보안 헤더 추가
- **수정 파일**: `src/middleware.ts`
- **추가 헤더**: CSP, X-Frame-Options: DENY, X-Content-Type-Options: nosniff, HSTS, Referrer-Policy

#### M-2. CORS 와일드카드 수정
- **문제**: `feeds.ts`에서 `Access-Control-Allow-Origin: *`
- **수정**: `https://aikorea24.kr` 로 교체
- **수정 파일**: `src/pages/api/network/feeds.ts`

#### M-3. .gitignore 보강
- **추가 패턴**: `*.log`, `backup2.py`, `backup3.py`, `naver_blog/logs/`, `scripts/threads/logs/`
- **수정 파일**: `.gitignore`

---

## 2. auth.ts Import 경로 수정

### 문제
- `npm run build` 시 `Could not resolve "../../../lib/auth"` 오류 발생

### 원인
- `src/pages/api/` 하위 3단계 디렉토리(`tools/`, `briefing/`, `admin/`, `posts/`) 파일들이 `../../lib/auth` (2단계)로 import
- `callback/` 디렉토리(4단계) 파일들이 `../../../lib/auth` (3단계)로 import

### 수정 파일 (8곳)
| 파일 | 수정 전 | 수정 후 |
|------|---------|---------|
| `api/tools/vote.ts` | `../../lib/auth` | `../../../lib/auth` |
| `api/briefing/publish.ts` | `../../lib/auth` | `../../../lib/auth` |
| `api/briefing/send-email.ts` | `../../lib/auth` | `../../../lib/auth` |
| `api/briefing/deepdive.ts` | `../../lib/auth` | `../../../lib/auth` |
| `api/admin/grant.ts` | `../../lib/auth` | `../../../lib/auth` |
| `api/posts/index.ts` | `../../lib/auth` | `../../../lib/auth` |
| `api/auth/callback/kakao.ts` | `../../../lib/auth` | `../../../../lib/auth` |
| `api/auth/callback/google.ts` | `../../../lib/auth` | `../../../../lib/auth` |

### 교훈
- Astro의 `src/pages/`에서 `src/lib/`까지의 상대 경로는 **파일 위치 기준**으로 계산
- `src/pages/api/XXX/` = 3단계 → `../../../lib/auth`
- `src/pages/api/auth/callback/` = 4단계 → `../../../../lib/auth`

---

## 3. 코드 상태 점검

### 보안 수정 검증 — 전체 통과
- `auth.ts` export: `signSession`, `verifySession`, `getSessionUser` ✅
- `publish.ts` 인증: `requireAdmin()` ✅
- `send-email.ts` 인증 + XSS: `escapeHtml()` 적용 ✅
- `admin/index.astro` XSS: `esc()` 적용 ✅
- `middleware.ts` 보안 헤더 5개 ✅
- `gov_doc_collector.py` shell=True 제거 ✅
- `news_collector.py` SQL: `--file` 방식 사용 ✅

### 발견된 문제점

#### 죽은 코드 (즉시 삭제 가능)
- `src/navigation.ts` — AstroWind 템플릿 잔재, 깨진 import 경로
- `src/lib/slug.ts` — `generateSlug()` 미사용

#### 사용되지 않는 컴포넌트 (6곳)
- `src/components/home/ContentHub.astro` — import만 하고 렌더링 안 함
- `src/components/home/GlobalNews.astro`
- `src/components/home/LatestNews.astro`
- `src/components/home/GrantSection.astro`
- `src/components/home/PolicyBriefing.astro`
- `src/components/home/WelfareSection.astro`
- `src/components/home/DonationBanner.astro`

#### 미사용 함수
- `src/lib/auth.ts` — `canAccess()` (import하는 곳 없음)
- `src/lib/sitemap.ts` — `SitemapEntry` interface (외부 import 없음)

#### 구버전 스레드 스크립트 (v1/v2)
- `scripts/threads/main_v2.py`, `writer_v2.py`, `db_reader_v2.py`, `scorer_v2.py`
- `scripts/threads/main.py`, `writer.py`
- 모두 v3로 대체됨. 활성 파이프라인에서 미사용

#### 환경변수 이슈
- `.env`에 있지만 미사용: `AUTH_SECRET`, `BIZINFO_API_KEY`, `FIGMA_TOKEN`, `FIGMA_FILE_KEY`, `GOOGLE_ADS_*`, `THREADS_APP_ID/SECRET`, `THREADS_REDIRECT_URI`
- 코드에서 사용하지만 `.env`에 없음: `KAKAO_CLIENT_ID`, `KAKAO_CLIENT_SECRET`, `TOSS_CLIENT_KEY`

---

## 4. sitemap.xml 404 수정

### 문제
- `https://aikorea24.kr/sitemap.xml` → 404 반환

### 원인
- sitemap 인덱스가 `/sitemap-index.xml`에 있고 `/sitemap.xml`에는 라우트 없음

### 수정
- `src/pages/sitemap-index.xml.ts` → `src/pages/sitemap.xml.ts` 이름 변경

### 검증
- `https://aikorea24.kr/sitemap.xml` → 200 OK
- 6개 서브사이트맵 포함: blog, tools, briefing, pages, glossary, chronicle
- 브리핑 페이지는 DB에서 동적 생성

---

## 5. 배포 이력

| 시간 | 내용 | 결과 |
|------|------|------|
| 09:21 | 보안 수정 + auth import 경로 수정 | 빌드 성공, 배포 완료 |
| 09:39 | sitemap.xml 수정 | 빌드 성공, 배포 완료 |

---

## 참고사항

- `SESSION_SECRET` 환경변수는 Cloudflare Workers 환경변수에 별도 등록 필요
- `KAKAO_CLIENT_ID`, `KAKAO_CLIENT_SECRET`, `TOSS_CLIENT_KEY`는 Cloudflare 환경변수 확인 필요
- 기존 `AUTH_SECRET`은 `SESSION_SECRET`으로 교체된 것으로 보임. 확인 후 `.env`에서 삭제 검토
