# aikorea24.kr 프로젝트 SOP

**버전: 2.0**
**최종 업데이트: 2026-02-13**

## 프로젝트 개요
- 사이트: https://aikorea24.kr
- 목적: AI 도구 추천, 무료 강좌, 정부 지원사업 정보, AI 뉴스 한국어 큐레이션
- 핵심 가치: AI가 어떻게 내 호주머니를 불려줄 수 있을까?
- 스택: Astro 5 (SSR) + Cloudflare Pages + D1 + Tailwind CSS 3 + MDX
- 레포: https://github.com/hugh79757-cmyk/aikorea24

---

## 완료된 작업

### 1. 인프라 구축
- Astro SSR 전환 (output: server, @astrojs/cloudflare 어댑터)
- Cloudflare Pages 배포 (커스텀 도메인 aikorea24.kr)
- wrangler.toml 설정 (D1 바인딩, pages_build_output_dir)
- D1 데이터베이스 생성 (aikorea24-db, ID: bec650ce-f732-46bc-87c0-bd76ed17e42a)
- D1 테이블: users, posts, comments, news, payments

### 2. 인증 (Google OAuth)
- Google Cloud Console OAuth 2.0 클라이언트 설정
- 리다이렉트 URI: https://aikorea24.kr/api/auth/callback/google
- Cloudflare 환경변수: GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, AUTH_SECRET
- wrangler pages secret으로 시크릿 등록
- runtime.env로 환경변수 읽기
- /api/auth/login.ts, /api/auth/callback/google.ts 구현

### 3. 뉴스 수집기 (v2.1)
- api_test/news_collector.py: 네이버 뉴스, AI타임스 RSS, 과기부 보도자료/사업공고
- AI 필터 강화: 강한 키워드(AI, GPT, 인공지능 등) + 약한 키워드 2개 이상 조합
- 제외 키워드: 귀촌, 귀어, 교복, 부동산, 스포츠 등
- 중복 방지: 제목 해시 기반, 특수문자 안전 처리
- D1 저장: wrangler d1 execute로 개별 INSERT
- 현재 뉴스 102건 (네이버 83, AI타임스 10, 과기부 4, 정부공문서 1, 기타 4)

### 4. 정부 공문서 AI 학습데이터 API 연동
- api_test/gov_doc_collector.py: 행정안전부 API 연동
- Base URL: http://apis.data.go.kr/1741000/publicDoc
- 엔드포인트: getDocPress(보도자료), getDocReport(정책보고서), getDocSpeech(연설문)
- 필수 파라미터: serviceKey, title (검색 키워드)
- API 키: .env의 DATA_GO_KR_KEY 사용
- news_collector.py에 fetch_gov_docs() 함수로 통합
- 공공데이터포털 활용신청 완료 (개발계정, 일 10,000건)

### 5. 커뮤니티 게시판
- 목록: /community (페이지네이션, 카테고리 필터)
- 글쓰기: /community/write (로그인 필수)
- 상세: /community/[id] (조회수, 댓글)
- 수정/삭제: 본인 글만 가능
- API: /api/posts (CRUD), /api/posts/[id]/comments (댓글)
- D1 스키마: posts (user_id, title, content, category, views, access_level, price, preview_content)
- D1 스키마: comments (post_id, user_id, content)

### 6. 유료/무료 콘텐츠 구분
- posts.access_level: free, basic, premium
- users.membership: free, basic, premium (+ membership_expires, purchased_posts)
- 접근 제어: free=전체공개, basic=로그인필요, premium=유료결제
- 상세 페이지에서 등급 체크 후 미리보기 + 잠금 오버레이
- 목록에서 Basic(노란)/Premium(빨간) 배지 표시

### 7. 결제 시스템
- 토스페이먼츠 연동 코드 완료 (키 미등록 - 테스트 대기)
- API: /api/payments/request.ts, confirm.ts, membership.ts
- 결과 페이지: /payments/success.astro, fail.astro
- 카카오페이 송금 링크 연동 완료: https://qr.kakaopay.com/FFhsfSTOm
- /pricing 페이지 + 홈페이지 후원 배너에 적용
- 토스 비용: 초기 22만원 + 연 11만원 + 거래 3.4% (현 단계에서는 카카오페이로 시작)

### 8. 요금제 페이지
- /pricing: Free, Basic(4,900원/월), Premium(9,900원/월) 카드
- 월간/연간 토글, 카카오페이 후원 버튼 포함

### 9. 다크/라이트 모드
- Tailwind darkMode: class 설정 (tailwind.config.mjs)
- Layout.astro: 테마 토글 버튼 (해/달 아이콘), localStorage 저장
- FOUC 방지: html 인라인 스크립트로 깜빡임 제거
- 적용 완료: Layout.astro, index.astro, news.astro, community.astro, pricing.astro
- 적용 진행 중: community/index.astro, community/write.astro, blog 세부 색상 조정

### 10. 블로그
- src/content/blog/: 마크다운 포스트 8개+
- src/content/config.ts: 컬렉션 스키마 (Zod)
- blog/[...page].astro: 목록 + 페이지네이션 (prerender = true)
- blog/[...id].astro: 개별 포스트 (prerender = true)
- 카테고리 필터, 이모지 매핑

### 11. 모바일 대응
- 헤더 햄버거 메뉴 + 모바일 로그인 버튼 추가
- 반응형 레이아웃 (md: 브레이크포인트)

### 12. 기타 페이지
- /about, /contact, /privacy, /terms
- sitemap.xml 자동 생성 (@astrojs/sitemap)

---

## 주요 파일 목록

- wrangler.toml: Cloudflare 설정
- package.json: 의존성 (Astro 5, Tailwind 3, MDX)
- tailwind.config.mjs: darkMode class
- SOP.md: 이 문서
- api_test/news_collector.py: 뉴스 수집기 v2.1
- api_test/gov_doc_collector.py: 정부 공문서 수집기
- api_test/.env: API 키들
- src/content/config.ts: 컬렉션 스키마
- src/content/blog/: 마크다운 포스트 8개+
- src/layouts/Layout.astro: 공통 레이아웃 (다크/라이트 토글)
- src/lib/auth.ts: 인증 유틸 (getSessionUser, canAccess)
- src/styles/global.css: Tailwind + 테마 변수
- src/pages/index.astro: 홈
- src/pages/news.astro: 뉴스
- src/pages/pricing.astro: 요금제
- src/pages/blog/[...page].astro: 블로그 목록
- src/pages/blog/[...id].astro: 블로그 상세
- src/pages/community/index.astro: 게시판 목록
- src/pages/community/write.astro: 글쓰기
- src/pages/community/[id].astro: 글 상세/댓글
- src/pages/api/posts/index.ts: 글 목록/작성 API
- src/pages/api/posts/[id].ts: 글 상세/수정/삭제 API
- src/pages/api/posts/[id]/comments.ts: 댓글 API
- src/pages/api/payments/: 결제 API (request, confirm, membership)

---

## 환경변수 및 시크릿

### Cloudflare Pages 시크릿 (wrangler pages secret)
- GOOGLE_CLIENT_ID
- GOOGLE_CLIENT_SECRET
- AUTH_SECRET
- TOSS_CLIENT_KEY (미등록)
- TOSS_SECRET_KEY (미등록)

### 로컬 .env
- DATA_GO_KR_KEY: 공공데이터포털 API 키
- NAVER_CLIENT_ID: 네이버 검색 API
- NAVER_CLIENT_SECRET: 네이버 검색 API

---

## D1 데이터베이스 스키마

### users
- id INTEGER PRIMARY KEY
- google_id TEXT NOT NULL
- email TEXT NOT NULL
- name TEXT NOT NULL
- avatar TEXT
- created_at TEXT DEFAULT datetime('now')
- membership TEXT DEFAULT 'free'
- membership_expires TEXT
- purchased_posts TEXT DEFAULT '[]'

### posts
- id INTEGER PRIMARY KEY
- user_id INTEGER NOT NULL
- title TEXT NOT NULL
- content TEXT NOT NULL
- category TEXT DEFAULT 'general'
- views INTEGER DEFAULT 0
- created_at TEXT DEFAULT datetime('now')
- updated_at TEXT DEFAULT datetime('now')
- access_level TEXT DEFAULT 'free'
- price INTEGER DEFAULT 0
- preview_content TEXT
- author_email TEXT DEFAULT ''
- author_name TEXT DEFAULT '익명'

### comments
- id INTEGER PRIMARY KEY
- post_id INTEGER NOT NULL
- user_id INTEGER NOT NULL
- content TEXT NOT NULL
- created_at TEXT DEFAULT datetime('now')
- author_email TEXT DEFAULT ''
- author_name TEXT DEFAULT '익명'

### news
- id INTEGER PRIMARY KEY
- title TEXT
- link TEXT
- description TEXT
- source TEXT
- category TEXT
- pub_date TEXT

### payments
- id INTEGER PRIMARY KEY
- user_email TEXT NOT NULL
- type TEXT NOT NULL
- amount INTEGER NOT NULL
- post_id INTEGER
- plan TEXT
- status TEXT DEFAULT 'pending'
- payment_key TEXT
- order_id TEXT UNIQUE
- created_at TEXT DEFAULT datetime('now')
- expires_at TEXT

---

## 다음 단계 (TODO)

### Phase 1 - 안정화 (우선)
- [ ] 라이트 모드 세부 페이지 마무리 (community/index, write, blog 색상)
- [ ] 커뮤니티 글 수정 페이지 (/community/edit/[id]) 완성
- [ ] 빌드 경고 해결 (blog prerender Astro.request.headers)

### Phase 2 - 자동화
- [ ] GitHub Actions 또는 Cloudflare Workers로 뉴스 수집 크론 (매일)
- [ ] OpenAI 요약 파이프라인

### Phase 3 - 수익화
- [ ] 토스페이먼츠 테스트 키 등록 및 결제 플로우 검증
- [ ] 유료 콘텐츠 제작 및 판매 시작
- [ ] 구독 모델 활성화

### Phase 4 - 확장
- [ ] 뉴스 카테고리 필터 (전체/뉴스/정책/AI타임스)
- [ ] R2 이미지 저장소
- [ ] Workers AI 챗봇
- [ ] 다국어 지원 (영어)
- [ ] PWA 전환
- [ ] 뉴스레터 발송

---

## 변경 이력

| 날짜 | 버전 | 변경 내용 |
|------|------|-----------|
| 2026-02-12 | 1.0 | 초기 SOP 작성 (인프라, 인증, 뉴스, 블로그) |
| 2026-02-13 | 2.0 | 커뮤니티 게시판, 유료콘텐츠, 결제(토스+카카오페이), 다크/라이트 모드, 정부 공문서 API 연동, 뉴스 수집기 v2.1 AI 필터 강화, 모바일 메뉴 개선 |
