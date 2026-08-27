---
date: 2026-08-26
type: fix
status: resolved
---

# blog_draft_generator KST 날짜 불일치 수정 (tz 경계 버그)

## What
`blog_draft_generator.py`가 UTC 기준 `date.today()`로 브리핑 날짜를 계산하는데, `auto_briefing.py`는 KST 기준 `datetime.now(KST)`로 브리핑을 저장. KST/UTC 자정 경계에서 blog가 2026-08-26 브리핑만 찾고 2026-08-27 브리핑(258/259)을 놓쳐 → 해당 기사 `deep_dive_url`이 null로 남고 블로그 포스트 미생성·사이트 링크 미노출. 두 날짜 기준을 KST로 통일.

## Why
tz 경계 버그. `get_today_briefing_id()`(L121)와 `main()`(L564)가 머신 로컬 UTC를 사용, `auto_briefing`의 KST 저장과 불일치. (사용자 지시 "변경사항 저장" — 이번 세션의 미계획 수정 기록)

## Files changed
- `scripts/blog_draft_generator.py` — L121, L564: `date.today().strftime("%Y-%m-%d")` → `datetime.now(KST).strftime("%Y-%m-%d")` (기존 `KST = timezone(timedelta(hours=9))` 재사용)
- `scripts/auto_news_selector.py` — `route_person_stories(selected)` 추가 + main() 말미 try-except 호출 (person_gate 분기, 격리)
- `pipeline/threads/person_gate.py` — 신규 (LLM 인물 게이트, JSON 펜스 정규화, retries=1)
- `docs/person_gate_patch.md` — 신규 (패치 지시서)

## How
UTC 날짜 소스 2곳을 KST로 교체(최소 diff, 기존 KST 정의 재사용). person_gate는 선별 결과에 LLM 단일 호출로 3판정(비관료 당사자/직접인용/구체적대가), 미통과 시 로그 + kicker7 건너뛰기.

## Verification
- `py_compile` OK.
- `datetime.now(KST)` = 2026-08-27, `get_today_briefing_id()` → 259 반환(이전 257 오판 해소).
- D1 확인: 브리핑 259 아이템 6건 `deep_dive_url` 전부 연결.
- 라이브 신규 포스트 2건 `curl` HTTP 200.
- 브리핑 258(3건 테스트 아티팩트) `status='draft'` 전환(데이터 보존).
- person_gate 패치: 일일 선별 6건 전부 탈락(0/6, 정상), 기존 파이프라인 무결성 확인.
