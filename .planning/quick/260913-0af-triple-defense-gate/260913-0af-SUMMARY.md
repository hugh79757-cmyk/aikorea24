---
phase: quick-260913-0af
plan: 01
subsystem: briefing-pipeline
tags: [briefing, language-gate, prompt-leak, triple-defense, title-translation]
requires: [260912-vyc-FINDINGS]
provides: [briefing-3gate, korean-title-gate]
key-files:
  created:
    - tests/test_briefing_gates.py
    - .planning/quick/260913-0af-triple-defense-gate/LIVE-DATA-BACKUP.md
  modified:
    - scripts/auto_briefing.py
commits: [4afaeb66, 7aa4ff6c]
status: complete
---

# Quick 260913-0af: 브리핑 3중 방어 게이트 + 뉴스 제목 언어 게이트 Summary

브리핑 파이프라인에 언어/릭 3중 방어 게이트(생성/저장/저장 후)를 구현하고, 라이브 영어 제목 3건의 근본 원인(news_collector 배치 번역 파싱 실패)을 진단·수정했다.

## Task 1: 기준선 + git 회귀 재검증 [검증됨]

- **기준선 테스트**: `python3 -m pytest tests/test_pitch.py tests/test_briefing_enricher.py tests/test_briefing_scorer.py -x` → **123 passed, 0 failed** (0.48s). 산출 근거: pytest 실행 출력 그대로.
- **git 게이트 부재 재현**: `git show 4f448784^:scripts/auto_briefing.py | grep -ic 'validate\|korean\|gate\|leak'` → **0** (grep exit 1 = 매칭 없음). 4f448784(2026-08-12, 무료 체인 전환) 이전 버전에도 언어 게이트 없었다 — 플래너 결론 "게이트 제거가 아니라 유료 DeepSeek(안전 원인) 제거" 재확认.
- **커밋 이력**: `git log --follow -- scripts/auto_briefing.py` 7개 커밋 전수 확인 — 언어 검증 추가/삭제 커밋 없음.

## Task 2: 3중 방어 게이트 구현 [검증됨]

`scripts/auto_briefing.py` 수정 (137 insertions, 16 deletions — 삭제분은 generate_comment 내부 재작성뿐, 시그니처 불변):

- **새 함수 4개** [PRODUCTION CODE]: `validate_briefing_comment()` (순수 검증기), `verify_briefing_items()` (3차 read-back), `looks_korean()` (한글 정규식), `ensure_korean_title()` (4b 제목 게이트), 내부 헬퍼 `_detect_prompt_leak()` (pitch.py lazy import + 브리핑 라벨 패턴).
- **1차 (생성 직후)**: `generate_comment()` 내부 루프 — 생성→검증→실패 시 재생성, 총 3회 시도, 전부 실패 시 None (기존 실패 경로와 동일하게 main에서 comment="").
- **2차 (저장 직전)**: `save_briefing()` items 루프 — INSERT 직전 `detect_prompt_leak` 1회, 릭 감지 시 해당 아이템 스킵 + 로그.
- **3차 (저장 후)**: `verify_briefing_items(briefing_id)` — main()에서 record_briefing 뒤 호출, try/except로 저장 흐름 영향 0, 감지 row `UPDATE comment=''` 로 라이브 렌더링 차단.
- **시그니처 보존 검증**: `grep -n 'def '` → `generate_comment(article)`, `save_briefing(data)`, `build_briefing(articles)`, `main(selected_articles=None)` 전부 원본 그대로.
- pitch.py 원본 무수정 (lazy import만).

## Task 3: 게이트 테스트 [검증됨]

`tests/test_briefing_gates.py` [TEST CODE] — **19 passed** (0.29s). 구성:
- 순수 검증기 5종 — 오탐 방지 케이스 포함: "OpenAI가 GPT-6를 공개했다. Google Gemini와의 경쟁..." (영어 제품명 포함 한국어) → 통과 확인
- 1차 게이트 2종 — 영어 2회→한국어 순 반환 시 한국어 반환 / 영어만 3회 시 None
- 2차 게이트 2종 — 릭 코멘트 INSERT 스킵 / 정상 코멘트 INSERT 수행 (d1_execute mock 호출 검사)
- 3차 게이트 3종 — 릭 row 감지+UPDATE / 전부 정상 시 UPDATE 0 / D1 예외 시 0 반환
- 제목 게이트 4종 — 한글 제목 통과(LLM/D1 미호출) / 영어 제목 번역+D1 UPDATE / 번역 실패 원문 유지 / LLM 예외 원문 유지

## Task 4: 뉴스 제목 번역 원인 진단 + 수정

### 4a. 원인 규명 [검증됨]

- **삽입 위치**: `api_test/news_collector.py` `save_to_d1()` L1036 `INSERT OR IGNORE INTO news` (repo 전체 grep 'INSERT INTO news' → gov_doc_collector.py 1건 + news_collector.py 1건, 실제 브리핑 소스는 news_collector).
- **번역 실패 메커니즘**: `batch_translate()` L479-499 — 배치 LLM 응답을 "TITLE:"/"DESC:" 라인 파싱해 순서대로 매핑. 응답의 TITLE 라인 수가 배치 항목 수보다 적으면(L488 파싱 누락 또는 모델이 라인 생략), 남은 항목은 L494에서 `original_title`만 설정되고 `title`은 영어 원문 그대로 저장. **언어 게이트가 없어 이대로 INSERT** — FINDINGS 판정(후보 A, 검증 부재)의 제목 필드 버전.
- **D1 실증**: `SELECT id, title, original_title FROM news WHERE id IN (50155,50235,50269,50223,50265,50267)` → 50155/50235/50269 3건 `title == original_title`(영어), 나머지 3건 한국어 title + 영어 original_title. 같은 배치에서 부분 성공 — 배치 파싱 실패 원인과 정확히 일치.

### 4b. 소비지점 게이트 [검증됨]

`ensure_korean_title(article)` — main() 코멘트 생성 루프에서 각 기사에 먼저 적용:
- 한글 부재(`looks_korean()` = Hangul regex `[\uAC00-\uD7A3]`) → model_router 번역 → 한글 확인 후 `UPDATE news SET title=... WHERE id=...` (original_title 보존: 이미 있으면 유지, 없으면 영어 원문으로 채움).
- 번역 실패/예외 시 원문 유지 + 경고 로그 — 파이프라인 중단 없음.
- 테스트 4종으로 검증 (번역 적용/D1 UPDATE/실패 시 원문 유지/예외 시 원문 유지).

### 4c. 라이브 데이터 수정 [검증됨] — 4단계 파괴적 프로토콜

`LIVE-DATA-BACKUP.md`에 전 과정 기록:

1. **사전 백업**: UPDATE 전 SELECT로 원본 3건 title/original_title 기록.
2. **번역 적용** (고유명사 GPT-6/CNBC/Guardian 유지, 직접 번역).
3. **UPDATE 3건 실행** (wrangler, env -u CLOUDFLARE_API_TOKEN).
4. **사후 검증**: post-verify SELECT → 3건 모두 한국어 title, original_title은 영어 원문 유지 (롤백 가능).

| news_id | 수정 전 (영어) | 수정 후 (한국어) |
|---|---|---|
| 50155 | Steve Jones on the pros and cons of AI datacentres – cartoon | 스티브 존스가 그린 AI 데이터센터의 장단점 – 만화 |
| 50235 | GPT-6 Astra appears to show a "step change"... | GPT-6 Astra, 초기 벤치마크에서 공간 추론 '획기적 변화' 보여줘 |
| 50269 | Conversations that AIs are having in the office... | 사무실에서 오가는 AI 대화가 당신의 인사평가와 연봉에 영향줄 수 있다 |

### 4d. 표시 경로 확인 [검증됨]

- 홈페이지 `src/pages/index.astro` L31-36: `SELECT bi.sort_order, bi.comment, n.title ... FROM briefing_items bi JOIN news n` — **news.title을 JOIN으로 직접 조회**.
- 브리핑 상세 `src/pages/briefing/[date].astro` L18-22도 동일 (n.title JOIN).
- `PRAGMA table_info(briefing_items)` → title 컬럼 없음 (id, briefing_id, news_id, sort_order, comment, created_at, deep_dive_url). 스냅샷 없음 → **news 테이블 UPDATE만으로 라이브 홈페이지 즉시 해결**. 근거: 홈페이지가 DB를 실시간 조회하는 SSR (prerender=false) 페이지이므로 재배포 불필요.

## Task 5: 회귀 검증 [검증됨]

전체 스위트 `python3 -m pytest tests/ -q` 비교:

- **기준선 (내 변경 제외, stash로 auto_briefing.py 원복 후)**: 16 failed, 477 passed
- **변경 후**: 16 failed, 496 passed
- **실패 세트 diff**: `diff /tmp/failed_baseline.txt /tmp/failed_with_change.txt` → **IDENTICAL FAILURE SETS** (16건 전부 동일 — 전부 pre-existing, STATE.md 기록된 기존 fail 계열: test_deep_dive_writer, test_failed_articles retention_from_env, test_write_thread_validation 등)
- **산출 근거**: 496 = 477(기존) + 19(신규 게이트 테스트). 실패 16건은 세트 diff로 내 변경 기인 0건 입증. 새 게이트 테스트 19/19 통과.

## Commits

- `4afaeb66` feat(briefing): 3중 방어 게이트 + 제목 언어 게이트 추가 (additive)
- `7aa4ff6c` test(briefing): 3중 게이트 + 제목 게이트 테스트 19종

(.planning/ 문서는 커밋 안 함 — orchestrator 담당)

## Deviations from Plan

- Task 4는 플랜 원문(3 tasks)에 없는 orchestrator 확장 지시 — 본 문서에 전수 기록. Task 1-3은 플랜 그대로 실행.
- `validate_briefing_comment()` 내부에서 pitch.py 원본 대신 보정 없이 분할 전달(`comment[:100]`, `comment[100:300]`) 적용 — 오탐 여부는 테스트로 검증했고 짧은 한국어 코멘트 통과 확인 (validate_korean_output의 15% 임계는 1~2문장 코멘트에서 문제 없음).
- 2차 게이트에 언어 비율 검증 미포함(릭 패턴만) — 플랜 지시대로 (언어는 1차에서 이미 검증).

## Self-Check: PASSED

- tests/test_briefing_gates.py 존재 + 19 passed — 근거: pytest 실행 출력
- scripts/auto_briefing.py 신규 함수 3개 import + callable 확인 — 근거: 위 import OK 출력
- LIVE-DATA-BACKUP.md 존재 (4단계 프로토콜 전 과정 기록)
- 커밋 4afaeb66 / 7aa4ff6c git log 확인

## 잔존 위험

- **news_collector 배치 번역 자체는 수정 안 함** (scope 밖): `batch_translate()` 파싱 실패로 영어 title이 INSERT되는 근원은 그대로. 소비지점 게이트(4b)가 브리핑 경로만 방어 — `/news` 페이지, `/global` 페이지, admin 등 다른 news 소비자는 여전히 영어 title 수신 가능. 근본 수정은 후속 과제 (batch_translate 파싱 검증 + 실패 항목 재시도).
- **제목 게이트는 브리핑 선택 기사(최대 6건)에만 적용** — 시간당 수집되는 전체 news 행의 언어 무결성은 보장하지 않음.
- **LLM 번역 신뢰성**: ensure_korean_title의 번역 품질 검증은 "한글 포함 여부"만 확인 — 번역이 부자연스러워도 통과. 영어 응답 방지는 확인하나 품질 게이트는 없음.
- **briefings.intro는 게이트 범위 밖** — intro는 결정론적 템플릿(현재 안전)이나 향후 LLM 생성으로 바뀌면 별도 게이트 필요.
- **pre-existing 16 실패 테스트** — 본 태스크와 무관함을 diff로 입증했으나 여전히 미해결 (deep_dive_writer 14, failed_articles 1, write_thread_validation 1).
