---
phase: 40-compass-writing-mode-diversification
plan: 01
type: execute
wave: 1
depends_on: [39]
files_modified:
  - pipeline/threads/compass.py
  - pipeline/threads/fact_gate.py
  - tests/test_compass_*.py
  - tests/test_fact_gate.py
requirements:
  - REQ-40-01 (weighted random rotation)
  - REQ-40-02 (independent style/h2 axes)
  - REQ-40-03 (conditional H2 rearrangement)
  - REQ-40-04 (optional H2s)
  - REQ-40-05 (tone-based Pass 2 branching)
  - REQ-40-06 (summary block variation)
  - REQ-40-07 (cross-language fact-gate)
user_setup: []
estimate:
  tokens: 60000
  raw_tokens: 35000
  tasks: 3
  confidence: med
must_haves:
  truths:
    - "intro_style과 h2_flow가 독립된 축으로 분리 (5×5=25 조합)"
    - "회전이 순환(0→1→2→3→4→0)이 아닌 가중 랜덤 (최근 2회 사용 패턴 제외)"
    - "Pass 2 블로그 본문의 요약 블록이 3가지 이상 변형"
    - "같은 카테고리 글도 H2 수가 3~6개로 가변"
    - "영어+한국어 혼합 기사에서 G4 Layer 1이 정밀 매칭"
    - "tone 필드가 Pass 2 프롬프트에 의미적 분기를 일으킴"
    - "기존 테스트 100% 통과 (기존 compass + fact_gate)"
  artifacts:
    - pipeline/threads/compass.py (rotation logic + H2 conditional rearrange + prompt branching)
    - pipeline/threads/fact_gate.py (cross-language matching)
    - tests/test_compass_rotation.py (weighted random verification)
    - tests/test_compass_h2_variation.py (H2 count distribution)
    - tests/test_compass_summary_variation.py (summary block types)
  key_links:
    - compass.py: _load_compass_rotation → weighted_random_pick()
    - compass.py: _build_blog_pass2_user_prompt() → tone branch + summary_format
    - compass.py: _build_blog_pass2_user_prompt() → conditional H2 rearrange
    - fact_gate.py: _layer1_substring_match() → language-aware matching
---

## Objective

Compass 글쓰기 모드의 패턴 다양성을 구조적으로 확보. 5개 개선 축(회전, H2, 톤, fact-gate, 마무리)을 additive 방식으로 적용하여 "구조가 바뀌어도 읽는 느낌이 다른" 시스템 구현.

## Execution Context

@/Users/twinssn/.config/opencode/gsd-core/workflows/execute-plan.md
@/Users/twinssn/.config/opencode/gsd-core/templates/summary.md

## Context

@/Users/twinssn/Projects/aikorea24/.planning/PROJECT.md
@/Users/twinssn/Projects/aikorea24/.planning/ROADMAP.md
@/Users/twinssn/Projects/aikorea24/.planning/STATE.md
@/Users/twinssn/Projects/aikorea24/.planning/phases/40-compass-writing-mode-diversification/CONTEXT.md

---

## Wave 1: 회전 메커니즘 재설계 (独立 axes + weighted random)

**Purpose:** 예측 가능한 5순환 → 독립 2축 가중 랜덤으로 패턴 공간 5→25 확장

### Task 1-1: `intro_style`과 `h2_flow` 축 분리

- `compass.py`에서 `_load_compass_rotation()` 2개로 분리: `_load_intro_rotation()`, `_load_h2_rotation()`
- `posted.json`에 `compass_intro_rotation`, `compass_h2_rotation` 별도 저장
- 각각 독립 증가

**검증:** `tests/test_compass_rotation.py` — 2개 카운터가 독립적으로 증가하는지 확인

### Task 1-2: 가중 랜덤 선택 (no recent repeat)

- 새 함수 `weighted_pick(items, recent_items, exclude_count=2)` 구현
- 최근 2회 사용 항목 가중치 0, 나머지 균등 분배
- `intro_style` Pass 1 프롬프트 + `h2_flow` Pass 2 프롬프트 모두 적용

**검증:** 100회 시뮬레이션 → 연속 같은 패턴 0회 발생, 최근 2개 제외 확률 100%

### Task 1-3: `intro_style` 패턴 2~3개 추가

- `quote_lead`: 인용문으로 시작 ("..."이라며—")
- `reverse_chronology`: 시간 역순 (결과 → 원인)
- `what_if`: 가정법 질문 ("만약 ~였다면?")
- INTRO_STYLE_EXAMPLES + INTRO_STYLE_PREFIXES에 추가

**검증:** `tests/test_compass_generation.py` — 7~8개 패턴 모두 회전 가능 확인

---

## Wave 2: H2 흐름 가변화 (conditional rearrange + optional H2s)

**Purpose:** 같은 카테고리도 소재에 따라 다른 구조

### Task 2-1: H2 conditional rearrange 규칙

- `compass.py`에 `_rearrange_h2(compass, h2_flow)` 함수 추가
- 규칙 예시:
  - `slot2_compare`에 구체적 경쟁사명 있으면 → 비교 H2를 2번째로 당기기
  - `slot4_outlook`이 불확실성 표현 있으면 → 전망 H2를 4번째로
- 변경 사항 Pass 2 프롬프트에 적용

**검증:** 드라이런 10회 → H2 순서 분포 분석 (5개 동일 순서 < 30%)

### Task 2-2: H2 필수/선택 분리

- H2 5개 중 3개 필수, 2개 선택 (category preset에 정의)
- Pass 2 프롬프트에 "선택적 H2 포함 가능" 가이드라인 추가
- 생성된 본문 H2 수 3~6개 범위 허용

**검증:** `tests/test_compass_h2_variation.py` — H2 수 3~6개 분포 확인

### Task 2-3: 글 길이 구간화

- Pass 2 프롬프트: "1500자 이상" → "1200~2500자"
- 블로그 mode 최소 길이 확인 로직 변경

**검증:** 드라이런 10회 → 본문 길이 1200~2500자 범위 확인

---

## Wave 3: Pass 2 프롬프트 분기 + 마무리 변주

**Purpose:** 문체와 마무리에서 패턴 파괴

### Task 3-1: tone별 프롬프트 분기

- `build_blog_system_prompt()`에 `tone` 파라미터 추가
- `neutral_careful`: 현재 동작 (합쇼체, 공식)
- `fan_friendly`: 해요체(~요), 비유 허용, 독자 호칭 "여러분"
- `analytical`: 해라체(~이다), 수치 강조, 인용문 많게
- 각 tone별 종결어미 규칙, 문장 길이 범위 차이

**검증:** 드라이런 3 tone 각각 → 종결어미 분포 확인

### Task 3-2: 요약 블록 3~4가지 변형

- `_build_summary_block(summary, format)` 함수 추가
- 형식: 불릿 리스트 (현재), 서술형 한 문단, 핵심 질문, 마지막 H2 자연종결
- `compass.tone` 또는 rotation counter 기반 가중 랜덤 선택

**검증:** `tests/test_compass_summary_variation.py` — 3+ 형식 분포 확인

---

## Wave 4: Fact-gate 정교화

**Purpose:** 영어 원문 + 한국어 slot3 매칭 개선

### Task 4-1: 고유명사 영/한 매칭

- `_layer1_substring_match()`에 영어 고유명사 → 한글 음차 매핑 시도
- 예: "Scott Bessent" → "스콧 베센트" 매칭 시도
- 단순 음차 dict (50개 주요 인물/기관) 추가

**검증:** `tests/test_fact_gate.py` — 영어 본문 + 한국어 slot3 테스트 추가

### Task 4-2: 언어 중립 요소 우선 매칭

- 숫자, 날짜, 백분율 등은 언어 중립 → 항상 매칭 시도
- 영어 숫자("2.4") ↔ 한글 숫자("2.4") 매칭 로직 추가

**검증:** `tests/test_fact_gate.py` — 숫자/날짜 매칭 테스트 추가

### Task 4-3: 혼합 언어 기사 임계값 조정

- 현재 한국어 비중 <10% → Layer 1 건너뜀
- 한국어+영어 혼합(10~50%) → 부분 매칭 (한국어만, 영어만) 시도
- 한국어 비중 >50% → 전체 Layer 1 실행 (현재 동작)

**검증:** 3가지 언어 비중 시나리오 각각 테스트

---

## Verification

### 드라이런 테스트

```bash
# 10회 실행 → 분포 확인
for i in $(seq 1 10); do
  python3 scripts/threads/compass_dryrun.py --blog --skip-g4 2>&1 | grep "intro_style\|category"
done
# intro_style: 7~8 패턴 분포 확인
# h2_flow: H2 수 3~6개 확인
# 요약: 3+ 형식 확인
```

### 테스트

```bash
python3 -m pytest tests/test_compass_*.py tests/test_fact_gate.py -m unit -v
# 목표: 기존 19개 + 신규 10개 = 29개 이상 통과
```

### 저품질 수동 점검

- 생성된 10개 본문 → HTML 구조 반복 여부 확인
- 문장 수준 n-gram 분포 비교 (전체 vs 개별)
- 메타 수준: H2 태그 순서 패턴, 요약 블록 패턴

---

## Residual Risks

1. **패턴 증가 = 복잡도 증가**: 가중 랜덤 + 조건부 재배열 → Pass 2 프롬프트가 길어짐. LLM 프롬프트 충돌 가능성 모니터링
2. **테스트 범위 확장**: 29개 테스트 중 일부가 LLM 의존 → mock 기반 검증 필요
3. **저품질 판정 기준 변화**: Naver 블로그 알고리즘이 패턴을 잡는 기준은 시간에 따라 변함 → 분기별 재점검 필요
