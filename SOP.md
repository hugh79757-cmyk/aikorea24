# aikorea24.kr 프로젝트 SOP

## 프로젝트 개요
- 사이트: https://aikorea24.kr
- 목적: AI 도구 추천, 무료 강좌, 정부 지원사업 정보, AI 뉴스 한국어 큐레이션
- 핵심 가치: AI가 어떻게 내 호주머니를 불려줄 수 있을까?
- 스택: Astro (SSR) + Cloudflare Pages + D1 + Tailwind CSS
- 레포: https://github.com/hugh79757-cmyk/aikorea24

---

## 완료된 작업

### 1. 인프라 구축
- Astro SSR 전환 (output: server, @astrojs/cloudflare 어댑터)
- Cloudflare Pages 배포 (커스텀 도메인 aikorea24.kr)
- wrangler.toml 설정 (D1 바인딩, pages_build_output_dir)
- D1 데이터베이스 생성 (aikorea24-db, ID: bec650ce-f732-46bc-87c0-bd76ed17e42a)
- D1 테이블: users, posts, comments, news

### 2. 인증 (Google OAuth)
- Google Cloud Console OAuth 2.0 클라이언트 설정
- 리다이렉트 URI: https://aikorea24.kr/api/auth/callback/google
- Cloudflare 환경변수: GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, AUTH_SECRET
- wrangler pages secret으로 시크릿 등록
- runtime.env로 환경변수 읽기 (import.meta.env → locals.runtime.env 수정)
- /api/auth/login.ts, /api/auth/callback/google.ts 구현
- /api/debug 엔드포인트 (환경변수 디버깅용)

### 3. 뉴스 수집기
- 수집 스크립트: api_test/news_collector.py
- 수집 소스 (5개):
  - 과기부 사업공고 API (apis.data.go.kr/1721000/msitannouncementinfo)
  - 과기부 보도자료 API (apis.data.go.kr/1721000/msitpressreleaseinfo)
  - 행안부 공공서비스(혜택) API
  - 네이버 뉴스 검색 API (키워드: AI 지원사업, 인공지능 정책, AI 바우처 2026)
  - AI타임스 RSS 피드
- D1 news 테이블 저장 (47건)
- 카테고리 분류: news, AI, policy, benefit
- 공공데이터 API User-Agent 이슈 해결 (-A Mozilla/5.0)

### 4. 홈페이지 (index.astro)
- 히어로 섹션 (particles.js 배경)
- AI 도구 픽 (하드코딩 4개)
- AI 정책 브리핑 — D1 policy 카테고리에서 동적 로드 (3건)
- AI 지원사업 — D1 benefit 카테고리에서 동적 로드 (3건)
- 최신 AI 뉴스 — D1 news/AI 카테고리에서 동적 로드 (5건)
- 인기 AI 강좌 (하드코딩 3개)
- 최신 블로그 (astro:content에서 동적 로드)
- CTA 섹션
- 다크 테마 + 글래스모피즘 디자인

### 5. API 엔드포인트
- /api/auth/login — Google OAuth 로그인 시작
- /api/auth/callback/google — OAuth 콜백 처리
- /api/news/latest — 최신 뉴스 (news, AI 카테고리)
- /api/news/policy — 정책 브리핑 (policy 카테고리)
- /api/news/benefits — 지원사업 (benefit 카테고리)
- /api/debug — 환경변수 디버깅

### 6. 시크릿/보안
- .gitignore에 .env, .env.production, api_test/.env.sh 등록
- git filter-repo로 시크릿 히스토리 완전 삭제
- GitHub secret scanning으로 push 차단 확인 (시크릿 미노출)

---

## 보류/미완료 작업

### 우선순위 높음
- Cloudflare 재배포 후 로그인 테스트
- 뉴스 수집기 개선: 과기부 사업공고 AI 키워드 필터 확대
- GitHub Actions 크론 스케줄 (하루 2회 자동 수집)
- /news 페이지 (전체 뉴스 목록)

### 우선순위 중간
- 디자인 구현: 다크/라이트 모드 토글
- 타이포그래피 업그레이드 (Pretendard, Inter 등)
- 카드뉴스 이미지 자동 생성 (Python Pillow)
- 커뮤니티 게시판 (/community)

### 우선순위 낮음
- Instagram/Threads 자동 발행 (Meta API 승인 필요)
- 국고보조금 공모사업 API 연동 (현재 Forbidden)
- 뉴스레터 구독 기능

---

## 환경 변수 목록

| 변수명 | 용도 | 발급처 |
|--------|------|--------|
| GOOGLE_CLIENT_ID | OAuth 로그인 | Google Cloud Console |
| GOOGLE_CLIENT_SECRET | OAuth 로그인 | Google Cloud Console |
| AUTH_SECRET | 세션 암호화 | openssl rand -base64 32 |
| NAVER_CLIENT_ID | 뉴스 검색 API | developers.naver.com |
| NAVER_CLIENT_SECRET | 뉴스 검색 API | developers.naver.com |
| OPENAI_API_KEY | 뉴스 요약 | platform.openai.com |
| DATA_GO_KR_KEY | 공공데이터 API | data.go.kr |

---

## 주요 파일 경로

- src/pages/index.astro — 홈페이지 (D1 동적 섹션)
- src/pages/api/auth/login.ts — OAuth 로그인
- src/pages/api/auth/callback/google.ts — OAuth 콜백
- src/pages/api/news/latest.ts — 최신 뉴스 API
- src/pages/api/news/policy.ts — 정책 API
- src/pages/api/news/benefits.ts — 지원사업 API
- src/pages/api/debug.ts — 디버그 API
- api_test/.env.sh — 로컬 환경변수 (git 제외)
- api_test/news_collector.py — 뉴스 수집 스크립트
- wrangler.toml — Cloudflare 설정
- astro.config.mjs — Astro 설정

---

## 배포 절차

1. cd /Users/twinssn/Projects/aikorea24
2. npm run build
3. git add -A
4. git commit -m "설명"
5. git push origin main
6. Cloudflare Pages 자동 빌드/배포

---

## 트러블슈팅 기록

| 문제 | 원인 | 해결 |
|------|------|------|
| client_id=undefined | Cloudflare에서 import.meta.env로 시크릿 접근 불가 | locals.runtime.env로 변경 |
| GOOGLE_CLIENT_ID 공백 | 환경변수명 끝에 스페이스 포함 | 삭제 후 재등록 |
| git push 거부 | api_test/.env.sh가 히스토리에 포함 | git filter-repo로 제거 |
| 공공데이터 API 400 | curl 기본 User-Agent 차단 | -A Mozilla/5.0 추가 |
| .env.sh 덮어쓰기 실패 | 기존 파일 잔존 | rm 후 cat 재생성 |

---

마지막 업데이트: 2026-02-13
