# TECH.md — aikorea24.kr 시스템 기술 문서

> 프로젝트 루트: ~/Projects/aikorea24
> 변경 이력은 CHANGES.md 참조

---

## 1. 전체 파이프라인

```
keywords.json → D1 DB ← db_reader (기사 수집)
                     ↓
            narrative_pitcher (피치 생성)
                     ↓
               writer (쓰레드 작성, format='D' 고정)
                     ↓
         validate_final_cards (검증)
                     ↓
           publisher (Threads 발행)
                     ↓
            posted.json (중복 방지 저장)
```

### 실행 주기
- **launchd**: 2시간 간격 (`pipeline/__main__.py` → `StepRunThreads` → `main_v3.py`)
- **1회 실행**: `python -m pipeline run` 또는 `python -m pipeline run --dry-run`
- **실패 알림**: `PipelineOrchestrator._send_telegram_failure()`가 step 실패 시 Telegram 전송

### 별도 파이프라인
- **Tools 수집** (`scripts/tools_collector.py`): 매일 06:00 launchd 실행 — Section 10 참조
- **Briefing/블로그** (`scripts/run_pipeline.py`): launchd 06/20시 — Section 9 참조

### 주요 진입점
- `scripts/threads/main_v3.py` — 메인 파이프라인 (`run_v3()`)
- `scripts/threads/v3/writer_v3.py` — 쓰레드 생성 (`write_thread()`)
- `scripts/threads/v3/narrative_pitcher.py` — 피치 생성 (`get_pitches()`)
- `scripts/threads/v3/format_selector.py` — 형식 선택 (`select_format()`)
- `scripts/threads/db_reader.py` — D1 DB 연결

---

## 2. 형식: D (펀치 브리핑형)

> 유일한 활성 형식. 5개 콘텐츠 카드 + 1개 링크 카드 (자동 추가).

### 프롬프트 구조 (build_system_prompt_D)
- stanza 구조: 3~5줄 + 빈 줄 반복. 빈 줄이 리듬
- 한 줄 25~40자. 카드당 450~500자
- 반말체 강제 (~임, ~했음, ~있음)
- 숫자-설명 쌍 구조: 숫자 먼저 → 의미 풀어쓰기
- 대비 구조: "A였음. 그런데 B."

### 각 카드 역할

| 순서 | 역할 | 설명 |
|------|------|------|
| 1 | 훅 | punch → 빈 줄 → 숫자/날짜 |
| 2 | 충돌 A면 | 구체적 사실, 숫자, 인용, 연구 결과 |
| 3 | 반전 | 예상 못 한 제3의 사실 |
| 4 | 확장 | 더 큰 맥락 또는 연결점 |
| 5 | 여운 | 숫자/사실 반전. 선언형 마무리 |
| 6 | 링크 | 자동 추가 (assemble_final) |

### 금지 규칙 (최소화)
- ~합니다, ~이다 금지 (반말체만)
- "많은", "대규모" 뭉뚱그린 표현 금지
- 없는 사실/연도 금지 (할루시네이션 방지)
- 피치 메타데이터 레이블 출력 금지

---

## 3. DB 구조

### D1 뉴스 DB
- 테이블: `articles` (또는 유사 이름)
- 주요 필드: `id`, `title`, `original_title`, `link`, `description`, `source`, `published_at`, `created_at`, `priority`

### posted.json (중복 발행 방지)
- `posted_ids`: 발행된 기사 ID 목록
- `posted_links`: 발행된 링크 목록
- `posted_titles`: 발행된 제목 목록
- `posted_original_titles`: 발행된 원제목 목록
- `posted_article_meta`: 기사 메타정보 (semantic dedup용)
- `last_reset`: 마지막 리셋 일자

### 중복 발행 방지 (3단계)
1. **Phase 1** (`db_reader.is_already_posted()`): original_title Jaccard + entity overlap (threshold 0.30 / 2개)
2. **Phase 2** (`narrative_pitcher.is_duplicate_pitch()`): article_original_titles entity overlap (2개)
3. **Phase 3** (`save_pitch_to_history().entities`): capitalized entity 저장 → Phase 2에 활용

---

## 4. 모델 라우팅

### model_router.py
- GPT-4o-mini 사용 (기본)
- GPT-4o로 변경 가능하나 현재 미적용

### 호출 포인트
| 단계 | 모델 | 용도 |
|------|------|------|
| 피치 생성 | GPT-4o-mini | 45~600개 기사에서 흥미로운 이야기 발견 |
| 피치 평가 | GPT-4o-mini | 0~5점 점수 + 상식충돌 검증 |
| 쓰레드 작성 | GPT-4o-mini | 5개 카드 + 링크 생성 |
| 휴머나이즈 | GPT-4o-mini | AI 말투 교정 |

---

## 5. 주요 함수 위치

| 함수 | 파일 (라인) | 설명 |
|------|-----------|------|
| `run_v3()` | `main_v3.py:129` | 전체 파이프라인 실행 |
| `validate_final_cards()` | `main_v3.py:41` | 발행 전 최종 검증 |
| `select_format()` | `format_selector.py:19` | 형식 선택 (항상 D) |
| `get_pitches()` | `pipeline/threads/pitch.py` | 피치 생성 |
| `write_thread()` | `pipeline/threads/writer.py:501` | 쓰레드 작성 |
| `parse_cards()` | `pipeline/threads/writer.py:491` | LLM 출력 → 카드 분할 (--- 우선, \n\n fallback) |
| `_repair_truncated_cards()` | `pipeline/threads/writer.py:463` | \n\n split 후 불완결 카드 병합 (forward + backward pass) |
| `_remove_duplicate_links()` | `pipeline/threads/writer.py:` | 중복 🔗 카드 자동 제거 |
| `build_system_prompt_D()` | `pipeline/threads/writer.py:59` | D 형식 프롬프트 |
| `assemble_final()` | `pipeline/threads/writer.py` | 링크 카드 추가 |
| `save_draft()` | `pipeline/threads/writer.py` | 초안 저장 |
| `validate_card_structure()` | `pipeline/threads/validator.py:239` | 카드 구조 검증 (길이, 한글비율, 문장 완성, 중복) |
| `validate_final_output()` | `pipeline/threads/validator.py:176` | 최종 출력 통합 검증 (3차 방어) |
| `publish_thread_chain()` | `pipeline/threads/publisher.py` | Threads 발행 |
| `load_failed_articles()` | `scripts/threads/failed_articles.py` | 영구 실패 기사 목록 로드 |
| `save_failed_article()` | `scripts/threads/failed_articles.py` | 실패 기사 영구 저장 |

---

## 6. 환경 설정

### .env
- `BREVO_API_KEY` — 이메일 발송 API 키
- `BREVO_LIST_ID` — Brevo 구독자 리스트 ID
- `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` — 텔레그램 알림
- Cloudflare API 토큰들
- OpenAI API 키 (GPT-4o-mini / GPT-4o)

### wrangler.toml
- Cloudflare Workers 설정
- D1 DB 바인딩
- `BREVO_API_KEY` / `BREVO_LIST_ID`는 Pages Secrets로 주입 (wrangler.toml에는 주석 처리)

---

## 7. 자주 쓰는 명령어

```bash
# 1회 실행 (실제 발행)
python3 scripts/threads/main_v3.py

# 1회 실행 (발행 없이 초안만)
python3 scripts/threads/main_v3.py --dry-run

# Briefing pipeline (블로그 브리핑, Threads와 별개)
python3 scripts/run_pipeline.py                                    # 전체 실행
python3 scripts/run_pipeline.py --skip-deploy                      # 배포 없이 실행
python3 scripts/run_pipeline.py --dry-run                          # 계획만 출력
BRIEFING_SCORER_MODE=dry_run python3 scripts/run_pipeline.py       # 점수 tagging만
BRIEFING_SCORER_MODE=shadow python3 scripts/run_pipeline.py        # + 2-Pass diff 로깅
# BRIEFING_SCORER_MODE=live  # Week 4 활성화 예정

# 수동 배포
bash scripts/deploy.sh
```

---

## 8. Briefing Pipeline (2-Pass Impact Scoring)

> Threads 쓰레드와 별개로, 블로그 브리핑 생성 시 뉴스를 선정하고 점수를 평가하는 파이프라인.  
> `run_pipeline.py` → `auto_news_selector.py` → `auto_briefing.py`

---

## 9. Blog Pipeline (뉴스 → 브리핑 → 블로그 → 이메일 → 배포)

> `run_pipeline.py`가 오케스트레이션하는 6단계 파이프라인.  
> Threads와는 별개 — 블로그 콘텐츠 생성 및 배포 전용.

### 9.1 처리 흐름

```
뉴스 선정 (auto_news_selector)
    ↓
브리핑 생성 (auto_briefing) → D1 briefings + briefing_items
    ↓
블로그 생성 (blog_draft_generator.py, launchd 07:00) → src/content/blog/{date}-{num}-{slug}.md
    ↓                                                       → briefing_items.deep_dive_url 자동 연결
이메일 발송 (auto_email_sender) → Brevo API
    ↓
빌드 + 배포 (deploy.sh) → npm run build → wrangler pages deploy

> **참고**: `auto_thumbnail.py`(Pexels)는 비활성화됨 (2026-07-14).
> blog-draft의 slug(SEO 제목 기반)와 pipeline의 slug(기사 제목 기반) 불일치로 사용 중단.
> 자세한 사유: `.planning/triage/20260714--auto-thumbnail-deactivation.md`
```

### 9.2 단계별 설명

| 단계 | 스크립트 | 하는 일 |
|------|---------|---------|
| 1. 뉴스 선정 | `auto_news_selector.py` | D1에서 최근 뉴스 조회, 중복 제거, 6개 선정 |
| 2. 브리핑 생성 | `auto_briefing.py` | 각 뉴스에 comment 생성, D1 `briefings`/`briefing_items` 저장 |
| 3. 블로그 생성 | `blog_draft_generator.py` (launchd 07:00) | 오늘 브리핑 기사 조회 → AI로 블로그 포스트 생성 → `src/content/blog/` 저장 → `briefing_items.deep_dive_url` 자동 UPDATE |
| 4. 이메일 | `auto_email_sender.py` | Brevo API로 뉴스레터 발송 |
| 5. 배포 | `deploy.sh` | `npm run build` + `npx wrangler pages deploy` |

### 9.3 deep_dive_url 연결

블로그 포스트 생성 직후 `run_pipeline.py:step_deep_articles()`가 자동 실행:

```python
blog_url = f"https://aikorea24.kr/blog/{filepath.stem}"
UPDATE briefing_items SET deep_dive_url = '{blog_url}'
WHERE briefing_id = {id} AND news_id = {id}
```

이 URL은 `src/pages/briefing/[date].astro:222-230`에서 "이 뉴스, 더 깊이 읽기 →" 링크로 렌더링됨.

**중요: 배포(Step 6)가 완료되어야 블로그 링크가 404가 나지 않음.** 블로그 포스트는 Astro 정적 사이트에 포함되어 pre-render되므로, 배포 전에는 접근 불가.

### 9.4 용어

| 문서상 표현 | 실제 의미 |
|------------|---------|
| 심층글 / deep article | **블로그 포스트** (`src/content/blog/`) |
| `auto_deep_article.py` | 블로그 생성기 (이름은 legacy, 기능은 단순 블로그 생성) |

### 8.1 평가 아키텍처 (Cascade)

```
D1 뉴스 100건 → cluster_by_topic (키워드 클러스터링)
                    ↓
           Phase 1 dedup (21~30건)
                    ↓
           Phase A: light score (4개 항목)
                    ↓
           Top-N 20 → 크롤링 (직렬)
                    ↓
           Phase B: full score (7개 항목)
                    ↓
           Pass 1: impact >= 70 (최대 3slot)
           Pass 2: round-robin + diversity (잔여 slot)
```

| 단계 | 평가 항목 | 데이터 |
|------|----------|--------|
| light (Phase A) | financial_impact, entity_tier, freshness, source_authority | title + description |
| full (Phase B) | + topic_blast_radius, conflict_drama, penalty_low_tier_entity, penalty_duplicate_theme | title + body + description |

### 8.2 3가지 모드

| 모드 | 선택 방식 | 점수 | Shadow diff | DB INSERT | 용도 |
|------|----------|------|-------------|-----------|------|
| `dry_run` (기본값) | 레거시 round-robin | tagging만 | Layer 1·2 | 영향 없음 | 회귀 검증 |
| `shadow` | 레거시 round-robin | tagging + 2-Pass 계산 | Layer 1·2·3 | 영향 없음 | 가중치 튜닝 데이터 |
| `live` (Week 4) | 2-Pass 활성 | tagging + 선택 | — | 변경됨 | 실제 운영 |

### 8.3 설정 파일

| 파일 | 내용 |
|------|------|
| `config/impact_weights.json` | 7개 평가 항목 가중치 + 임계값 + 환율 환산값 |
| `config/entity_tiers.json` | tier1 10개사, tier2 9개사 |

### 8.4 주요 함수

| 함수 | 파일:라인 | 설명 |
|------|---------|------|
| `score_article()` | `briefing_scorer.py:312` | light/full 평가 진입점 |
| `_parse_amounts()` | `briefing_scorer.py:101` | 본문에서 금액 추출 |
| `_match_entity_tiers()` | `briefing_scorer.py:184` | 등장 기업 티어 매칭 |
| `_compute_light_scores()` | `auto_news_selector.py:160` | Phase A (전체 후보) |
| `_crawl_and_full_score()` | `auto_news_selector.py:176` | Phase B (Top-N) |
| `_two_pass_selection()` | `auto_news_selector.py:193` | Pass 1 + Pass 2 선택 |
| `_expand_misc_for_legacy()` | `auto_news_selector.py:134` | 레거시 회귀용 misc 확장 |

### 8.5 Shadow Diff 로그 구조 (3층)

| Layer | 내용 | dry_run | shadow |
|-------|------|---------|--------|
| 1 | 레거시 vs 2-Pass URL set diff | O | O |
| 2 | 후보 전체 light/full score 히스토그램 (10점 bin) | O | O |
| 3 | score 65~75 경계역 기사의 breakdown + evidence | X | O |

로그 파일: `scripts/logs/briefing_shadow_diff.log` (JSONL)

### 8.6 버그 히스토리

| 버그 | 증상 | 수정 |
|------|------|------|
| _two_pass_selection 3개 반환 | misc light_score < 20 skip 후 deficit 처리 안됨 | fallback: misc full_score 순 인출 |
| cluster_by_topic 회귀 | source → misc 통합으로 round-robin 결과 불일치 | _expand_misc_for_legacy() 추가 |

---

## 10. Tools Collection Pipeline (자동 도구 수집기)

> AI 도구 디렉토리(`aikorea24.kr/tools/`)를 자동으로 채우는 독립 파이프라인.  
> Threads/Briefing과 별개로 매일 06:00에 실행되어 신규 AI 툴을 수집·가공·배포까지 완료.

### 10.1 처리 흐름

```
Product Hunt RSS ─┐
GitHub Awesome AI ─┤  (주 1회)
Futurepedia      ─┤→ collect_tools() → 중복 제거 → crawl_tool_page()
HuggingFace      ─┤                                    ↓
TopAI.tools      ─┘                         DeepSeek/GPT 한국어 메타데이터 생성
                                                    ↓
                                            im-not-ai 3단계 검증
                                            (humanize_md + ai_tell_score)
                                                    ↓
                                            MD 파일 저장
                                            src/content/tools/{slug}.md
                                                    ↓
                                            git commit + push
                                                    ↓
                                            Cloudflare Pages 배포
                                            (scripts/deploy.sh)
```

### 10.2 실행 주기

| 방식 | 실행 명령어 | 시각 |
|------|-----------|------|
| **launchd** (`kr.aikorea24.tools-collector`) | `.venv/bin/python3 scripts/tools_collector.py --collect --batch 10` | 매일 **06:00** |
| 수동 (수집+처리) | `python3 scripts/tools_collector.py --collect --batch 5` | — |
| dry-run | `python3 scripts/tools_collector.py --collect --dry-run` | — |
| 샘플 테스트 | `python3 scripts/tools_collector.py --sample` | — |

### 10.3 수집 소스

| 소스 | 방식 | 주기 |
|------|------|------|
| Product Hunt | Atom 피드 (`https://www.producthunt.com/feed`) | 매일 |
| GitHub Awesome AI Tools | `mahseema/awesome-ai-tools` README.md | **주 1회** (월요일) |
| Futurepedia | sitemap → 카테고리 페이지 → 개별 툴 카드 | 매일 |
| HuggingFace Papers | Daily Papers 페이지 (도구/모델 키워드 필터) | 매일 |
| TopAI.tools | 메인 페이지 카드 목록 | 매일 |

### 10.4 메타데이터 생성 (generate_metadata)

- **모델**: `deepseek/deepseek-v4-flash` (OpenRouter) → fallback `gpt-4o-mini`
- **온도**: `temperature=0.5`
- **크롤링**: 수집된 URL에서 실제 웹사이트 HTML 파싱 (title, description, pricing)
- **출력 JSON 구조**: description_kr, category, koreanSupport, difficulty, useCases, tags, tasks, tool_detail (summary, features, pricing, korean_detail, recommend_for, real_examples, vs_similar, faq)

### 10.5 im-not-ai 3단계 검증

| 단계 | 파일 내 위치 | 내용 |
|------|------------|------|
| 1단계 (예방) | `SYSTEM_PROMPT` 내 `HUMANIZE_RULES` | GPT 프롬프트에 금지 표현 사전 주입 |
| 2단계 (교정) | `humanize_md()` | regex 기반 후처리 (번역투, 관용구, 접속사, 평서체→정중체) |
| 3단계 (검증) | `ai_tell_score()` | AI스러움 점수 측정 (임계 15 초과 시 humanize 재실행) |

### 10.6 plist 설정 (`~/Library/LaunchAgents/kr.aikorea24.tools-collector.plist`)

```xml
<key>StartCalendarInterval</key>
<dict>
  <key>Hour</key><integer>6</integer>
  <key>Minute</key><integer>0</integer>
</dict>
<key>WorkingDirectory</key>
<string>/Users/twinssn/Projects/aikorea24</string>
```

**주의**: plist에 `EnvironmentVariables`로 `PATH`가 명시되어 있음 (homebrew 경로 포함).  
launchd 환경은 `~/.zshrc`를 읽지 않으므로 `sys.path`가 필요하며, `tools_collector.py` 상단에서 `__file__` 기반으로 `PROJECT_DIR`을 먼저 path에 추가한 후 `pipeline.infra`를 import함.

### 10.7 중복 방지

- **slug 중복**: `src/content/tools/{slug}.md` 파일 존재 여부 (filename)
- **name 중복**: frontmatter `name:` 필드 대소문자 무시 비교
- **URL 중복**: 수집 단계에서 `seen_urls` set으로 제거

### 10.8 주요 함수 위치

| 함수 | 라인 | 설명 |
|------|------|------|
| `main()` | 1403 | CLI 진입점 (argparse) |
| `collect_tools()` | 556 | 5개 소스 통합 수집 + 중복 제거 |
| `fetch_product_hunt()` | 191 | Product Hunt Atom 피드 파싱 |
| `fetch_github_awesome()` | 294 | GitHub README.md 링크 파싱 |
| `generate_metadata()` | 930 | DeepSeek/GPT 한국어 메타데이터 생성 |
| `crawl_tool_page()` | 882 | 툴 웹사이트 실제 정보 HTML 크롤링 |
| `humanize_md()` | 656 | im-not-ai 2단계 regex 후처리 |
| `ai_tell_score()` | 738 | im-not-ai 3단계 AI 티 점수 측정 |
| `save_tool_md()` | 1189 | frontmatter + body 조합해서 MD 저장 |
| `git_commit()` | 1236 | git add → commit → push |
| `process_batch()` | 1301 | 배치 처리 + ThreadPoolExecutor |

---

## 11. 검증 갭 분석 (Phase 8 대상)

> **2026-07-04 발견**: 프롬프트 노출/외국어 검증이 피치에는 적용되지만, 최종 카드에는 미적용.
> 동일한 오류 반복 방지를 위해 문서화.

### 11.1 현재 검증 체인 (Phase 11 이후)

```
피치 생성 (narrative_pitcher)
  ├→ detect_prompt_leak()      ✅ (시스템 프래그먼트 8개 + LEAKED_PROMPT_PATTERNS)
  ├→ clean_leaked_prompt()     ✅ (LEAKED_PROMPT_PATTERNS 3패턴 제거)
  ├→ validate_korean_output()  ✅ (CHINESE_PATTERN from validator, 한글 비율 ≥15%)
  └→ FOREIGN LANGUAGE PATTERNS CONSOLIDATED → validator.py  (CHINESE_PATTERN, JAPANESE_PATTERN)

쓰레드 작성 (writer)
  ├→ humanize_cards()          ✅ (AI 말투 교정)
  ├→ _strip_model_explanatory() ✅ (MODEL_MESSAGE_PATTERNS from validator, lines filtered)
  ├→ _strip_instruction_leak() ✅ (humanize + fix_cards output)
  ├→ fix_cards()               ✅ (_strip_model_explanatory applied, 영어 누출, 조사 간격)
  ├→ validate_cards()          ✅ (카드 수 + hook 길이)
  ├→ validate_year()           ✅ (연도 hallucination 방지)
  ├→ validate_keywords()       ✅ (키워드 변형 방지)
  ├→ validate_model_message()  ✅ (ALL_MESSAGE_PATTERNS 26개 + structural checks)
  ├→ validate_card_structure() ✅ (중복, 길이, 한글 비율, 문장 완성, hook/body 검증)
  └→ validate_final_output()   ✅ (ALL_MESSAGE_PATTERNS + foreign lang + prompt leak + 한국어 ≥30% + unicodedata NFKC)
```

### Phase 11 Defense Hardening Changes

| 변경 | 설명 |
|------|------|
| **Pattern Consolidation** | `MODEL_MESSAGE_PATTERNS`는 이제 validator.py에서 단일 진실 공급원. writer.py는 import만 사용. |
| **Unified Pattern Set** | `validate_final_output()`가 `ALL_MESSAGE_PATTERNS` (26개) 사용 — 이전에는 8개만. |
| **Threshold Harmonization** | 한국어 비율 ≥30%로 통일 (이전 final_output은 10%). |
| **Link Card Strip Fix** | `validate_model_message()`에서 `card.strip().startswith('🔗')` 사용. |
| **Dead Import Removal** | writer.py에서 `validate_no_foreign_language` import 제거 (validator에는 유지). |
| **NFKC Normalization** | `validate_final_output()`에서 `unicodedata.normalize('NFKC', card)` 적용 — 전각/반각 문자 통합. |
| **Foreign Language Pattern Consolidation** | `CHINESE_PATTERN`, `JAPANESE_PATTERN` → validator.py에서 export, pitch.py가 import. |
| **Strengthened LLM Prompt** | `build_system_prompt_D()`에 일본어(히라가나·가타카나) 금지 + 한자 1글자라도 차단 경고 + 고유명사는 영어만. |
| **Integration Tests** | `tests/test_write_thread_validation.py` — E2E retry chain 6 tests. |

### 11.2 발견된 갭 (Phase 11 Status)

| # | 갭 | 영향 | 심각도 | 상태 |
|---|-----|------|--------|------|
| G1 | 최종 카드에 프롬프트 노출 검증 없음 | `상식(A):`, `실제(B):` 라벨 발행 | 높음 | ✅ PHASE 11 해결 (ALL_MESSAGE_PATTERNS 26개) |
| G2 | `detect_prompt_leak()`가 시스템 프래그먼트만 검사 | `LEAKED_PROMPT_PATTERNS` 무시 | 중간 | ✅ 해결됨 |
| G3 | `response_format={'type': 'json_object'}` 미적용 | 쓰레드 작성 시 프롬프트 누출 가능 | 높음 | ✅ 해결됨 |
| G4 | `_strip_instruction_leak()`는 humanize에만 적용 | 원본 카드 프롬프트 노출 무시 | 중간 | ✅ 해결됨 |
| G5 | MODEL_MESSAGE_PATTERNS duplicated (validator + writer) | 유지보수 드리프트 위험 | 중간 | ✅ PHASE 11 해결 (validator 단일 소스) |
| G6 | validate_final_output Korean ratio 10% vs others 30% | 불일치 | 낮음 | ✅ PHASE 11 해결 (≥30% 통일) |

### 11.3 반복 오류 패턴

```
Phase 6: 피치에만 검증 적용 → 최종 카드 무시 → 재발
Phase 8: 전체 검증 체인 재설계 필요
```

**교훈**: 검증 로직 추가 시, 해당 단계의 "최종 출력"에만 적용하지 말고,
다음 단계의 "입력"에도 적용되는지 스코프를 확인할 것.

### 11.4 3중 방어 체계 설계 원칙

> **"지금은 다됐다"는 결론을 신뢰하지 않는다 — 반드시 터진다.**

| 방어 | 위치 | 검증 대상 | 실패 시 |
|------|------|----------|--------|
| **1차** | 피치 생성 | `validate_korean_output()` + `detect_prompt_leak()` | 피치 폐기, 재생성 |
| **2차** | 쓰레드 작성 후 | `validate_final_output()` | 카드 재생성 |
| **3차** | 발행 직전 | `validate_cards()` + `validate_final_output()` | 발행 차단 |

**핵심 규칙**:
1. 어떤 검증도 단 한 곳에서만 의존하지 않는다
2. "해결됨"이라고 안심하지 않는다 — 반드시 회귀 테스트로 확인
3. 검증은 "해당 단계 출력"이 아니라 "다음 단계 입력" 기준으로 설계

---

## 12. 강좌 시스템 (Course System)

> 마일스톤 v2.0 — 커뮤니티 게이트웨이 패턴 기반.

### 12.1 아키텍처 원칙

- **커뮤니티 게이트웨이**: 강좌 콘텐츠는 `posts` 테이블에 저장, 이메일은 티저 + 커뮤니티 링크만 발송
- **visibility 3종**: `public`(기존), `members`(로그인 필요), `premium`(추후 유료)
- **이메일**: Brevo 트랜잭셔널 API — Cloudflare Workers에서 직접 호출
- **태그 체계**: `course-enrolled-{slug}`, `course-completed-{slug}`

### 12.2 DB 스키마

| 테이블 | 설명 |
|--------|------|
| `courses` | 강좌 메타 (slug, title, total_days, default_send_hour) |
| `course_lessons` | 레슨-커뮤니티글 매핑 (course_slug, day_number, community_post_id, teaser_html) |
| `enrollments` | 수강 등록 (email, course_slug, start_date, days_sent, completed) |
| `lesson_clicks` | 이메일 클릭 추적 (enrollment_id, day_number, clicked_at) |

### 12.3 강좌 목록 (v2.0)

| 슬러그 | 제목 | 일수 | 상태 |
|--------|------|------|------|
| `7day-starter` | 첫 AI, 7일 — AI에게 말로 일을 시키는 첫 7일 | day 0~7 (8개) | ✅ 시드 완료 |
| `7day-infra` | 0원 인프라, 7일 — AI에게 사이트를 만들라 하고, 0원으로 운영한다 | day 8~14 (7개) | ✅ 시드 완료 |
| `7day-agent` | 무료 에이전트, 7일 | day 15~21 (7개) | ⏳ 설계 대기 |

### 12.4 API 엔드포인트

| 경로 | 메서드 | 설명 |
|------|--------|------|
| `/api/courses/enroll` | POST | 강좌 등록 (D1 + Brevo 태그) |
| `/api/courses/send-daily` | POST | 당일 발송 대상 조회 → 이메일 전송 |
| `/api/courses/track` | GET | 클릭 추적 리다이렉트 |
| `/courses/7day-starter` | GET | 강좌 랜딩 페이지 |

### 12.5 시드 데이터

- `scripts/seed_course_7day_starter.py` — `--update` 모드 지원 (UPSERT)
- `scripts/seed_course_7day_infra.py` — 0원 인프라 7개 레슨
- 실행: `python3 scripts/seed_course_7day_starter.py --update`

### 12.6 발송 상태

- **launchd plist**: 미설치 — 모든 콘텐츠 준비 후 마지막에 활성화 예정
- **day 0 즉시 발송 hook**: enroll.ts에 미구현 — Phase 22에서 처리 예정
- **강좌 페이지**: 현재 Coming Soon 상태 (오픈 알림만 등록 가능)

---

## 13. Abbductive Reasoning Pipeline (브리핑 추론 보강)

> 브리핑 코멘트에 "어긋남 탐지 → 가설 생성 → 산문 조합"을 추가하는 모듈.
> `auto_briefing.py`의 comment 생성 후, `enrich_briefing_items()`가 in-memory로 comment를 보강.
> 2026-08-28 구현.

### 13.1 처리 흐름

```
selected_items (뉴스 6건)
       ↓
  S1: abductive_finder.py
  find_abduction_candidates()
  → 뉴스 간(A), 통념 대비(B), 시점 불일치(C) 탐지
  → gap_summary + quote 검증
       ↓
  select_candidates(max_n=2)     ← briefing_enricher.py
       ↓
  S2: hypothesis_generator.py
  generate_hypotheses()
  → 10 관점에서 가설 생성
  → evidence_checker로 환각 검증
  → 중복 제거 (SequenceMatcher > 0.8)
       ↓
  select_hypotheses(max_n=3)     ← briefing_enricher.py
       ↓
  S3: briefing_enricher.py
  _compose_prose()               ← 결정론적 템플릿 (LLM 미사용)
  → 기존 comment 뒤에 삽입
       ↓
  D1 UPDATE (또는 in-memory)
```

### 13.2 모듈 시그니처

| 모듈 | 주요 함수 | 입출력 |
|------|----------|--------|
| `abductive_finder.py` | `find_abduction_candidates(selected_items)` | `list[dict]` (type, source_item_ids, quote_1, quote_2, gap_summary, verification_path) |
| `hypothesis_generator.py` | `generate_hypotheses(candidate, selected_items)` | `list[dict]` (perspective, one_line, falsifiable_news, confidence, evidence_source) |
| `briefing_enricher.py` | `enrich_briefing(selected_items, dry_run=True)` | `list[dict]` (기존 item에 comment 보강) |
| `evidence_checker.py` | `check_evidence(claim, source_text, threshold=0.4)` | `bool` |
| `evidence_checker.py` | `check_gap_fidelity(gap, q1, q2, source, threshold=0.4)` | `bool` |

### 13.3 환각 방어 3중 레이어

| 레이어 | 위치 | 검증 대상 |
|--------|------|----------|
| 1차 | S1 `_verify_and_filter()` | quote_1, quote_2가 원문에 실제 존재하는지 (`verify_quote`) |
| 2차 | S1 `check_gap_fidelity()` | gap_summary의 핵심 단어가 원문+인용에 매칭되는지 |
| 3차 | S2 prompt rule 5 + `check_evidence()` | 가설이 추론 마커("~할 수 있다") 사용하고, 구체적 수치/고유명사 없는지 |

### 13.4 환경변수

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `ENABLE_ABDUCTION` | `false` | `true`일 때만 enrich 실행 |
| `ABDUCTION_MODEL` | `gpt-4o-mini` | S1/S2 LLM 모델 |

### 13.5 테스트

| 파일 | 테스트 수 | 비고 |
|------|----------|------|
| `tests/test_abductive_finder.py` | 17 | quote 검증, JSON 파싱, 본문 fallback |
| `tests/test_hypothesis_generator.py` | 16 | 10 관점, 중복 제거, 환각 필터 |
| `tests/test_briefing_enricher.py` | 18 | 후보 선별, 가설 선별, 산문 조립, 주입 |
| `tests/test_evidence_checker.py` | 22 | 단어 매칭, 수치 패턴, 고유명사, 절대 표현 |

---

## 14. Weekly Contrast Deep Dive Pipeline (주간 대비 분석)

> 지난 7일 뉴스를 분석해 "대비 쌍"을 탐지하고, 심층 분석 블로그 포스트를 자동 생성.
> 매주 토요일 09:00 launchd 실행.
> 2026-08-28 구현.

### 14.1 처리 흐름

```
S0: weekly_contrast_collector.py
  D1 JOIN (briefing_items → news → briefings)
  → 지난 7일 브리핑 선정 기사 수집 (최대 93건)
  + description 신뢰도 검증 (embedding 유사도)
       ↓
S1: contrast_cluster_finder.py
  LLM 2회:
    Stage 1: 50건 제목 → 키워드 클러스터링
    Stage 2: 각 클러스터 → 대비 증거 추출
  → diversity 필터 (토큰 중복 > 0.4 제외)
  → 대비 후보 (Type A/B/C)
       ↓
S2: deep_dive_writer.py
  5단락 분석체 블로그 포스트 작성
  + 환각 인용 검증 (check_evidence)
  + 품질 판단 (추천/보류/폐기)
       ↓
S3: weekly_blog_publisher.py
  추천 → src/content/blog/ (발행)
  보류 → src/content/blog/_drafts/ (사람 검토 대기)
  폐기 → skip
```

### 14.2 모듈 시그니처

| 모듈 | 주요 함수 | 입출력 |
|------|----------|--------|
| `weekly_contrast_collector.py` | `collect_weekly_articles(days=7)` | `list[dict]` (id, title, description, source, category, pub_date, link, description_reliable) |
| `contrast_cluster_finder.py` | `find_contrast_candidates(articles)` | `list[dict]` (topic, contrast_frame, type, source_articles, quote_1, quote_2, gap_summary, reading_angle) |
| `deep_dive_writer.py` | `write_deep_dive(candidate)` | `dict` (title, body, tags, source_links, quality_judgment) |
| `deep_dive_writer.py` | `write_all_deep_dives(candidates, max_writes=2)` | `list[dict]` |
| `weekly_blog_publisher.py` | `publish_blog_post(dive)` | `str` (저장된 파일 경로) |
| `weekly_blog_publisher.py` | `publish_all(dives)` | `list[str]` |
| `run_weekly_contrast.py` | `run_pipeline(dry_run, days, max_writes)` | `dict` (result) |

### 14.3 발행 게이트

| 판단 | 기준 | 결과 |
|------|------|------|
| **추천** | verified_quotes ≥ 1 AND unverified_quotes = 0 | `src/content/blog/weekly-contrast-*.md` |
| **보류** | verified_quotes = 0 (추론만 있음) | `src/content/blog/_drafts/weekly-contrast-*.md` |
| **폐기** | hallucinated_quotes ≥ 1 | skip (로그만 기록) |

### 14.4 description 신뢰도 검증

`weekly_contrast_collector.py`에서 title↔description 임베딩 유사도 측정:
- `get_embedding()` (text-embedding-3-small) → cosine similarity
- 임계값: 0.7 이상이면 `description_reliable=True`
- API 실패 시: `description_reliable=None` (검증 스킵)
- S1 클러스터링에서 `description_reliable=False`인 기사는 description 제외

### 14.5 로깅

| 항목 | 기록 위치 |
|------|----------|
| 단계별 진행 | `logs/weekly_contrast.log` (launchd stdout/stderr) |
| 결과 JSON | `tmp_test/weekly_contrast_result.json` |
| 대비 후보 | `tmp_test/weekly_candidates.json` |

### 14.6 launchd 설정

| 항목 | 값 |
|------|-----|
| plist | `~/Library/LaunchAgents/kr.aikorea24.weekly-contrast.plist` |
| 스케줄 | 매주 토요일 09:00 (Weekday=6) |
| 환경변수 | `OPENAI_API_KEY` (description 임베딩용) |
| 로그 | `logs/weekly_contrast.log` |

### 14.7 운영

운영 체크리스트 및 4주 관측 지표는 `docs/weekly-contrast-ops.md` 참조.

### 14.8 테스트

| 파일 | 테스트 수 | 비고 |
|------|----------|------|
| `tests/test_weekly_contrast_collector.py` | 10 | SQL 쿼리, 코사인 유사도, 신뢰도 검증 |
| `tests/test_contrast_cluster_finder.py` | 20 | 클러스터 파싱, 증거 파싱, diversity 필터 |
| `tests/test_deep_dive_writer.py` | 15 | JSON 파싱, 프롬프트, 품질 판단, 환각 검증 |
| `tests/test_weekly_blog_publisher.py` | 12 | 슬러그, 발행, 게이트 (추천/보류/폐기) |
