# person_gate 통합 패치 지시서

> 상태: 2026-08-26 검증 완료 → 실사용 가능 확정. 본 문서는 `auto_news_selector.py`
> 출력부에 게이트 분기를 추가하는 **작업 지시서**(에이전트/대표가 적용).
> `pipeline/threads/person_gate.py` 는 이미 이관 완료됨.

## 1. 검증 결과 (선행 확정 사항)

| 단계 | 결과 |
|---|---|
| 양성 케이스 확보 | 404 Media "Charges Dropped Against Person Who Clapped at a City Data Center Meeting" (럭스 클라리지, 고교 교사) |
| person_gate | `pass=true`, person="Lux Claridge(고등학교 교사)" — 비관료 당사자 + 직접 인용 + 8시간 구금·형사 charge |
| standalone_extractor(B/C) | 인용 4건(화자 실명), 수치 2건 정상 추출 |
| kicker7 | 7카드 생성 (cross=5 bg=3) → `/tmp/kicker7_v3_output.txt` |
| 루브릭 | 무근거 0 · 화자 실명 · 키커 귀결 → **통과** |

## 2. 추가할 import (auto_news_selector.py 상단)

```python
from pipeline.threads.person_gate import person_gate
import pipeline.threads.crawler as _crawler
import logging
logger = logging.getLogger("auto_news_selector")
```

## 3. 게이트 분기 삽입 위치

`select_top_articles()` / `_two_pass_selection()` 이 반환한 `selected`(일일 ~6건)를
처리하는 루프에서 **crawler 본문 추출 직후, standalone_extractor 직전**에 삽입.

```python
def _gate_and_route(selected):
    """선별 기사에 person_gate 적용 → 통과분만 kicker7 경로로 라우팅."""
    routed = []
    for art in selected:
        title = art.get("title")
        link = art.get("link")
        try:
            body = _crawler.fetch_article_body(link, title=title)
        except Exception as ex:
            logger.warning("person_gate: crawl failed %s (%s)", link, ex)
            continue  # 본문 없으면 게이트 불가 → 탈락
        gate = person_gate(title, body)  # 내부 재시도 1회, 실패 시 pass=False
        if not gate.get("pass"):
            logger.info("person_gate: no person story — %s | %s", title, gate.get("reason"))
            continue  # kicker7 호출 건너뛰기
        art["gate"] = gate
        art["body"] = body
        routed.append(art)
    return routed
```

- **호출 시점**: 기존 `standalone_extractor` / `kicker7` 호출 직전에 `_gate_and_route(selected)` 실행.
- **탈락 로그**: 반드시 `"person_gate: no person story"` 문자열 포함(운영 모니터링 키).
- **kicker7 건너뛰기**: `routed` 에만 kicker7 발행 파이프라인 진입.
- **JSON 파싱 실패**: `person_gate()` 내부에서 재시도 1회, 그래도 실패하면 `pass=False`(탈락). 호출부 추가 처리 불필요.

## 4. minor fix (이미 반영됨 — person_gate.py)

- 프롬프트에 `"출력은 JSON 펜스(```json) 없이 순수 JSON만 출력하라"` 명시.
- `_normalize_json()` 로 응답 정규화(```json 펜스 제거 + 첫 `{...}` 추출).
- 실측에서 발생했던 `#5 빌 게이츠` 파싱오류 해소 확인.

## 5. 비용

- 일일 6건 × 1회 flash 호출 ≈ 월 $0.06 (유료 flash 가정).
- 실제는 무료 폴백체인(gemini-3.1-flash-lite) 사용 → $0.
- kicker7(딥시크)은 통과분에만 호출 → 비용 폭증 없음.

## 6. 잔존 위험 (적용 전 검토)

- 게이트는 주관적 LLM 판단 — 경계 사례(익명 내부고발자, 집단 피해) 기준 보강 필요.
- `selected` 가 비어 있으면 `_gate_and_route` 는 빈 리스트 반환(정상).
- 기존 `is_ai_related` 는 건드리지 않음(게이트는 AI 정체성 유지된 선별 결과에 적용).
