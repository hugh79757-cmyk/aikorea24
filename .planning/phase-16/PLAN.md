# Phase 16 — PLAN.md

> **Phase:** 16 — Writer prompt restructuring: jisang-aligned thread structure
> **Mode:** ad-hoc
> **Depends on:** Phase 15, commit 39fe67c (selection logic v2)
> **Created:** 2026-07-09

---

## Goal

Restructure the 6-card thread definition and writer prompt so GPT-4o produces jisang-pattern threads: 통념→전환→증거→열린 질문, with no closed conclusions.

---

## Task 1: Card structure redefinition (build_system_prompt_D)

**File:** `pipeline/threads/writer.py`, function `build_system_prompt_D()`

**Changes:**
1.1 Redefine [카드 구조 — 6개]:
  - 1번: 통념 세우기 (기사 밖의 일반적 믿음/기대/상황. 기사 본문이 아님)
  - 2번: 전환 = but_line (기사의 사실이 1번 통념을 깸. "하지만..." 전환)
  - 3번: 증거 A (기사에서 구체적 숫자/발언/사실. but_line 뒷받침)
  - 4번: 증거 B (기사에서 또 다른 구체적 사실, 또는 더 큰 맥락에서의 해석)
  - 5번: 열린 질문 = question (답을 주지 않음. "선언" 금지. "결론" 금지. 질문만 던짐)
  - 6번: 출처 링크만 (🔗 URL)

1.2 Add 금지 규칙 for Card 5:
  - "결론은 명확함", "이것이 핵심임", "우리는 ~해야 한다" 같은 닫힌 결론 금지
  - "선언" 형태의 마무리 금지
  - 질문 다음에 답을 붙이는 것 금지
  - 5번 카드는 반드시 question 필드의 질문으로 끝나야 함

1.3 Replace [전환 시그널]:
  - 3/4/5번 시그널 → **2번(전환) 집중**
  - Card 1 (통념 세우기) 시작 패턴 추가: "~라는 말, 지난 N년간 모두가 믿었음" 등
  - Card 2 (전환) 시그널: "근데 이게 깨지는 중임", "하지만 여기서 방향이 꺾임" 등
  - Card 5 (열린 질문) 패턴: "남는 질문은 하나임", "진짜 질문은 이거임" 등

1.4 Remove old sections:
  - "[찾는 방법]" (pitch 영역, writer와 무관)
  - "[소스 신뢰도]" (pitch 영역)

**검증:** `py_compile` 통과

---

## Task 2: User prompt update (write_thread)

**File:** `pipeline/threads/writer.py`, function `write_thread()`

**Changes:**
2.1 Add but_line, question, gap_source to user prompt:
  ```
  모순 한 줄 (but_line): {pitch.get('but_line','')}
  열린 질문 (question): {pitch.get('question','')}
  간극 유형 (gap_source): {pitch.get('gap_source','')}
  ```

2.2 Add 카드별 필수 규칙 section:
  - 1번 카드: but_line에 나온 통념의 반대편을 일반화해서 세우기. 기사 본문 인용 아님.
  - 2번 카드: but_line을 그대로 전환점으로 사용. "하지만..." 흐름.
  - 3번 카드: 기사에서 but_line을 뒷받침하는 구체적 숫자/발언 인용.
  - 4번 카드: 기사에서 또 다른 증거, 또는 but_line을 더 큰 맥락에서 해석.
  - 5번 카드: question을 그대로 사용. 질문 다음에 답 붙이지 말 것. 결론·선언 금지.
  - 6번 카드: 출처 링크만.

2.3 Add gap_source 분기 section:
  - gap_source=explicit: but_line이 기사에 명시적 모순으로 존재. 3번 카드에서 기사 직접 인용.
  - gap_source=reconstructed: but_line이 기사 사실을 재연결해 구성한 모순. 2번 카드에서 통념과 기사 사실을 연결해 but_line을 직접 구성. 3번 카드는 기사의 핵심 사실만 인용.

**검증:** `py_compile` 통과

---

## Task 3: style_examples.md update

**File:** `scripts/threads/v3/style_examples.md`

**Changes:**
3.1 Replace all 6-card examples with new structure:
  - Card 1: 통념 세우기 (기사 밖)
  - Card 2: 전환 = but_line
  - Card 3: 증거 A
  - Card 4: 증거 B
  - Card 5: 열린 질문 (no closed conclusion)
  - Card 6: 🔗 URL

3.2 Ensure stanza + line break patterns preserved (shared with writer.py)

**검증:** File parses as valid Markdown

---

## Task 4: Verify and commit

4.1 `py_compile` on `pipeline/threads/writer.py`
4.2 Verify `scripts/threads/v3/style_examples.md` is readable
4.3 Commit with message: `feat: Writer prompt v2 — jisang-aligned 6-card structure (통념→전환→증거→열린질문)`
4.4 Update STATE.md

**검증:** `git log -1` 확인, `STATE.md` 업데이트 확인
