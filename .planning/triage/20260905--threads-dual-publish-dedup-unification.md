---
date: 2026-09-05
type: fix
status: resolved
---

# 쓰레드 이중 발행 (18:03 v3 + 18:30 k7) — 중복본 삭제 + 원문병기 제거 + v3↔k7 dedup 통합

## What
같은 기사 48526(TechCrunch OpenAI 에이전트)이 18:03 main_v3, 18:30 kicker7 두 번 발행됨. 18:30 카드에 "(원문: The administrator...)" 영어 원문 병기 존재. 사용자 요청: 중복본 삭제, 원문 표기 제거, 30분 재발행 차단, 자동발행 전면 비활성화.

## Why
- v3(정시 크론)와 k7(30분 오프셋 크론) 발행기 dedup 파일 분리 (posted.json ↔ posted_ids.json) — 서로 발행 이력 못 봄
- k7 초안 k7_48526_20260905_170530은 17:05 수동 run_pipeline.py가 생성 → 18:30 k7 슬롯에서 발행. v3는 18:03 이미 발행
- 원문 병기는 prompts.py 규칙 12의 설계된 동작 (substring 검증용) — 의도된 것이지만 사용자 불호

## Files changed
- `pipeline/threads/contrast/prompts.py` — 3곳(144/171/216행) 병기 요구 문장 → "번역문만, (원문:) 병기 절대 금지"로 교체
- `pipeline/threads/contrast/kicker7_writer.py` — `_strip_redundant_original()` 모든 인라인 (원문:) 무조건 제거로 변경. 카드6 "원문: URL"(괄호 없음)은 미영향
- `scripts/threads/publish_kicker7_drafts.py` — `_v3_posted_links()` 발행 전 체크 + `_record_v3_posted()` 발행 후 v3 posted.json 기록. `datetime.now()`→`datetime.datetime.now()` 버그 수정
- `scripts/threads/logs/drafts/kicker7_selector/posted_ids.json` — 삭제된 18:30본 k7_48526 제거

## How
- 중복본 삭제: Threads API DELETE 6개(루트 18107731334159068 + 카드4 + 링크 답글) — 전부 200
- dedup 통합: posted.json을 단일 진실 공급원으로. k7 발행 전 v3 링크(1,445개) 체크 → SKIP + hold/_v3_dedup 이동. k7 발행 성공 시 역방향 기록
- 자동발행: launchctl bootout+disable (threads-publisher, kicker7-publisher) — b3 조치, print-disabled 확인. 수동 발행만 유지

## Verification
- 삭제: API 응답 200 × 6, 라이브 재확인 400 Object not found(삭제본) / 200(18:03 v3본 유지)
- 원문 제거: py_compile OK + assert 4개 (외국어 병기 제거/한국어 제거/카드6 URL 보존/영어 잔존 0) + grep "원문 앞 30자" 0건
- dedup: assert 6개 (링크 수집/신규 기록/중복 append 없음/고장 파일 graceful). 실 posted.json 1,445 링크 로드 확인
- [검증불가] 라이브 이중 발행 재발 방지 실전 검증 — 자동발행 비활성화 상태라 당분간 발생 자체가 없음. 재개 시 첫 주가 실전 검증
