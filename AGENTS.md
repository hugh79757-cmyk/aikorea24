
---

## 키워드 테이블 (scripts/keywords.json)

검색 수요 기반 키워드 테이블. 수동 관리, 추후 확장 예정.

### outline_generator.py 수정사항
기존 고단가 키워드 하드코딩 방식 대신 scripts/keywords.json 을 로딩해서 사용할 것.

### 처리 흐름
1. keywords.json 로드
2. 각 키워드의 db_query 항목으로 D1 뉴스 DB 검색 (오늘 + 어제)
3. 매칭 기사 있으면 → 키워드 intent + 기사 내용으로 아웃라인 생성
4. 매칭 기사 없으면 → 키워드 intent 만으로 아웃라인 생성 (뉴스 없음 표기)
5. scripts/outlines/YYYYMMDD/키워드슬러그_outline.md 저장

### 아웃라인 md 파일 상단에 추가할 메타정보
- 키워드: {keyword}
- 검색량: {search_volume}
- 등급: {grade}
- 매칭기사: {매칭된 기사 수}건
- 검색의도: {intent}

---

## 중복 발행 방지 (threads 파이프라인)

### 3단계 Semantic Dedup

| 단계 | 파일 | 검사 방식 | threshold |
|------|------|---------|----------|
| Phase 1 | `db_reader.is_already_posted()` | original_title Jaccard + entity overlap | 0.30 / 2개 |
| Phase 2 | `narrative_pitcher.is_duplicate_pitch()` | article_original_titles entity overlap | 2개 |
| Phase 3 | `save_pitch_to_history().entities` | capitalized entity 저장 → 이후 Phase 2에 활용 | — |

**목적:** 동일 뉴스 이벤트를 다른 매체(Reuters, Guardian, TNW, BBC)가 다르게 보도해도 중복 탐지.
- English original_title 기준 word Jaccard (stopword 제외, 2글자+)
- `extract_title_entities()`: `\b[A-Z][a-zA-Z0-9.&+#\-]{1,}\b` 패턴의 capitalized entity
- phase 1이 가장 강력: 기사 로딩 단계에서 차단 → Phase 2는 2차 방어
