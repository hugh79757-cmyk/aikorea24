# Quick Task Summary — weekly-contrast-thumb-leak (2026-08-29)

## Task
심층분석글 2개(weekly-contrast-20260829-001/002)에 대해:
1. 썸네일 부재 → 생성
2. 프롬프트릭(A측/B측/대비 기계적 소제목) → 자연어화
3. 하단 `참고 기사` / `원문 기사 링크` 중복 → `원문 기사 링크` 섹션 삭제

## Root Cause Fixes (recurrence 방지)
- `scripts/deep_dive_writer.py` [출력 형식]: H2에 A측/B측/대비/측: 등 구조 라벨 금지 규칙 추가, 기계적 소제목 예시 → 자연스러운 한국어 소제목 예시로 교체.
- `scripts/weekly_blog_publisher.py`: 포스트 저장 직후 `generate_thumbnails.generate_thumbnail(slug, title, category="심층분석")` 호출, `image: "/images/thumbnails/{slug}.jpg"` frontmatter 자동 삽입. (미래 자동 생성분도 썸네일 보유)

## Depth Reinforcement (2026-08-29 저녁, m0068)
사용자 지적: "두 기사 이어붙인 꼴, 맥락 너무 짧음". 원인: 기존 프롬프트가 `기사1 요약 → 기사2 요약` 병렬 나열 구조 강제.
- `deep_dive_writer.py` 프롬프트 개편: 5단락(도입/기사1/기사2/분석/전망) → 4섹션 통합 분석 구조(도입 / 두 입장 교차대조 / 본질적 배경 / 전망). 각 본문 섹션 "최소 6문장" 전개 규정, "단순 나열 금지·교차대조 통합" 규칙(11) 추가. `max_tokens` 4000→6000.
- 2건 재생성: 001(인간고유영역)은 새 프롬프트로 재생성(추천, 통합 구조 적용 확인). 002(투자 편의성/보호)는 fallback 모델(gemini)이 원문 없는 인용 생성→환각 게이트 `폐기` 걸림. 따라서 삭제된 원본 검증 인용 보존하며 새 통합 포맷으로 수동 복원(publish_blog_post 호출, 추천).
- 2건 모두 썸네일 재생성, 배포 완료.

## Per-file Edits
### 001 (AI 투자 시대, 편의성과 보호 사이의 갈등)
- image 필드 추가
- 소제목 5건 자연어화 (대비의 발견→편의성과 규제 충돌하는 두 길 / A측:→플랫폼의 거래 편의성 증대 / B측:→금융 당국의 소비자 보호 경고 / 분석:→충돌이 생긴 배경 / 전망:→향후 전망)
- 이미 `### 참고 기사`만 존재 (원문기사링크 블록 없음) → 중복 해당 없음

### 002 (AI 시대, 인간만의 영역은 어디인가?)
- image 필드 추가
- 소제목 5건 자연어화 (대비의 발견→효율성과 인간 고유 가치 엇갈리는 시선 / A측:→제도적 보호를 통한 일자리 보존 / B측:→인간 고유의 창의적 역량 유지 / 분석:→충돌이 생긴 배경 / 전망:→향후 전망)
- `[원문 기사 링크]` 블록 + `---` 구분선 삭제, `### 참고 기사` 목록 유지

## Thumbnails (generated)
- `public/images/thumbnails/weekly-contrast-20260829-001-...jpg`
- `public/images/thumbnails/weekly-contrast-20260829-002-...jpg`

## Verification
- `validate_blog_posts.py` → ✅ 모든 블로그 포스트 정상
- `bash scripts/deploy.sh` → rc=0, 배포 완료 https://aikorea24.kr

## Residual Risk
- **콘텐츠 깊이**: 사용자 지적대로 2건 모두 "두 기사 이어붙인 꼴"로 맥락이 짧음. 본 task는 썸네일+릭+중복섹션 삭제에 한정. 깊이 보강이 필요하면 `deep_dive_writer.py`에 "기사 2건을 단순 나열하지 말고 통합 논점으로 확장(분량/synthesis 가이드)" 규칙 추가 필요 — 별도 task 권장.
- 썸네일은 카테고리 악센트색 단색 배경(텍스트 오버레이) 템플릿 사용. bg_img 없음.
