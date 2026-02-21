# Changelog

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
