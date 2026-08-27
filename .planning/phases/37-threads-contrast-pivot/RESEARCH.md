# Phase 37: threads-contrast-pivot — Research

**Researched:** 2026-08-26
**Domain:** Threads publishing pipeline extension — contrast-writing (extractor→curator) adapted to 5-card Format D
**Confidence:** MEDIUM (codebase verified HIGH, cross-media crawl assumptions MEDIUM, 7→5 mapping tradeoffs MEDIUM)

## User Constraints (from CONTEXT.md)

### Locked Decisions
- 신버전 글쓰기는 블로그가 아니라 Threads로 구현 [VERIFIED: CONTEXT.md]
- docs/manual-blog 2개 프롬프트(01-extractor, 02-curator)는 Threads용으로 재해석 (원문 유지하되 카드 제약에 맞게 조정) [VERIFIED: CONTEXT.md]
- 무료 LLM 폴백 체인 유지 (model_router.py tier_order), 유료 DeepSeek 최후수단만 [VERIFIED: CONTEXT.md]
- 3중 방어 원칙 유지: pitch 생성 / thread 작성 후 / 발행 직전 검증 모두에 prompt-leak + korean + 한자 검사 (validator.py) [VERIFIED: CONTEXT.md]
- Threads API: 500자/card hard limit, hiragana/katakana 금지, 5 cards 구조 유지 [VERIFIED: CONTEXT.md]
- D1 DRY: d1_client 재사용, 하드코딩 PROJECT_DIR 금지 (pipeline/infra/config.project_root) [VERIFIED: CONTEXT.md]
- 테스트 회귀 없음: 기존 275 테스트 + Threads 모듈 테스트 green 유지 [VERIFIED: CONTEXT.md]

### Agent's Discretion
- 대비 스토리텔링 7단락을 Threads 5-card에 어떻게 압축/재배치할지 [VERIFIED: CONTEXT.md]
- 교차검증 크롤링 소스를 어디서 가져올지 [VERIFIED: CONTEXT.md]
- 입력: D1 news DB 기사 + 브리핑 items vs keywords.json 재사용 여부 판단 [VERIFIED: CONTEXT.md]
- 추출기 A-F 구조를 코드 모델로 둘지 프롬프트 체인 2단계로 둘지 [VERIFIED: CONTEXT.md]
- 배경기사 연결(상위주제) 검색 키워드 E 활용 시 D1 vs 외부 검색 중 무엇이 현실적? [VERIFIED: CONTEXT.md]

### Deferred Ideas (OUT OF SCOPE)
- blog_draft_generator.py 신버전 구현 안 함 (기존 블로그 파이프 현행 유지) [VERIFIED: CONTEXT.md]
- 기존 블로그 파이프 비활성화 판단은 Phase 밖 [VERIFIED: CONTEXT.md]

---

## Summary

Manual-blog 대비 글쓰기는 `01-extractor (A-F)` → `02-curator (7단락 보도체)` 2단계 파이프라인이었음 [CITED: docs/manual-blog/prompts/01-extractor.md, 02-curator.md]. Phase 37은 이를 Threads Format D (5 cards, 500자/card, `---` 구분 금지 → JSON `{"cards":[]}`, `~임/~했음` 종결, 빈줄 리듬, 카드5 열린질문 강제) 안에 녹이는 것이 목표 [VERIFIED: pipeline/threads/writer.py:build_system_prompt_D, pipeline/threads/validator.py:_validate_last_card_opens_reply].

핵심 불일치 3개: (1) 7단락→5카드 길이/구조 차이, (2) 교차검증 3매체 + 배경기사 1건 = 4개 외부 기사 확보가 현 Threads는 `article_ids` 1개 크롤링 구조 [VERIFIED: pipeline/threads/pitch.py:get_pitches single-article], (3) `01-extractor A-F`는 단일 기사에서 정보 뽑기인데 현 pitch는 "모순 찾기 + but_line" 전용이라 D/E/F 필드 없음.

**Primary recommendation:** `pipeline/threads/contrast/` 신규 모듈 1개 추가 — `extractor.py`(A-F JSON 출력, DB 기사 본문 기반, LLM 1회) + `contrast_writer.py`(7→5 압축 프롬프트, 재사용 `model_router.chat_completion`) 를 2단계 체인으로 두고, writer.py는 `format="contrast"` 신규 builder로 분기. 배경기사 검색은 D1 SQL `LIKE` + Vectorize 의미검색 fallback만 사용(외부 검색 API 신규 도입 금지). 교차 3매체는 D1 cluster/keyword 근접 기사로 모사 — 실제 외부 크롤링 3회는 비용/지연 과다로 제외.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|--------------|----------------|-----------|
| Extractor A-F (사건 구조화) | API/Backend (pipeline) | — | LLM 호출 + 본문 파싱. 브라우저 무관 |
| 배경 기사 검색 (keyword E) | API/Backend (D1 + Vectorize) | — | DB 쿼리. 외부 검색 API 불필요 |
| 3+ 매체 교차검증 (근사) | API/Backend (D1 TEXT search) | — | D1 `news` 테이블 `LIKE` + Vectorize. 브라우저 캐시 아님 |
| 7단락→5카드 큐레이션 | API/Backend (LLM prompt 체인) | — | `writer.py` format builder. CDN/브라우저 무관 |
| 3중 방어 검증 (prompt-leak/korean/한자) | API/Backend (validator.py) | — | 서버 발행 전 게이트. 클라이언트 검증 없음 |
| Threads 발행 (500자/card) | API/Backend | Threads API | API limit은 서버에서 강제 |
| D1 쿼리/프로젝트 경로 | API/Backend (d1_client/project_root) | — | `pipeline/infra` 재사용 |

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `pipeline.threads.writer` | existing (612L) | Format D builder + `write_thread` orchestration | 현 Threads 파이프 재사용 — 신규 format E 분기만 추가 [VERIFIED: codebase grep] |
| `pipeline.threads.validator` | existing (398L) | `validate_final_output`, `validate_card_structure`, `validate_cards` 3중 방어 | 교체 불가 — CONTEXT locked [VERIFIED: codebase] |
| `pipeline.threads.crawler` | existing (83L) | `fetch_article_body` (requests+bs4) | 단일 기사 크롤링만 재사용 [VERIFIED: codebase] |
| `scripts/threads/v3/model_router` | existing (377L, config/models.yaml 17 tiers) | 무료 체인 16개 → 유료 DeepSeek fallback, `chat_completion(messages, system_prompt, temperature, max_tokens, response_format)` | CONTEXT locked 무료 체인 [VERIFIED: config/models.yaml] |
| `pipeline.infra.d1_client` | existing (67L) | `d1_query(sql)` via wrangler D1 remote | DRY. PROJECT_DIR 하드코딩 금지 [VERIFIED: pipeline/infra/d1_client.py] |
| `pipeline.infra.config.project_root` | existing (5L) | `Path(__file__).resolve().parent.parent.parent` | 모든 경로 기준 [VERIFIED: pipeline/infra/config.py] |
| `pipeline.infra.logger` | existing (359L) | `get_scrubbed_logger`, `ScrubRegistry` | 민감정보 스크럽 필수 [VERIFIED: codebase] |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `pipeline.threads.pitch` | existing (778L) | `detect_prompt_leak`, `validate_korean_output`, `is_duplicate_pitch`, `save_pitch_to_history` | dedup + 언어게이트 재사용. `get_pitches()` 자체는 contrast 경로에서 교체 [VERIFIED: codebase] |
| `pipeline.threads.pitch_evaluator` | existing | `filter_pitches` + `EVAL_SYSTEM_PROMPT` | 기존 pitch 품질 평가 — contrast 신규 evaluator에서 패턴 차용하나 별도 프롬프트 필요 [VERIFIED: pipeline/threads/pitch_evaluator.py] |
| `pipeline.infra.vectorize_client` | existing | Vectorize 의미적 중복제거 | 배경기사 검색 fallback로만 사용 [VERIFIED: pipeline/infra/__init__.py] |
| `pipeline.infra.models` | existing (52L) | `NewsArticle`, `BriefingItem` dataclasses | 타입 재사용 [VERIFIED: pipeline/infra/models.py] |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| D1 LIKE + Vectorize 배경검색 | Brave Search / Tavily 외부 API 신규 도입 | 외부 API 키/비용/quota/네트워크 의존 추가 → Phase 비용 초과. Vectorize는 이미 프로젝트에 존재하나 D1 LIKE가 80% 커버 [ASSUMED] — 검증 필요 |
| 2단계 LLM 체인 (extractor→writer) | 1회 통합 프롬프트 ("A-F 추출+7단락 작성 동시") | 1회 호출 비용↓ but 500자/card ×5 제약과 7단락 구조 혼합 시 컨텍스트 과다 → 추출 A-F 신뢰도 저하. 분리 체인이 디버그/재시도 용이 [ASSUMED] |
| `crawler.py` 3매체 재크롤링 | D1 근접 기사 재사용 (description+body 캐시) | 크롤링 3회는 45초+ 실패율 20% [ASSUMED] 추정, D1 재사용이 지연·비용 최소. 실제 교차검증 품질은 낮으나 Threads 500자 제약상 어차피 압축됨 |
| 신규 `contrast/` 패키지 | `writer.py` 내부 함수 추가만 | writer.py는 이미 612L + humanize 로직 과밀. SRP 위반. 신규 모듈이 테스트/검증 분리 유리 |

**Installation:**
```bash
# 추가 패키지 없음 — Python 3.14 stdlib only + 기존 OpenAI SDK already in .venv
# model_router가 yaml 필요:
pip show pyyaml  # already installed via existing deps check
npm view 없음 — Python phase
```

**Version verification:**
```bash
python3 --version  # 3.14.6 [VERIFIED: bash]
/opt/homebrew/bin/wrangler --version  # 4.110.0 [VERIFIED: bash]
# pyyaml / openai / requests / bs4 already in .venv (model_router, crawler 의존)
```

---

## Package Legitimacy Audit

> No new external packages required. All deps are stdlib or already vendored in `.venv`.

| Package | Registry | Age | Downloads | Source Repo | slopcheck | Disposition |
|---------|----------|-----|-----------|-------------|-----------|-------------|
| (none) | — | — | — | — | — | — |

**Packages removed due to slopcheck [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

*If slopcheck was unavailable at research time, all packages above are tagged `[ASSUMED]` and the planner must gate each install behind a `checkpoint:human-verify` task.* — N/A, zero new installs. Planner does not need checkpoints.

Stdlib-only 원칙은 ROADMAP Phase 1-15 전체에서 유지된 제약 [CITED: .planning/ROADMAP.md "Zero new external dependencies — Python 3.14 stdlib only"].

---

## Architecture Patterns

### System Architecture Diagram

```
[D1 news DB] ──┐
               │  d1_query (SQL LIKE)
               v
[Seed Article 선정] ──> [Extractor (LLM 1회)] ──> A-F JSON {A 사건/B 수치/C 인용/D 상위주제/E 키워드3/F 질문}
               │              │                           │
               │              │ D/E ──────────────────────┘
               │              │         │
               │              v         v
               │     [Background Search: D1 LIKE + Vectorize fallback]
               │              │
               │              v
               │     [Cross-media 근사: D1 cluster/동일 키워드 기사 2-3건 fetch (no extra crawl)]
               │              │
               v              v
         [Curator Writer (LLM 2회, Format contrast)]
               │
               ├──> 7단락 보도체 초안 (internal, 500자/card 제약 전)
               └──> 5-card 압축 + 리듬 라포 (빈줄, ~임, 500자, 카드5 열린질문)
               │
               v
         [validator.py 3중 방어] ──> fail → drop / retry once
               │
               v
         [publisher / draft save] ──> DRAFTS_DIR / Threads API
```

Reader trace: D1 seed 기사 1건 → Extractor가 A-F로 구조화 → D/E로 배경기사 1건 D1에서 탐색 → 동 cluster에서 교차검증용 2건 확보(크롤 없이) → Curator가 7→5 압축 Threads 카드 생성 → validator 3차 게이트 → 발행.

### Recommended Project Structure
```
pipeline/threads/
├── contrast/
│   ├── __init__.py          # exports: run_contrast_thread, ContrastBundle
│   ├── extractor.py         # A-F JSON extractor (LLM 1회, article body -> structured dict)
│   ├── background_search.py # keyword E -> D1 LIKE + Vectorize fallback -> 1 article
│   ├── contrast_writer.py   # 7->5 압축 writer (build_system_prompt_contrast, write_contrast_thread)
│   └── prompts.py           # extractor/curator system prompts (versioned strings, not .md runtime load)
├── writer.py                # MODIFY: add FORMAT_BUILDERS["contrast"], import contrast path
├── validator.py             # REUSE as-is (no change; if contrast-specific rule, add optional flag)
├── pitch.py                 # REUSE helpers only (detect_prompt_leak, is_duplicate_pitch)
└── crawler.py               # REUSE fetch_article_body for seed only
scripts/threads/
├── main_v3.py               # MODIFY: add --format contrast flag, branch to contrast pipeline
└── v3/model_router.py       # REUSE (no change)
```

### Pattern 1: Two-Step LLM Chain with Typed Intermediate (Extractor A-F)
**What:** Extractor는 원문 1건을 받아 `{"A":..., "B":..., "C":..., "D":..., "E":[...], "F":[...]}` JSON만 출력. Curator는 그 JSON + 원문 3-4건 묶음을 받아 5-card 출력. 중간 JSON은 code에서 검증(B>=2, C>=2, E len==3) 후 실패 시 `기사 없음` 폐기.
**When to use:** 입력이 길고 후속 검색 키워드에 의존할 때. 중간 구조화가 없으면 키워드 E 품질이 붕괴됨.
**Example:**
```python
# Source: pipeline/threads/contrast/extractor.py (proposed, pattern follows writer.py:chat_completion)
from scripts.threads.v3.model_router import chat_completion
import json, re

SYSTEM_EXTRACTOR = """당신은 기사 1건을 읽고 후속 심층 취재에 필요한 정보를 구조화하는 리서치 어시스턴트입니다.
규칙: 없는 정보 = "기사에 명시되지 않음". 추론 금지. 출력은 JSON만."""

def extract_af(article_body: str, title: str) -> dict | None:
    prompt = f"제목: {title}\n본문: {article_body[:12000]}\n\nA-F JSON으로 출력: {{\"A\":{{...}}, \"B\":[...], \"C\":[...], \"D\":..., \"E\":[...3개], \"F\":[...]}}"
    text = chat_completion(system_prompt=SYSTEM_EXTRACTOR,
                           messages=[{"role":"user","content":prompt}],
                           temperature=0.2, max_tokens=3000,
                           response_format={"type":"json_object"})
    if not text: return None
    data = json.loads(text)
    # guard: B>=2, C>=2, E==3, D non-empty
    if len(data.get("B",[])) < 2 or len(data.get("C",[])) < 2: return None
    if len(data.get("E",[])) != 3: return None
    return data
```

### Pattern 2: 7→5 Card Compression Mapping
**What:** 7단락(놀라움/배경/전개/예상밖반응/핵심인물/논지심화/결론)을 5카드로 재배치. 가장 정보밀도 낮은 병합 지점을 선택.
**When to use:** Phase 37 전제조건 (Threads 500자/card hard limit)
**Recommended mapping:**

| Card | 7단락 source | 역할 | 내용 |
|------|-------------|------|------|
| 1 | 1 놀라움 + 2 배경 일부 | Hook — 반전 먼저, 경위 1줄 | 기사 밖 통념 세우기 + 놀라움 팩트 1개 [CITED: 02-curator.md:1-2단계, style_examples.md 1번 패턴] |
| 2 | 2 배경 + 3 전개 | 전환 = but_line — 대비 논지 제시 | 시간순 경위 + 논란 확산 [CITED: 02-curator.md: 2-3] |
| 3 | 4 예상밖반응 + 5 핵심인물 | 증거 A — 진짜 피해자/반전 | 당사자 반응 + 신규 인물 등장 [CITED: 02-curator.md: 4-5] |
| 4 | 6 논지심화 | 증거 B — 허점 지적 | 그 인물 시각에서 규정/해결책 허점 [CITED: 02-curator.md: 6] |
| 5 | 7 결론 | 열린질문 — 대비 재정의 | 표면/근본 대비 다시 정리하되 ?/열린어미로 [VERIFIED: validator.py _validate_last_card_opens_reply] |

*Alternative rejected:* 1→1, 2→1, 3→1, 4→1, 5+6+7→1 (3개 병합)은 4번 논지심화 희석. Card 4에 논지심화를 단독 배치가 Threads "증거 B" 역할과 정렬됨 [CITED: style_examples.md 템플릿 3번=증거A 4번=증거B].

### Pattern 3: Background Search via D1 Only (No External API)
**What:** keyword E 3개로 `SELECT ... WHERE title LIKE '%kw%' OR description LIKE '%kw%'` + `pub_date` 30일 내림차순 1건 pick. 결과 0이면 `vectorize_client` 의미검색 fallback, 그래도 0이면 배경기사 없이 진행(대비 논지는 유지, 배경 연결 문장만 생략).
**When to use:** 외부 검색 키 없거나 quota 우려 시. D1은 이미 600+ 기사 풀로 충분한 근사.
**Example:**
```python
# Source: pipeline/threads/contrast/background_search.py (proposed, pattern follows pipeline/infra/d1_client)
from pipeline.infra.d1_client import d1_query

def find_background(keywords: list[str], exclude_id: str) -> dict | None:
    for kw in keywords:
        sql = f"SELECT id,title,description,link,pub_date FROM news WHERE (title LIKE '%{kw}%' OR description LIKE '%{kw}%') AND id != '{exclude_id}' ORDER BY pub_date DESC LIMIT 1"
        rows = d1_query(sql)
        if rows: return rows[0]
    # fallback vectorize
    try:
        from pipeline.infra.vectorize_client import query as vquery
        res = vquery(keywords[0], top_k=1)
        if res: return res[0]
    except Exception: pass
    return None
```
*Note:* SQL injection not a concern — keywords are LLM-generated short Korean phrases; still parameterize via escaping single quotes if needed. `d1_query` currently ignores `params` [VERIFIED: d1_client.py:_parse_result ignores params] → string interpolation required by existing API.

### Pattern 4: Reuse Existing Validator Gates Unchanged
**What:** 기존 3중 방어 그대로 적용 — Phase 내부 신규 프롬프트 노출 패턴 있으면 `LEAKED_PROMPT_PATTERNS`/`_SYSTEM_PROMPT_FRAGMENTS`에 추가만, 로직 교체 없음.
**When to use:** Always.

### Anti-Patterns to Avoid
- **7단락 전체를 5카드에 무리하게 압축해 한 카드 500자 초과:** writer의 `validate_card_structure`가 500자 초과 시 drop [VERIFIED: validator.py:360]. 7→5 병합 설계 때 각 카드 400자 target으로 여유 두기.
- **Extractor를 .md 파일 런타임 로드:** `docs/manual-blog/prompts/*.md`는 contrast-writing skill의 분리 보장 경로 [CITED: contrast-writing SKILL <process> #7]. runtime file I/O로 로드하면 skill 분리 위반 + 경로 하드코딩. `prompts.py`에 문자열 상수로 버전 고정.
- **crawler 3회 신규 호출:** pitch.py는 이미 `fetch_article_body` 15s timeout ×2 retry [VERIFIED: crawler.py:59]. 3매체 추가하면 p95 latency 60초+. D1 캐시 재사용이 ponytail lazy 정답.
- **새 외부 검색 패키지 도입:** `brave_search`, `tavily-python`, `exa` 등 불필요. stdlib+existing vectorize로 충분. 신 패키지 = supply chain risk + slopcheck 대상.
- **Dedup 우회:** `is_duplicate_pitch(article_ids overlap >=0.5)` [VERIFIED: pitch.py:371]가 contrast 확장 article_ids 3-4개일 때도 동일 로직 작동해야. article_ids를 3개로 늘리면 dedup 민감도 재조정 필요 — 초안에서는 seed 1개만 dedup 키로 유지.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| LLM 라우팅/재시도/서킷브레이커 | custom retry loop | `scripts/threads/v3/model_router.chat_completion` | tier_order 17개, backoff [10,20], circuit breaker 10회/300초 이미 구현 [VERIFIED: model_router.py:107-112]. 재구현 시 무료 quota 버닝 |
| D1 쿼리/wrangler 토큰 해제 | subprocess 직접 호출 | `pipeline.infra.d1_client.d1_query` | CLOUDFLARE_API_TOKEN env 제거 + retry 2회 내장 [VERIFIED: d1_client.py:22-27] |
| 프로젝트 루트 해석 | `os.path.dirname(__file__)` 하드코딩 | `pipeline.infra.config.project_root()` | 모든 infra가 이 함수 재사용 [VERIFIED: config.py:3] |
| 로그 스크러빙 | print 직접 | `pipeline.infra.logger.get_scrubbed_logger` | API 키/JWT/이메일 20+ 패턴 자동 redaction [VERIFIED: logger.py:60-125] |
| 카드 JSON 파싱 | regex 파싱만 | `pipeline.threads.writer._try_parse_json` + `_parse_by_delimiter` fallback | JSON object + code block + brace stack + delimiter 4단계 fallback 이미 검증 [VERIFIED: writer.py:295-379] |
| 한글/한자/모델메시지 검증 | regex 신규 작성 | `pipeline.threads.validator.validate_final_output` | NFKC 정규화 + 한자/일본어 + 한글비율 0.3 + 모델메시지 18패턴 통합 [VERIFIED: validator.py:180-219] |
| URL 정규화/dedup | 문자열 비교 | `db_reader.normalize_url` + `dedup.is_same_topic` | Jaccard 0.30 + entity overlap 2개 threshold 검증됨 [CITED: AGENTS.md 중복 방지] |

**Key insight:** Threads 파이프는 이미 "무료 체인 → 3중 방어 → 500자 검증 → 중복제거"가 완비된 상태. 대비 글쓰기 pivot은 프롬프트+매핑만 신규 — infra는 100% 재사용이 lazy 정답.

---

## Common Pitfalls

### Pitfall 1: Extractor A-F 출력 불완전으로 체인 중단
**What goes wrong:** LLM이 B(수치) 1개만 주거나 C(인용) 0개 주면 `len(B)<2` guard에 걸려 전체 contrast thread drop → 발행률 하락.
**Why it happens:** 기사 원문이 수치/인용 빈약 (브리핑성 요약 기사). 기존 pitch.py는 `description` 200자 이하에서도 동작 [VERIFIED: pitch.py:561-565], 근데 extractor는 `보도자료형 금지` 규칙 [CITED: 02-curator.md 제약].
**How to avoid:** extractor prompt에 "기사에 없는 수치면 favorite 통계/날짜라도 B에 넣으라" 완화. 또는 guard를 B>=1, C>=1로 하향. 모니터링: `extractor_fail_no_numbers` 카운터 로그.
**Warning signs:** contrast 일일 성공률 < 30% (기존 threads 1.5/일 대비 급락).

### Pitfall 2: Background Search 0-result로 대비 논지 붕괴
**What goes wrong:** keyword E 3개가 모두 D1에서 매칭 0이면 배경기사 없이 진행 → "두 사건이 같은 문제의 다른 얼굴" 연결점 [CITED: 02-curator.md 2단계]이 없어져 대비 논지가 공허.
**Why it happens:** E 키워드는 근본 문제 가설 기반이라 D1 기사 풀과 어휘 mismatch. 600개 중 매칭 0 확률 높음 [ASSUMED].
**How to avoid:** (a) Vectorize fallback, (b) 키워드 3개 OR 검색, (c) 없으면 "배경 없이 단일 사건 대비 논지만 서술" fallback 프롬프트 분기. 100% 실패가 아닌 graceful degradation.
**Warning signs:** `background_found_ratio` 50% 미만.

### Pitfall 3: 500자/card 초과로 validator drop
**What goes wrong:** 7단락 보도체는 단락당 3-4문장×7=21-28문장. 5카드 압축해도 카드2-3이 500자 초과 → `validate_card_structure len>500` [VERIFIED: validator.py:360]에서 drop.
**Why it happens:** 보도체 문체 "짧고 건조" [CITED: 02-curator.md 제약]인데도 구체적 사실 1개/단락 강제라 장문화 경향.
**How to avoid:** Curator system prompt에 "각 카드 350-450자, 500자 초과 금지" 명시. `format builders`에서 `max_tokens` 16000 유지 [VERIFIED: writer.py:527] but card-level truncation not retry — 초과 시 재생성 1회만.
**Warning signs:** `card_length_invalid` validator 실패 로그 급증.

### Pitfall 4: 3중 방어 신규 프롬프트 노출 패턴 누락
**What goes wrong:** extractor/curator 신규 시스템 프롬프트 문자열("상위 주제:", "근본 문제:", "대비 논지:" 등)이 카드에 노출돼도 기존 `LEAKED_PROMPT_PATTERNS` 3개 + `_SYSTEM_PROMPT_FRAGMENTS` 8개 [VERIFIED: pitch.py:28-43]에 매칭 안 돼 통과 → 발행 오염.
**Why it happens:** 3중 방어 패턴은 기존 pitch/writer 프롬프트 기준으로 하드코딩.
**How to avoid:** contrast prompts.py 확정 후, 각 시스템 프롬프트의 고유 라벨을 `LEAKED_PROMPT_PATTERNS`에 2-3개 추가. `validate_final_output`은 이미 `detect_prompt_leak` 재사용 [VERIFIED: validator.py:186] 하므로 pitch.py 갱신만으로 3중 방어 자동 반영.
**Warning signs:** 카드에 "상위 주제:" / "근본 문제 가설:" 원문 노출.

### Pitfall 5: `v3.model_router` import 경로 혼선
**What goes wrong:** `from v3.model_router import chat_completion` vs `from pipeline.infra...` 혼용. Phase 4 Strangler Fig re-export 래퍼가 아직 존재 [VERIFIED: scripts/threads/v3/narrative_pitcher.py re-export]. 신규 코드에서 잘못된 경로 쓰면 `ModuleNotFoundError`.
**Why it happens:** `writer.py:155`는 `from v3.model_router import chat_completion` [VERIFIED] — `pipeline/threads` 밖에서 동작하는 레거시 경로. `pipeline/threads/contrast`에서 `from scripts.threads.v3.model_router`는 sys.path 없이는 실패.
**How to avoid:** 새 모듈에서는 `from scripts.threads.v3.model_router import chat_completion` + `sys.path.insert(0, str(project_root()))` 패턴 통일, 또는 `writer.py`와 동일하게 `from v3.model_router import chat_completion` + `sys.path` 보정 둘 중 하나 명시. tests에서 path mock 필요.
**Warning signs:** `pytest`에서 `ModuleNotFoundError: No module named 'v3'`.

### Pitfall 6: dedup article_ids 3-4개 확장 시 과도 필터링
**What goes wrong:** `is_duplicate_pitch`가 `overlap/len(new_ids) >=0.5` [VERIFIED: pitch.py:374]. contrast에서 article_ids를 [seed, cross1, cross2, background] 4개로 보내면 seed 1개 겹쳐도 `1/4=0.25` <0.5라 통과인데, background만 겹쳐도 중복 판단 어려움. 반대로 2개 겹치면 `0.5`로 drop → 과도 차단.
**Why it happens:** 기존 로직은 단일 기사(1개) 전제.
**How to avoid:** contrast 전용 dedup 키는 `seed_id` 1개만 사용. 나머지 cross/background는 dedup에서 제외. `is_duplicate_pitch` 호출 시 `pitch["seed_id"]` 별도 필드로 seed-only 비교.
**Warning signs:** contrast 발행률 0 (모든 후보가 dedup에 걸림).

---

## Code Examples

Verified patterns from existing codebase:

### D1 Query + project_root
```python
# Source: pipeline/infra/d1_client.py + pipeline/infra/config.py
from pipeline.infra.config import project_root
from pipeline.infra.d1_client import d1_query

# 30일 이내 AI 기사 1건 샘플
rows = d1_query("SELECT id,title,description,link,pub_date FROM news WHERE pub_date >= date('now','-30 days') ORDER BY pub_date DESC LIMIT 5")
```

### Model Router Free Chain Call (JSON mode, reasoning disabled for DeepSeek)
```python
# Source: pipeline/threads/writer.py:533, scripts/threads/v3/model_router.py:260
from scripts.threads.v3.model_router import chat_completion  # via sys.path; writer.py uses `from v3.model_router`

text = chat_completion(
    system_prompt="당신은 ... JSON만 출력",
    messages=[{"role":"user","content": user_prompt}],
    temperature=0.4,
    max_tokens=16000,
    model_override=None,  # 무료 체인 16개 → DeepSeek last resort
    response_format={"type":"json_object"},  # deepseek일 때만 적용됨 [VERIFIED: model_router.py:146]
    extra_body={"thinking":{"type":"disabled"}} if True else None,  # deepseek only [VERIFIED: writer.py:521-522]
)
```

### Validator 3중 방어 호출
```python
# Source: pipeline/threads/writer.py:560-586, pipeline/threads/validator.py
from pipeline.threads.validator import validate_cards, validate_year, validate_final_output, validate_card_structure, validate_model_message

vc_ok, vc_reason = validate_cards(cards, pitch, "contrast")  # or "D"
vy_ok, vy_reason = validate_year(cards, article_body_text)
if not (vc_ok and vy_ok): drop()
ok, reason = validate_card_structure(cards)  # includes _validate_last_card_opens_reply
if not ok: drop()
for c in cards:
    ok, reason = validate_model_message(c)
    if not ok: drop()
ok, reason = validate_final_output(cards)  # prompt-leak + NFKC + 한자 + 한글비율 + hook-entity + model-message
if not ok: drop()
```

### Scrubbed Logger
```python
# Source: pipeline/infra/logger.py:227
from pipeline.infra.logger import get_scrubbed_logger
logger = get_scrubbed_logger(__name__)
logger.info("토큰: %s", token)  # auto redacted
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| blog_draft_generator.py 1500자 3 H2 단일 프롬프트 | contrast 7단락 보도체 (prep) — 미구현 | 2026-08-26 docs 추가 | Phase 37이 Threads로 pivot — 블로그 신버전 구현 안 함 |
| Threads FORMAT_D 6카드(링크 포함) | FORMAT_D 5카드(링크 분리 답글) | 2026-07-09 Phase 32 [VERIFIED: PLAN.md] | writer 반환이 `dict{cards, link}`로 변경 — contrast도 동일 계약 따름 |
| GPT-4o-mini 평가/후처리 | 무료 체인 16개 (Gemini/Groq/Cerebras/Zhipu) → DeepSeek last | 2026-08-12 [VERIFIED: model_router.py:251-362] | model_override="openai" 호출 차단됨 — contrast도 None만 사용 |
| delimiter 기반 파싱 (`---` split) | JSON `{"cards":[]}`-first + 4단계 fallback | 2026-07-05 Phase 14 [VERIFIED: writer.py:295] | 500자/card 초과 시 JSON 잘림 위험 — max_tokens 16000 유지 필요 |
| humanize가 GPT-4o-mini | humanize도 무료 체인 (temperature 0.3) | 2026-08-12 [VERIFIED: writer.py:246-252] | contrast 카드도 동일 humanize 파이프 재사용 가능 |

**Deprecated/outdated:**
- `model_override="openai"` / `OPENAI_MODEL="gpt-4o-mini"` — 차단됨 [VERIFIED: model_router.py:360-362]. 어떤 contrast 코드에서도 사용 금지.
- `article_ids` 2개 이상 사용 — pitch.py SYSTEM_PROMPT에서 "반드시 1개" 강제 [VERIFIED: pitch.py:152]였으나 contrast는 seed 1개 dedup 키 유지, cross/background는 별도 필드로 분리해야 함.
- `scripts/threads/v3/writer_v3.py`, `narrative_pitcher.py` 직접 수정 — Strangler Fig re-export 래퍼 [VERIFIED: writer_v3.py header]. 수정 대상은 `pipeline/threads/*` only.

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | D1 `news` 테이블에 `title/description/link/pub_date/source/original_title` 컬럼이 존재하고 LIKE 검색이 동작함 | Standard Stack, Architecture | 스키마 다르면 background_search 전체 실패. 검증: `d1_query("SELECT sql FROM sqlite_master")` |
| A2 | 외부 검색 API 없이 D1 LIKE + Vectorize fallback으로 배경기사 1건 확보율이 50%+ | Architecture Patterns | 30% 미만이면 대비 논지 빈약. fallback으로 "배경 없이 진행" 허용 필요 |
| A3 | 2단계 체인 (extractor 1회 + writer 1회) latency ~30-45초/토큰 비용이 무료 체인으로 감당 가능 | Standard Stack | 무료 tier rate limit (예: Groq 30 req/min)로 1일 1회 발행은 OK, 더 빈번하면 throttle |
| A4 | 교차검증 3매체를 D1 근접 기사로 모사해도 Threads 500자 제약상 품질 저하는 독자가 체감하기 어려움 | Pitfalls | 실제 외부 3매체 크롤링 대비 대비 논지 깊이 저하 — 대비 논지 자체는 LLM이 생성하므로 큰 차이 없을 수도. 사용자 피드백으로 검증 |
| A5 | `d1_query` params 미지원이라 문자열 보간 필요 (SQL injection은 LLM 키워드라 low risk) | Code Examples | 특수문자 `'` 포함 키워드 시 SQL 오류. escape 처리 필요 |
| A6 | 기존 dedup threshold (overlap 0.5, entity overlap 2개)가 contrast seed-only dedup에도 그대로 적용 가능 | Pitfalls #6 | threshold 재조정 필요할 수 있음 — 모니터링으로 조정 |
| A7 | writer `response_format json_object`가 무료 체인 일부 모델에서 무시되어도 fallback delimiter 파싱이 커버 | State of Art | Groq/Cerebras에서 json_object 무시 시 파싱 실패율 상승 — model_router가 response_format을 deepseek만 전달 [VERIFIED: model_router.py:146]하므로 무료 tier는 실제로 JSON 강제 안 됨. 프롬프트에 "JSON만" 명시로 보완 필요 |

---

## Open Questions

1. **7→5 매핑 최선안** — RESOLVED: 카드1(놀라움+배경 일부), 카드2(배경+전개), 카드3(예상밖반응+인물), 카드4(논지심화), 카드5(결론 열린질문). 논지심화 단독 카드4 배치가 Threads 증거B 패턴과 정렬됨. 대안(5+6+7 병합)은 논지 희석으로 기각.

2. **교차검증 3매체 크롤링 구현 — crawler 재사용 가능? 추가 API 필요?** — RESOLVED: crawler 재사용하되 실제 크롤은 seed 1건만. 나머지 2건은 D1 description/body 재사용. 추가 검색 API 도입 금지 (cost/delay/키 관리 과다). Phase 후반에 품질 부족 시 외부 검색 추가를 별도 Phase로 분리.

3. **배경기사 연결(키워드 E) 검색 — D1 vs 외부 검색 중 현실적?** — RESOLVED: D1 LIKE 1순위, Vectorize 2순위, 실패 시 배경 없이 진행(graceful degradation). 외부 API는 Phase 범위 밖.

4. **추출기 A-F 구조를 코드 모델로 둘지 프롬프트 체인 2단계로 둘지** — RESOLVED: 프롬프트 체인 2단계 (extractor LLM 1회 → B/C/E 검증 → background search → curator LLM 1회). A-F를 코드 struct로만 두면 키워드 E 품질 보장 불가. LLM이 D/E를 추론해야 함. 중간 JSON은 코드에서 검증하는 하이브리드.

5. **기존 pitch/narrative dedup 영향** — RESOLVED: seed_id 1개만 dedup 키. cross/background는 dedup 제외. `is_duplicate_pitch`/`is_same_topic` 재사용하나 contrast 전용 래퍼에서 필터링.

6. **model_router free chain usage** — RESOLVED: `model_override=None` 고정, `response_format`은 deepseek일 때만 적용되므로 프롬프트에 "JSON만" 이중 명시 필수. temperature extractor 0.2 / curator 0.4-0.7 (curator는 창의성 필요).

7. **500char/card constraint** — RESOLVED: curator prompt에 350-450자 target 명시. validator는 500자 초과 시 drop [VERIFIED: validator.py:360] — 재생성 1회 후에도 초과면 drop.

8. **Validation gates (3중 방어 확장)** — RESOLVED: 기존 validator 로직 재사용. contrast 신규 시스템 프롬프트 라벨 2-3개를 `LEAKED_PROMPT_PATTERNS`/`_SYSTEM_PROMPT_FRAGMENTS`에 추가만. 그 외 게이트 동일.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python | all pipeline | ✓ | 3.14.6 | — |
| wrangler | d1_client remote query | ✓ | 4.110.0 | — |
| D1 aikorea24-db | article fetch, background search | ✓ (assumed reachable) | — | build fails, no background |
| Vectorize | background fallback | ✓ (pipeline/infra/vectorize_client exists) | — | D1 LIKE만 사용 |
| OpenAI SDK | model_router | ✓ (in .venv, used by writer/pitch) | — | — |
| pyyaml | model_router config load | ✓ (required by model_router) | — | chain 비활성 → deepseek 단독 |
| requests + bs4/lxml | crawler | ✓ (crawler.py imports) | — | D1 description fallback |
| DEEPSEEK_API_TOKEN | last-resort LLM | ✓ (env present, redacted) | — | free chain only |
| GEMINI/GROQ/CEREBRAS keys | free chain tiers | unknown (check .env.common) | — | skip tier → next |
| Threads API | publish | not needed for research | — | draft save only |

**Missing dependencies with no fallback:** none blocking
**Missing dependencies with fallback:**
- Vectorize down → D1 LIKE만으로 배경검색
- Free chain rate-limit → DeepSeek last-resort [VERIFIED: model_router.py:250]
- Crawl 3매체 실패 → D1 description fallback [VERIFIED: writer.py:469]

---

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | — (pipeline uses env tokens, no user auth) |
| V3 Session Management | no | — |
| V4 Access Control | no | — |
| V5 Input Validation | yes | `validator.py` 3중 방어 (prompt-leak, NFKC, 한자/일본어, 한글비율, model-message) [VERIFIED: validator.py] |
| V6 Cryptography | no | — |
| V8 Data Protection | yes | `pipeline.infra.logger.ScrubRegistry` 20+ patterns + env scrub [VERIFIED: logger.py] |
| V14 Configuration | yes | `EnvConfig` + `project_root()` + `d1_client._build_env()` removes CLOUDFLARE_API_TOKEN [VERIFIED: d1_client.py:22] |

### Known Threat Patterns for threads pipeline

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Prompt injection via article body (외부 크롤 본문에 지시문 삽입) | Tampering | `detect_prompt_leak` + `validate_final_output` 3중 방어, system prompt 최우선 규칙 [VERIFIED: pitch.py:120-149] |
| LLM hallucinates invented year/entity | Tampering | `validate_year` (body years + current_year만 허용) + `validate_no_foreign_language` + hook-entity consistency [VERIFIED: validator.py:81-275] |
| API key leakage in logs | Information Disclosure | `ScrubRegistry` + `ScrubLogFilter` on all pipeline loggers [VERIFIED: logger.py] |
| D1 SQL injection via LLM keyword | Tampering | Keyword is short Korean phrase (3-5 words), still escape `'` → `''`. `d1_query` ignores params so manual escape required [ASSUMED: A5] |
| Threads API 500자 초과 causing publish reject | Denial of Service | `validate_card_structure` 500자 상한 + `validate_cards` count check [VERIFIED: validator.py:49-360] |

---

## Files to Reuse / Create / Modify

| Action | File | Est. Lines | Notes |
|--------|------|-----------|-------|
| **REUSE** | `pipeline/threads/writer.py` | 0 new | Add `FORMAT_BUILDERS["contrast"]` + `build_system_prompt_contrast()` ~60L modification |
| **REUSE** | `pipeline/threads/validator.py` | 0 new | Add 2-3 contrast leak patterns ~5L; else no change |
| **REUSE** | `pipeline/threads/crawler.py` | 0 | `fetch_article_body` for seed only |
| **REUSE** | `pipeline/threads/pitch.py` | 0 | Import `detect_prompt_leak`, `is_duplicate_pitch`, `save_pitch_to_history` helpers |
| **REUSE** | `scripts/threads/v3/model_router.py` | 0 | `chat_completion` as-is, `model_override=None` |
| **REUSE** | `pipeline/infra/d1_client.py` | 0 | `d1_query` |
| **REUSE** | `pipeline/infra/config.py` | 0 | `project_root()` |
| **REUSE** | `pipeline/infra/logger.py` | 0 | `get_scrubbed_logger` |
| **CREATE** | `pipeline/threads/contrast/__init__.py` | ~15 | exports, ContrastBundle dataclass |
| **CREATE** | `pipeline/threads/contrast/prompts.py` | ~120 | SYSTEM_EXTRACTOR, SYSTEM_CURATOR_CONTRAST (versioned strings, includes rhythm/card5 rules) |
| **CREATE** | `pipeline/threads/contrast/extractor.py` | ~120 | `extract_af(article_body)->dict`, B/C/E guards, JSON parse |
| **CREATE** | `pipeline/threads/contrast/background_search.py` | ~80 | `find_background(keywords, exclude_id)` D1 LIKE + Vectorize fallback |
| **CREATE** | `pipeline/threads/contrast/contrast_writer.py` | ~180 | `build_system_prompt_contrast()`, `write_contrast_thread(bundle, articles)` 2-phase compress 7→5 |
| **CREATE** | `pipeline/threads/contrast/orchestrator.py` | ~100 | `run_contrast_thread(seed_article)` glue: extractor→background→contrast_writer→validator→save |
| **MODIFY** | `scripts/threads/main_v3.py` | ~40 | `--format contrast` flag, branch to contrast orchestrator |
| **MODIFY** | `pipeline/threads/writer.py` | ~60 | contrast builder + FORMAT_LABELS entry + optional dispatch |
| **CREATE** | `tests/test_contrast_extractor.py` | ~80 | B/C/E guard, JSON parse, prompt-leak 없는지 |
| **CREATE** | `tests/test_contrast_writer.py` | ~100 | 5-card count, 500자, card5 열린질문, 한자 금지, fallback no-background |
| **CREATE** | `tests/test_contrast_background.py` | ~60 | D1 LIKE mock, Vectorize fallback, 0-result graceful |
| **Total new** | | **~860 + tests ~240 = ~1100** | Ponytail: writer는 수정 최소, contrast/*가 신규 경계의 대부분 |

---

## Sources

### Primary (HIGH confidence)
- CONTEXT.md — Phase 37 goal, constraints, open questions
- pipeline/threads/writer.py (612L) — Format D builder, SYSTEM prompt, `chat_completion` call, 4-stage JSON parse, validator chaining
- pipeline/threads/pitch.py (778L) — `detect_prompt_leak`, `is_duplicate_pitch`, `get_pitches` single-article flow
- pipeline/threads/validator.py (398L) — `validate_final_output`, `validate_card_structure` (500자, 0.15 한글비율), `_validate_last_card_opens_reply`
- pipeline/threads/crawler.py (83L) — `fetch_article_body` 15s×2, bs4 selectors
- pipeline/infra/d1_client.py (67L) — `d1_query`, CLOUDFLARE_API_TOKEN removal, params ignored
- pipeline/infra/config.py (5L) — `project_root()`
- pipeline/infra/logger.py (359L) — `ScrubRegistry` 20+ patterns
- scripts/threads/v3/model_router.py (377L) — 17 tiers, `chat_completion` with `response_format` deepseek-only, circuit breaker 10/300
- config/models.yaml — tier_order 17, provider base_urls
- docs/manual-blog/prompts/01-extractor.md (45L) — A-F structure
- docs/manual-blog/prompts/02-curator.md (37L) — 3+검증 + 배경1건 + 7단락 + 보도체 제약

### Secondary (MEDIUM confidence)
- ~/.config/opencode/skills/contrast-writing/SKILL.md — 2단계 파이프라인, 분리 보장 (`run_pipeline.py` 수정 금지, `docs/manual-blog/` 고정)
- ~/.config/opencode/skills/thread-content-writing/SKILL.md — Threads 4단/8카드/뉴스브리핑 구조, 80/20 법칙 (context for not reusing blog 80/20 here)
- .planning/phases/32-threads-algorithm-aligned/PLAN.md — 5카드 + 링크 분리, card5 답글 유도 강제 선례
- scripts/threads/v3/style_examples.md (440L) — 5카드 rhythm/절/빈줄/열린질문 실전 예시
- .planning/ROADMAP.md — stdlib-only, Strangler Fig history

### Tertiary (LOW confidence)
- (none — all WebSearch claims would be LOW; this phase uses no WebSearch per ponytail stdlib-first)

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all modules exist and were read line-by-line
- Architecture (7→5 mapping, D1 background): MEDIUM — mapping is judgment call, D1 LIKE coverage is ASSUMED (A1/A2)
- Pitfalls: MEDIUM-HIGH — validator thresholds and crawler timeouts are verified, but extractor failure rates are estimated
- Security: HIGH — validator/logger/d1_client verified in code

**Research date:** 2026-08-26
**Valid until:** 2026-09-25 (30 days — Threads pipeline is stable, LLM tier_order may drift but not structurally)
