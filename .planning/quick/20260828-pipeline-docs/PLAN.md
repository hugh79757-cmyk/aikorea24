---
title: "파이프라인 가지 문서화"
created: 2026-08-28
status: in-progress
---

# 오늘 새로 만든 파이프라인 가지 문서화

## 목적

오늘(2026-08-28) 구현한 두 가지 파이프라인을 TECH.md에 기록한다:

1. **Abbductive Reasoning Pipeline** (S1-S3 + Evidence Checker) — 브리핑 코멘트에 추론적 해석을 추가하는 모듈
2. **Weekly Contrast Deep Dive Pipeline** (S0-S3) — 주간 대비 분석 블로그 포스트 자동 생성

## 수정 대상

- `docs/TECH.md` — 새 섹션 추가 (기존 구조 보존)

## 문서화할 파일 목록

### Abbductive Reasoning Pipeline
| 파일 | 역할 |
|------|------|
| `scripts/abductive_finder.py` | S1: 뉴스 간 불일치 탐지 (Type A/B/C) |
| `scripts/hypothesis_generator.py` | S2: 10 관점 가설 생성 |
| `scripts/briefing_enricher.py` | S3: 산문 조합 + 브리핑 주입 |
| `scripts/evidence_checker.py` | 공유: 환각 인용 검증 |

### Weekly Contrast Deep Dive Pipeline
| 파일 | 역할 |
|------|------|
| `scripts/weekly_contrast_collector.py` | S0: D1에서 주간 기사 수집 |
| `scripts/contrast_cluster_finder.py` | S1: LLM 클러스터링 + 대비 쌍 탐지 |
| `scripts/deep_dive_writer.py` | S2: 5단락 분석체 블로그 포스트 |
| `scripts/weekly_blog_publisher.py` | S3: Astro 블로그 발행 |
| `scripts/run_weekly_contrast.py` | 오케스트레이터 |
| `docs/weekly-contrast-ops.md` | 운영 가이드 |

### 테스트
| 파일 | 테스트 수 |
|------|----------|
| `tests/test_abductive_finder.py` | 17 |
| `tests/test_hypothesis_generator.py` | 16 |
| `tests/test_briefing_enricher.py` | 18 |
| `tests/test_evidence_checker.py` | 22 |
| `tests/test_contrast_cluster_finder.py` | 20 |
| `tests/test_deep_dive_writer.py` | 15 |
| `tests/test_weekly_blog_publisher.py` | 12 |
| `tests/test_weekly_contrast_collector.py` | 10 |

## TECH.md에 추가할 섹션

### Section N: Abbductive Reasoning Pipeline
- 아키텍처 다이어그램 (S1→S2→S3)
- 각 모듈 시그니처 + 입출력
- evidence_checker.py 공유 모듈
- 환각 방어 3중 레이어
- ENABLE_ABDUCTION 환경변수

### Section N+1: Weekly Contrast Deep Dive Pipeline
- 파이프라인 흐름 (S0→S1→S2→S3)
- launchd 스케줄
- 발행 게이트 (추천/보류/폐기)
- description 신뢰도 검증
- 품질 판단 기준

## 검증

- TECH.md 읽어서 새 섹션 존재 확인
- 기존 섹션 손상 없는지 확인
