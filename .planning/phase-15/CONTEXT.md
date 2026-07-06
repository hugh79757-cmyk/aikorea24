# Phase 15 — CONTEXT.md

> **Phase:** 15 — Vectorize + 크롤링 실패 수정 + 카드 분할 JSON 전환
> **Status:** Planning
> **Created:** 2026-07-06
> **Depends on:** Phase 14 (Delimiter Reconfiguration — Complete)

---

## 1. Objective

세 가지 잠금 결정을 기반으로 쓰레드 파이프라인 안정성과 품질을 대폭 향상한다.

| # | 의제 | 목적 |
|---|------|------|
| A | **Cloudflare Vectorize 도입** | O(N) 키워드 기반 중복제거 → O(1) 의미적 중복제거로 전환 |
| B | **크롤링 실패 영구 제외 수정** | `failed_crawls.json` 영구 저장으로 인한 기사 풀 고갈 해결 |
| C | **카드 분할 JSON 전환** | delimiter 충돌 문제 근본 해결 — ThreadForge 방식 JSON 배열 출력 |

---

## 2. Locked Decisions (이미 결정됨, 재논의 불가)

### Decision A-1: Vectorize는 Cloudflare REST API로 접근
- **근거:** aikorea24의 Python 스크립트는 Cloudflare에 `CLOUDFLARE_ACCOUNT_ID` + `CLOUDFLARE_API_TOKEN`으로 REST API 접근 (이미 `keyword_updater.py` 등 6개 스크립트에서 사용 중)
- **방법:** `https://api.cloudflare.com/client/v4/accounts/{account_id}/vectorize/v2/indexes/{index_name}` 엔드포인트 사용
- **바인딩 불가:** Python에서 Cloudflare 바인딩 직접 사용 불가 → REST API만 가능

### Decision A-2: 기존 `is_same_topic()`을 유지하고 Vectorize를 보조로 추가
- **근거:** 기존 Jaccard/entity 방식이 이미 안정적으로 동작. 전면 교체가 아닌 레이어 추가
- **흐름:** exact match (id/url/title) → `is_same_topic()` (1차 필터) → Vectorize query (2차 정밀 검증)

### Decision A-3: 임베딩 모델은 OpenAI `text-embedding-3-small` (1536차원)
- **근거:** ThreadForge와 동일한 모델. aikorea24에 이미 OpenAI API 키 설정됨
- **비용:** ~$0.00002/건 (무시할 수준)

### Decision B-1: `failed_crawls.json`에 TTL (Time-To-Live) 도입
- **근거:** 영구 제외는 기사 풀 고갈 → 발행 실패. **24시간** 후 자동 만료
- **대안 (기각):** 전체 초기화 → 너무 많은 실패 기사 재시도 비용
- **대안 (기각):** 재시도 로직 추가 → 복잡도 증가, 크롤링 불가 소스 반복

### Decision B-2: 만료된 실패 기사는 재시도하지 않음
- **근거:** 99%가 `validate_link_fail` (비크롤러블 소스). 재시도해도 실패
- **동작:** TTL 만료 → 목록에서 제거 → 다음 실행 시 기사 풀에 포함 가능성 (크롤링은 별도)

### Decision C-1: LLM 출력 형식을 JSON 배열로 전환
- **현재:** `{"cards": ["text1", "text2", ...]}` + delimiter fallback
- **변경:** `[{"cardNumber": 1, "role": "hook", "text": "..."}, ...]`
- **근거:** ThreadForge가 이 방식으로 delimiter 충돌 문제 완전 회피
- **이점:** 카드 분할이 필요 없음 (JSON 파싱만으로 해결)

### Decision C-2: role 필드 추가 (선택적 검증용)
- **역할:** `hook`, `point`, `data`, `context`, `summary`, `link`
- **용도:** 검증 로직에서 역할별 품질 기준 적용 가능 (예: hook은 30~350자, link는 URL만)
- **강제:** 아니오 — LLM이 role을 잘못 지정해도 발행은 허용

### Decision C-3: 6카드 유지 (ThreadForge의 7+1이 아닌)
- **근거:** aikorea24의 5막 내러티브 구조 (Hook→A면→반전→확장→여운+링크)가 6카드에 최적화됨
- **ThreadForge 차이:** ThreadForge는 역할 기반 (7카드 + 소스 카드 자동 추가)

---

## 3. Gray Areas (이번 Phase에서 결정해야 함)

### Gray Area 1: Vectorize 인덱스 이름과 초기화
- 인덱스 이름: `aikorea24-dedup` (확정)
- 기존 posted.json의 342건 기사를 벡터로 **마이그레이션** (확정)

### Gray Area 2: Vectorize 실패 시 Fallback
- Vectorize API 장애 시 기존 `is_same_topic()`만으로 동작
- Vectorize를 **보조 검증**으로 설정하므로 실패해도 파이프라인 차단 없음

### Gray Area 3: 카드 분할 전환 시 기존 검증 로직 영향
- `validate_card_structure()`의 8단계 검증이 JSON 출력에 맞게 조정 필요
- `_repair_truncated_cards()`는 **제거** (JSON이므로 불필요) (확정)
- `parse_cards()` delimiter fallback은 **제거** (JSON-only 파싱) (확정)

### Gray Area 4: `failed_crawls.json` TTL 값
- **24시간** (확정)
- URL 크롤링 실패 기사 목록 — 24시간 후 자동 만료
- `validate_link_fail` 상태도 동일하게 TTL 적용

---

## 4. Non-Functional Requirements

| 요구사항 | 값 |
|---------|---|
| Python 버전 | 3.14 (stdlib only — 새 의존성 없음) |
| Vectorize 레이턴시 | < 200ms (REST API 오버헤드 포함) |
| 카드 분할 실패율 | 0% (JSON 파싱은 deterministic) |
| 발행 실패율 | < 5% (기사 풀 고갈 해결) |
| 기존 테스트 | 회귀 없이 통과 |

---

## 5. Key Files

| 파일 | 변경 유형 |
|------|----------|
| `pipeline/threads/dedup.py` | Vectorize 쿼리 레이어 추가 |
| `pipeline/threads/writer.py` | 프롬프트 JSON 전환 + `parse_cards`/`_repair_truncated_cards` 제거 |
| `pipeline/threads/validator.py` | JSON 출력에 맞는 검증 조정 + delimiter 검증 제거 |
| `scripts/threads/main_v3.py` | Vectorize 호출 + failed_crawls TTL 로직 |
| `scripts/threads/db_reader.py` | Vectorize 기반 중복 체크 추가 |
| `scripts/threads/logs/failed_crawls.json` | TTL 필드 추가 |
| `pipeline/infra/vectorize_client.py` | **신규** — Vectorize REST API 클라이언트 |

---

## 6. Success Criteria (Phase 15 완료 기준)

1. Vectorize 인덱스 `aikorea24-dedup` 생성 및 기존 기사 342건 임베딩 저장
2. `is_duplicate_with_vectorize()` 함수가 cosine similarity ≥ 0.85일 때 True 반환
3. 기존 `is_same_topic()` + Vectorize 2단계 중복 제거 동작 확인
4. `failed_crawls.json`에 `expired_at` 필드 추가, **24시간** 후 자동 만료
5. 크롤링 실패 기사가 기사 풀에서 제외되지 않음 (만료 후)
6. LLM 출력이 JSON 배열 `[{cardNumber, role, text}]` 형식
7. delimiter fallback 로직 **제거** (JSON-only 파싱)
8. `_repair_truncated_cards()` **제거**
9. `validate_card结构调整` JSON에 맞게 조정
10. `py_compile` + 기존 테스트 회귀 없이 통과
11. `run_pipeline.py --dry-run` 정상 동작
