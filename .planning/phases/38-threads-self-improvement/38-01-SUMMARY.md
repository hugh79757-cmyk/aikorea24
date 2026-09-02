# 38-01-SUMMARY — Measurement: 발행 메타 기록

**Status:** ✅ Complete
**Completed:** 2026-09-02

## What was done

- `scripts/threads/performance_log.py` 신규 (~270L, 전 Phase 38 로직 통합):
  - `PERF_LOG = scripts/threads/logs/performance_log.json`, `_load()/_atomic_save()` (tmp→rename)
  - `record_publish(root_id, posted_at, fmt, article_id, title, source, topic_tags=None)` — posts 배열 append, 스키마: `{root_id, posted_at, format, article_id, title, source, topic_tags, metrics:null}`
- `main_v3.py` 발행 성공 블록 line 430 직후 (`_log_api_based_publish` 인근) +16줄 삽입 — try/except 감싸 실패 시 `⚠️ 성과 로그 기록 실패 (무시)` 로그만, 발행 흐름 무영향. dry-run은 별도 분기라 미삽입 (root_id 없음)
- `test_performance_log.py`: record_publish 스키마/지속성 검증

## Verification

- [검증됨] `py_compile` 통과, test 5/5 (test_record_publish: 2건 기록, 8개 스키마 필드, 재로드 지속성). 근거: pytest 실행 출력 m0331.
- [검증됨] 라이브 발행 건 백필 3건 → performance_log.json에 기록 확인 (18122058901870182 / 18426508516181136 / 18006332270978685). 근거: m0336 수집 로그.
- [부분검증] main_v3 삽입 경로의 실발행 검증 — 22:04 발행 건은 삽입 전 코드로 발행됨. 삽입 후 첫 발행은 2026-09-03 00:00 슬롯. 제한 사유: 코드 디스크 반영은 확인(컴파일+import 성공)이나 프로세스 실행 대기. 복구 계획: 09-03 아침 로그에서 `📊 성과 로그 기록 완료` 라인 확인.
