---
slug: weekly-contrast-thumb-leak
date: 2026-08-29
status: in-progress
---

# 심층분석글 2개 — 썸네일 누락 + 프롬프트릭(A측/B측/대비 소제목) 개선

## 문제
- `weekly-contrast-20260829-001/002` 2건: `image:` frontmatter 없음 + `public/images/thumbnails/` 썸네일 파일 없음 → 블로그 카드에 썸네일 미표시
- 소제목에 기계적 라벨 `A측:` / `B측:` / `대비` 노출 = 프롬프트 구조 지시어가 그대로 릭됨

## 근본 원인 (root cause)
1. `scripts/deep_dive_writer.py` 프롬프트(출력 형식)가 소제목을 `## 대비의 발견` / `## A측:` / `## B측:` / `## 분석: 왜 이런 대비가 발생했는가` 로 지시 → 모델이 라벨 그대로 출력
2. `scripts/weekly_blog_publisher.py` 가 썸네일 생성을 호출하지 않음 (일일 파이프라인의 `auto_thumbnail` 경로와 분리)

## 작업
1. [root] `deep_dive_writer.py` 프롬프트: 소제목을 자연스러운 한국어로 쓰도록 지시 + `A측/B측/대비/측:` 사용 금지 규칙 추가
2. [root] `weekly_blog_publisher.py`: 발행 시 `generate_thumbnails.generate_thumbnail()` 호출 → `image: /images/thumbnails/{slug}.jpg` 주입
3. [재발행] 2건 마크다운 소제목 자연화 + `image:` 필드 추가 + `참고 기사` 중복 블록 제거
4. 썸네일 2건 생성 (`generate_thumbnails.py`)
5. 재배포 (`bash scripts/deploy.sh`)

## 검증
- `validate_blog_posts.py` 통과
- 라이브 `/blog` 에서 2건 썸네일 표시 + 소제목에 A측/B측/대비 없음 확인
