---
phase: quick-260912-vyc
plan: 01
subsystem: briefing-pipeline
tags: [diagnosis, prompt-leak, llm-fallback-chain, briefing, outline]
status: complete
requires:
  - "QUICK-260912-briefing-leak-diagnosis 조사 대상: 브리핑 체인 LLM 호출 지점 및 D1/아웃라인 산출물"
provides:
  - "FINDINGS.md — 원인 판정(primary: 검증 부재 / secondary: tier+원문 패스스루) + 3중 방어 게이트 3곳 위치 권고"
  - "후속 수정 quick task의 입력: 게이트 구현 위치 3곳, 기존 검증기(pitch.py detect_prompt_leak/validate_korean_output) 재사용 경로"
affects:
  - "scripts/auto_briefing.py (후속 권고 대상, 본 진단에서 수정 없음)"
  - "scripts/thread_topics/outline_generator.py (후속 권고 대상, 본 진단에서 수정 없음)"
tech-stack:
  added: []
  patterns:
    - "read-only 진단: wrangler SELECT + 정규식 스캔 + grep 정적 감사 (코드 수정 0건, DB 변경 0건)"
key-files:
  created:
    - .planning/quick/260912-vyc-briefing-pipeline-prompt-leak-rCA/FINDINGS.md
  modified: []
decisions:
  - "Primary 원인 = 브리핑 체인 검증 부재(구조적) — model_router L247 return text.strip()에 언어 게이트 없음이 코드로 입증"
  - "Secondary 원인 = tier 특성 + 원문 영어 패스스루 복합 [부분검증] — 유일 실측 릭(반복 루프, 2026-09-11-2)이 nvidia-nemotron 시각대와 일치"
  - "수정 권고 = 신규 코드 없이 pitch.py 기존 검증기 import 재사용, 3중 방어 게이트 3곳(생성 직후/저장 직전/렌더링 직전)"
metrics:
  duration: 29min
  completed: 2026-09-12
  tasks: 3
  files: 1
actuals:
  tokens: 9500    # chars/4 — FINDINGS.md 약 38,000자 / 4, 참조 코드 리딩 제외
  tasks: 3
  commits: 3
---

# quick-260912-vyc: 브리핑 파이프라인 프롬프트 릭 진달 Summary

원-라이너: 브리핑 체인의 프롬프트 릭 원인 진단 — primary=검증 부재(구조적, 코드 입증), secondary=tier+원문 패스스루(추정), D1 최근 14일+전체 이력+아웃라인 745파일 스캔에서 영어 문장 릭 0건, 반복 루프 릭 1건(nvidia-nemotron 시각대).

## What Was Done

3개 진단 태스크 (read-only, 코드 수정 0건, DB 변경 0건):

**Task 1 — 라이브 증거 수집** (commit ec5df3f2)
- D1 briefing_items 최근 14일 150 rows + 전체 이력 1,496 rows(영어 메타 LIKE 8패턴) + briefings.intro 25 rows 스캔
- 아웃라인 MD 745 files 스캔 (영어 문장 패턴 + 기능어 분석)
- 결과: 영어 문장/메타 릭 0건, 정상 고유명사 73건, 반복 루프 릭 1건 (2026-09-11-2 / news_id 49731 — 프롬프트 템플릿을 채우지 않고 재출력하는 미러링 형태, nvidia-nemotron 응답 시각대와 일치 [부분검증])

**Task 2 — 코드 경로 감사** (commit 7dee85a4)
- LLM 호출 지점 9곳 전수 목록: auto_briefing(한국어 지시 O/검증 X/한자 전용 안전망), outline_generator 2개 함수(지시 X/검증 X/영어 원문 직접 주입), thread_topic_finder 2곳(영어 system 프롬프트), abductive_finder·hypothesis_generator(JSON 게이트만), briefing_enricher·scorer(LLM 없음 룰베이스)
- 검증 부재 grep 입증: `detect_prompt_leak\|validate_korean_output` 브리핑 경로 import 0건
- 17 tier 영어 경향 표: 높음 6~7종(codestral, gpt-oss-20b×2, nemotron×2, lingvl, nexmini)

**Task 3 — 원인 판정 + 수정 권고** (commit 631af5c6)
- 판정: primary=검증 부재(A, 통과 조건, [검증됨]), secondary=tier+패스스루 복합(B+D, 트리거, [부분검증])
- 권고: pitch.py 기존 검증기 import 재사용, 3중 방어 게이트 3곳(생성 직후/저장 직전/렌더링 직전) + 아웃라인 경로 _LANG_SECTION 프롬프트 복사
- 잔존 위험 5종 명시 (전역 규칙 준수)

## Deviations from Plan

None — 플랜이 지정한 3 태스크 그대로 실행. D1 조회 중 컬럼명 불일치(`briefings.date` — 플랜 context에 컬럼명 명시 없었음)는 스키마 PRAGMA로 해소, read-only 원칙 유지.

## Verification

[검증됨] 플랜 `<verification>` 기준 —
- FINDINGS.md 존재 + 6개 `## ` 섹션 (증거/호출 지점 감사/원인 후보/판정/수정 권고/잔존 위험): `grep -c '^## '` = 6. 근거: 실행 출력.
- 검증 부재 grep 명령 출력 입증: 2.2절에 명령+exit code 1(0 matches) 기록. 근거: 재현 명령 실행.
- 진단 read-only 무결성: `git log` — 3 커밋 전부 FINDINGS.md 문서 파일만 변경(코드 0건), wrangler 세션에서 SELECT/PRAGMA만 실행(INSERT/UPDATE/DELETE 0건).
- [부분검증] must_haves truths: 3열 대응표는 릭 샘플 1행(반복 루프) — 플랜 done 기준 "0건이면 스캔 범위/명령 기록, 0건도 유효" 조항과 1건 실측 혼합. tier 상관은 로그 content 스니펫 부재로 추정 [부분검증] 태그 유지.

## Known Stubs

없음 — 진단 보고서 산출물에 스텁 없음. 본 태스크는 수정이 아닌 진단이므로 코드 스텁 해당 없음. 수정 권고는 구현체가 아니라 권고로만 존재(플랜 목적상 의도된 것).

## Auth Gates

없음.

## Self-Check: PASSED

- FINDINGS.md 존재 (`test -s` 통과) — 6개 `## ` 섹션, 표 46+행
- SUMMARY.md 존재 (`test -s` 통과)
- 커밋 3건 전부 존재 (ec5df3f2, 7dee85a4, 631af5c6 — `git log` 확인)
- 플랜 verify 자동화 3종 전부 실행 통과 (grep '^|' 10→46행, '^## ' 1→6개, '잔존 위험' 1)

## Next Steps (후속 quick task 후보)

1. 수정 구현 quick task: 게이트 3곳(pitch.py 검증기 import) + 아웃라인 _LANG_SECTION 프롬프트 주입
2. model_router `_log_to_file`에 `content[:80]` 스니펫 추가 — tier↔릭 인과 재현 가능화
3. 릭 목격 사례(브리핑 페이지 URL/날짜) 확보 시 해당 row 재스캔 — 영어 원형 릭 실측
