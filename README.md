# 🤖 AI코리아24 (aikorea24.kr)

> **AI, 누구나 쓸 수 있습니다**

일반인이 AI를 일상에서 쉽게 활용하도록 돕는 한국어 플랫폼

## 📋 프로젝트 개요

| 항목 | 내용 |
|---|---|
| 도메인 | aikorea24.kr |
| 목적 | AI 도구 사용법·강좌·지원사업·뉴스를 한국어로 큐레이션 |
| 벤치마크 | gg24.kr (지원금24) |
| 차별점 | AI 특화 + 바이브코딩 강좌 + 커뮤니티 + SNS 자동배포 |
| 타겟 | ChatGPT를 써본 한국인 일반 사용자 |

## 🏗️ 기술 스택

| 계층 | 기술 | 이유 |
|---|---|---|
| 프레임워크 | **Astro** | 콘텐츠 사이트 최적, CF Pages 공식 지원 |
| 배포 | **Cloudflare Pages** | 무료 무제한 대역폭, 한국 엣지 CDN |
| 인증 | **Better Auth** (Google OAuth) | CF Workers 호환 |
| DB | **Cloudflare D1** (SQLite) | 무료 5GB |
| 파일저장 | **Cloudflare R2** | 무료 10GB, 카드뉴스 + SNS API용 공개 URL |
| 캐시 | **Cloudflare KV** | 무료 일 10만 읽기 |
| 자동화 | **Python + GitHub Actions** | 뉴스수집, 카드생성, SNS배포, DB삽입 |
| SNS | **Threads API** + Instagram Graph API | R2 공개 URL → Meta API 자동 게시 |
| 앱 | **스윙투앱 웹뷰** | 33만원 1회, Phase 4 |

## 📁 사이트 구조

| 경로 | 설명 |
|---|---|
| `/` | 홈 — 주간 AI 도구 픽, 인기 강좌, 지원사업 |
| `/tools` | AI 도구 디렉토리 — 업종별 추천 + 사용법 |
| `/courses` | AI 강좌 — 바이브코딩 기초, GitHub+CF 배포 |
| `/try` | AI 체험 — 프롬프트 템플릿, 직접 해보기 |
| `/grants` | AI 지원사업 — 정부 보조금 자동수집 |
| `/news` | AI 뉴스 — 매일 자동 요약 |
| `/community` | 커뮤니티 — 강좌 Q&A + 익명 라운지 |
| `/my` | 마이페이지 — GitHub 연동, 북마크, 학습 진도 |

## 🔄 자동화 파이프라인 (매일 07:00 KST)

| 스크립트 | 역할 |
|---|---|
| `news_collector.py` | RSS 3개 + 공공데이터 API 4개 → AI 뉴스 수집 |
| `grants_collector.py` | 보조금API + NIPA/IRIS 크롤링 → 지원사업 수집 |
| `card_generator.py` | Pillow → 1080x1080 카드뉴스 이미지 생성 |
| `r2_uploader.py` | R2 버킷 업로드 → 공개 URL 획득 |
| `threads_poster.py` | Threads API → 자동 게시 |
| `instagram_poster.py` | Instagram Graph API → 자동 게시 |
| `d1_inserter.py` | D1 DB 삽입 → 웹사이트 자동 반영 |

## 📡 데이터 소스 현황

### 공공데이터 API (승인 완료 2026-02-12)
- ✅ 과기정통부_사업공고
- ✅ 과기정통부_보도자료
- ✅ 행정안전부_공공서비스(혜택) 정보
- ✅ 재정경제부_국고보조금 공모사업 상세

### RSS (키 불필요)
- ✅ 과기정통부 RSS — AI 18건
- ✅ 정책뉴스 RSS — AI 16건
- ✅ 보도자료 RSS — AI 13건

### 크롤링 (키 불필요)
- ✅ NIPA 사업공고 — AI 11건
- ✅ IRIS R&D 사업공고

## 💰 비용

| 항목 | 비용 |
|---|---|
| Cloudflare 전체 | 월 0원 |
| GitHub Actions | 월 0원 |
| Meta API | 월 0원 |
| 공공데이터 API | 월 0원 |
| 도메인 | 월 1,500원 |
| **런칭 총 월비용** | **1,500원** |

## 📅 작업계획

| Phase | 기간 | 목표 | 릴리즈 |
|---|---|---|---|
| 1 기반구축 | 2/12~2/18 | Astro+CF Pages+D1+R2+Auth | v0.2.0 |
| 2 자동화 | 2/19~2/25 | 파이프라인+Threads 자동배포 | v0.3.0 |
| 3 콘텐츠 | 2/26~3/4 | 강좌+AdSense+SEO | v1.0.0 |
| 4 확장 | 3/5~3/18 | 앱출시+네이버API+OpenAI | v1.1.0 |

## 🎨 브랜딩

- **캐치프레이즈**: AI, 누구나 쓸 수 있습니다
- **주 색상**: #2563EB (일렉트릭 블루)
- **보조**: #7C3AED (바이올렛)
- **포인트**: #14B8A6 (틸)

## 📄 License

MIT
