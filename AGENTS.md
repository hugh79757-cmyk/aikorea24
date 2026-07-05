
# AGENTS.md — aikorea24.kr

> 프로젝트 루트: ~/Projects/aikorea24
> 작업 로그: /Users/twinssn/Desktop/메모 Hugh/logs/YYYYMMDD.md
> 전역 행동 규칙은 SOUL.md 참조

---

## 문서 성격

| 문서 | 성격 | 언제 읽는가 | 내용 |
|------|------|-----------|------|
| `docs/TECH.md` | **기술 참조 — 고정** | 최초 1회 + 구조 변경 시 | 시스템 아키텍처, 모듈, 프롬프트, DB, 함수 위치 |
| `CHANGES.md` | **세션 이력 — 변동** | **매 세션 시작 시 먼저 읽을 것** | 직전 세션까지의 변경 내역 요약 |
| `AGENTS.md` | **작업 규칙 — 고정** | **매 세션 시작 시 먼저 읽을 것** | 작업 절차, 위임 규칙, 중복 방지 규칙 (지금 읽는 파일) |

## GSD 통합 — CHANGES.md ↔ .planning 연결

- `CHANGES.md`(프로젝트 루트)는 GSD 세션 간 변경 이력의 단일 진실 공급원
- `.planning/CHANGES.md`는 GSD가 참조할 수 있도록 symbolic link (`ln -s ../CHANGES.md .planning/`)
- resume-project workflow는 `.planning/CHANGES.md`를 읽도록 구성

## 세션 시작 시 — `/gsd-resume-work`

`/gsd-resume-work` 명령 또는 에이전트 기동 시 자동 실행:

1. `AGENTS.md`를 **Read** tool로 읽어서 프로젝트 규칙 로드
2. `CHANGES.md`를 **Read** tool로 읽어서 직전 상황 파악
3. `docs/TECH.md`는 최초 1회만 읽으면 됨 (이미 읽었으면 skip)
4. `.planning/STATE.md` 읽어서 현재 phase/진행률 확인
5. `.planning/ROADMAP.md` 읽어서 전체 마일스톤 현황 확인
6. `.planning/triage/INDEX.md` 읽어서 최근 triage 항목 확인
7. **`.continue-here.md` 읽어서 상세 handoff 맥락 복원**
8. `git status`로 작업 트리 상태 확인
9. 사용자에게 현재 상태 요약 제시

## 세션 종료 시 — `/gsd-pause-work`

사용자가 "세션 끝", "종료", `/gsd-pause-work` 명령 시 아래를 수행:

1. `CHANGES.md`에 금일 변경사항 append (포맷 아래 참조)
2. `.planning/STATE.md`의 `last_updated` / `last_activity` 타임스탬프 갱신
3. `.planning/triage/INDEX.md`에 triage 항목이 있으면 함께 기록
4. `/Users/twinssn/Desktop/메모 Hugh/logs/YYYYMMDD.md`에 작업 로그 append
5. 구조 변경이 있었다면 `docs/TECH.md`도 함께 업데이트
6. `.continue-here.md` handoff 파일 업데이트 (필요시)

---

## 서브에이전트 위임 규칙

- 파일 읽기, 코드 분석, 스크립트 실행은 반드시 **opencode**로 위임
- terminal 직접 실행 금지 (cat / grep / find / python3 등)
- opencode 실패 시 → **reasonix code**로 폴백
- reasonix도 실패 시 → 즉시 중단, 사용자에게 보고

---

## 작업 로그 규칙

- 모든 작업 결과를 세션 종료 전
  `/Users/twinssn/Desktop/메모 Hugh/logs/YYYYMMDD.md` 에 append
- 로그 형식:
```

## HH:MM — \[작업 요약]

* 프로젝트: \[경로]
* 결과: \[성공/실패/중단]
* 산출물: \[생성된 파일 경로 등]
* 비고: \[특이사항]
dry-run 결과는 [DRY-RUN] 태그로 구분

---

## 키워드 파이프라인 (outline_generator.py)

키워드 소스: `scripts/keywords.json` (수동 관리, 하드코딩 방식 사용 금지)

### 처리 흐름
1. `keywords.json` 로드
2. 각 키워드의 `db_query` 항목으로 D1 뉴스 DB 검색 (오늘 + 어제)
3. 매칭 기사 있으면 → 키워드 intent + 기사 내용으로 아웃라인 생성
4. 매칭 기사 없으면 → 키워드 intent 만으로 아웃라인 생성 (뉴스 없음 표기)
5. `scripts/outlines/YYYYMMDD/키워드슬러그_outline.md` 저장

### 아웃라인 파일 상단 메타정보
```

* 키워드: {keyword}
* 검색량: {search\_volume}
* 등급: {grade}
* 매칭기사: {매칭된 기사 수}건
* 검색의도: {intent}


## Tools Collection Pipeline (자동 도구 수집기)

> 기술 상세: `docs/TECH.md` Section 10 참조

- **실행**: launchd `kr.aikorea24.tools-collector` → 매일 **06:00**
- **소스**: Product Hunt / GitHub Awesome AI / Futurepedia / HuggingFace / TopAI.tools
- **흐름**: 수집 → 중복 제거 → 웹 크롤링 → DeepSeek 한국어 메타 생성 → im-not-ai 3단계 검증 → MD 저장 → git push → 배포
- **결과물**: `src/content/tools/{slug}.md` (Astro content collection)
- **진입점**: `scripts/tools_collector.py`
- **1회 수동**: `python3 scripts/tools_collector.py --collect --batch 5`
- **주의**: `sys.path.insert`가 `pipeline` import보다 먼저 실행되어야 함 (launchd 환경)

## 중복 발행 방지 (threads 파이프라인)

### 3단계 Semantic Dedup

| 단계 | 파일 | 검사 방식 | threshold |
|------|------|---------|----------|
| Phase 1 | `db_reader.is_already_posted()` | original_title Jaccard + entity overlap | 0.30 / 2개 |
| Phase 2 | `narrative_pitcher.is_duplicate_pitch()` | article_original_titles entity overlap | 2개 |
| Phase 3 | `save_pitch_to_history().entities` | capitalized entity 저장 → 이후 Phase 2에 활용 | — |

- English `original_title` 기준 word Jaccard (stopword 제외, 2글자+)
- `extract_title_entities()`: `\b[A-Z][a-zA-Z0-9.&+#\-]{1,}\b` 패턴
- Phase 1이 가장 강력 (기사 로딩 단계 차단) → Phase 2는 2차 방어

---

## 3중 방어 원칙 (검증 로직 설계 시)

> **"지금은 다됐다"는 결론을 신뢰하지 않는다 — 반드시 터진다.**

### 교훈 (Phase 6 재발 사례)

Phase 6가 피치에만 프롬프트 검증 적용 → "해결됨" → 결국 최종 카드에서 재발.
어떤 검증도 단 한 곳에서만 의존해서는 안 된다.

### 3중 방어 체계

| 방어 | 위치 | 검증 대상 | 실패 시 |
|------|------|----------|--------|
| **1차** | 피치 생성 | `validate_korean_output()` + `detect_prompt_leak()` | 피치 폐기, 재생성 |
| **2차** | 쓰레드 작성 후 | `validate_final_output()` | 카드 재생성 |
| **3차** | 발행 직전 | `validate_cards()` + `validate_final_output()` | 발행 차단 |

### 핵심 규칙

1. **어떤 검증도 단 한 곳에서만 의존하지 않는다**
2. **"해결됨"이라고 안심하지 않는다** — 반드시 회귀 테스트로 확인
3. **검증은 "해당 단계 출력"이 아니라 "다음 단계 입력" 기준으로 설계**
4. **검증 추가 시 스코프 확인** — 해당 단계만이 아니라 다음 단계에도 적용되는지
```
