# Phase 39 Context — Compass 2-pass Korean Article Writing Pipeline

## Goal (verbatim from user)

Create a new GSD phase 39 for the Korean article-writing Compass 2-pass system.

## Stated Requirements (verbatim)

- A **Compass 2-pass writing system**:
  - **Pass 1** emits a JSON **compass** with fields:
    - `category`
    - `slot1_fact`
    - `slot2_compare`
    - `slot3_context`
    - `slot4_outlook`
    - `intro_style` (5-pattern rotation)
    - `h2_flow` (category presets)
    - `tone` (`neutral_careful` / `fan_friendly` / `analytical`)
    - `table_plan`
  - **Pass 2** drafts the body from that compass.
- Must include a **G4 fact-gate** that blocks `slot3` claims not supported by sources.
- Must support **writeArticle** execution and inspection of compass + body.
- Goal: verify the structure actually fills all 4 slots, follows `h2_flow`, and rotates `intro_style`, and to diversify writing patterns.

## Constraints

- Do not modify any existing phase or production code.
- New phase must not rename or renumber existing phases.
- Existing codebase conventions: Python 3.14, stdlib only for new pipeline modules, `pipeline/threads/` is the Threads writing module home, JSON-first parsing pattern from Phase 14, fact-gate / source-citation patterns from Phase 28-05.

## Scope

- **In scope**: Revising compass.py prompts and Pass 2 writing logic to fix 5 identified issues from live dry-run.
- **Out of scope**: New modules, new phases, structural changes.

## Replan Feedback (2026-09-21) — 5 Issues from Live Dry-Run

User reviewed compass blog output ("전력부터 냉각·GPU까지…GS, AI 데이터센터 밸류체인 강화") and identified 5 structural issues. The compass JSON was generated correctly (9 fields present) but the Pass 2 body draft has writing-logic failures.

### Issue 1: H2 순서 뒤집힘

현재: "향후 전략과 전망"이 맨 위, "시장 배경과 규모"가 중간.

문제: 독자는 "무슨 일이 있었는지" 먼저 알아야 맥락·전망에 관심. 지금은 결론부터 말하고 근거를 나중에 대는 형태.

요구: 팩트 → 비교 → 맥락 → 전망 순서. compass 슬롯 순서와 H2 흐름이 일치해야 함. Pass 2 프롬프트에서 "컴퍼스의 slot 순서를 반드시 따르세요" 명시.

### Issue 2: 정보 밀도 저하 — 동일 내용 반복

현재: "2028년 동해시 1.2GW → 최종 2.4GW"가 시장 배경, 실적과 수치, 요약에서 세 번 반복. "스타트업과 기술 협력"도 거의 모든 섹션에서 반복.

문제: 글자수를 채우기 위해 같은 팩트를 돌려쓰는 건 저품질 신호.

요구: 각 섹션은 고유한 정보만 담을 것. compass JSON이 이미 각 슬롯에 다른 내용을 할당했으므로, Pass 2 프롬프트에서 "섹션별 중복 금지" 강제.

### Issue 3: 비교 슬롯에 실제 비교 대상 부재

현재: "경쟁 구도와 주요 플레이어" H2에 SK, KT, 네이버, 카카오 등 경쟁사 이름 없음. "GS가 차별화된 무기를 활용합니다"만 있음.

문제: 비교 없는 비교 섹션. slot2_compare의 의미가 없음.

요구: slot2_compare에 구체적 경쟁사·경쟁 구도 포함. Pass 1 프롬프트에서 경쟁사 정보를 기반으로 채우도록 유도.

### Issue 4: 홍보성 톤

현재: "비약적인 성장 기회를 확보하게 됩니다", "대한민국이 AI 강국으로 도약하는 데 필요한 물리적 토대를 성공적으로 구축해 나가고 있습니다"

문제: GS그룹 홍보팀이 쓴 것 같은 문장. 뉴스 큐레이션은 기업 관점이 아니라 독자 관점이어야 함.

요구: 홍보·광고성 표현 금지. 독자 관점에서 사실 전달. Pass 2 시스템 프롬프트에 금지 표현 명시.

### Issue 5: intro_style 패턴 미준수

현재: "지에스(GS)그룹이 단순한 전력 공급 인프라 사업을 넘어~"로 시작. intro_style="conflicting_fact"라고 했지만 해당 패턴에 맞지 않음.

문제: intro_style 5종(질문형/시간순/대조형/인용형/수치형)의 정의가 모호하여 LLM이 임의로 서술형 시작.

요구: intro_style 각 패턴의 실제 예시를 Pass 1/Pass 2 프롬프트에 포함. LLM이 정확히 어떤 패턴으로 시작해야 하는지 알 수 있도록.

## Reference:理想的 Compass JSON (from user)

```json
{
  "category": "biz",
  "slot1_fact": "GS그룹, 강남 GS타워에서 AI 데이터센터 기술 행사 개최. 허태수 회장 참석. GS벤처스 주도. 2028년 동해시 1.2GW 착공, 최종 2.4GW 목표.",
  "slot2_compare": "SK·KT·네이버 등 경쟁사 DC 투자 현황 대비 GS의 차별점: 에너지-건설 수직계열화 + 스타트업 기술 결합 모델",
  "slot3_context": "글로벌 AI 인프라 전력 수요 급증 속 에너지 기업의 DC 진출 트렌드. GS가 발전-송배전-건설을 내부 보유한 구조적 이점.",
  "slot4_outlook": "2028년 1단계 준공 성공 여부에 따라 국내 DC 시장 판도 변화 가능성. 전력 수급 인허가 리스크 존재.",
  "intro_style": "number_lead",
  "h2_flow": ["2.4GW 프로젝트의 전모", "기존 DC 사업자와 뭐가 다른가", "에너지 기업이 DC를 짓는 이유", "2028년 이후 변수"],
  "tone": "analytical",
  "table_plan": "comparison"
}
```

## Changes Required in compass.py

### Pass 1 Prompt Changes

1. **slot2_compare 필수 항목**: "경쟁사명 + 경쟁 구도 + GS의 차별점" 포함 강제
2. **intro_style 예시 추가**: 각 패턴별 1줄 예시를 프롬프트에 삽입
   - self_identity_call: "~의 핵심은 ~입니다"
   - number_shock: "숫자로 시작 (예: 2.4GW)"
   - reversal: "예상과 반전되는 사실로 시작"
   - contrast: "A와 B를 대비하며 시작"
   - conflicting_fact: "서로 모순되는 사실로 시작"
3. **h2_flow 슬롯 매핑 명시**: "h2_flow[0]은 slot1_fact, h2_flow[1]은 slot2_compare, h2_flow[2]은 slot3_context, h2_flow[3]은 slot4_outlook을 다루세요"

### Pass 2 Prompt Changes

4. **섹션별 중복 금지 규칙 추가**: "각 H2 섹션은 compass의 해당 슬롯 정보만 포함. 다른 섹션에서 이미 언급한 수치·사실 반복 금지"
5. **홍보성 표현 금지 규칙 추가**: "기업 홍보·광고성 표현 금지. '~도약합니다', '~성공적으로 구축합니다' 같은 표현 대신 사실 전달"
6. **독자 관점 강조**: "독자가 이 기사에서 얻을 수 있는 실질적 정보에 집중"

### H2 Flow Presets Change

7. **business 프리셋 개선**: "향후 전략과 전망" → "2028년 이후 변수" (구체적), "실적과 수치" → "수치로 보는 프로젝트 규모" (informational)

## Existing Writing-Pipeline Code (referenced by this phase)

- `pipeline/threads/compass.py` — Compass 2-pass system (510 lines). Key functions: `write_compass_article()`, `build_system_prompt_compass()`, `build_blog_system_prompt()`, `_build_pass1_user_prompt()`, `_build_blog_pass2_user_prompt()`.
- `pipeline/threads/writer.py` — `write_thread(pitch, all_articles, format_choice=None)` at line 431.
- `pipeline/threads/fact_gate.py` — G4 fact-gate: `check_slot3()`.
- `pipeline/threads/pitch.py` — pitch logic, `detect_prompt_leak()`.
- `scripts/threads/compass_dryrun.py` — Dry-run script.

## Dependencies (from ROADMAP.md)

- Phase 14: JSON-first parsing.
- Phase 28-05: fact-gate patterns.
- Phase 38: `main_v3.py` structure and `performance_log.py`.
