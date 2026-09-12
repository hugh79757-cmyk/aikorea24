# FINDINGS: 브리핑 파이프라인 프롬프트 릭 진단

> 진단일: 2026-09-12 · quick-260912-vyc · 산출물 성격: 진단 보고서 (코드 수정 0건, DB 변경 0건)

## 1. 증거

### 1.1 스캔 범위 및 명령

| 데이터 소스 | 범위 | 명령/방법 |
|---|---|---|
| D1 briefing_items.comment (최근 14일) | 150 rows (2026-08-29 ~ 2026-09-12) | `env -u CLOUDFLARE_API_TOKEN /opt/homebrew/bin/wrangler d1 execute aikorea24-db --remote --json --command "SELECT b.date, i.news_id, i.comment FROM briefing_items i JOIN briefings b ON i.briefing_id=b.id WHERE b.date >= '2026-08-29' ORDER BY b.date DESC, i.id LIMIT 200"` → 로컬 python 정규식 스캔 |
| D1 briefing_items.comment (전체 이력, 영어 메타 패턴) | 전체 1,496 rows | `WHERE i.comment LIKE '%Here is%' OR ... OR i.comment LIKE '%I cannot%'` (8패턴) |
| D1 briefings.intro (최근 14일) | 25 rows | 동일 wrangler SELECT → python 스캔 |
| 아웃라인 MD | 745 files (scripts/thread_topics/outlines/2026*) | python `glob` + 행 단위 영어 문장 스캔 (기능어 3개 이상 + 행 내 한글 미세) |
| model_router 일일 로그 | scripts/threads/logs/2026-09-11.log, 2026-09-12.log (릭 row 생성 시각대) | `grep -E 'finish_reason' scripts/threads/logs/2026-09-12.log` |

### 1.2 영어 릭 샘플 ↔ 출처 ↔ tier 상관표

**[검증불가] 영어 문장/영어 메타 텍스트("Here is", "Sure," 등) 릭 샘플: 0건.**
근거: D1 최근 14일 150 rows + 전체 이력 영어 메타 LIKE 8패턴 0건 + briefings.intro 25 rows 0건 + 아웃라인 745 files 0건. 어떤 스캔에서도 영어 문장 형태의 프롬프트 릭이 검출되지 않았다. 검출 스크립트는 영어 기능어(the/is/are/will/of/to 등) 3개 이상 + 한글 부재 문장, LLM 메타 인사말 8패턴, latin 문자 비율 25% 초과 3종을 모두 시도했다.

**[부분검증] 프롬프트 구조 미러링(반복 루프) 릭: 1건** — 영어가 아닌 형태지만 "프롬프트 구조" 후보의 직접 증거. 아래 3열 대응표:

| 릭 샘플 (원문 인용, 앞부분) | 출처 파일/DB row | 추정 응답 tier |
|---|---|---|
| `**제목: 앤트로픽, 악성 AI 에이전트도 CAPTCHA를 싫어한다고 공개** ... **코멘트:**` 블록이 **동일 내용으로 반복** (제목/출처/내용/코멘트 템플릿을 채우지 않고 템플릿 자체를 수회 재출력, 코멘트 비어있음) | D1 `briefing_items` (briefing_date=2026-09-11-2, news_id=49731, created_at=2026-09-12 13:25:08 UTC). 라이브 렌더링: src/pages/briefing/[date].astro가 이 row를 그대로 출력 | **nvidia-nemotron** [부분검증] — 근거: 일일 로그 `scripts/threads/logs/2026-09-12.log`에서 해당 시각대(13:25 UTC = 로컬 20:25)에 `nvidia-nemotron finish_reason=stop content_len=708/1429/122/135/56/78/79/116` 연속 응답 블록 존재. 로그에 content 스니펫이 없어 "동일 응답"은 확증 불가, 시각적 일치만으로 추정 |

### 1.3 스캔 결과 요약 (3분법)

- [검증됨] 영어 메타 릭 0건 — D1 전체 이력 LIKE 8패턴 + 최근 14일 150 rows 정규식 + 아웃라인 745 files 모두 0건. 재현: 위 1.1 표의 SELECT/LIKE 명령 그대로 실행.
- [검증됨] 정상 영어(제품명/매체명/컨퍼런스명)만 73개 아웃라인 파일에서 검출 — 예: `MIT Tech Review`, `GitHub Copilot CLI`, `IEEE International Conference on Robotics and Automation`, `The Next Web` (출처 표기/고유명사 = 릭 아님). 근거: 73건 전수 육안 분류, 영어 문장 형태(기능어 3개+한글 부재) 재스캔 시 0건.
- [부분검증] 반복 루프 릭 1건 (위 표) — tier 상관은 로그 content 스니펫 부재로 시각적 추정.
- [검증불가] "한국어 출력에 영어가 섞이는" 원형 릭의 라이브 샘플 특정 — 본 진단 시점 스캔 범위에서는 발견되지 않음. 유저가 목격한 릭이 과거 데이터(스캔 범위 외 날짜)이거나, 현재 라이브가 아닌 다른 경로(아웃라인→블로그 초안 변환 단계 등)에서 발생했을 가능성. 복구 계획: 후속 quick task에서 릭 목격 사례의 구체 URL/날짜를 입력받아 해당 row만 재스캔.

## 2. 호출 지점 감사

### 2.1 브리핑 체인 LLM 호출 지점 전수 목록

재현 명령: `grep -rn 'chat_completion' scripts/auto_briefing.py scripts/briefing_*.py scripts/thread_topics/ scripts/abductive_finder.py scripts/hypothesis_generator.py`

| # | 호출 지점 | LLM | system 프롬프트 한국어 지시 | 출력 후 검증 | 안전망 | user_prompt 영어 원문 주입 |
|---|---|---|---|---|---|---|
| 1 | `scripts/auto_briefing.py` `generate_comment()` L65 | model_router 17-tier 회전 | **있음** — "모든 내용을 순수 한국어로만 작성" (L53) | **없음** | `remove_chinese()` L76 (한자만 제거, **영어 무대책**) | title/description 원문 그대로 (L57-60) — 국내 기사는 한국어, 해외 기사는 영어 description 가능 |
| 2 | `scripts/thread_topics/outline_generator.py` `generate_outline_with_articles()` L216 | model_router | **없음** | **없음** | **없음** | **있음** — `[기사 i] 제목/내용` 블록에 title+description[:500] 원문 그대로 (L155-164). 영어 기사면 영어 수백 자가 user_prompt에 들어감 |
| 3 | `scripts/thread_topics/outline_generator.py` `generate_outline_no_articles()` (L232~) | model_router | **없음** ("콘텐츠 전략 전문가"만) | **없음** | **없음** | 없음 (키워드+intent만) |
| 4 | `scripts/thread_topics/thread_topic_finder.py` L209 (`cluster_articles`) | model_router | **없음** — 오히려 영어 system 프롬프트 ("You are a news clustering specialist... Output valid JSON only.") | JSON 파싱 게이트만 (response_format=json_object + ```json 펜스 제거) — 언어 게이트 없음 | JSON 파싱 | articles_str 원문 주입 (L160) |
| 5 | `scripts/thread_topics/thread_topic_finder.py` L382 (`generate_thread_outline`) | model_router | **없음** — 영어 system 프롬프트 ("You are a thread/social media content strategist...") | **없음** | **없음** | **있음** — 클러스터 기사 title/description[:500] 원문 그대로 (L307-315). "Korean audiences"라는 단어만 있고 한국어 출력 강제 없음 |
| 6 | `scripts/abductive_finder.py` L167 | model_router | **있음** — "순수 한국어로만 작성" (L162) | JSON 파싱만 (response_format=json_object) — 언어 게이트 없음 | JSON 파싱 | selected_items 원문 주입 |
| 7 | `scripts/hypothesis_generator.py` L138 | model_router | **있음** — "순수 한국어로만 작성" (L133) | JSON 파싱만 | JSON 파싱 | selected_items 원문 주입 |
| 8 | `scripts/briefing_enricher.py` `enrich_briefing()` | **LLM 없음** — `_compose_prose()` 결정론적 템플릿 조립 (L126 "결정론적 템플릟으로 산문 조립") | — | — | — | — |
| 9 | `scripts/briefing_scorer.py` | **LLM 없음** — 룰베이스 점수화 (`_score_financial_impact`, `_score_freshness` 등 순수 python) | — | — | — | — |

**유일한 진입점**: `run_pipeline.py` L49-53 → `auto_briefing.main(articles)`. launchd `kr.aikorea24.pipeline-runner.plist` → `run_pipeline.py`. thread_topic_finder/outline_generator은 별도 launchd (`kr.aikorea24.thread-topic-finder.plist`, outline-generator.plist.disabled).

### 2.2 검증 부재 증거 (grep)

재현 명령 및 실측 출력:

```
$ grep -n 'detect_prompt_leak\|validate_korean_output' scripts/auto_briefing.py scripts/briefing_*.py scripts/thread_topics/*.py
(0 matches — exit code 1)
```

- [검증됨] 브리핑 경로(auto_briefing, briefing_enricher, briefing_scorer, thread_topics 전체)에서 기존 검증기 `detect_prompt_leak()`(pipeline/threads/pitch.py L58) / `validate_korean_output()`(동 L85) **import 0건**. Threads 파이프라인(pitch→writer→validator 3중 방어)에만 적용되어 있고 브리핑 체인은 완전 무방비.
- [검증됨] `auto_briefing.py` L40-42: `remove_chinese()`는 `re.sub(r'[\u4e00-\u9fff\u3400-\u4dbf]', '', text)` — CJK 한자 블록만 제거. 라틴 문자 `[A-Za-z]`에는 어떤 처분도 없음. 영어 문장이 응답에 섞여도 그대로 D1에 INSERT됨 (L142 `sql_item`).

### 2.3 구조적 사실 — 어떤 tier가 응답하든 언어 게이트 없음

`scripts/threads/v3/model_router.py` `_call_tier_once()` L247:

```python
return text.strip()
```

- [검증됨] model_router는 성공한 tier의 응답에 `text.strip()`만 적용해 반환. 언어 비율 검사, 릭 패턴 검사, 메타 인사말 검사 전부 없음. JSON 게이트(`response_format=json_object`)는 해당 파라미터를 넘긴 호출 지점(#4/#6/#7)에서만 작동하고, 그마저도 "유효 JSON인가"만 보지 "한국어 JSON인가"는 보지 않음. auto_briefing(#1)/outline(#2/#3/#5)은 JSON 요청조차 없음.
- 즉 **17개 무료 tier + 유료 default 어느 것이 응답하든, 영어·메타 텍스트·프롬프트 미러링이 섞인 응답은 아무 저항 없이 D1/MD 파일에 저장**된다.

### 2.4 tier 리스크 표 — config/models.yaml 17 tier 영어 응답 경향

근거: models.yaml L59-112 모델명 + 벤더 특성 + 일일 로그(scripts/threads/logs/2026-09-1[12].log)에서 관측된 실제 사용.

| tier | 모델 | 한국어/영어 응답 경향 평가 | 관측 근거 |
|---|---|---|---|
| groq-qwen | qwen/qwen3.6-27b (+reasoning_effort: none) | 중상 — Qwen 계열 한국어 가능하나 긴 영어 원문 컨텍스트에서 영어 미러링 가능 | 로그 사용 빈발 |
| groq-gpt120b | openai/gpt-oss-120b | 중상 — gpt-oss는 영어 중심 학습, 한국어 약함. 120B라 지시는 따르나 언어 지시 없으면 영어 기본 | 로그 사용 빈발 |
| groq-gpt20b | openai/gpt-oss-20b | **높음** — 소형 gpt-oss, 지시 추종력 낮음. 언어 지시 없으면 영어 기본 | 로그 빈발, `finish_reason=length` 관측 |
| groq2-qwen | qwen/qwen3.6-27b (2번째 키) | 중상 — groq-qwen과 동일 | 로그 관측 |
| groq2-gpt20b | openai/gpt-oss-20b (2번째 키) | **높음** — 위와 동일 | 로그 빈발 |
| gemini-flash | gemini-3.6-flash | 중 — 한국어 우수하나 긴 영어 원문에 영어 섞임 가능 | 로그 관측 |
| nvidia-nemotron | nvidia/nemotron-3-super-120b-a12b | **높음** — 추론 특화 모델. reasoning 과정에서 영어 thinking 잔여물·프롬프트 템플릿 미러링 관측 (반복 루프 릭 row 1.2표 참조) | 로그 빈발, 릭 row 시각대 응답 |
| orca-ds4free | deepseek/deepseek-v4-flash-free | 중 — DeepSeek 한국어 가능 | 로그 429 빈발 |
| orca-hy3 | tencent/hy3-free | 중 — Hunyuan 한국어 가능하나 중국어 간섭 가능성 | 로그 429 빈발 |
| mistral-codestral | codestral-latest | **높음** — **코드 특화 모델**. 자연어 한국어 약함, 코드/영어 템플릿 톤. 2026-09-11 로그에서 이 tier가 브리핑 시간대 대량 응답 (전날 JSON 파싱 실패도 관측: `[체인] mistral-codestral: JSON 파싱 실패 → 뒤로 회전`) | 로그 최빈 응답 tier |
| cohere-commanda | command-a-03-2025 | 중 — Command A 한국어 일부 지원 | 로그 400 TOO_MANY_TOKENS 관측 |
| or-nexpro | nex-agi/nex-n2.5-pro:free | 중 (신규 2026-09-12 추가, 관측 부족) | models.yaml L96-97 |
| or-nexmini | nex-agi/nex-n2.5-mini:free | **높음** — 소형, 언어 일관성 불안정 (신규, 관측 부족) | models.yaml L98-99 |
| or-nemotron | nvidia/nemotron-3-super-120b-a12b:free | **높음** — nvidia-nemotron과 동일 모델, 무료 버전 | models.yaml L101-103 |
| or-lingvl | inclusionai/ling-3.0-flash-vl:free | **높음** — **비주얼 언어 모델**, 텍스트 생성 언어 일관성 불안정 (신규) | models.yaml L104-106 |
| zhipu-glm | glm-4.5-flash | 중 — GLM 한국어 가능 | 로그 관측 |
| default | deepseek-v4-flash (유료) | 낮음 — 유료 DeepSeek, 한국어 품질 안정적 | 최후 수단 (models.yaml L110-112) |

- [검증됨] 17 tier 중 6~7개 tier가 영어 응답 경향 "높음" — 코드 특화(mistral-codestral), 소형 gpt-oss 20B 2종, 추론 특화 nemotron 2종, 비주얼 언어 or-lingvl, 소형 or-nexmini. 이 tier들이 회전 큐에서 응답을 가져오는 순간 언어 게이트가 없으면 그대로 통과한다.

### 2.5 프롬프트 구조 분석

- [검증됨] **outline_generator 2개 함수(#2/#3)**: user_prompt에 영어 원문 title+description[:500]이 그대로 주입되며(L155-164) system 프롬프트는 "당신은 콘텐츠 분석 전문가입니다"가 전부 — "한국어로만 작성" 지시가 없다. 모델이 원문 영어를 미러링하거나 영어로 응답해도 저장 전 어떤 검증도 없다 (L216-226 `chat_completion` → 바로 `return content`).
- [검증됨] **thread_topic_finder(#5)**: system 프롬프트 자체가 영어("You are a thread/social media content strategist... for Korean Naver/Instagram audiences") — 한국어 출력 강제 없음. 클러스터 기사 원문도 그대로 주입.
- [검증됨] **auto_briefing(#1)**: "순수 한국어로만 작성" 지시는 **있으나 강제 수단 없음**. 지시는 요청(request)이지 게이트(gate)가 아니다. 검증 없이 그대로 저장. 안전망 `remove_chinese()`는 한자 전용.
- [검증됨] **유일하게 방어된 경로는 Threads 파이프라인뿐** — pipeline/threads/pitch.py L58/L85 + validator.py + 발행 직전 validate_cards(). 브리핑 체인과는 완전 분리.

## 3. 원인 후보 분석

4개 후보 각각 "가설 → 반박 가능한 확인 방법":

| 후보 | 가설 | 반박 가능한 확인 방법 |
|---|---|---|
| **A. 검증 부재 (구조적)** | 브리핑 체인에 언어/릭 게이트가 전무해, 어떤 tier가 영어·메타·미러링을 뱉어도 D1/MD에 그대로 저장된다. 릭의 **통과 조건**을 만든다. | grep 2.2의 명령 — 검증기 import 0건이 재현되면 가설 확정. model_router L247 `return text.strip()` 라인 인용. |
| **B. tier 모델 특성 (트리거)** | 회전 큐의 영어 경향 "높음" tier(codestral/gpt20b/nemotron/lingvl)이 응답하는 순간 영어·템플릿 미러링이 발생한다. 릭의 **발생 조건**을 만든다. | 일일 로그에서 릭 샘플 날짜의 `성공: {tier}` / `finish_reason` 조합 대조. 단 로그에 content 스니펫이 없어 [부분검증]에 그침 — model_router `_log_to_file`에 content 앞 80자 로깅 추가 시 반박 가능해짐. |
| **C. 프롬프트 구조 (트리거)** | "한국어로만 작성" 지시가 없거나(아웃라인/토픽파인더) 있어도 강제가 없으면(auto_briefing), 모델 기본 언어로 응답한다. | outline_generator L166/L235 system 프롬프트 라인 인용 — 지시 부재 문장 확인. auto_briefing L51-55는 지시 있음 → C는 아웃라인 경로에 국한. |
| **D. 원문 영어 패스스루 (트리거)** | user_prompt에 영어 title/description이 수백 자 주입되면 모델이 원문을 미러링한다. 반복 루프 릭(1.2표)이 이 경로의 실증 사례다. | D1 news 테이블에서 영어 description 기사 비율 SELECT로 측정 가능: `SELECT COUNT(*) FROM news WHERE description GLOB '*[A-Za-z]*' AND ...` (본 진단에서는 실행 안 함 — A가 통과 조건임이 확정적이어서 트리거 정량화는 후속 과제). |

## 4. 판정

### Primary: 후보 A — 브리핑 체인 검증 부재 (구조적) [검증됨]

**근거:**
1. [검증됨] grep 재현 (2.2절): `detect_prompt_leak\|validate_korean_output` — 브리핑 경로 import 0건. 기존 검증기가 Threads 파이프라인에만 존재.
2. [검증됨] model_router.py `_call_tier_once()` L247 `return text.strip()` — 응답 통과 경로에 언어 게이트 없음. 코드 라인으로 입증되는 구조적 사실.
3. [검증됨] auto_briefing `remove_chinese()` L40-42 — 안전망이 한자 전용, 라틴 문자 무대책.
4. [검증됨] 아웃라인 2개 함수는 한국어 지시조차 없음 (2.5절 라인 인용).

A가 primary인 이유: A는 릭이 **시스템에 저장·렌더링되는 조건**이다. B/C/D가 발생시키는 어떤 결함 응답도 A가 없으면 (즉 게이트가 있으면) 차단된다. 3중 방어 원칙(AGENTS.md) 관점에서 B/C/D는 예방(1차 방어, 프롬프트) 수준, A는 차단(2·3차 방어) 수준 — 차단 계층 부재가 근본 수용 조건.

### Secondary: 후보 B+D 복합 (트리거) [부분검증]

**근거:**
1. [부분검증] 유일한 실측 릭 샘플(1.2표, 반복 루프)이 nvidia-nemotron 응답 시각대와 일치 — 추론 특화 모델(B)이 템플릿 원문 미러링(D)을 생성한 조합. 단 로그 content 스니펫 부재로 확증 불가.
2. [검증불가] 영어 문장 원형 릭의 라이브 샘플이 본 진단 스캔 범위에서 0건 — 트리거 tier 특정은 데이터 부족으로 불가. "구조적 취약은 코드로 입증됨(위 primary), 라이브 트리거 특정 불가"가 정직한 한계 진술이다.
3. [검증됨] 2.4표 — 회전 큐 17 tier 중 6~7개가 영어 경향 높음. 매 시간 브리핑이 큐 어디에 걸리든 상당 확률로 언어 취약 tier에 할당됨.

### 부판정: C는 경로별로 다름

- 아웃라인/thread_topic_finder 경로: C(한국어 지시 부재) **성립** [검증됨, 라인 인용 2.5절]
- auto_briefing 경로: C는 **약함** — 지시는 있음. 지시가 있어도 게이트가 없으면(A) 통과한다는 게 실측 릭 샘플(지시 있는 경로에서 발생)의 함의.

## 5. 수정 권고 (구현 아님 — 권고만, 후속 quick task 대상)

### 최소 수정안: 기존 검증기 재사용 — 신규 코드 작성 최소 경로

pipeline/threads/pitch.py의 `detect_prompt_leak()` (L58) / `validate_korean_output()` (L85)을 **import해서 호출**하는 것만으로 1차 방어 수준의 게이트가 즉시 확보된다. `validate_korean_output(hook, narrative)`는 2-문자열 인터페이스이므로 브리핑 코멘트는 `(comment[:100], comment[100:300])` 식으로 분할 전달하거나, 내부 로직(한글 비율 15% 임계 + 영문 문장 패턴 + 한자 검사)을 그대로 적용받도록 짝 지으면 된다.

### 3중 방어 게이트 위치 (AGENTS.md "3중 방어 원칙" 준수)

| 방어 | 게이트 위치 | 적용 검증기 | 실패 시 동작 |
|---|---|---|---|
| **1차** (생성 직후) | `auto_briefing.generate_comment()` — `chat_completion` 반환 후 `remove_chinese()` 대체/병행 시점 | `validate_korean_output()` + `detect_prompt_leak()` | 재생성 (최대 2회, 초과 시 해당 아이템 comment="") |
| **2차** (저장 직전) | `auto_briefing.save_briefing()` — `sql_item` INSERT 직전, 전 items 루프 | `detect_prompt_leak()` | 해당 아이템 저장 스킵 + 로그 |
| **3차** (발행/렌더링 직전) | `src/pages/briefing/[date].astro` 또는 run_pipeline 저장 완료 직후 배치 검증 | `detect_prompt_leak()` (comment 전수) | 문제 row 제외 처리 + 알림 |

아웃라인 경로 추가 게이트: `outline_generator` 2개 함수 + `thread_topic_finder.generate_thread_outline()` — `chat_completion` 반환 후 저장 전 `detect_prompt_leak()` + 한글 비율 체크. 동시에 system 프롬프트에 `pitch.py _LANG_SECTION` 패턴("[언어 규칙 - 최우선]" 블록, L125-131) 복사 — 이 프롬프트 블록은 Threads 체인에서 이미 검증된 문구다.

### 권고의 3분법 태그

- [부분검증] "기존 검증기 재사용으로 브리핑 게이트 확보 가능" — 검증기 코드 존재와 인터페이스는 검증됨(라인 인용)이지만, 브리핑 코멘트(1~2문장)가 pitch의 hook/narrative(카드 문단)와 동일 분포가 아니므로 임계값 호환성은 구현 시 검증 필요. `validate_korean_output`의 한글 비율 15% 임계는 짧은 코멘트에 민감할 수 있음.
- [검증불가] "수정 후 라이브 재발 방지" — 본 진단 범위 밖. 후속 quick task에서 게이트 구현 후 최소 14일 D1 row 재스캔으로 방지 효과 측정해야 [검증됨]으로 승격 가능.
- [검증불가] 반복 루프 릭에 대한 수정 (max_tokens/프롬프트 구조 조정) — 1건 관측이라 원인-효과가 불명확. 게이트가 잡아주는 수준(차단)이 먼저고, 발생 억제는 데이터 더 모은 후 판단.

## 6. 잔존 위험

- [부분검증] **model_router 로그에 content 스니펫 없음** — tier 상관이 시각 추정에 그침. `_log_to_file`에 `content[:80]` 로깅 추가 전까지 tier↔릭 인과 재현 불가. 이 진단의 tier 판정(1.2표, 판정 secondary)은 이 한계를 안고 있음.
- [검증불가] **영어 원형 릭 라이브 샘플 0건** — 유저가 목격한 릭의 실제 row가 본 스캔 범위 밖일 가능성. 릭 목격 사례(브리핑 페이지 URL/날짜)가 확인되면 해당 row 재스캔 필요. 지금까지의 판정은 "구조적 취약 입증 + 트리거 추정"이지 "특정 릭 사건의 재구성"이 아니다.
- [부분검증] **D1 과거 데이터 소실 가능성** — briefing_items 전체 1,496 rows 스캔했으나 LIKE 8패턴은 영어 메타 문구만 커버. 패턴 외 영어 삽입(예: 문장 중간 영어 절)은 정규식 비율 스캔을 14일치 150rows에만 적용 — 전체 이력 정규식 재스캔은 쿼터 비용상 생략.
- [검증불가] **outline_generator가 생성하는 이후 단계(블로그 초안 변환) 미감사** — 아웃라인 MD는 깨끗했으나, 아웃라인을 소비하는 downstream(blog_draft_generator 등)에서 영어가 재유입되는 경로는 본 진단 범위 밖.
- [부분검증] **신규 tier 4종(or-nexpro/or-nexmini/or-nemotron/or-lingvl, 2026-09-12 추가)** 관측 데이터 0건 — 경향 평가는 모델 계열 추론. 실측 릭이 이 tier에서 나올 가능성 배제 불가.

**진단 무결성 선언**: 본 진단 전체가 read-only로 수행되었다 (코드 수정 0건 — 커밋은 FINDINGS.md 문서만; DB 변경 0건 — SELECT/PRAGMA만 실행, INSERT/UPDATE/DELETE 0건).

