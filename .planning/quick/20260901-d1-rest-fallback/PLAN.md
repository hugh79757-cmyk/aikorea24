---
slug: d1-rest-fallback
date: 2026-09-01
status: planned
---

# D1 REST API 폴백 — Workers D1 바인딩 우회 경로

## 문제
Cloudflare D1 REST API (`/accounts/{acct}/d1/database/{db}/query`)가 500/7500으로 장애.
`db_reader.py`의 `d1_query()`는 `wrangler d1 execute` CLI를 shell out → REST API 경로 사용 → 기사 로드 불가.
동일 계정의 Workers D1 바인딩은 정상 동작 (aikorea24.kr `/api/briefing/latest` 확인).

## 해결책
1. aikorea24.kr에 `/api/articles/pool` 엔드포인트 추가 (Workers D1 바인딩으로 3단계 기사 쿼리)
2. `db_reader.py`의 `d1_query()`에 HTTP 폴백 추가 (wrangler 실패 시 HTTP API 호출)

## 아키텍처

```
[현재] db_reader.py → wrangler d1 execute (CLI) → REST API → 7500 ❌
[폴백] db_reader.py → wrangler d1 execute → 실패 시 → HTTP GET aikorea24.kr/api/articles/pool → Workers D1 바인딩 ✅
```

## 변경 대상

### 1. `src/pages/api/articles/pool.ts` (신규)
- Astro APIRoute (`GET`)
- `env.DB` (Workers D1 바인딩) 사용
- 쿼리 파라미터: `date` (오늘 날짜, 필수)
- 3단계 쿼리 (db_reader.py의 get_articles()와 동일 로직):
  - 1순위: 오늘 브리핑 기사 (briefing_items JOIN news JOIN briefings)
  - 2순위: 최근 7일 news
  - 3순위: 이전 news (최대 50건)
- 소스 필터: `crawlable_sources.json`의 crawlable + api_based 목록 기반 `AND source IN (...)`
- 반환 형식: `{ "articles": [...], "meta": { "total": N, "p1": N, "p2": N, "p3": N } }`
- 주의: 이 엔드포인트는 중복 제거(posted.json)를 하지 않는다 — 그건 db_reader.py가 담당

### 2. `scripts/threads/db_reader.py` (수정)
- `d1_query()` 함수에 HTTP 폴백 추가:
  - wrangler CLI 실패 (빈 결과 + stderr에 "7500" 또는 "internal error") → HTTP GET으로 폴백
  - 폴백 URL: `https://aikorea24.kr/api/articles/pool?date={today}`
  - 응답 형식: `{ "articles": [...] }` → `list[dict]` 반환
- `get_articles()`는 변경 불필요 (d1_query 반환값 형식 동일)

### 3. 배포
- aikorea24 Pages 배포: `env -u CLOUDFLARE_API_TOKEN /opt/homebrew/bin/wrangler pages deploy dist --project-name aikorea24 --branch main`

## 구현 순서

### Task 1: API 엔드포인트 생성
- `src/pages/api/articles/pool.ts` 작성
- crawlable_sources.json에서 소스 목록 로드하여 SQL WHERE절에 주입
- 3단계 쿼리 + JSON 응답 반환
- 로컬 테스트 불가 (Cloudflare Workers 환경 필요) → 배포 후 라이브 테스트

### Task 2: db_reader.py 폴백 로직
- `d1_query()`에 시그니처 변경 없이 내부 로직 추가
- REST API 감지: stderr에 "7500" 또는 "internal error" 포함 시 폴백 트리거
- HTTP 폴백: `urllib.request` 사용 (이미 import됨)
- 폴백 URL 환경변수: `D1_API_FALLBACK_URL` (기본값: `https://aikorea24.kr/api/articles/pool`)
- 폴백 실패 시 기존처럼 빈 리스트 반환

### Task 3: 라이브 검증
- REST API가 아직 장애 중일 때: `db_reader.py`가 자동으로 HTTP 폴백 사용 확인
- REST API 복구 후: wrangler가 성공하면 폴백 미사용 확인
- aikorea24.kr/api/articles/pool 직접 curl 테스트

## 검증 기준
- [ ] `py_compile scripts/threads/db_reader.py` 통과
- [ ] aikorea24.kr/api/articles/pool에서 JSON 응답 정상 반환
- [ ] REST API 장애 시 db_reader.py가 HTTP 폴백으로 기사 로드 성공
- [ ] REST API 정상 시 db_reader.py가 wrangler CLI 사용 (폴백 미사용)

## 잔존 위험
- aikorea24.kr이 다운되면 폴백도 실패 (단일 장애점 이전)
- API 엔드포인트 인증 없음 — 공개 URL로 기사 풀 노출 (read-only, 기사 제목/링크만)
- aikorea24 Pages 배포 시 기존 기능 회귀 가능성
