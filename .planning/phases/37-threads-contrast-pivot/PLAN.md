# PLAN — Phase 37: Threads Contrast Writing Pivot

**Phase:** 37-threads-contrast-pivot
**Goal:** 대비 구조 7단락 보도체(`docs/manual-blog/prompts/01-extractor + 02-curator`) 를 Threads Format D 5-card 안에 녹여 2-stage LLM 체인으로 발행. 기존 Threads 파이프 500자/card + 3중 방어 + 무료 체인 유지.
**Type:** execute (3 plans, 2 waves)
**Depends on:** Phase 15 (Vectorize + JSON cards), Phase 16 (writer prompt v2)
**Constraints:** stdlib only, 기존 275+ tests green, `model_override=None` 고정, D1 LIKE only (외부 검색 API 금지), `project_root()` DRY

---

## Goal (outcome)

Seed 기사 1건 → Extractor가 A-F JSON으로 구조화 → E 키워드 3개로 D1 LIKE(+Vectorize fallback)로 배경 기사 1건 탐색 → D1 cluster에서 교차 검증용 2건 D1 description 재사용 → Curator가 7→5 압축해 5 cards 생성(~임 리듬, 350-450자/card target, 500 hard limit, 카드5 열린질문) → validator 3중 방어 통과 → `DRAFTS_DIR` 저장 또는 Threads 발행.

## Success Criteria (truths)

1. Extractor는 원문 1건에서 `A-F JSON`을 LLM 1회(temp 0.2, json_object)로 뽑고 B>=1/C>=1/E==3 guard 통과한 것만 다음 단계로 넘김. 실패 시 drop, 체인 중단 없이 로그.
2. Background search는 E 3개로 D1 LIKE `title/description LIKE '%kw%'` 30일 내림차순 1건 pick, 0이면 Vectorize fallback, 그래도 0이면 graceful degradation(배경 없이 진행, 대비 논지 유지).
3. 교차 검증 3매체는 실제 크롤 1건(seed `fetch_article_body`) + D1 description 2건 재사용으로 시뮬레이션. 외부 크롤 3회/외부 검색 API 없음.
4. Curator는 7→5 매핑 고정으로 5 cards 생성: C1 놀라움+배경 / C2 배경+전개(but_line) / C3 예상밖반응+인물 / C4 논지심화 / C5 결론 열린질문. 각 350-450자 target, 500자 hard limit 초과 시 재생성 1회 후 drop.
5. 3중 방어 그대로: 기존 `validate_final_output` + `validate_card_structure` + `validate_cards`/`validate_year` 체인 통과, 추가로 contrast 신규 시스템 프롬프트 라벨 2-3개를 `LEAKED_PROMPT_PATTERNS`/`_SYSTEM_PROMPT_FRAGMENTS`에 추가.
6. 발행물은 threads 제약 통과: 5 cards, 500자 이하, `validate_last_card_opens_reply`(?/열린어미), 한자/히라가나 0, 한글 비율 0.3/0.15 이중 게이트, `detect_prompt_leak` 0.
7. `scripts/threads/main_v3.py --format contrast` 와 `--format D` (기본) 병행. contrast 실패가 기존 D 경로에 영향 0. 기존 275+ tests green, 신규 contrast tests 3파일 ~240L 통과.

---

## Architecture (reuse map)

```
[D1 news] → seed 1건 ──> Extractor(LLM temp0.2) → A-F JSON ─┐
                           │  D/E                           │
                           └──> BackgroundSearch(D1 LIKE → Vectorize) → bg 1건 ──┤
                                Cross-media(D1 cluster LIKE, description reuse) 2건 ─> Curator(LLM 0.4-0.7) → 5 cards → validator 3중 → draft/publish
```

Reuse 100%: `pipeline.threads.writer` (FORMAT_BUILDERS, parse, humanize, validate chain), `pipeline.threads.validator` (3중 방어), `pipeline.threads.crawler.fetch_article_body` (seed only), `pipeline.threads.pitch.detect_prompt_leak/is_duplicate_pitch`, `scripts/threads/v3/model_router.chat_completion`, `pipeline.infra.d1_client.d1_query`, `pipeline.infra.config.project_root`, `pipeline.infra.logger.get_scrubbed_logger`

New boundary: `pipeline/threads/contrast/` 패키지 5 files (~535L). Modify 2 files only: `writer.py` (+60L FORMAT contrast), `main_v3.py` (+40L --format branch), `pitch.py/validator.py` (+5L leak patterns).

---

## Dependencies & File Ownership

| Plan | Wave | Depends | Files Owned (exclusive) |
|------|------|---------|------------------------|
| 37-01 Foundation | 1 | none | `pipeline/threads/contrast/prompts.py`, `extractor.py`, `background_search.py`, `__init__.py`, `validator.py`(+patterns), `pitch.py`(+fragments), `tests/test_contrast_*.py` (extractor/background) |
| 37-02 Writer | 2 | 37-01 | `pipeline/threads/contrast/contrast_writer.py`, `pipeline/threads/writer.py` (FORMAT contrast builder) |
| 37-03 Orchestrator | 2 | 37-01 | `pipeline/threads/contrast/orchestrator.py`, `scripts/threads/main_v3.py`, `tests/test_contrast_writer.py` (e2e) |

Wave 1 and Wave 2 parallel after extractor contract stable. No file overlap across waves except `tests/` (different files).

---

## Plan 37-01 — Foundation: Extractor + Background + Prompts + Validator Gates

**Wave:** 1
**Goal:** A-F 추출과 배경 탐색이 단독 테스트 가능하게 동작. Curator 없이도 체인 절반 검증.
**Files:** 6 created/modified

### Task 01-1: prompts.py — versioned system prompts (no runtime .md load)

**Files:** `pipeline/threads/contrast/prompts.py` (~120L new), `pipeline/threads/contrast/__init__.py` (~15L new)

**Action:**
- Create `pipeline/threads/contrast/` package.
- Copy/adapt `docs/manual-blog/prompts/01-extractor.md` + `02-curator.md` into string constants, not file I/O. Must NOT `open(docs/manual-blog/...)` at runtime — skill 분리 보장 위반.
- `SYSTEM_EXTRACTOR`: "You are research assistant, JSON only, temp 0.2, rule: 없는 정보 = '기사에 명시되지 않음', 추론 금지, output JSON only with keys A,B,C,D,E,F". Include Korean instruction + JSON schema example from RESEARCH.md Pattern 1. Max 12000자 article_body slice hint.
- `SYSTEM_CURATOR_CONTRAST`: "You are curation journalist, 7->5 compression, 350-450자/card target, 500 hard limit, ~임/~했음 종결, 빈줄 리듬 \n\n, 카드5 열린질문 ?/열린어미 강제, 한자/일본어 금지, 출처 자연스럽게 녹이기, 각주 금지". Include card mapping table comment.
- Export `CONTRAST_CARD_MAP` dict describing 7→5 merge.
- `__init__.py` exports `ContrastBundle` dataclass(TypedDict): `seed_article: dict, af: dict, background: dict|None, cross_articles: list[dict], cards: list[str]|None`

**Verify:**
```bash
python3 -c "from pipeline.threads.contrast.prompts import SYSTEM_EXTRACTOR, SYSTEM_CURATOR_CONTRAST; assert 'A' in SYSTEM_EXTRACTOR and '350' in SYSTEM_CURATOR_CONTRAST"
python3 -m py_compile pipeline/threads/contrast/prompts.py
```

**Done:** prompts.py imports clean, no file I/O, contains both system prompts with JSON/card rules, __init__.py defines ContrastBundle.

### Task 01-2: extractor.py — A-F JSON extractor (LLM 1회, guard B>=1 C>=1 E==3)

**Files:** `pipeline/threads/contrast/extractor.py` (~120L new)

**Action:**
- Reuse `scripts/threads/v3/model_router.chat_completion`. Import via `from scripts.threads.v3.model_router import chat_completion` with `sys.path.insert(0, str(project_root()))` preamble (same as writer.py:155). Temp 0.2, max_tokens 3000, response_format json_object, extra_body thinking disabled for deepseek.
- Function `extract_af(article_body: str, title: str) -> dict|None`:
  - prompt = `제목: {title}\n본문: {article_body[:12000]}\n\nA-F JSON으로 출력: {"A":{"사건명":...},"B":[...],"C":[...],"D":"...","E":["kw1","kw2","kw3"],"F":[...]}` + SYSTEM_EXTRACTOR
  - Call chat_completion, if None return None.
  - Parse json.loads, strip. Guard: `len(B) >=1`, `len(C) >=1`, `len(E)==3`, `D` non-empty string >5. If fail, log via get_scrubbed_logger and return None (do NOT raise). Catch JSONDecodeError → None.
  - Escape single quotes in E keywords for later LIKE use: keep original, but ensure no crash.
- Helper `_validate_af(data) -> bool` separate for unit test.
- Do NOT call D1 here. Single responsibility.

**Verify:**
```bash
.venv/bin/python3 -m pytest tests/test_contrast_extractor.py -v  # to be created in 01-4
python3 -m py_compile pipeline/threads/contrast/extractor.py
```

**Done:** extractor handles full/missing B/C/E cases, JSON parse fallback, temp 0.2 call, no new deps, 10 unit tests spec'd.

### Task 01-3: background_search.py — D1 LIKE + Vectorize fallback → 1 article

**Files:** `pipeline/threads/contrast/background_search.py` (~80L new)

**Action:**
- Reuse `pipeline.infra.d1_client.d1_query` (already removes CLOUDFLARE_API_TOKEN, retry 2). Do NOT use raw subprocess/wrangler.
- `find_background(keywords: list[str], exclude_id: str) -> dict|None`:
  - For each kw in keywords (order given): escape `'` → `''`, run `SELECT id,title,description,link,pub_date,source FROM news WHERE (title LIKE '%{kw}%' OR description LIKE '%{kw}%') AND id != '{exclude_id}' ORDER BY pub_date DESC LIMIT 1`. If rows, return rows[0].
  - If all 0: try Vectorize fallback — `from pipeline.infra.vectorize_client import query as vquery` lazy import inside try/except, `vquery(keywords[0], top_k=1)` → adapt to dict shape. If fails, return None.
  - If still None: return None (graceful). Caller (orchestrator) will proceed without background.
  - Use `get_scrubbed_logger`.
- Helper `find_cross_articles(seed_id: str, keywords: list[str], limit=2) -> list[dict]` same D1 LIKE but `ORDER BY pub_date DESC LIMIT 2` and `id != seed AND id != background_id` → returns 0-2 items (description as body surrogate, no crawl).
- D1 LIKE covers 80%, Vectorize is backup; no Brave/Tavily/Exa.

**Verify:**
```bash
python3 -m py_compile pipeline/threads/contrast/background_search.py
# mocked D1 test in 01-4
```

**Done:** LIKE escaping works, 0-result returns None without raise, Vectorize fallback is optional.

### Task 01-4: validator/pitch leak patterns + tests for 01-2/01-3

**Files:** `pipeline/threads/validator.py` (+5L), `pipeline/threads/pitch.py` (+5L), `tests/test_contrast_extractor.py` (~80L new), `tests/test_contrast_background.py` (~60L new)

**Action:**
- Add 2-3 contrast leak patterns to `LEAKED_PROMPT_PATTERNS` and `_SYSTEM_PROMPT_FRAGMENTS`:
  - `r'상위\s*주제\s*[:：]'`, `r'근본\s*문제\s*[:：]'`, `r'대비\s*논지\s*[:：]'` or fragments `상위 주제`, `근본 문제`, `대비 논지` to `_SYSTEM_PROMPT_FRAGMENTS`. This propagates to `detect_prompt_leak` and `validate_final_output` automatically (3중 방어).
- Do NOT change validator logic otherwise.
- Tests:
  - `test_contrast_extractor.py`: 8-10 cases — valid A-F parse, B 0→None, C 0→None, E 2→None, empty D→None, JSON garbage→None, keyword quote escape, detect_prompt_leak not triggered on clean card but triggered on "상위 주제:".
  - `test_contrast_background.py`: D1 LIKE mock (patch d1_query), first kw hit, second kw fallback, 0-result None, Vectorize fallback path, SQL quote escape.

**Verify:**
```bash
.venv/bin/python3 -m pytest tests/test_contrast_extractor.py tests/test_contrast_background.py -v
.venv/bin/python3 -m pytest tests/test_validator.py tests/test_pitch.py -q  # regression
# leak check
python3 -c "from pipeline.threads.pitch import detect_prompt_leak; print(detect_prompt_leak('상위 주제: AI 폭발'))"
```

**Done:** leak patterns block contrast system labels, 14+ new tests green, 275 existing green.

---

## Plan 37-02 — Contrast Writer: 7→5 Compression + writer.py FORMAT Builders

**Wave:** 2 (depends on 37-01 prompts contract)
**Goal:** Curator가 7→5 매핑으로 500자/card 리듬 카드 생성, writer.py에 FORMAT contrast로 등록, JSON-first parsing + validator 체인 그대로.
**Files:** 2 created/modified

### Task 02-1: contrast_writer.py — 7→5 curator (build_system_prompt_contrast + write_contrast_thread)

**Files:** `pipeline/threads/contrast/contrast_writer.py` (~180L new)

**Action:**
- Reuse `model_router.chat_completion`, `project_root`, `get_scrubbed_logger`, `pipeline.infra.models.NewsArticle` typing.
- `build_system_prompt_contrast() -> str`: returns f-string combining SYSTEM_CURATOR_CONTRAST + rhythm rules from writer.py D (절 10-25자, 빈줄 \n\n, 60자 절단, ~임 종결) + CARD 5 RULE (?/열린어미 강제) + "각 카드 350-450자 target, 500자 초과 금지" + JSON output `{cards:[5]}`. Do NOT duplicate FORMAT_LABELS string, keep compact.
- `write_contrast_thread(bundle: ContrastBundle, all_articles: list[dict]) -> dict|None`:
  - Build `related_text` from seed + background(optional) + cross 2(optional) using same template as writer.py:595 (`기사 {id}: 제목/발행일/본문/출처/링크`). For cross/background use D1 `description` as body surrogate when `fetch_article_body` not called (lazy: only seed may have crawled_body). If all fallback → return None.
  - Build user_prompt: pitch-like but contrast-specific — includes `A-F JSON` + `related_text` + `FORMAT: 대비 5카드 (놀라움+배경 / 배경+전개 but_line / 예상밖반응+인물 / 논지심화 / 결론 열린질문)` + 7→5 mapping comment.
  - Call `chat_completion(system_prompt=build_system_prompt_contrast(), messages=[user], temp 0.4-0.5, max_tokens 16000, response_format json_object, extra thinking disabled)`. Retry once on None (same as writer.py _try_model pattern).
  - Parse via `pipeline.threads.writer.parse_cards_json_first` + `_try_parse_json` fallback (import, do NOT reimplement). If >5 trim, if <5 return None.
  - Cleanup: `_cleanup_source_attribution` + `_remove_duplicate_links` reuse (import from writer).
  - Validate chain: `validate_cards(cards, pitch_stub, "contrast")`, `validate_year(cards, article_body_text)`, `validate_card_structure(cards)`, per-card `validate_model_message`, `validate_final_output(cards)`. On fail → log and return None (no retry beyond 1 LLM retry).
  - Return `{"cards": cards, "link": primary_url}` same contract as writer.py:595.
  - Do NOT add new validator logic here.

**Verify:**
```bash
python3 -m py_compile pipeline/threads/contrast/contrast_writer.py
.venv/bin/python3 -m pytest tests/test_contrast_writer.py -v  # see 02-2
```

**Done:** contrast_writer does 7→5 prompt → JSON parse → validator chain → 5 cards or None, reuses writer parsing/validation.

### Task 02-2: writer.py FORMAT contrast registration + FORMAT labels

**Files:** `pipeline/threads/writer.py` (~60L modify)

**Action:**
- Add to `FORMAT_LABELS`: `'contrast': '대비 스토리텔링형 (7→5 압축, 상위주제 연결, 열린질문 종결)'`
- Add `FORMAT_CARD_COUNTS['contrast']=5`, `FORMAT_CARD_COUNT_TOLERANCE['contrast']=(5,5)` via update or direct dict entry. Also ensure `validator.py` gets same (patch validator if needed, but import same dict — single source is validator, so writer imports correctly).
- Add `build_system_prompt_contrast()` thin wrapper that imports from `pipeline.threads.contrast.contrast_writer` and returns it — OR directly assign `FORMAT_BUILDERS['contrast'] = build_system_prompt_contrast` after import. Prefer lazy import inside function to avoid circular.
- Ensure `write_thread(pitch, all_articles, format_choice="contrast")` dispatch works: if format_choice=="contrast", delegate to `pipeline.threads.contrast.contrast_writer.write_contrast_thread` (lazy import). Else existing D path unchanged. Keep `assemble_final` path intact for D.
- Do NOT change `humanize_cards`, `parse_cards_json_first`, or validation thresholds.
- Keep 612L file SRP — add ~60L only.

**Verify:**
```bash
python3 -c "from pipeline.threads.writer import FORMAT_BUILDERS, FORMAT_LABELS; assert 'contrast' in FORMAT_BUILDERS; print(FORMAT_LABELS['contrast'])"
python3 -c "from pipeline.threads.validator import FORMAT_CARD_COUNTS; assert FORMAT_CARD_COUNTS['contrast']==5"
.venv/bin/python3 -m pytest tests/test_writer.py -q
.venv/bin/python3 -m pytest tests/test_validator.py -q
.venv/bin/python3 -m pytest tests/test_write_thread_validation.py -q
```

**Done:** FORMAT contrast selectable, existing D tests still pass, writer.py increment minimal.

---

## Plan 37-03 — Orchestrator Glue + main_v3 Branch + E2E Dry-Run

**Wave:** 2 (depends 37-01, parallel with 37-02)
**Goal:** End-to-end pipeline glued, CLI `--format contrast` working, dry-run + regression green.
**Files:** 2 created/modified + 1 test

### Task 03-1: orchestrator.py — run_contrast_thread(seed_article) glue

**Files:** `pipeline/threads/contrast/orchestrator.py` (~100L new)

**Action:**
- `run_contrast_thread(seed_article: dict, all_articles: list[dict]|None) -> dict|None`:
  1. Extract body: if `seed_article` has `crawled_body` use it, else `fetch_article_body(link)` via `pipeline.threads.crawler`, else `description` fallback. If no body → log drop return None.
  2. `extract_af(body, title)` → if None → log `extractor_fail_no_numbers` return None.
  3. `find_background(E_keywords, seed_id)` → may be None (graceful). `find_cross_articles(seed_id, E_keywords, 2)` → 0-2.
  4. Build `ContrastBundle(seed, af, background, cross_articles)`.
  5. `write_contrast_thread(bundle, all_articles_with_background)` → if None → drop.
  6. On success, deduplicate `article_ids`: use `seed_id` only as dedup key — call `is_duplicate_pitch`/`save_pitch_to_history` pattern but with `seed_id` key only (cross/background excluded) to avoid overlap>=0.5 over-filter.
  7. Save draft via `pipeline.threads.writer.save_draft(cards, pitch_stub)` where pitch_stub = `{"hook": af["A"]["사건명"], "article_ids": [seed_id]}`. Also handle `DRAFTS_DIR` creation.
  8. All steps use `get_scrubbed_logger`, no exception leak — catch and log → None.
- Export `run_contrast_thread` in `__init__.py`.
- Do NOT implement publish (publisher.py already handles cards+link).

**Verify:**
```bash
python3 -m py_compile pipeline/threads/contrast/orchestrator.py
python3 -c "from pipeline.threads.contrast.orchestrator import run_contrast_thread; print('import ok')"
```

**Done:** orchestrator wires extractor→background→writer→validator→save without new deps.

### Task 03-2: main_v3.py --format contrast branch

**Files:** `scripts/threads/main_v3.py` (~40L modify)

**Action:**
- Add argparse `--format {D,contrast}` default D, help "Threads format: D(기본 5카드 브리핑) vs contrast(대비 스토리텔링 7→5)".
- In `run_v3(dry_run, format_choice)`:
  - If format_choice == "contrast": after article load/pitch selection, pick `seed_article` = first article from `pitches[0]` or direct D1 top 1 if pitch absent (reuse existing `get_pitches` seed selection? simpler: `articles[0]` as seed for contrast dry-run). Call `from pipeline.threads.contrast.orchestrator import run_contrast_thread; result = run_contrast_thread(seed_article, articles)`. Then same save_draft→validate_final_cards→dry-run print→publisher path as D branch (reuse helpers, avoid duplicate code).
  - Else 기존 D branch 100% unchanged. Put contrast branch as `if format_choice=="contrast": ... else: existing` to isolate.
- Keep `failed_articles` exclude logic for contrast too (seed_id).
- Ensure `validate_final_cards(cards)` + `validate_final_output` still run before publish (3중 방어 already in write, but main_v3 extra gate stays).
- Log `format: contrast` via _log.

**Verify:**
```bash
python3 -m py_compile scripts/threads/main_v3.py
scripts/threads/main_v3.py --help | grep format
# dry-run mock (no D1/API hit) — unit test mocks d1_query + chat_completion
.venv/bin/python3 -m pytest tests/test_cascade_2pass.py -q  # regression: main_v3 still works
```

**Done:** CLI flag works, D default untouched, contrast branch calls orchestrator, no regression.

### Task 03-3: E2E tests + regression gate (3rd test file) + manual dry-run checklist

**Files:** `tests/test_contrast_writer.py` (~100L new, if not done in 37-02), plus manual checklist

**Action:**
- `test_contrast_writer.py` covers 8 cases:
  1. 5-card count ok, 500자 each under, card5 ends ?/열린어미.
  2. card >500자 → drop (validate_card_structure).
  3. 한자/히라가나 injected → validate_final_output fail.
  4. background None graceful → still 5 cards (no background text).
  5. leak "상위 주제:" in card → detect_prompt_leak fail.
  6. hook entity not in body → _validate_hook_body_entity_consistency fail (via validate_final_output).
  7. JSON brace fallback parsing still works (mock chat returns ```json {cards:[]}```).
  8. orchestrator E2E with mocked extractor+background+writer → save_draft called.
- Regression: run full suite:
```bash
.venv/bin/python3 -m pytest tests/ -q  # must be 275+3 files green, 0 failures
```
- Manual dry-run (after mocks pass, with real D1+free chain if env present):
```bash
python3 scripts/threads/main_v3.py --dry-run --format contrast 2>&1 | head -80
# expect: seed log, extractor log, background hit/miss log, 5 cards printed with blank-line rhythm, card lengths <500, last card ?, no 한자
```

**Verify:**
```bash
.venv/bin/python3 -m pytest tests/test_contrast_writer.py tests/test_contrast_extractor.py tests/test_contrast_background.py -v
.venv/bin/python3 -m pytest tests/ -q  # full regression
```

**Done:** 3 new test files ~240L, full suite green, dry-run checklist documented.

---

## Risk Mitigation

| Risk | Likelihood | Impact | Mitigation in Plan |
|------|-----------|--------|-------------------|
| Extractor guard too strict B>=2/C>=2 → <30% success | HIGH | drop | Guard lowered to B>=1/C>=1 in 01-2, log counter, no raise |
| Background 0-result → 대비 논지 붕괴 | MEDIUM | weak cards | 01-3 graceful degradation + Vectorize fallback + curator prompt branch "배경 없이 단일 사건 대비만" |
| 500자 초과 drop surge | HIGH | publish 0 | Curator prompt 350-450 target + 500 hard limit + 재생성 1회 in 02-1 |
| 3중 방어에 contrast 라벨 노출 미탐 | MEDIUM | prompt leak publish | 01-4 leak patterns 2-3 추가, existing detect_prompt_leak 재사용 검증 |
| D1 LIKE SQL ' escape crash | LOW | exception | 01-3 manual `''` escape, test case in 01-4 |
| `v3.model_router` import path 혼선 ModuleNotFound | HIGH | test fail | 01-2 `sys.path.insert(0, project_root)` + `from scripts.threads.v3...` 통일, py_compile gate |
| dedup 4 ids → 과도 drop | MEDIUM | filter 0 | 03-1 seed-only dedup key, cross/background excluded |
| Free chain json_object 무시 → 파싱 fail | MEDIUM | write fail | Prompts에 "JSON만" 이중 명시 + 4단계 parse fallback reuse (02-1) |
| Existing D regression | LOW | break pipeline | 02-2 writer delegation isolated, 03-2 main_v3 else branch, full pytest gate in 03-3 |

---

## Execution Order

```
Wave 1: 37-01 Foundation (prompts, extractor, background, validator patterns + tests)
   ↓
Wave 2: 37-02 Writer  +  37-03 Orchestrator  (parallel, both depend 37-01, no file overlap)
```

**Estimator:** Wave1 ~30-40% context (4 tasks, 5 files+tests), Wave2 each ~20-30%. Total ~1100L new, stdlib only, deletion over addition.

**Ponytail skips:** No new LLM client, no new D1 wrapper, no new vector client, no Brave/Tavily, no crawler 3×, no .md runtime load. Add when: background hit ratio <30% then consider external search Phase; extractor failure >70% then relax guards further.

---

## Verification (overall phase gate)

```bash
# compile gates
python3 -m py_compile pipeline/threads/contrast/*.py
python3 -m py_compile pipeline/threads/writer.py pipeline/threads/validator.py scripts/threads/main_v3.py

# unit
.venv/bin/python3 -m pytest tests/test_contrast_extractor.py tests/test_contrast_background.py tests/test_contrast_writer.py -v

# regression
.venv/bin/python3 -m pytest tests/ -q  # 0 failures

# leak patterns
python3 -c "from pipeline.threads.pitch import detect_prompt_leak; assert detect_prompt_leak('상위 주제: 테스트')[0]; assert detect_prompt_leak('근본 문제: 테스트')[0]"

# format builder
python3 -c "from pipeline.threads.writer import FORMAT_BUILDERS; assert 'contrast' in FORMAT_BUILDERS"

# dry-run (requires D1 env, free chain keys)
python3 scripts/threads/main_v3.py --dry-run --format contrast 2>&1 | tee /tmp/contrast_dry.log
grep -c "5개 콘텐츠 카드" /tmp/contrast_dry.log
# manual: check /tmp/contrast_dry.log cards each <500, last line ends ?, no 한자, rhythm \n\n present
```

## Output

Plans produce `.planning/phases/37-threads-contrast-pivot/37-01-SUMMARY.md`, `37-02-SUMMARY.md`, `37-03-SUMMARY.md` on completion via gsd-executor.

