# Thread Writing Version Comparison — aikorea24

> 작성일: 2026-08-26
> 목적: 사용자가 정의한 "신규 글쓰기 로직"(URL → af_json 추출 → kicker7 v3 프롬프트 → 스레드 발행)이 실제 코드와 어떻게 다른지 규정하고, 기존 **스레드** 라이터들과의 차이를 문서화한다.

---

## 0. 결론 먼저 (사용자 정의 vs 실제 코드)

사용자 정의 흐름:

```
URL → extract.py(standalone_extractor.py) → af_json → kicker7 v3 프롬프트 → 스레드 발행
```

**2026-08-27 기준: 운영중(live).** 단, 사용자 정의 스케치(`standalone_extractor.py` 단독)와 실제 배선은 다르다:

- 사용자 스케치의 `standalone_extractor.py`는 **프로토타입 테스트 전용** — 실제 운영 경로는 쓰지 않음.
- **실제 운영 경로**: `auto_news_selector.route_person_stories()` → `orchestrator.run_contrast_thread(writer_fn=write_kicker7_thread)` (기존 extractor/background_search 수집 재사용) → `kicker7_writer.write_kicker7_thread()` 가 `SYSTEM_KICKER7_V3` 호출 → 드래프트 저장 → `publish_kicker7_drafts.py`(별도 launchd) 발행.
- `SYSTEM_KICKER7_V3`는 `prompts.py` 상수로 존재하나, 호출부는 `kicker7_writer.py`(운영) + `standalone_extractor.py`(테스트) 2곳. `main_v3` contrast 경로는 여전히 `contrast_writer` 사용(미변경).

즉 "신규 로직"은 **(A) writer_fn 주입으로 기존 수집 재사용 + (B) 프롬프트 교체(kicker7_writer) + (C) 단일단계 카드 생성 + (D) 비동기 발행기 분리** 로 배선 완료. 상세: `docs/THREADS-PIPELINE-TECH.md` §17.

### ⚠️ 용어 정정 (중요)
`scripts/blog_draft_generator.py` 는 **스레드 발행기가 아니다**. 이건 **블로그 발행기**다 — 출력이 `src/content/blog/*.md` (Astro 마크다운) → `aikorea24.kr/blog/` 배포. 따라서 본 문서는 "스레드 글쓰기 버전" 비교에서 **auto-blog를 제외**한다. auto-blog는 별개 제품(블로그)이며 본 비교의 범위 밖.

---

## 1. 스레드 라이터별 코드 위치 및 상태 [검증됨]

| 버전 | 추출기 | 생성 프롬프트 | 단계 | 배선 상태 | 코드 위치 |
|------|--------|--------------|------|----------|----------|
| **D 포맷 (레거시)** | `get_articles()` (D1 뉴스) | `v3.writer_v3` 내장 | 1단계 | 운영중 (main_v3 --format D 기본) | `scripts/threads/v3/writer_v3.py` |
| **contrast 파이프라인 (Phase 37)** | `extractor.py` → SYSTEM_EXTRACTOR (A~F) | SYSTEM_CURATOR_CONTRAST + SYSTEM_SENTENCE | 2단계 (outline→sentence) | 운영중 (main_v3 --format contrast, 발행 비승인) | `pipeline/threads/contrast/` |
| **신규 kicker7 v3 (본 문서 대상)** | `extractor.extract_af` (orchestrator 수집 재사용) | SYSTEM_KICKER7_V3 (v2.5: 5카드+출처카드) | 1단계 (직접 카드 생성) | **운영중(live 2026-08-27)** | `pipeline/threads/contrast/kicker7_writer.py` + `scripts/threads/publish_kicker7_drafts.py` |

근거:
- `grep -rl "standalone_extractor" --include="*.py" .` → `standalone_extractor.py` 1건만 (자기 자신). 파이프라인 참조 0.
- `grep "SYSTEM_KICKER7" pipeline/threads/contrast/*.py` → `prompts.py` 정의만, `extractor.py`/`contrast_writer.py`/`orchestrator.py` 호출 0.
- `main_v3.py:128` → `_fmt not in ("D","contrast")` 거부. `:167` D는 `v3.writer_v3`, `:171` contrast는 `run_contrast_thread`.
- `blog_draft_generator.py:6` 주석 "src/content/blog/ 에 마크다운 파일 저장", `:304` `blog_url = https://aikorea24.kr/blog/{slug}/` → 블로그 제품 확인.

> 별도 제품(비교 제외): `scripts/blog_draft_generator.py` = 블로그 발행기. 스레드와 무관.

---

## 2. 신규 로직의 핵심 특징 (kicker7 v3)

`SYSTEM_KICKER7_V3` (prompts.py:183) 단일 프롬프트가 A~F JSON을 받아 5~7장 카드를 1회 호출로 생성. 기존과 결정적 차이:

### 2.1 사실 봉쇄 (제1부)
- **규칙 1**: 카드의 모든 고유명사/수치/날짜/인용 근거는 입력 JSON뿐. 추정·보간·반올림 금지. 평가 문장은 JSON에 문자 그대로 있을 때만.
- **규칙 2**: C.speaker != null 이면 화자 **실명 + attribution** 함께 기재. "외무장관은" 식 축약 금지 (기존 대비 대폭 강화).
- **규칙 3**: 수치는 반드시 B.condition(한정어) 함께. 조건 없는 수치 = 미작성.
- **규칙 5**: 침묵 진술 최대 1문장.

### 2.2 판단 카드 마무리 규정 (규칙 9) — 가장 큰 차이
- (가) 앞 카드 사실 3개↑ 재배열, 수치 최소 2개 재배치.
- (나) 첫 문장: 충돌/어긋나는 사실 2개 나란히 OR 역설.
- (다) **마지막 문장 귀결 위계**: 1순위 일반인 당사자 소환 → 2순위 피해 집단 처지 → 3순위 되돌 수 없는 사실.
- (라) 금지 종결 어미 6종 + 기관/제도 주어 금지.
- (마) 자기 시험: "대가를 누가 치렀는가" 답 안 되면 재작성.

### 2.3 출력 형식
- 카드: `--- 카드 N ---`, 마지막: `--- 판단 ---`.
- 재료 신고 3종 (`[재료 신고: 장면/인물 재료 없음 | 인용 부족]`) — 유일한 허용 부가 출력.

---

## 3. 기존 스레드 라이터와의 차이 [검증됨]

### 3.1 kicker7 v3 vs contrast 파이프라인 (Phase 37)

| 차원 | Phase 37 contrast | 신규 kicker7 v3 |
|------|-------------------|-----------------|
| 생성 단계 | outline 생성 → sentence 작성 (2단계) | 1단계 직접 카드 생성 |
| 추출 스키마 | SYSTEM_EXTRACTOR (B/C dict: value_text/metric/condition/evidence_sentence, C: text/speakers/speaker_type/source_topic_tag) | standalone_extractor.py (B/C simpler dict, _meta 검증) |
| 출력 포맷 | JSON `{"cards":[...]}` (validator 파싱) | 텍스트 `--- 카드 N ---` 헤더 구분 |
| 화자 규칙 | speaker_type joint_statement 복수화자 규칙 | speaker 실명 + attribution 강제 (규칙 2) |
| 판단 카드 | C5 확정통찰/열린질문 (이전 사양) | 규칙 9 귀결 위계 + 금지 종결 |
| 배분 계획 | SLOT_PLAN 동적 3~8, distinct_fact_count 기반 | 규칙 6 내부 배분 (출력 안 함) |
| 인용 언어 | SYSTEM_SENTENCE_KICKER7 규칙 11 (번역+원문30자 병기) | 규칙 11 동일 |

근거:
- `contrast_writer.py:303` → `chat_completion(system_prompt=SYSTEM_SENTENCE+"\n"+SYSTEM_CURATOR_CONTRAST, ..., response_format={"type":"json_object"})` (2단계, JSON 출력).
- 신규 v3는 `response_format` 없이 텍스트 헤더 포맷 출력 → 파서 교체 필요.
- `extractor.py:151` → `SYSTEM_EXTRACTOR` 호출. 신규는 `standalone_extractor.py` 가 별도 추출.

### 3.2 kicker7 v3 vs D 포맷 (레거시)

| 차원 | D 포맷 (v3.writer_v3) | 신규 kicker7 v3 |
|------|----------------------|-----------------|
| 입력 | D1 뉴스 기사 요약/브리핑 | A~F 구조화 추출물 |
| 서사 구조 | 브리핑 5카드 (사실 나열) | 장면→메커니즘→반전→목소리→책임→대가→판단 7역할 |
| 사실 검증 | 없음 (자유 생성) | 제1부 사실 봉쇄 strict |
| 판단 카드 | 없음 | 규칙 9 귀결 위계 필수 |

근거: `main_v3.py:257` D branch → `v3.writer_v3.write_thread(pitch, articles)`. `v3/writer_v3.py` 는 1531바이트 소형 모듈, SYSTEM 프롬프트 내장, structured extraction 없음.

---

## 4. 배선 완료 / 운영 상태 (2026-08-27)

아래 배선은 **완료**됨 (이전 "필요 목록" → 실행 완료):

1. **writer_fn 주입**: `orchestrator.run_contrast_thread(seed, all, writer_fn=None)` — 기존 extractor/background_search 수집은 그대로, 글쓰기만 교체. kicker7은 `write_kicker7_thread` 주입.
2. **프롬프트 교체**: `kicker7_writer.py` 가 `SYSTEM_KICKER7_V3`(v2.5) 호출. `--- 카드 N ---` / `--- 카드 6 ---` 텍스트 파서 내장(`_parse_kicker7_cards`).
3. **출력 파서**: `--- 카드 N ---` / plain `---` / `\n---\n` 모두 카드 경계로 인정 (카드내부 절구분 `\n\n` 보존).
4. **validator 재사용**: `validate_final_cards(cards[:5])` — 카드6(출처) 면제. 루브릭 게이트(무근거0/화자실명/출처카드)는 `publish_kicker7_drafts.py` 에서 추가.
5. **딥시크 thinking-off**: `kicker7_writer` 호출 시 `extra_body={"thinking":{"type":"disabled"}}` 적용 (model_router 버그 우회).

> 발행은 `main_v3` 가 아닌 **별도 비동기 경로**: `auto_news_selector`(드래프트 생성, `:00`계열) → `publish_kicker7_drafts.py`(발행, launchd `kr.aikorea24.kicker7-publisher` `:30`). 상세는 `docs/THREADS-PIPELINE-TECH.md` §17.

---

## 5. 잔존 위험

- **[검증됨]** kicker7 v3 실제 발행 품질: 2026-08-27 live 전환. 첫 발행 `k7_46941`(Meta AI layoff, The Decoder) 5카드+링크답글 성공(root `17866975854642583`). 동 사이클 4건은 루브릭 `무근거 카드N` 으로 HOLD(보수적 차단, 의도된 동작).
- **[부분검증]** standalone_extractor.py 출력 스키마가 contrast `extractor.py` 스키마와 필드명 불일치 가능 (B: value_text vs metric 구조). 교차 검증 안 함.
- **[검증됨]** Phase 37 contrast는 현재 운영중이나 발행 비승인 (dry-run only) — 신규가 대체 투입돼도 동일 게이트 유지 권장.
- 딥시크 유료 호출 비용: v3 고정 시 무료 체인 포기 → 비용 모델 확정 필요.
