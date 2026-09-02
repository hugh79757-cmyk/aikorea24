# 38-03-SUMMARY — Feedback Injection: 피치 프롬프트 주입

**Status:** ✅ Complete
**Completed:** 2026-09-02

## What was done

- `pipeline/threads/pitch.py`:
  - `_top_topics_hint()` 신규 — `scripts/threads/logs/insights_report.json` 존재 + top_topics 비었지 않을 때만 `"📌 최근 30일 반응 상위 토픽 (참고용, 강제 아님): t1, t2, t3"` 반환. report 없음/빈 top_topics/파일 오류 → `''` (주입 0건, 기존 동작 그대로)
  - 주입 지점 3곳 (기존 프롬프트 변경 아님 — user 프롬프트 말미 append):
    1. `get_pitches()` 본 배치 user 프롬프트 (배치당 1회 산출, 주입 시 로그 1줄)
    2. `get_pitches()` fallback 재요청 user 프롬프트 (동일 hint 재사용)
    3. `_regenerate_pitch_from_crawl()` user_msg 참고 섹션 말미

## Verification

- [검증됨] report 부재 시 `_top_topics_hint() == ''` — 주입 0건. 근거: m0355.
- [검증됨] fixture report → hint에 상위 3토픽 + '참고용, 강제 아님' 문구 포함. report 삭제 → `''` (롤백 = 파일 삭제만). 근거: m0365.
- [검증됨] 주입 문구가 `detect_prompt_leak` 오탐 없음 (프래그먼트/라벨 패턴 미출동) + `validate_korean_output` 회귀 없음. 근거: m0355, m0365.
- [검증됨] 기존 pitch 테스트 회귀: `tests/test_pitch.py` + `tests/test_pitch_evaluator.py` 43 passed. 근거: m0359.
- [부분검증] 실제 LLM dry-run에서 주입 라인 확인 — report 파일이 아직 없음(부트스트랩 3/30건)으로 fixture 테스트로 대체. 복구 계획: 30건 축적 후(약 10-14일) dry-run 로그에서 `📌 성과 상위 토픽 주입 (참고용)` 라인 확인.

## 잔존 위험

- 부트스트랩 기간 (~09-13까지) 주입 없음 — 의도된 동작 (설계상 min_posts=30)
- LLM이 hint 토픽을 hook에 직접 인용할 가능성 — '참고용, 강제 아님' 문구로 완화, 발행 전 validate_korean_output/detect_prompt_leak 3중 방어 존재
