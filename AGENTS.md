
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
| `docs/state.md` | **작업 스테이트먼트 — append-only** | 작업 완료 시 기록 | 프로젝트 전체 작업 기록 (9,597줄). **도구로만 추가한다** |

## state.md 기록 규칙 — 도구로만 추가 (AIK24-STATE-GUARD-01)

`docs/state.md` 는 **append-only** 다. 기존 항목은 삭제하지 않는다.

| 용도 | 명령 |
|------|------|
| 보고를 맨 위에 추가 | `python3 scripts/state_prepend.py --report <보고서.md>` |
| 과거 기록을 맨 아래에 추가 | `python3 scripts/state_prepend.py --report <파일> --bottom` |
| 현재 통계 확인 | `python3 scripts/state_prepend.py --stats` |
| 미리보기 (쓰지 않음) | 위 명령에 `--dry-run` |
| 오래된 항목 아카이브 | `python3 scripts/state_rotate.py --days 30` → 확인 후 `--apply` |
| 감소 가드 단독 확인 | `python3 scripts/state_guard.py --old origin/main --new HEAD` |

- 도구는 ① 기존 헤딩이 하나라도 사라지면 **쓰기를 거부** ② 쓰기 전 백업(`docs/state.md.bak.YYYYMMDD_HHMM`)
  ③ 쓰기 후 재검증 실패 시 **자동 복원** ④ 읽기~쓰기 사이 외부 변경 감지 시 중단 을 수행한다.
- **금지**: `open('docs/state.md','w').write(...)` 로 직접 쓰기. 특히 아래 형태는 기존 기록을 전부 지운다.
  ```python
  open(p,'w',encoding='utf-8').write(new + open(p,encoding='utf-8').read())  # ← 금지
  ```
  파이썬이 인자를 왼쪽부터 평가해 모드 `w` 가 **먼저** 파일을 0바이트로 자르고, 그 다음 읽어 `''` 를 붙인다.
  exit 0 + "기록 완료" 가 함께 출력되어 **조용히** 터진다. (2026-10-14 6,550줄 / 2026-10-17 2,805줄)
- pre-push 훅(정본 `scripts/hooks/pre-push`)이 state.md 가 100줄 이상 줄면 push 를 차단한다.
  의도적 감소만 `ALLOW_STATE_TRUNCATE=1 git push` 로 우회한다.
- 사고 복구: `git show <사고커밋>^:docs/state.md` 로 사고 직전 버전을 꺼내 `--bottom` 으로 복원한다.

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

---

## Cloudflare Auth Profile (2026-07-14 설정)

> **문제**: OpenCode/Codex agent가 매 세션 `CLOUDFLARE_API_TOKEN` 환경변수를 설정 → wrangler auth profile보다 우선 적용되어 Pages 배포 실패 (`Authentication error code: 10000`)

### 현재 설정

| Profile | Bind Directory | 계정 |
|---|---|---|
| `hugh79757` | `/Users/twinssn/Projects/aikorea24` | hugh79757@gmail.com |
| `farmsolution` | `/Users/twinssn/projects2/farmsolution` | farmsolution 계정 |

### 권장: 배포는 scripts/deploy.sh 하나로 (2026-10-17 현행화)

- 배포는 Pages → Workers 전환 완료. `wrangler pages deploy` 방식은 폐기.
- `scripts/deploy.sh`가 .env의 신계정 자격(`$EXPECTED_ACCOUNT_ID` 가드)을 검증하고
  homebrew wrangler 4.110+ 로 `wrangler deploy`를 3회 재시도한다.
- deploy 대상 설정은 Astro 7 빌드가 등록하는 `.wrangler/deploy/config.json`
  (dist/server/wrangler.json) 체인으로 확정된다. 루트 wrangler.jsonc 는 main 이 없으므로
  `--config wrangler.jsonc` 로 지정하면 assets-only Worker 로 오인해 3회 연속 실패 — 지정 금지.
- wrangler.toml(Pages 잔재)은 2026-10-17 삭제(참조 0건, 커밋 08088f55).

### D1 읽기 예산 가드 (2026-10-17)

모든 D1 사용 스크립트는 `scripts/cfnew.py` 의 `check_quota(threshold=0.8)` 를 경유한다 —
읽기 80% 초과 시 작업 중단. 사양: `docs/d1-budget.md`.

### .zshrc 함수 (interactive shell 전용)

`.zshrc` lines 84-99에 wrangler 함수 이미 정의 — `CLOUDFLARE_API_TOKEN` 등 4개 env var를 자동 unset/restore.

### deploy.sh (이전 "수정 필요" 표기는 해제 — 이미 Workers deploy로 정상화됨)

과거 기록: `scripts/deploy.sh`가 과거 `npx wrangler pages deploy`를 쓴 적이 있으나,
현재는 `wrangler deploy`(Workers, Assets)로 동작하며 2026-10-17 실측 배포 성공.
`env -u CLOUDFLARE_API_TOKEN …` 우회 조치는 더 이상 필요하지 않다 —
deploy.sh 가 .env 의 신계정 자격을 명시 검증한다(위 "권장" 섹션 참조).

### 참고

- 상세: `.planning/triage/20260714--wrangler-auth-profile-setup.md`
- wrangler 4.110.0 이상에서 auth profiles 지원 (2026-07-14 업그레이드 완료)
```
