# Phase 15 — SUMMARY.md

> **Phase:** 15 — Vectorize + 크롤링 실패 수정 + 카드 분할 JSON 전환
> **Status:** Planning Complete
> **Created:** 2026-07-06

---

## 의제 요약

| # | 의제 | 핵심 변경 | 파일 |
|---|------|----------|------|
| A | Vectorize 도입 | REST API로 의미적 중복제거 (cosine ≥ 0.85) | `vectorize_client.py`, `db_reader.py` |
| B | 크롤링 실패 수정 | `failed_crawls.json` TTL 24시간 + article_id 버그 수정 | `failed_articles.py`, `failed_crawls.json` |
| C | 카드 JSON 전환 | delimiter fallback 제거, JSON 배열만 | `writer.py`, `validator.py` |

## 작업 요약

| Task | 설명 | 예상 시간 |
|------|------|----------|
| 1 | Vectorize 클라이언트 생성 | 30분 |
| 2 | 임베딩 유틸리티 | 20분 |
| 3 | Vectorize 중복 체크 통합 | 30분 |
| 4 | 기존 기사 마이그레이션 | 15분 |
| 5 | failed_crawls TTL | 20분 |
| 6 | 프롬프트 JSON 전환 | 20분 |
| 7 | 파서 재작성 | 30분 |
| 8 | 검증 조정 | 10분 |
| 9 | 통합 검증 | 20분 |
| **합계** | | **~3시간** |

## 핵심 발견

1. **failed_crawls 버그**: `article_id`가 빈 문자열이라 제외 세트에 로드되지 않음 → `url` 키로 해결
2. **Vectorize 삽입 지점**: `db_reader.py` `is_already_posted()`에서 exact match 이후, `is_same_topic()` 이전
3. **카드 JSON 전환**: 프롬프트 1곳 + 파서 1곳 변경, 다운스트림은 `list[str]` 유지로 영향 없음
