
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
