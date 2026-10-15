---
name: aik24-free-models-page
description: Use when editing the aikorea24 free-models page (scripts/free_models_page.py, EmDash slug free-models), its eval table layout, model names, verification display, or its mobile card CSS.
---

# aik24-free-models-page — 무료 모델 페이지 작성법

대상: `scripts/free_models_page.py` → EmDash 글 `free-models`
(`https://emdash.aikorea24.kr/posts/free-models`).
이 페이지의 퀄리티 기준을 고정한다. 아래 규칙을 어기면 대표님 모바일 실측에서 바로 지적받는다.

## 파이프라인 (3개 명령, 순서대로)

```bash
cd /Users/twinssn/Projects/aikorea24 && set -a && . ./.env && set +a
.venv/bin/python3 scripts/verify_models_daily.py   # 호출 검증 → 캐시 갱신 (PASS만 기록, .bak-YYYYMMDD 백업)
.venv/bin/python3 scripts/free_models_page.py page  # 렌더 + EmDash 발행
.venv/bin/python3 -m pytest tests/test_free_models_page.py -q  # 8개 테스트
```

- 검증 방법론은 `model_eval.cli_call()` 재사용 PONG 호출. 방법론 표시: "호출 검증 시각 (KST)".
- 검증 실패 모델은 표에서 빼지 말고 FAIL 표시 + "## 점검 중" 섹션으로.
- 캐시: `free_models_verify.json` 별도 저장. PASS한 것만 캐시에 기록.

## 표 규칙 (5컬럼 고정 — 7컬럼으로 돌이키지 말 것)

헤더: `모델명 | 프로바이더 | 컨텍스트 | 지표 | 상태`

- **모델명 단축**: `:free` / `-free` 접미사만 제거. **org prefix는 유지**
  (kilo nemotron-3.5-lightning vs zen nemotron-3.5-lightning처럼 동명 모델이 있어 prefix를 떼면 구분 불가).
- **지표** = 재사용률 + KiloBench 합침 (`" · ".join`). 둘 다 없으면 빈 셀.
- **상태** = `현재 무료 · {데이터 정책 전문}`. **30자 자름 + "..." 금지** —
  문장은 끝을 맺는다 (2026-10-15 실측 지적 사항, 커밋 `831aa82e`).
- 데이터 정책이 없으면 `현재 무료` 단독. FAIL 모델은 상태가 아니라 점검 중 섹션으로.

## EmDash 발행 제약 (회귀 유발 1순위)

- 발행 경로: `upsert_post` → `md_to_pt(body_md)` → Portable Text.
- **`md_to_pt()`는 HTML을 처리하지 않는다.** HTML 표를 넣으면 태그가 텍스트로 그대로 노출된다 (실증됨).
  표는 **마크다운 표만** 사용. 반응형은 EmDash 렌더러가 담당
  (table PT 블록 → `<div class="emdash-table-wrapper">` + `min-width:576px` 인라인 + `.emdash-table` nowrap CSS).
- "EmDash CSS는 제어 불가"라는 전제로 작업하지 말 것 — 실제로 wrapper/CSS가 이미 있으니 라이브 HTML을 먼저 실측할 것.

## 모바일 카드 CSS (별도 저장소!)

- 위치: `/Users/twinssn/projects2/aikorea24emdash` — `src/styles/theme.css`,
  `article[data-slug="free-models"]` 스코프 (slug 한정이라 다른 글 표에 영향 없음).
- 패턴: 768px 이하에서 thead 숨김, tr 카드, td block, nth-child 라벨
  (프로바이더/컨텍스트/지표/상태), 빈 셀 숨김, 첫 셀(모델명) 크게.
- `article`에 `data-slug={slug}` 속성이 있어야 스코프가 동작한다
  (`src/pages/posts/[slug].astro`).
- **금지어**: `overflow-wrap: anywhere` (글자 단위로 쪼개져서 읽기 불가) → `break-word` 사용.
- CSS 수정 후 EmDash 재배포 → Playwright 375px 실측 (표 341px 이내, 가로 스크롤 없음) → 스크린샷 확인.

## 검증 체크리스트 (발행 전)

1. `pytest tests/test_free_models_page.py` 전부 통과 (컬럼 수·단축명·무자름 테스트 포함).
2. 라이브 HTML 실측: 75셀(15행×5) 중 `...`/`…`로 끝나는 셀 0개.
3. 모바일 375px: 가로 스크롤 없음, 카드형 표시, 스크린샷 1장.
4. 테스트 추가 시: `TAG_ORDER` 전체 키를 `tag_counts`에 넣을 것,
   `select_top_articles` 프로바이더 로테이션 때문에 신선 카드 2건은 서로 다른 `MODEL_SOURCES`여야 통과한다.

## 흔한 실수

| 실수 | 결과 |
|---|---|
| 상태 셀 30자 자름 + "..." | 모바일에서 "사용하는 조..." — 문장 미완성으로 보임 |
| org prefix 제거 | 동명 모델 2건 구분 불가 |
| 마크다운 표를 HTML 표로 교체 | 태그 문자열이 페이지에 그대로 노출 (회귀 확정) |
| EmDash CSS를 aikorea24 저장소에서 수정 | 반영 안 됨 — 저장소가 다름 (`projects2/aikorea24emdash`) |
| 전역 테이블 CSS 수정 | 다른 글 표까지 깨짐 — 반드시 `[data-slug="free-models"]` 스코프 |
