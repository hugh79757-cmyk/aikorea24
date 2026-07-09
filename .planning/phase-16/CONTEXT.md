# Phase 16 — CONTEXT.md

> **Phase:** 16 — Writer prompt restructuring: jisang-aligned thread structure
> **Mode:** ad-hoc
> **Depends on:** Phase 15 (Vectorize + crawl fix + JSON cards — Complete), Phase 1 of Threads v2 (selection logic — commit 39fe67c)
> **Created:** 2026-07-09

---

## 1. Objective

Phase 1 (committed) improved article SELECTION logic (contradiction-based pitch, 3-day window, api_based sources, 6-criteria eval). Phase 16 improves article WRITING logic — restructuring the thread card structure and writer prompt to align with the high-performing jisang0914 pattern.

---

## 2. Background: Why the current writer prompt fails

Analysis of Yvette thread and 17 jisang0914 articles revealed **4 structural problems**:

| # | Problem | Current prompt | jisang pattern |
|---|---------|---------------|----------------|
| 1 | Card 1 "훅" is narrative hook, not 통념 | "이야기의 핵심 긴장" | 기사 밖의 일반적 믿음/통념을 세움 |
| 2 | Card 2 "충돌의 A면" requires explicit contradiction | "구체적 사실/숫자"를 A면으로 | but_line을 전환점으로 사용 |
| 3 | Card 3 "반전" fails when no explicit reversal | "예상 못 한 사실" — 없으면 반복됨 | 증거 A/B로 but_line 뒷받침 |
| 4 | Card 5 "여운/선언" produces closed conclusions | "되돌아보기/선언" — 답을 줌 | 열린 질문 — 답을 안 줌 |
| **X** | but_line/question/gap_source not passed to writer | pitch 필드 누락 | 모순/질문을 카드에 반영 불가 |

---

## 3. Locked Decisions

### Decision 1: 6-card structure maintained (not 7)
- **근거:** Threads API 500자 제한, 6장이면 충분
- **변경:** 카드 역할만 재정의 (통념→전환→증거A→증거B→열린질문→링크)

### Decision 2: Phase 1 Task 4 (post-processing + validation) deferred
- **근거:** 프롬프트만 바꿔도 상당 개선 가능. 후처리/검증은 샘플 5~10건 확인 후 2단계로
- **Task 4 내용:** `_detect_closed_conclusion()` 후처리 + `validate_open_question()` 검증 체인

### Decision 3: style_examples.md updated together
- **근거:** 예시도 현재 카드 구조 기준이라 부정합 방지

### Decision 4: CTA not included in this phase
- **근거:** "팔로우" CTA는 품질 안정 후 별도 추가

---

## 4. Files to Modify

| File | Change Type | Risk |
|------|------------|------|
| `pipeline/threads/writer.py` | `build_system_prompt_D()` — 카드 구조 재정의 + 전환 시그널 | Low (prompt only) |
| `pipeline/threads/writer.py` | `write_thread()` — 유저 프롬프트에 but_line/question/gap_source 전달 | Low (prompt only) |
| `scripts/threads/v3/style_examples.md` | 예시를 새 카드 구조에 맞게 업데이트 | Low (docs only) |

---

## 5. Success Criteria

1. `build_system_prompt_D()` defines 6-card structure: 통념→전환→증거A→증거B→열린질문→링크
2. Card 1 explicitly builds "기사 밖 통념" (not narrative hook)
3. Card 2 uses but_line as the transition point
4. Card 5 mandates open question, forbids closed conclusions
5. Transition signals updated: Card 1 (통념 세우기), Card 2 (전환), Card 5 (열린 질문)
6. User prompt passes but_line, question, gap_source to model
7. Card-specific rules per position (1→통념, 2→but_line, 5→question)
8. gap_source branching (explicit vs reconstructed) in user prompt
9. style_examples.md updated with new card structure
10. `py_compile` passes on all modified files
