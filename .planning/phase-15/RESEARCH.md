# Phase 15 — RESEARCH.md

> **Phase:** 15 — Vectorize + 크롤링 실패 수정 + 카드 분할 JSON 전환
> **Researched:** 2026-07-06
> **Researcher:** opencode

---

## A. Vectorize Integration

### A1. 삽입 지점
- `scripts/threads/db_reader.py` `is_already_posted()` (lines 172-179): 4개 exact match 이후, 기존 `is_same_topic()` 이전
- `scripts/threads/db_reader.py` `get_exclusion_reasons()` (lines 221-237): 동일 위치
- **흐름:** exact match → **Vectorize query** → `is_same_topic()` (fallback)

### A2. 임베딩 대상 텍스트
- `original_title + " " + title + " " + description` (영문+한글 모두 포함)
- posted_article_meta의 342건에 대해 임베딩 생성 후 Vectorize에 upsert

### A3. API 자격증명
- `OPENAI_API_KEY`: `.env` line 6, `~/.env.common` line 3 — **확인됨**
- `CLOUDFLARE_ACCOUNT_ID`: `.env` — **확인됨**
- `CLOUDFLARE_API_TOKEN`: `.env` — **확인됨**

### A4. REST API 템플릿
- `scripts/keyword_updater.py` lines 63-79 — D1 REST API 패턴
- Vectorize 엔드포인트: `POST .../vectorize/v2/indexes/{name}/upsert|query`

### A5. 새 파일
- `pipeline/infra/vectorize_client.py` — Vectorize REST API 클라이언트
  - `upsert_vectors(vectors)` — 벡터 저장
  - `query_vectors(vector, top_k=10)` — 유사도 검색
  - `delete_vectors(ids)` — 벡터 삭제

---

## B. failed_crawls TTL

### B1. 치명적 버그 발견
- `failed_crawls.json`의 27개 항목 중 대부분 `article_id`가 빈 문자열 `""` 또는 없음
- `failed_articles.py` lines 77-94: `article_id`가 non-empty일 때만 merge
- **결과:** failed_crawls의 항목이 제외 세트에 로드되지 않음 (데이터 유실)

### B2. 수정 방향
- `failed_crawls.json` 항목에 `expired_at` 필드 추가 (기본 24시간 TTL)
- `failed_articles.py` merge 로직: `article_id` 대신 `url`을 키로 사용
- TTL 만료된 항목은 `load_failed_articles()` 호출 시 자동 제거

### B3. 현재 구조
```json
{
  "failed": [
    {"url": "...", "source": "...", "title": "...", "status": "...", "failed_at": "..."}
  ],
  "updated_at": "..."
}
```

### B4. 변경 후 구조
```json
{
  "failed": [
    {"url": "...", "source": "...", "title": "...", "status": "...", "failed_at": "...", "expired_at": "..."}
  ],
  "updated_at": "..."
}
```

---

## C. Card Splitting JSON Conversion

### C1. 프롬프트 변경 지점
- `pipeline/threads/writer.py` lines 200-213 — `build_system_prompt_D()`의 OUTPUT FORMAT 섹션
- 현재: `{"cards": ["...", "..."]}` → 변경: `[{cardNumber, role, text}, ...]`

### C2. 파서 변경 지점
- `pipeline/threads/writer.py` lines 536-555 — `parse_cards_json_first()`
- 새 형식 감지: 배열의 첫 요소가 dict이고 `text` 키 보유 → `.text` 추출
- 하위 호환: 기존 `{"cards": [...]}` 형식도 여전히 지원

### C3. 제거 대상
- `pipeline/threads/writer.py` `parse_cards()` (lines 512-533) — delimiter fallback
- `pipeline/threads/writer.py` `_repair_truncated_cards()` (lines 481-509)

### C4. 하위 호환
- `parse_cards_json_first()`가 두 형식 모두 처리
- 다운스트림 코드는 모두 `list[str]` 기대 — 추출은 파서 내부에서 처리
- `role` 메타데이터는 검증 로직에서 선택적으로 사용 가능

### C5. role 매핑
| role | 설명 | 검증 |
|------|------|------|
| `hook` | 관심 유도 헤드라인 | 30~350자 |
| `body` | 본문 내용 | 50~500자, 문장 미완성 검증 |
| `twist` | 반전 | body와 동일 |
| `expansion` | 확장 | body와 동일 |
| `closing` | 여운/마무리 | body와 동일 |
| `source` | 출처 링크 | `🔗` 포함 |
