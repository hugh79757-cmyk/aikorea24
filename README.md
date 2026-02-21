# aikorea24.kr

> 한국어 AI 뉴스 큐레이션 플랫폼

AI 관련 국내외 뉴스를 자동 수집, 번역, 큐레이션하여 한국어로 제공하는 웹사이트입니다.

## 사이트

- **메인**: https://aikorea24.kr
- **운영**: 스타일 팩토리9

## 기술 스택

| 구분 | 기술 |
|------|------|
| 프레임워크 | Astro 5 (SSR) |
| 스타일링 | Tailwind CSS 3 + Typography |
| 배포 | Cloudflare Pages |
| 데이터베이스 | Cloudflare D1 (SQLite) |
| 인증 | Google OAuth 2.0 |
| 뉴스 수집 | Python 3 (네이버 API, RSS, 공공데이터) |
| AI 번역/요약 | OpenAI GPT-4o-mini |
| 카드뉴스 | Pillow + OpenAI (자동 생성) |

## 주요 기능

### 뉴스 수집 (api_test/)

- **국내 뉴스**: 네이버 검색 API, 과기정통부/행안부 보도자료, 정부 공문서
- **해외 뉴스**: TechCrunch AI, MIT Tech Review, Hacker News (v2.0+)
- **AI 기업 공식**: OpenAI, Anthropic, Google DeepMind 블로그 (v2.0+)
- **필터링**: 강화된 AI 관련성 판별 (strong/weak 키워드 + 제외어)
- **중복 제거**: 제목 해시 기반 중복 방지

### 웹사이트 (src/)

- 카테고리별 뉴스 API (latest, policy, benefits, global, official)
- 블로그 (Astro Content Collections, MDX)
- AI 도구 소개
- Google 로그인 + 게시판
- 다크모드 지원

### 자동화

- macOS launchd 스케줄러로 뉴스 수집 자동 실행
- 카드뉴스 자동 생성 후 안드로이드 폰 전송 (KDE Connect)
- 노인복지 브리핑 HTML 자동 생성

## 뉴스 카테고리

| 카테고리 | 설명 | 소스 |
|----------|------|------|
| news / AI | AI 최신 뉴스 | 네이버, RSS |
| policy | AI 정책, 규제 | 네이버, 과기부 |
| benefit | AI 혜택, 지원사업 | 네이버, 공공데이터 |
| senior | 노인복지 (비공개) | 네이버 |
| global | 해외 AI 뉴스 (v2.0+) | TechCrunch, MIT, HN |
| official | AI 기업 공식 발표 (v2.0+) | OpenAI, Anthropic, Google |

## 프로젝트 구조

| 경로 | 설명 |
|------|------|
| api_test/ | 뉴스 수집 Python 스크립트 |
| api_test/news_collector.py | 메인 수집기 |
| api_test/card_news_generator.py | 카드뉴스 생성 |
| api_test/senior_briefing.py | 노인복지 브리핑 |
| api_test/gov_doc_collector.py | 정부 문서 수집 |
| src/pages/api/news/ | 뉴스 API 엔드포인트 |
| src/content/ | 블로그, 도구 콘텐츠 |
| src/lib/auth.ts | 인증 |
| src/styles/global.css | 전역 스타일 |
| schema.sql | D1 데이터베이스 스키마 |
| wrangler.toml | Cloudflare 설정 |

## 로컬 개발

웹사이트:

    npm install
    npm run dev

뉴스 수집:

    cd api_test
    python3 -m venv venv && source venv/bin/activate
    pip install -r requirements.txt
    source .env.sh
    python3 news_collector.py

## 버전 히스토리

| 버전 | 날짜 | 주요 변경 |
|------|------|-----------|
| v2.0.0 | 2026-02-21 | 해외 뉴스 수집, AI 기업 공식 블로그, 필터링 강화 |
| v1.4.0 | 2026-02-16 | 블로그 UI 개선 (썸네일 4:3, 카테고리 필터 하단 이동) |
| v1.3.0 | 2026-02 | Google AdSense, Pinterest 연동 |
| v1.2.1 | 2026-02 | 버그 수정 |
| v1.2.0 | 2026-02 | 노인복지 섹션, 카드뉴스 시스템 |
| v1.1.0 | 2026-01 | 뉴스 수집 고도화, 게시판 |
| v1.0.0 | 2026-01 | 최초 릴리즈 |
| v0.2.0 | 2025-12 | 프로토타입 |

## 라이선스

Private - All rights reserved
