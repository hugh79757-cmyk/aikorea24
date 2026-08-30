---
date: 2026-08-29
type: fix
status: resolved
---

# weekly-contrast 포스트 썸네일·프롬프트릭·중복섹션·깊이 보강

## What
주간 심층분석 2건(weekly-contrast-20260829-001/002)에 대해: (1) 썸네일 부재 생성, (2) A측/B측/대비 기계적 소제목 프롬프트릭 자연어화, (3) 하단 `원문 기사 링크` 중복 섹션 삭제, (4) "두 기사 이어붙인 꼴" 병렬 나열 → 통합 분석 구조로 깊이 보강.

## Why
- 썸네일: `weekly_blog_publisher.py`가 image frontmatter 생성 안 함 (다른 포스트는 generate_thumbnails로 보유).
- 프롬프트릭: `deep_dive_writer.py` 프롬프트가 `## A측:`/`## B측:`/`## 대비의 발견` 등 라벨 소제목을 예시로 강제.
- 중복섹션: 발행 로직이 본문 하단에 `원문 기사 링크` + `### 참고 기사`를 모두 붙임.
- 얕음: 프롬프트가 `기사1 요약 → 기사2 요약` 병렬 구조 강제 → 통합 분석 부재.

## Files changed
- scripts/deep_dive_writer.py (프롬프트 4섹션 통합 개편, A측/B측/대비 금지, max_tokens 4000→6000)
- scripts/weekly_blog_publisher.py (generate_thumbnails 연동, image frontmatter 자동 삽입)
- src/content/blog/weekly-contrast-20260829-001-ai-시대-인간-고유-영역을-지키는-법.md (재생성)
- src/content/blog/weekly-contrast-20260829-002-ai-투자-시대-편의성과-보호-사이의-갈등.md (수동 복원)
- public/images/thumbnails/weekly-contrast-20260829-00{1,2}.jpg (gitignore 대상, Pages 직배포)
- .planning/STATE.md, .planning/quick/20260829-weekly-contrast-thumb-leak/SUMMARY.md

## How
- 루트픽스: deep_dive_writer 프롬프트를 5단락 병렬 → 4섹션 통합 분석(도입/교차대조/본질적 배경/전망)으로 교체, "단순 나열 금지·교차대조 통합" 규칙 추가.
- weekly_blog_publisher가 저장 직후 generate_thumbnail 호출해 image 필드 삽입.
- 001은 새 프롬프트로 LLM 재생성(추천). 002는 fallback 모델(gemini)이 원문 없는 인용 생성→환각 게이트 폐기 → 삭제된 원본 검증 인용 보존하며 통합 포맷으로 수동 복원.
- 원문 기사 링크 블록 제거, 참고 기사만 유지.

## Verification
- scripts/validate_blog_posts.py → ✅ 모든 블로그 포스트 정상
- bash scripts/deploy.sh → rc=0, https://aikorea24.kr 배포 완료
- 커밋: 952391b (썸네일/릭/중복), c0af9ee (깊이 보강)
