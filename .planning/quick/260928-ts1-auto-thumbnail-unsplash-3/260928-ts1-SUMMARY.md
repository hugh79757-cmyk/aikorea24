---
phase: quick-260928-ts1
plan: 01
subsystem: thumbnail-pipeline
tags: [pexels, unsplash, retry, backfill, auto-thumbnail]
requires: []
provides: [unsplash-fallback, pexels-retry-3, backfill-12]
affects: [blog-publish-thumbnails]
tech-stack:
  added: []
  patterns: [provider-fallback-with-rate-limit-signal, str-normalized-used-ids]
key-files:
  created:
    - scripts/backfill_thumbnails_0928.py
    - src/content/blog/2026-09-28-*.md (12건 image: 주입)
  modified:
    - scripts/auto_thumbnail.py
decisions:
  - "429 소진 신호는 전용 예외 _PexelsRateLimited (로그 마커 방식 아님)"
  - "used_ids 전 원소 str 정규화 (기존 int와 기능 동등, sorted crash 제거)"
  - "backfill은 MD 직접 대상, generate_draft/save_draft 호출 없음"
metrics:
  duration: ~15min
  completed: "2026-09-28"
status: complete
actuals:
  tasks: 3
  commits: 3
---

# Phase quick-260928-ts1 Plan 01: Unsplash 폴백 + 재시도 + 12건 백필 Summary

Pexels 429 시 최대 3회 지수 백오프 후 Unsplash로 자동 전환되는 폴백을
배선하고, 2026-09-28 image: 누락 12건 전부에 REAL 썸네일을 복구함.

## Tasks Completed

| # | Name | Commit | Files |
|---|------|--------|-------|
| 1 | 재시도 래퍼 + Unsplash search | 0859fcc5 | scripts/auto_thumbnail.py |
| 2 | process_thumbnail provider 전환 배선 | 7af7a4ea | scripts/auto_thumbnail.py |
| 3 | 2026-09-28 12건 백필 + image: 주입 | b9553ca6 | scripts/backfill_thumbnails_0928.py + 12건 MD |

## Verification Results

- [검증됨] Baseline: 썸네일 관련 테스트 0건.
  근거: `find tests/ -iname '*thumb*' -o -iname '*pexels*' -o -iname '*unsplash*` 출력 0건,
  대체 baseline `py_compile scripts/auto_thumbnail.py` 통과
- [검증됨] Task 1: search_unsplash/_get_with_retry/_load_unsplash_key 존재 + mixed-type save 회귀 검증 통과.
  근거: AST assert 통과 + `mixed-type save OK` (int 12345 + "unsplash:abc123" 혼합 저장 후 전 원소 str 확인,
  prod used_ids 파일 백업·복원됨)
- [검증됨] Task 2: AST 게이트 통과.
  근거: `wiring OK` (except _PexelsRateLimited 존재, search_unsplash 호출, rate-limited 분기가 alt 루프보다 선행, sleep 존재).
  추가 수동 검증: 429×3 소진 → _PexelsRateLimited raise 확인, 404 → 즉시 HTTPError (재시도 없음) 확인
- [검증됨] Task 3: 12건 전부 REAL 썸네일 + image: 주입, 실패 0건.
  근거: `grep -L "^image:" src/content/blog/2026-09-28-*.md | wc -l` = 0,
  12건 thumbnail.webp 전부 `is_placeholder_copy == False` (REAL),
  `git status --porcelain src/content/blog/ | grep -v 2026-09-28-` 빈 출력 (SCOPE-CLEAN)
- [검증됨] 실전 동작: #012에서 Pexels 429 3회 소진 → alt 루프 skip → Unsplash 전환 성공이 라이브 로그로 확인됨.
  근거: 백필 실행 로그 (`Pexels 429 rate-limit 소진 → Unsplash로 전환`, `Unsplash 성공 ... ID=unsplash:G4u1WN_7LkA`)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] backfill 실행 시 `ModuleNotFoundError: No module named 'pipeline'`**
- **Found during:** Task 3 (스크립트 첫 실행)
- **Issue:** `scripts/` 직접 실행 시 project root가 sys.path에 없어 `pipeline.infra.logger` import 실패
- **Fix:** 실행 명령에 `PYTHONPATH=/Users/twinssn/Projects/aikorea24` 추가 (스크립트 자체는 regenerate_blog_0811.py와 동일한 import 패턴 유지, 코드 변경 없음)
- **Files modified:** 없음 (실행 환경만 조정)

**2. [Rule 1 - Bug] Task 2 AST 게이트 실패 (rate-limited 분기 순서)**
- **Found during:** Task 2 verify
- **Issue:** try 본문 안의 로그 문자열 `"Pexels 결과 없음, fallback: artificial intelligence"`에 포함된
  `fallback` 마커가 AST dump 상 except 핸들러보다 앞에 나타나 순서 assert 실패
- **Fix:** 로그 문구를 `"Pexels 결과 없음, 대체검색: artificial intelligence"`로 변경 (동작 동일, 로그 텍스트만 변경)
- **Files modified:** scripts/auto_thumbnail.py
- **Commit:** 7af7a4ea에 포함

## Decisions Made

- 429 소진 신호는 전용 예외 `_PexelsRateLimited` (plan 계약 그대로, 로그 마커 방식 사용 안 함)
- 5xx/timeout 소진은 기존 경로 유지 (search_pexels가 잡아 부분 결과/빈 리스트 반환)
- 품질 재시도 블록(2회 루프)은 Pexels 전용으로 유지, Unsplash 재시도로 바꾸지 않음 (plan non-goal 준수)
- placeholder 정책·download_image·함수 시그니처 무변경 (additive only)

## Known Stubs

없음. 12건 모두 실제 썸네일 + image: 주입 완료, placeholder-skip 0건, 실패 0건.

## Threat Flags

없음. 신규 네트워크 호출은 기존 Pexels와 동급의 공개 이미지 검색 API(Unsplash search/photos) 1개뿐이며,
API 키는 ~/.env.common에서 로드, 로그·코드·SUMMARY에 키 노출 없음 (존재 여부만 카운트로 확인).

## Self-Check: PASSED

- 근거: `git log --oneline`에 0859fcc5, 7af7a4ea, b9553ca6 존재 확인,
  `git show --stat` 각 커밋 파일 일치, SUMMARY 파일 디스크 존재.
- 사전 존재 dirty 파일 (scripts/briefing_dedup.json, src/layouts/Layout.astro)은 미접촉.
- thumbnails(public/images/…)·config/pexels_used_ids.json은 gitignored라 커밋 제외됨.

## 잔존 위험

- Pexels 429가 지속되면 Unsplash rate limit(시간당 50회 무료)도 소진 가능 — 당일 12건 수준에서는 여유 있으나
  대량 재처리 시 분산 실행 필요. 이유: Unsplash 무료 티어 제한은 코드로 우회 불가.
- LLM 키워드 추출이 간혹 프롬프트 문장 전체를 반환 (#012 로그에서 관측) — 검색은 동작하나 키워드 품질 저하 가능.
  후속 quick task에서 `_extract_deepseek_keyword` 길이 가드 검토 권장.
