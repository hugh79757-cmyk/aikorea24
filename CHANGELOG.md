# Changelog

## [v2.4.0] - 2026-06-27

### 브리핑 시퀀스 접미사 시스템
- `auto_briefing.py`: `save_briefing()`가 `date LIKE '{today}%'`로 기존 브리핑을 찾아 `-1`, `-2` 접미사 자동 부여
- `publish.ts POST`: 시퀀스 계산 후 `{date}-{seq}` 형식으로 INSERT (덮어쓰기 방지)
- `publish.ts DELETE`: `WHERE date LIKE ? ORDER BY id DESC LIMIT 1`로 최신 시퀀스 삭제
- `briefing/index.astro`, `[date].astro`: `b.date.substring(0,10)`으로 접미사 제거 후 Date 파싱
- `BriefingSection.astro`: `formatDate()`에서 접미사 분리 처리
- `sitemap-briefing.xml.ts`: LIKE 검색으로 모든 시퀀스 포함
- `admin/index.astro`: 수정/발행 시 시퀀스 지원

### 팬텀 브리핑 방지
- `run_pipeline.py`: `step_briefing([])`이 `[]`(falsy)일 때 `None` 반환 (빈 `auto_briefing.main()` 호출 차단)
- `step_briefing(articles)` → `articles`가 `[]`이면 로그만 남기고 건너<0xEB><0x9C><0x8D>

### 크롤러 고도화 (`auto_deep_article.py`)
- User-Agent 강화 (Chrome 125 full UA + Accept 헤더)
- CSS 셀렉터 확장 (`.ArticleBody-articleBody`, `.article-body`, `.story-body`, `.story-text`, `[class*="articleBody" i]`)
- `body` 폴백 추가 (기존 셀렉터가 모두 실패할 경우 body 전체 텍스트 추출)

### 프롬프트 구조 개선
- `auto_deep_article.py DEEP_ANALYSIS_PROMPT`: `## 서론: ...` → `## ...` (소제목만)
- `## 결론: ...` → `## 마무리: ...` 로 변경

### H1 중복 제거
- 10개 블로그 파일에서 body 내 `# ` (h1) → `## ` (h2) 일괄 교체 (타이틀 중복 방지)

### D1 정리
- id=134 (0건 고아 브리핑), id=136 (팬텀 1건) 삭제

## [v2.3.0] - 2026-06-27

### 브리핑 파이프라인 v1
- `scripts/run_pipeline.py`: 6단계 자동화 (뉴스선정→브리핑→심층글→썸네일→이메일→배포)
- `scripts/auto_briefing.py`: MiMo API 뉴스 코멘트 생성, D1 저장
- `scripts/auto_email_sender.py`: Brevo API 이메일 발송 (listIds=[2])
- `scripts/auto_deep_article.py`: 심층글 생성 + `briefing_items.deep_dive_url` 자동 연결
- `scripts/deploy.sh`: npm build → wrangler pages deploy (Cloudflare Pages)
- `scripts/run_pipeline_with_notify.py`: launchd 래퍼 + 텔레그램 알림

## [v2.2.0] - 2026-06-10

### 동적 키워드 파이프라인 (신규)
- `scripts/keyword_updater.py`: D1 오늘 뉴스 기반 키워드 동적 추출 (gpt-4o-mini)
  - 네이버 검색광고 API 검색량/경쟁도 조회 (HMAC-SHA256 인증)
  - grade 자동 계산 (S: 10만+, A: 3만+ or 경쟁높음, B)
  - intent + db_query 자동 생성 (gpt-4o-mini 배치)
  - seeds.json 고정 키워드 + 뉴스 신규 키워드 병합, `source` 필드 구분
  - keywords.json 자동 갱신 (백업 `keywords.json.bak` 포함)
  - 실행: 매일 06:00 (launchd)

### 스레드 글감 생성기 (신규)
- `scripts/thread_topic_finder.py`: D1 뉴스 클러스터링 → 스레드 아웃라인
  - 1차: title 기반 클러스터링 (gpt-4o-mini)
  - 스코어링: 해외+국내 교차(+3), data_points 3개+(+2), contrast_possible(+2), 기사 3개+(+1)
  - Top 5 소재 → gpt-4o 아웃라인 생성 (훅/반전/스레드 7단계 구조)
  - 저장: `scripts/threads/YYYYMMDD/소재슬러그_thread.md`
  - 실행: 매일 06:10 (launchd)

### 저장 경로 변경
- `outline_generator.py`: `outlines/YYYY-MM-DD-*_outline.md` → `outlines/YYYYMMDD/*_outline.md`
- `thread_topic_finder.py`: `threads/YYYY-MM-DD-*_thread.md` → `threads/YYYYMMDD/*_thread.md`
- 날짜 prefix를 파일명에서 제거하고 날짜 폴더로 분리

### 기타
- `scripts/seeds.json` 신규 (베이스 씨드 키워드 관리)
- `AGENTS.md`: 아웃라인 저장 경로 정보 업데이트
- `README.md`: 파이프라인 구조, 프로젝트 구조 테이블 업데이트

## [v2.0.0] - 2026-02-21

### 해외 AI 뉴스 수집 (신규)
- TechCrunch AI, MIT Technology Review, Hacker News RSS 수집
- GPT-4o-mini 한국어 번역 (제목 + 설명)
- 카테고리 'global'로 D1 저장

### AI 기업 공식 발표 수집 (신규)
- OpenAI, Anthropic, Google DeepMind 블로그 수집
- 카테고리 'official'로 D1 저장
- 전용 API 엔드포인트 추가

### 국내 뉴스 필터링 강화
- 중복 기사 제거 (동일 주제 다른 언론사)
- 카테고리 오분류 방지 (policy, benefit 정확도 향상)
- 제외어 목록 확대

### 배치 전략 개선
- 소스별 분리 실행 (--source kr / global / official)
- 시간대별 최적 스케줄링

### 프로젝트 문서 정비
- README.md 전면 재작성
- CHANGELOG.md 체계화
- package.json 버전 동기화

## [v1.4.0] - 2026-02-16

### 블로그 UI 개선
- **썸네일 비율 변경**: `aspect-video`(16:9) → `aspect-[4/3]`(4:3)로 변경하여 정사각형 이미지가 잘리지 않도록 개선
- **카테고리 필터 하단 이동**: 블로그 목록 상단에 있던 카테고리 태그 버튼을 하단(페이지네이션 아래)으로 이동
- **카테고리 필터 5개 제한**: 전체 카테고리 노출 → 최대 5개만 표시
- **다크모드 보강**: 블로그 목록 페이지 카드, 텍스트, 버튼에 다크모드 클래스 추가
- **홈 LatestBlog 동기화**: 홈페이지 최신 블로그 섹션도 동일 비율(4:3) 적용

### 수정 파일
- `src/pages/blog/[...page].astro`
- `src/components/home/LatestBlog.astro`

---

## [v1.3.0] 이전
- Google AdSense 스크립트 추가
- Pinterest 연결 및 도메인 인증
- Astro 블로그 발행 시스템
