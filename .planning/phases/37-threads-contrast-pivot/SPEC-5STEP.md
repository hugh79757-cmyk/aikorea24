# SPEC-5STEP — Contrast Storytelling Pipeline (5-Step)

**Phase:** 37-threads-contrast-pivot
**Date:** 2026-08-26
**Status:** SPEC (implements `docs/manual-blog/prompts/01-extractor.md + 02-curator.md` → 5-card Format D)
**Source:** user 5-step reality (Korean preserved where given)

---

## Overview

Seed 기사 1건 → 5-step 체인 → 5 cards (500자/card). 각 card 사실 1개+ 포함, AI prompt에 multiple sources + contrast 강제. 외부 검색 API 없이 D1 LIKE + Vectorize fallback만.

Pipeline: `extractor(A-F) → background_search(E→D1) → cross(3) → curator(7→5) → validator 3중`

---

## Step 1 — Core Event Multi-Angle (3-5 media 교차)

- **Input:** keyword search (person/event/institution). 예: `ARIA Awards AI category`
- **Collection:** 성격 다른 매체 3-5건. 예: `ABC / AFR / RollingStone / AlJazeera / ARIA` 공식문.
- **Sort:** date sort → timeline rebuild **4 timepoints** 예:
  - `Aug24 ARIA 발표` → `Aug28 MEAA 반발` → `Aug31 언론 확산` → ` ceremony 16 weeks 후`
- **Extract numbers (구체적 수치):** `4,800만(호주 음악산업 규모)`, `2nd/4th(ARIA 순위)`, `16 weeks(남은 기간)`, `Aug24(발표일)` — 각 매체에서 숫자 1개+ 확보.
- **Output:** A-F의 A(사건명/시점/장소/행위자/계기) + B(수치) 초안.

> Impl: `pipeline/threads/contrast/extractor.py:extract_af()` temp 0.2 + `background_search.py:find_cross_articles(limit=2)` + seed crawl 1 = total cross 3. timeline은 extractor A 시점 + B/C 날짜로 재구성 (LLM이 생성).

## Step 2 — Contrast Background (상위 주제 연결)

- **Extract upper topic D:** 한 문장. 예: `"AI impact on music jobs"` / `"AI가 음악 일자리에 미치는 영향"`
- **Separate search:** D 기반 키워드 E 3개로 **독립 기사 1건** 추가 탐색. 예: `Guardian / SMH / ABC Listen KeyComp` — 표면 무관해 보이는 배경 기사. — 두 독립 취재물 연결 시 카드2/카드4 첫 문장에 전환 명시 필수 (예: '이는 기술 검증 너머 실제 사용 현장으로 확장된다').
- **Connect:** 두 사건이 같은 문제의 다른 얼굴인지 판단. 예: `rule-makers vs unprotected` / `규칙 만드는 자 vs 보호받지 못하는 자` — ARIA(규칙 제정) vs 세션 뮤지션(보호받지 못함).
- **Output:** D(상위주제 한 문장) + background 1건 dict or None (graceful degradation).

> Impl: `background_search.py:find_background(E, exclude_id)` D1 `LIKE '%kw%'` 30일 DESC → Vectorize fallback → None. Curator에 `related_text`로 주입.

## Step 3 — Detail Checklist (5 categories × 3 each)

일반론 금지. 각 카테고리 **3개 이상** 없으면 drop/general론.

| # | Category | 예시 (ARIA case) | Validation |
|---|----------|-------------------|------------|
| 1 | 실명+직함 | `James Stenham MEAA fed rep` | regex `title_pat` |
| 2 | 경력 | `20yr Hamilton/Phantom` | `career_pat` |
| 3 | 수치 | `4,800만, 2nd/4th, 16 weeks, Aug24` | `number_pat` |
| 4 | 날짜 | `Aug24 / Aug31 / Aug28` | `date_pat` |
| 5 | 인용문 | `Powaz "great move"` | `quote_pat` |

- B/C/D/E가 이 5종을 커버해야 함. B는 수치/날짜, C는 인용문+실명, D는 상위주제.
- Guard: `B>=1, C>=1, E==3, D>5` (PLAN 37-01). 5-cat 3-each는 curator 단계에서 `detail_check`로 2차 검증.

> Impl: `extractor.py:_validate_af()` + `contrast_writer.py:_detail_check(cards)` (추가 예정).

## Step 4 — Narrative 7→5 (서사 압축 + 감정 라벨)

**7단락 원형:**
1 놀라움(background) → 2 배경 → 3 전개(논란 확산) → 4 예상 밖 반응 → 5 핵심 인물 → 6 논지 심화 → 7 요약

**5-card 압축 + emotion label:**

| Card | 7 source | Emotion label | 역할 | 내용 |
|------|----------|---------------|------|------|
| C1 | 1+2 | 놀라움 | Hook | 반전 먼저 + 경위 1줄 |
| C2 | 2+3 | 배경전개 | 전환 but_line | 시간순 경위 + 논란 확산, 대비 논지 제시 |
| C3 | 4 | 반전 | 증거 A | 예상 밖 반응 (긴장 완화) |
| C4 | 5+6 | 핵심인물+논지 | 증거 B | 진짜 피해자 등장 + 규정/해결책 허점 |
| C5 | 7 | 요약 | 열린질문 | 대비 재정의, ?/열린어미 종결 |

- Reorder: 7→5 병합 시 C3(반전)을 독립 배치해 리듬. C1/C2/C4는 병합.
- 각 card: 350-450자 target, 500 hard limit, `~임/~했음` 종결, 10~25자 절 단위 빈줄 `\n\n` 리듬 필수, 60자 절단, 1+ fact.

> Impl: `contrast/prompts.py:CONTRAST_CARD_MAP` + `SYSTEM_CURATOR_CONTRAST` + `contrast_writer.py:build_system_prompt_contrast()`.

## Step 5 — Workflow (전체 게이트)

```
3+ media(1 crawl + 2 D1 desc) 
 → upper topic 1 sentence(D) 
 → 5 categories 3 each(B/C/D check) 
 → contrast point 1("rule-makers vs unprotected") 
 → 7→5 placement(C1..C5) 
 → each card 1+ fact + prompt에 multiple sources + contrast 명시
```

- **Search count spec:** `cross 3 + bg 1 = total 4` articles fed to curator. (seed crawl 1 + D1 cross 2 + D1 bg 1). 외부 크롤 3회 금지.
- **Each card 1+ fact:** validator `validate_cards` + `_detail_check`로 강제.
- **AI prompt must specify:** `multiple sources + contrast` — SYSTEM_CURATOR에 "서로 다른 매체 3개 이상 교차 + 배경 기사 1건 연결 + 표면/근본 대비" 문구 포함.

---

## 5-Category Validation Rules (regex)

```python
# pipeline/threads/contrast/validator_detail.py (예정) or inline in contrast_writer
TITLE_PAT  = r"[A-Z][a-z]+\s[A-Z][a-z]+.*(?:fed rep|대표|위원장|CEO|장관|공연자|Powaz|Stenham)"
CAREER_PAT = r"\d+\s*yr|\d+년|Hamilton|Phantom|경력|출연|공연"
NUMBER_PAT = r"4,800만|\d+[,\d]*만|\d+\s*weeks?|2nd|4th|AUD|\$|명|건|%"
DATE_PAT   = r"Aug\s*2[48]|Aug\s*31|8월\s*\d+|2026-\d{2}-\d{2}|\d{4}년.*월"
QUOTE_PAT  = r'"[^"]+"|「[^」]+」|Powaz.*great move|Stenham.*인용'
```

- Rule: 각 카테고리별 cards 전체에서 match count >=3 else `detail_check fail → regenerate 1회 → drop`.
- Graceful: niche 기사에서 경력 3개 불가 시 `기사에 명시되지 않음` 허용 but curator가 3개 채우도록 프롬프트 유도.

## Prompt Templates (delta vs current)

### SYSTEM_EXTRACTOR add D + detail_check

Current `prompts.py:12` → add:

```
- D: 상위 주제 한 문장 + 표면 문제 + 근본 문제 가설 (반드시 1문장+α, 5자 초과)
- detail_check: B(수치) C(인용) E(키워드3) 외에 5-category(실명+직함/경력/수치/날짜/인용) 각 3개 이상 확보 시도. 없으면 "기사에 명시되지 않음" 금지, 원문 재탐색.
```

### SYSTEM_CURATOR add contrast question + role labels

Current `prompts.py:32` → add:

```
- 역할 라벨: 각 card 상단에 emotion label 주석 (C1 놀라움, C2 배경전개, C3 반전, C4 핵심인물+논지, C5 요약) — 출력에는 라벨 노출 금지, 내부 reasoning용.
- contrast question: 카드2 but_line에 "표면적 해결처럼 보이는 문제 vs 실제 가려진 근본 문제" 1문장 대비 논지 필수.
- multiple sources 명시: "서로 다른 매체 3건(ABC/AFR/RollingStone 등) + 배경 기사 1건(Guardian/SMH/ABC Listen) 교차 검증" 프롬프트에 포함.
- 각 card 1+ fact 강제: 카드마다 실명 or 수치 or 날짜 or 인용 중 1개 이상 포함, 없으면 재생성.
```

## File References

| File | Role | Step |
|------|------|------|
| `pipeline/threads/contrast/prompts.py` | versioned prompts + CONTRAST_CARD_MAP | 4,5 |
| `pipeline/threads/contrast/extractor.py` | A-F extract, B>=1 C>=1 E==3 D>5 guard | 1,2,3 |
| `pipeline/threads/contrast/background_search.py` | find_background + find_cross_articles (D1 LIKE) | 1,2 |
| `pipeline/threads/contrast/contrast_writer.py` | build_system_prompt_contrast + write_contrast_thread 7→5 | 4,5 |
| `pipeline/threads/contrast/orchestrator.py` | run_contrast_thread glue | 5 |
| `pipeline/threads/writer.py` | FORMAT_BUILDERS["contrast"] dispatch | 5 |
| `pipeline/threads/validator.py` | 3중 방어 + leak patterns | 3,4 |
| `pipeline/threads/pitch.py` | LEAKED_PROMPT_PATTERNS + dedup | 4 |
| `scripts/threads/main_v3.py` | --format contrast branch | 5 |
| `docs/manual-blog/prompts/01-extractor.md` | A-F 원형 (런타임 로드 금지) | 1-3 |
| `docs/manual-blog/prompts/02-curator.md` | 7단락 원형 (런타임 로드 금지) | 4 |

## Verification Checklist

- [ ] `python3 -m py_compile pipeline/threads/contrast/*.py` pass
- [ ] `grep -c "상위 주제" pipeline/threads/contrast/prompts.py` >=1 (SYSTEM_EXTRACTOR D)
- [ ] `grep -c "대비 논지\|근본 문제" pipeline/threads/contrast/prompts.py` >=1 (SYSTEM_CURATOR contrast)
- [ ] `python3 -c "from pipeline.threads.contrast.prompts import CONTRAST_CARD_MAP; assert CONTRAST_CARD_MAP['C1'].startswith('1')"` 
- [ ] `python3 -c "from pipeline.threads.contrast.extractor import _validate_af; assert not _validate_af({'B':[],'C':['q'],'E':['a','b','c'],'D':'123456'})"` (B>=1 guard)
- [ ] `.venv/bin/pytest tests/test_contrast_extractor.py tests/test_contrast_background.py tests/test_contrast_writer.py -v` green (detail 5-cat cases)
- [ ] `python3 -c "from pipeline.threads.pitch import detect_prompt_leak; assert detect_prompt_leak('상위 주제: 테스트')[0]"` (leak gate)
- [ ] dry-run: `python3 scripts/threads/main_v3.py --dry-run --format contrast 2>&1 | grep -E "C[1-5]|cards|500"` — each card <500, C3 반전, C5 ?
- [ ] `python3 -c "from pipeline.threads.writer import FORMAT_BUILDERS; assert 'contrast' in FORMAT_BUILDERS"`

## Residual Risks

- D1 LIKE coverage 50% 미만 시 bg None → 대비 논지 약화 (graceful degradation allow, curator prompt에 "배경 없이 단일 사건 대비" 분기).
- 5-cat 3-each strict 시 extractor drop surge → guard는 B>=1 완화, detail_check는 curator에서 재생성 1회로 완화.
- 7→5 병합 시 C1/C2 장문화 → 450자 target 초과 drop → curator prompt 350-450 명시.

---
*Ponytail: 5 steps only, D1 LIKE only, 3 files mock, no external search. Add Brave/Tavily when bg hit <30%.*
