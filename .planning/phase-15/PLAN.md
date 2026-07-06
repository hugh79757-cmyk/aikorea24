# Phase 15 — PLAN.md

> **Phase:** 15 — Vectorize + 크롤링 실패 수정 + 카드 분할 JSON 전환
> **Mode:** ad-hoc
> **Depends on:** Phase 14
> **Created:** 2026-07-06

---

## Goal

세 가지 개선을 통해 쓰레드 파이프라인의 안정성과 중복 제거 정확도를 향상한다:
1. Cloudflare Vectorize로 의미적 중복 제거 추가
2. failed_crawls.json TTL 적용으로 기사 풀 고갈 해결
3. 카드 분할을 JSON 배열로 전환하여 delimiter 충돌 근본 해결

---

## Task 1: Vectorize 클라이언트 생성

**File:** `pipeline/infra/vectorize_client.py` (신규)

```
1.1 CLOUDFLARE_ACCOUNT_ID / CLOUDFLARE_API_TOKEN 로드
1.2 upsert_vectors(vectors: list[dict]) — 벡터 저장
    - 엔드포인트: POST .../vectorize/v2/indexes/aikorea24-dedup/upsert
    - 페이로드: {vectors: [{id, values, metadata}]}
1.3 query_vectors(vector: list[float], top_k=10) — 유사도 검색
    - 엔드포인트: POST .../vectorize/v2/indexes/aikorea24-dedup/query
    - 페이로드: {vector, topK, filter}
1.4 delete_vectors(ids: list[str]) — 벡터 삭제
1.5 retry 로직 (2회, 지수 백오프)
1.6 에러 시 None 반환 (파이프라인 차단 안 함)
```

**검증:** `py_compile` 통과

---

## Task 2: 임베딩 생성 유틸리티

**File:** `pipeline/infra/vectorize_client.py`에 추가

```
2.1 get_embedding(text: str) → list[float]
    - OpenAI text-embedding-3-small 사용
    - 1536차원
    - 최대 8191 토큰 (truncation)
2.2 embed_article(article: dict) → dict
    - 입력: {id, title, original_title, description}
    - 텍스트: f"{original_title} {title} {description}"
    - 출력: {id, values, metadata: {title, original_title}}
```

**검증:** 임베딩 생성 테스트 (기사 1건)

---

## Task 3: Vectorize 중복 체크 통합

**File:** `scripts/threads/db_reader.py`

```
3.1 import vectorize_client
3.2 is_already_posted()에 Stage 5 추가 (lines 172-179 이후):
    - 임베딩 생성: article의 title + original_title + description
    - Vectorize query: top_k=5, threshold ≥ 0.85
    - 매칭 발견 시 return True
3.3 get_exclusion_reasons()에 동일 로직 추가:
    - 매칭 시 reasons.add('posted_vectorize')
3.4 Vectorize 실패 시 조용히 건너뜀 (None 체크)
```

**검증:** 기존 테스트 회귀 확인

---

## Task 4: 기존 기사 마이그레이션

**File:** `scripts/threads/migrate_to_vectorize.py` (신규, 일회성 스크립트)

```
4.1 posted.json의 posted_article_meta 로드
4.2 각 기사에 대해 임베딩 생성
4.3 벡터 일괄 upsert (10건씩 배치)
4.4 결과 로깅
```

**검증:** 마이그레이션 후 Vectorize 인덱스에 342건 존재 확인

---

## Task 5: failed_crawls.json TTL 적용

**File:** `scripts/threads/failed_articles.py`

```
5.1 load_failed_articles()에서 failed_crawls.json 로드 시:
    - expired_at 필드가 없는 항목: failed_at + 24시간으로 설정
    - expired_at이 현재 시간 이전인 항목: skip (만료)
5.2 save_failed_crawls()에서 expired_at 포함 저장
5.3 FAILED_CRAWLS_FILE의 article_id 없음 문제 해결:
    - url을 키로 사용하여 매칭
```

**File:** `scripts/threads/logs/failed_crawls.json`

```
5.4 기존 27개 항목에 expired_at 필드 추가 (기본: failed_at + 24h)
```

**검증:** 24시간 후 failed_crawls에서 제외 기사 사라지는지 확인

---

## Task 6: 카드 분할 JSON 전환 — 프롬프트

**File:** `pipeline/threads/writer.py`

```
6.1 build_system_prompt_D() OUTPUT FORMAT 섹션 변경 (lines 200-213):
    - 기존: {"cards": ["...", "..."]}
    - 변경: [{"cardNumber": 1, "role": "hook", "text": "..."}, ...]
    - role 목록: hook, body, twist, expansion, closing, source
    - 6카드 유지
6.2 json_schema 설정 변경 (line 583):
    - 기존: {"type": "json_object"}
    - 변경: 배열 스키마 (응답 형식 지정)
```

**검증:** 프롬프트 변경 후 LLM이 새 형식으로 출력하는지 수동 확인

---

## Task 7: 카드 분할 JSON 전환 — 파서

**File:** `pipeline/threads/writer.py`

```
7.1 parse_cards_json_first() 재작성 (lines 536-555):
    - 새 형식 감지: isinstance(data, list) and isinstance(data[0], dict) and 'text' in data[0]
    - 텍스트 추출: [card['text'].strip() for card in data if card.get('text')]
    - 카드 수 검증: FORMAT_CARD_COUNT_TOLERANCE
    - 하위 호환: isinstance(data, dict) and 'cards' in data → 기존 로직
7.2 parse_cards() 제거 (lines 512-533)
7.3 _repair_truncated_cards() 제거 (lines 481-509)
7.4 parse_cards_json_first() 실패 시 빈 리스트 반환 (fallback 없음)
```

**검증:** JSON 파싱 테스트 (새 형식 + 기존 형식)

---

## Task 8: 카드 분할 JSON 전환 — 검증 조정

**File:** `pipeline/threads/validator.py`

```
8.1 validate_cards() — 변경 없음 (list[str] 기대)
8.2 validate_card_structure() — 변경 없음 (list[str] 기대)
8.3 validate_final_output() — 변경 없음 (list[str] 기대)
8.4 모든 검증이 list[str]을 기대하므로, 파서에서 text를 추출하면 다운스트림 영향 없음
```

**검증:** 기존 검증 테스트 회귀 확인

---

## Task 9: 통합 검증

```
9.1 py_compile: 변경된 모든 파일
9.2 기존 테스트 실행 (pytest tests/)
9.3 run_pipeline.py --dry-run 정상 동작
9.4 수동 테스트: 기사 1건으로 쓰레드 생성 → JSON 배열 출력 확인
```

---

## Task Summary

| # | Task | 예상 시간 | 의존성 |
|---|------|----------|--------|
| 1 | Vectorize 클라이언트 | 30분 | — |
| 2 | 임베딩 유틸리티 | 20분 | 1 |
| 3 | Vectorize 중복 체크 통합 | 30분 | 1, 2 |
| 4 | 기존 기사 마이그레이션 | 15분 | 1, 2 |
| 5 | failed_crawls TTL | 20분 | — |
| 6 | 프롬프트 JSON 전환 | 20분 | — |
| 7 | 파서 재작성 | 30분 | 6 |
| 8 | 검증 조정 | 10분 | 7 |
| 9 | 통합 검증 | 20분 | 1~8 |
| **합계** | | **~3시간** | |

---

## Success Criteria

1. ✅ `pipeline/infra/vectorize_client.py` 생성 및 py_compile 통과
2. ✅ `is_already_posted()`가 Vectorize 쿼리 포함 6단계 중복 체크
3. ✅ 기존 342건 기사 Vectorize에 저장
4. ✅ `failed_crawls.json`에 `expired_at` 필드, 24시간 TTL
5. ✅ LLM 출력이 `[{cardNumber, role, text}]` 형식
6. ✅ delimiter fallback 제거, JSON-only 파싱
7. ✅ `_repair_truncated_cards()` 제거
8. ✅ 기존 테스트 회귀 없이 통과
9. ✅ `run_pipeline.py --dry-run` 정상 동작
