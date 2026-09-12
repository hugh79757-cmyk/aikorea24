---
phase: quick-260912-vyc
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - .planning/quick/260912-vyc-briefing-pipeline-prompt-leak-rCA/FINDINGS.md
autonomous: true
requirements: [QUICK-260912-briefing-leak-diagnosis]
estimate:
  tokens: 30000
  raw_tokens: 28000
  tasks: 3
  confidence: high

must_haves:
  truths:
    - 실제 릭 증거가 (파일/DB row ↔ 응답한 tier ↔ 릭 패턴) 3열 대응표로 문서화됨
    - 브리핑 체인의 모든 LLM 호출 지점과 각 지점의 검증 적용 여부가 grep 증거와 함께 명시됨
    - 원인이 4개 후보 계층(검증 부재 / tier 모델 특성 / 프롬프트 구조 / 원문 영어 패스스루) 중 primary/secondary로 판정됨
    - FINDINGS.md에 재현 가능한 명령(grep, wrangler SELECT, curl)이 포함됨
  artifacts:
    - .planning/quick/260912-vyc-briefing-pipeline-prompt-leak-rCA/FINDINGS.md
  key_links:
    - D1 briefing_items.comment 라이브 데이터 → 영어 패턴 스캔 → model_router 일일 로그 tier 상관
---

<objective>
브리핑 파이프라인(keywords → outlines → briefing posts)의 한국어 출력에 영어가 섞이는
프롬프트 릭의 근본 원인을 규명한다. 수정이 아닌 진단 보고서가 최종 산출물.

Purpose: 릭이 "검증 부재"인지 "특정 모델 tier"인지 "프롬프트 구조"인지 판정해야
올바른 수정 위치를 정할 수 있다. 잘못된 계층에 패치하면 3중 방어 원칙 위반
(AGENTS.md "3중 방어" 섹션 — 단일 지점 의존) 재발.

Output: FINDINGS.md — 증거 대응표 + 호출 지점 감사 + 원인 판정 + 최소 수정 권고.
</objective>

<execution_context>
@/Users/twinssn/.config/opencode/gsd-core/workflows/execute-plan.md
@/Users/twinssn/.config/opencode/gsd-core/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@AGENTS.md

# 플래너가 이미 확인한 사실 (재조사 불필요, 실행 시 그대로 인용)
- 브리핑 체인 LLM 호출 지점:
  - scripts/auto_briefing.py `generate_comment()` (L44-83) — system 프롬프트에 "순수 한국어" 지시 있음, 안전망 = `remove_chinese()` (한자만, 영어 무대책), temperature=0.3, max_tokens=500
  - scripts/thread_topics/outline_generator.py `generate_outline_with_articles()` (L151) / `generate_outline_no_articles()` (L232) — "한국어로만" 지시 없음, 검증 없음, 원문 title/description 영어 그대로 user_prompt 주입
  - scripts/thread_topics/thread_topic_finder.py L209/L382 — chat_completion 호출 2곳 (감사 대상에 포함)
  - scripts/briefing_enricher.py, briefing_scorer.py — chat_completion 미탐지(룰베이스 추정), 실행 시 확인만
- 검증자 위치: pipeline/threads/pitch.py `detect_prompt_leak()`(L58) / `validate_korean_output()`(L85) — Threads 파이프라인 전용. 브리핑 경로 import 0건 (grep 확인 완료)
- LLM 체인: config/models.yaml 17 tier 무료 회전 + 유료 default. model_router.py `_call_tier_once()`은 `text.strip()`만 반환 — 언어/릭 게이트 없음. JSON 게이트는 response_format=json_object 요청 시에만 작동 (브리핑/아웃라인은 해당 없음)
- 모델 tier 로그: scripts/threads/logs/YYYY-MM-DD.log (model_router `_log_to_file` — tier별 finish_reason/content_len 기록)
- 라이브 렌더링: src/pages/briefing/[date].astro ← D1 briefings/briefing_items
- D1 조회 패턴: `env -u CLOUDFLARE_API_TOKEN /opt/homebrew/bin/wrangler d1 execute aikorea24-db --remote --command "SELECT..."` (AGENTS.md 섹션 3 — CLOUDFLARE_API_TOKEN 반드시 해제)
</context>

<tasks>

<task type="auto">
  <name>Task 1: 라이브 증거 수집 — 릭 샘플 ↔ 응답 tier 상관</name>
  <files>.planning/quick/260912-vyc-briefing-pipeline-prompt-leak-rCA/FINDINGS.md</files>
  <action>
3개 데이터 소스에서 영어 릭 샘플을 수집해 FINDINGS.md의 `## 1. 증거` 섹션에 3열 대응표(릭 샘플 | 출처 파일/DB row | 추정 응답 tier)로 기록한다.

데이터 소스:
1. D1 브리핑 코멘트: wrangler SELECT로 최근 14일 briefing_items.comment 조회 (위 context의 env -u 패턴 사용). 각 row에서 영어 비율 스캔 — 인라인 python 또는 grep. 영어 문장/메타 텍스트(예: "Here is", "Sure,", "코멘트:", 마크다운 펜스) 포함 row 전부 추출.
2. 아웃라인 파일: scripts/thread_topics/outlines/20260625, 20260626 디렉토리 MD 파일을 grep으로 영어 문장 패턴 스캔 (`[A-Z][a-z]+ (is|are|will|has|the) ` 류). 릭이 아닌 정상 영어(제품명, URL, 고유명사)와 구분해 기록 — 제품명은 릭 아님.
3. model_router 일일 로그: scripts/threads/logs/ 최근 로그에서 해당 날짜의 tier 성공 순서와 finish_reason 조합 확인. 릭 샘플 날짜의 `성공: {tier}` 라인으로 어떤 tier가 그 응답을 생성했는지 상관. 로그에 content 스니펫이 없으면 tier 상관은 "추정"으로 명시하고 한계 기록 (3분법: [부분검증]).

주의: 릭 샘플 원문을 그대로 인용한다 — 판단은 Task 3에서, Task 1은 데이터 수집만. wrangler SELECT는 read-only, 절대 INSERT/UPDATE 금지.
  </action>
  <verify>
    <automated>test -s .planning/quick/260912-vyc-briefing-pipeline-prompt-leak-rCA/FINDINGS.md && grep -c '^|' .planning/quick/260912-vyc-briefing-pipeline-prompt-leak-rCA/FINDINGS.md</automated>
  </verify>
  <done>FINDINGS.md에 `## 1. 증거` 섹션 존재, 릭 샘플 3열 표 1행 이상 (0건이면 "증거 0건 + 스캔 범위/명령"으로 기록 — 0건도 유효한 진단 결과). 각 샘플에 출처와 tier 상관(또는 상관 불가 사유) 명시.</done>
</task>

<task type="auto">
  <name>Task 2: 코드 경로 감사 — LLM 호출 지점 × 검증 적용 × tier 리스크</name>
  <files>.planning/quick/260912-vyc-briefing-pipeline-prompt-leak-rCA/FINDINGS.md</files>
  <action>
브리핑 체인 전체를 정적 감사해 FINDINGS.md `## 2. 호출 지점 감사` + `## 3. 원인 후보 분석` 섹션에 기록한다.

1. LLM 호출 지점 전수 목록: context에 나열된 호출 지점 + briefing_enricher.py/briefing_scorer.py 실제 확인(룰베이스면 "LLM 없음"으로 기록). 각 지점별: 프롬프트에 한국어 지시 유무 / 출력 후 검증 유무 / 안전망 종류.
2. 검증 부재 증거: `grep -rn 'detect_prompt_leak\|validate_korean_output' scripts/auto_briefing.py scripts/briefing_*.py scripts/thread_topics/` 결과 0건을 명령 출력과 함께 기록. auto_briefing의 remove_chinese()가 영어에 무력함을 코드 라인 인용.
3. tier 리스크 표: config/models.yaml 17개 tier 각각 영어 응답 경향 평가. 특히: mistral-codestral(코드 특화, 한국어 약함), or-lingvl(비주얼 언어 모델), groq gpt-oss 계열, nvidia nemotron(추론 모델 — thinking 잔여물), qwen reasoning_effort none 처리. "어떤 tier가 응답했든 언어 게이트가 없으면 그대로 통과"가 핵심 구조적 사실임을 model_router.py `_call_tier_once()` L247 `return text.strip()` 라인 인용으로 뒷받침.
4. 프롬프트 구조 분석: outline_generator 2개 함수의 user_prompt에 영어 원문(title/description)이 그대로 들어감 + "한국어로만 작성" 지시 없음 → 모델이 원문 영어를 미러링하는 경로. auto_briefing은 지시 있으나 강제 수단 없음(지시=요청, 게이트 아님).
5. 각 원인 후보(검증 부재/모델 tier/프롬프트 구조/원문 패스스루)에 "가설 → 반박 가능한 확인 방법" 1줄씩.
  </action>
  <verify>
    <automated>grep -c '^## ' .planning/quick/260912-vyc-briefing-pipeline-prompt-leak-rCA/FINDINGS.md</automated>
  </verify>
  <done>`## 2. 호출 지점 감사`(전수 목록 + 검증 유무 표)와 `## 3. 원인 후보 분석`(4후보 × 가설/확인방법) 존재. 검증 부재 grep 명령과 결과 포함. tier 리스크 표에 17 tier 전부 나열됨.</done>
</task>

<task type="auto">
  <name>Task 3: 원인 판정 + 최소 수정 권고</name>
  <files>.planning/quick/260912-vyc-briefing-pipeline-prompt-leak-rCA/FINDINGS.md</files>
  <action>
Task 1 증거 + Task 2 감사를 종합해 FINDINGS.md 마지막에 `## 4. 판정` + `## 5. 수정 권고` + `## 6. 잔존 위험` 섹션을 작성한다.

판정: 4개 후보 중 primary 원인과 secondary 원인을 증거 기반으로 판정. 예상 구조(증거가 다르면 증거 우선): primary = 브리핑 경로 검증 부재(구조적 — 어떤 tier가 영어를 뱉어도 통과), secondary = 트리거(tier 특성 또는 원문 패스스루 — 증거 표의 tier 상관이 담당). 증거 0건이면 "구조적 취약은 코드로 입증됨(부분검증), 라이브 트리거 특정 불가"로 명시.

수정 권고: 구현 아님. 권고만. 최소 수정안: pipeline/threads/pitch.py 기존 `detect_prompt_leak()`/`validate_korean_output()` 재사용(import + 호출 + 실패 시 재생성)을 generate_comment()과 outline 저장 전에 적용 — 신규 코드 작성 없이 기존 검증기 재사용이 최단 경로. 3중 방어 원칙(AGENTS.md)에 맞춰 어느 3개 지점에 게이트를 넣을지 명시. 각 권고에 3분법([검증됨]/[부분검증]/[검증불가]) 태그 — 라이브 재발 방지 검증은 이번 진단 범위 밖임을 명시.

잔존 위험 섹션 필수(전역 규칙): model_router 로그에 content 스니펫 없어 tier 상관이 불완전한 경우, D1 과거 데이터 소실 등.
  </action>
  <verify>
    <automated>grep -c '잔존 위험' .planning/quick/260912-vyc-briefing-pipeline-prompt-leak-rCA/FINDINGS.md && grep -c '^## ' .planning/quick/260912-vyc-briefing-pipeline-prompt-leak-rCA/FINDINGS.md</automated>
  </verify>
  <done>`## 4. 판정`(primary/secondary + 근거), `## 5. 수정 권고`(게이트 위치 3곳, 기존 검증기 재사용), `## 6. 잔존 위험` 존재. 보고서 전체가 3분법 준수 — "완료" 단독 사용 없음, 근거 없는 ✅ 없음.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| D1 remote → 로컬 스크립트 | wrangler SELECT read-only 조회 (진단 전용) |

## STRIDE Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation Plan |
|-----------|----------|-----------|----------|-------------|-----------------|
| T-260912-01 | Tampering | D1 조회 시 실수로 INSERT/UPDATE | medium | mitigate | SELECT 전용 명령만 사용, 원본 데이터 무변경 원칙을 Task 1 action에 명시 |
| T-260912-02 | Info Disclosure | FINDINGS.md에 DB row 원문 인용 | low | accept | 내부 .planning 산출물, 공개 repo 게시 아님 |
</threat_model>

<verification>
- FINDINGS.md 존재 + 6개 `## ` 섹션 (증거/호출 지점 감사/원인 후보/판정/수정 권고/잔존 위험)
- 검증 부재가 grep 명령 출력으로 입증됨
- 모든 판정에 근거(코드 라인 인용, grep 결과, D1 row, 로그) 동반 — 전역 보고 형식 규칙(AGENTS.md 섹션 2) 준수
</verification>

<success_criteria>
- 원인이 primary/secondary로 판정되고 각 판정에 증거가 붙음
- 수정 위치(3중 방어 게이트 3곳)가 구체 명시됨 — 구현은 후속 quick task
- 진단 과정 전체가 read-only (코드 수정 0건, DB 변경 0건)
</success_criteria>

<output>
Create `.planning/quick/260912-vyc-briefing-pipeline-prompt-leak-rCA/260912-vyc-SUMMARY.md` when done
</output>
