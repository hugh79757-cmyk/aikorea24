# Phase 32: Threads 알고리즘 정렬 개선 — 2-1/2-2/2-3 적용

**Phase:** 32  
**Phase Name:** Threads 알고리즘 정렬 개선 — 2-1/2-2/2-3 적용  
**Mode:** ad-hoc  
**Depends on:** Phase 24 (Batch 최적화, 완료), Phase 16 (Writer prompt v2, 완료)  
**Predecessor:** Phase 31 (description 추출 버그 수정, 완료)  
**Rollback Base:** `da69c88bdd8bbd04800b3a00655c1b37d7092ba1`

---

## Goal

Threads 알고리즘 정렬을 위해 FORMAT_D를 5콘텐츠 카드로 재설계하고, 카드 5를 답글 유도형으로 강제하며, humanize_cards()의 상태를 명확히 정리한다.

## Scope

**포함:**
- 2-1: FORMAT_D 링크 카드 제거 → 5콘텐츠 카드 + 루트 답글 링크
- 2-2: 마지막 카드 답글 유도형 강제 (SYSTEM 프롬프트 + validator)
- 2-3: humanize_cards() 상태 정리 + AI 어휘 패턴 확장

**제외 (별도 phase/session):**
- ~~2-4: 발행 후 30분 답글 자동 응답 루프~~
- ~~2-5: launchd 스케줄 조정 (KST 8/12:30/19)~~
- ~~2-6: A/B 테스트 인프라~~
- ~~2-7: 계정 답글 비율 관리 가이드~~

## 변경 대상 파일

| 파일 | 변경 내용 | 비고 |
|------|---------|------|
| `pipeline/threads/writer.py` | `build_system_prompt_D()`, `FORMAT_LABELS`, `write_thread()`, `assemble_final()` | 5카드 + 링크 분리 반환 |
| `pipeline/threads/validator.py` | `FORMAT_CARD_COUNTS`, `FORMAT_CARD_COUNT_TOLERANCE`, `validate_cards()`, `validate_final_output()`, `validate_card_structure()` + `_validate_last_card_opens_reply()` | 카드 수 조정, 마지막 카드 검증 |
| `scripts/threads/publisher.py` | `publish_thread_chain()` | 5카드 발행 후 루트 답글로 링크 발행 |
| `scripts/threads/main_v3.py` | `validate_final_cards()`, dry-run 출력 | 카드 수 관련 로직 조정 |
| `tests/test_write_thread_validation.py` | `test_link_card_stripped` 제거, `test_link_returned_separately`, `test_only_5_content_cards` 신규, 카드 답글 유도 검증 테스트 추가 | |
| `docs/THREADS-PIPELINE-TECH.md` | 섹션 4.3, 10, 부록 A.2 업데이트 | 2-1/2-2 변경사항 반영 |

## Success Criteria

1. `write_thread()`가 `{"cards": [5개], "link": "url"}` 딕셔너리 반환
2. `assemble_final()`이 링크 카드 미포함 (5카드만 반환)
3. `main_v3.py`와 `publisher.py`가 `write_thread()`의 새 반환 스펙에 맞게 인자 조정
4. `build_system_prompt_D()`가 "5 content cards only" 지침으로 변경됨
5. `FORMAT_CARD_COUNTS['D']` = 5, `FORMAT_CARD_COUNT_TOLERANCE['D']` = (5,5)
6. `publish_thread_chain()`가 5카드 체인 발행 후 루트 답글로 링크 발행 (발행 전 15초 대기 포함)
7. `_validate_last_card_opens_reply()`가 `cards[-1]`의 열린 종결 검사
8. `validate_card_structure()`가 마지막 카드 열린 종결 실패 시 전체 실패
9. `humanize_cards()` 존재 확인, `AI_KOREAN_PATTERNS` 교체, 호출 확인
10. writer_v3.py 테스트 주석의 "removed" → "preserved as AI-vocabulary defense"
11. tests/test_write_thread_validation.py 모든 테스트 통과 (`test_link_card_stripped` 제거, 신규 2개 포함)
12. `python scripts/threads/main_v3.py --dry-run`이 5카드 생성 + 링크 답글 분리 표시
13. docs/THREADS-PIPELINE-TECH.md 섹션 4.3, 10, 부록 A.2에 2-1/2-2 변경사항 반영
14. 롤백 베이스 커밋 해시 확보됨

## Tasks

### Task 2-1: FORMAT_D 링크 카드 제거 (우선순위: 1, 최우선)

**변경 파일:** `pipeline/threads/writer.py`, `pipeline/threads/validator.py`, `scripts/threads/publisher.py`, `scripts/threads/main_v3.py`, `tests/test_write_thread_validation.py`, `docs/THREADS-PIPELINE-TECH.md`

**write_thread() 반환 스펙 변경:**
- 기존: `list[str]` (6개 카드)
- 신규: `dict` — `{"cards": [card1, card2, card3, card4, card5], "link": "https://..."}`
  - `cards`: 5개 콘텐츠 카드 리스트
  - `link`: 원문 URL 문자열 (publisher가 별도 답글로 발행)

**assemble_final() 변경:**
- 기존: `list[str]` 반환 (링크 카드 포함)
- 신규: `list[str]` 반환 (링크 카드 미포함, 5카드만)
- 링크 카드 생성 로직 제거 (publisher로 이동)

**main_v3.py 변경:**
- `write_thread()` 반환 타입이 dict임을 처리 (cards unpacking)
- `validate_final_cards()`가 dict의 `cards` 키에서 리스트 추출
- dry-run 출력: 5카드 표시 + "링크 답글: {url}" 분리 표시

**publisher.py 변경:**
- `publish_thread_chain(cards: list[str], article, link_url: str = "")` 시그니처 확장
- 5카드 연속 답글 발행 → 카드1 ID로 reply_to_id 설정하여 링크 답글 발행
- 카드 5 발행 후 15초 대기 → 링크 답글 발행

**writer.py 변경:**
- `build_system_prompt_D()`: "6 cards total: 5 content cards + 1 link card" → "5 content cards only"
- 카드 6 관련 지침 전체 제거
- JSON 출력 형식: `{"cards": ["card1", ..., "card5"]}`
- `FORMAT_LABELS['D']`: '펀치 브리핑형 (5개 콘텐츠 카드 + 루트 답글 링크)'
- `FORMAT_CARD_COUNTS['D']`: 6 → 5
- `FORMAT_CARD_COUNT_TOLERANCE['D']`: (4,7) → **(5,5)** (5 only 엄격 적용, 4카드 시 다음 tier 폴백 유도)
- `validate_cards()`: 링크 카드 예외 처리 제거
- `validate_final_output()`: 링크 카드 예외 처리 제거

**validator.py 변경:**
- `FORMAT_CARD_COUNT_TOLERANCE['D']` = (5,5)
- `validate_cards()`에서 최소 카드 수 검증 시 (5,5) 기준으로 4카드 거부

**테스트:**
- `test_link_card_stripped` 제거
- 신규 `test_link_returned_separately`: write_thread()가 dict 반환, cards=5개, link=url 확인
- 신규 `test_only_5_content_cards`: 5개 초과/미만 카드 출력 시 다음 tier 폴백 유도 확인

**docs/THREADS-PIPELINE-TECH.md 업데이트 범위:**
- 섹션 4.3 (Step 3: 쓰레드 작성): FORMAT_D 5카드 + 링크 분리 반환 설명
- 섹션 10 (주요 숫자/제약): 카드 수 6→5, 카드 최대 길이 500자 유지
- 부록 A.2 (FORMAT_D SYSTEM 프롬프트): 5카드 + CARD 5 RULE 포함

**커밋 메시지:**
```
feat(writer): remove link card from FORMAT_D, move URL to separate reply

Threads algorithm suppresses posts with external links (2026)
Main chain now 5 content cards only, link posted as root reply
write_thread() returns dict {"cards": [...], "link": url}
FORMAT_CARD_COUNT_TOLERANCE['D'] = (5,5) strict
Aligns with Threads ranking: link penalty avoidance
```

---

### Task 2-2: 마지막 카드 답글 유도형 강제 (우선순위: 2)

**변경 파일:** `pipeline/threads/writer.py`, `pipeline/threads/validator.py`, `tests/test_write_thread_validation.py`, `docs/THREADS-PIPELINE-TECH.md`

**변경 내용:**
- writer.py `build_system_prompt_D()` SYSTEM 프롬프트에 CARD 5 RULE 추가:
  ```
  CARD 5 RULE (필수):
  반드시 열린 질문, 불완전한 결론, 또는 반론을 유발하는 형태로 끝낼 것
  물음표(?) 또는 열린 어미(("~일까", "~일수록", "~인데" 등)로 종결
  완결된 주장("~했다", "~이다")으로 끝내는 것 금지
  독자가 답글을 쓰고 싶게 만드는 한 줄만 허용
  ```
- validator.py에 `_validate_last_card_opens_reply()` 함수 추가 (cards[-1] 검사)
- validator.py `validate_card_structure()`에 마지막 카드 열린 종결 검사 통합

**_validate_last_card_opens_reply() 구현:**
```python
def _validate_last_card_opens_reply(cards: list[str]) -> bool:
    """마지막 콘텐츠 카드가 답글을 유도하는 열린 형태로 끝나는지 검사"""
    if len(cards) < 4:
        return True  # 카드 수 자체가 문제
    last_card = cards[-1].strip()
    last_char = last_card[-1] if last_card else ""
    open_endings = ("?", "까", "까?", "일수록", "인데", "을까", "일까", "ㄹ까")
    if last_char == "?":
        return True
    for ending in open_endings:
        if last_card.endswith(ending):
            return True
    return False
```

- `FORMAT_CARD_COUNT_TOLERANCE['D']` = (5,5) 적용 시 5카드만 허용되므로 영향 적음

**테스트:**
- `test_last_card_closed_ending_rejected`: "이것이 결론이다."로 끝나는 마지막 카드 → 거부
- `test_last_card_open_ending_accepted`: "이것이 맞을까?"로 끝나는 마지막 카드 → 통과

**커밋 메시지:**
```
feat(writer): force last card to open-ended reply-bait format

- Reply engagement is Threads' strongest ranking signal
- Last card must end with question or open ending
- Renamed _validate_card5_opens_reply → _validate_last_card_opens_reply
- Inspects cards[-1] for open ending
- Added _validate_last_card_opens_reply() to validator
```

---

### Task 2-3: humanize_cards() 상태 정리 (우선순위: 3)

**변경 파일:** `pipeline/threads/writer.py`, `scripts/threads/v3/writer_v3.py`, `docs/THREADS-PIPELINE-TECH.md`

**변경 내용:**
- `pipeline/threads/writer.py`에서 `humanize_cards()` 함수 존재 확인
- 존재하면 `AI_KOREAN_PATTERNS` 리스트를 실제 한국어 AI 출력 패턴으로 교체:
  ```python
  AI_KOREAN_PATTERNS = [
      ("획기적인", "새로운"),
      ("혁명적인", "큰"),
      ("궁극적으로", "결국"),
      ("가속화되", "빨라지"),
      ("융합하여", "합쳐"),
      ("핵심은", "중요한 건"),
      ("중요한 것은", "중요한 건"),
      ("~게 됩니다", "~게 돼"),
      ("~할 수 있습니다", "~할 수 있어"),
      ("~입니다.", "~임."),
      ("~합니다.", "~함."),
  ]
  ```
  - 제거: "딜브", "트랜스포머티브", "판타스틱", "어메이징" (실제 AI 출력에서 빈도 낮음)
  - 추가: 실전에서 자주 나오는 AI 한국체 패턴 (과도한 정중체, 번역투 종결어미)
- `write_thread()` 파이프라인에서 `humanize_cards()` 호출 확인
- `scripts/threads/v3/writer_v3.py` 테스트 주석 수정: "humanize/MiMo pipeline removed" → "humanize preserved as AI-vocabulary defense"
- `docs/THREADS-PIPELINE-TECH.md` 16.4항 업데이트 (humanize_cards 상태 명확화)

**테스트:** 기존 테스트 영향 없음

**커밋 메시지:**
```
fix(writer): clarify humanize_cards() status, expand AI vocabulary patterns

- humanize is required defense against Threads AI-vocabulary suppression
- Replaced unrealistic patterns with actual Korean AI output patterns
- Updated misleading "removed" comment
- Expanded Korean AI pattern list with realistic replacements
```

---

## Verification Checklist

- [ ] 2-1 적용 후 `write_thread()`가 `{"cards": [5개], "link": "url"}` 반환
- [ ] 2-1 적용 후 `assemble_final()`이 5카드만 반환 (링크 카드 미포함)
- [ ] 2-1 적용 후 `main_v3.py`가 dict 반환값 처리
- [ ] 2-1 적용 후 `publisher.py`가 `cards` + `link_url` 분리 인자 처리
- [ ] 2-1 적용 후 `build_system_prompt_D()`에 "5 content cards only" 포함
- [ ] 2-1 적용 후 `FORMAT_CARD_COUNTS['D']` = 5
- [ ] 2-1 적용 후 `FORMAT_CARD_COUNT_TOLERANCE['D']` = (5,5)
- [ ] 2-1 적용 후 `publish_thread_chain()`가 5카드 체인 발행 + 15초 대기 후 루트 답글 링크 발행
- [ ] 2-2 적용 후 SYSTEM 프롬프트에 CARD 5 RULE 포함
- [ ] 2-2 적용 후 `_validate_last_card_opens_reply()` 함수가 `cards[-1]` 검사
- [ ] 2-2 적용 후 `validate_card_structure()`가 마지막 카드 열린 종결 검사
- [ ] 2-3 적용 후 `humanize_cards()` 함수 존재 확인
- [ ] 2-3 적용 후 `AI_KOREAN_PATTERNS`가 실제 패턴으로 교체됨
- [ ] 2-3 적용 후 writer_v3.py 테스트 주석 "preserved as AI-vocabulary defense"로 변경
- [ ] tests/test_write_thread_validation.py: `test_link_card_stripped` 제거, `test_link_returned_separately` + `test_only_5_content_cards` 통과
- [ ] tests/test_write_thread_validation.py 모든 테스트 통과
- [ ] `python scripts/threads/main_v3.py --dry-run`이 5카드 생성 + 링크 답글 분리 표시
- [ ] docs/THREADS-PIPELINE-TECH.md 섹션 4.3, 10, 부록 A.2에 2-1/2-2 변경사항 반영
- [ ] 롤백 베이스 커밋 해시 기록됨

## Rollback Procedure

문제 발생 시:
```bash
cd /Users/twinssn/Projects/aikorea24
git reset --hard da69c88bdd8bbd04800b3a00655c1b37d7092ba1
git push origin main --force
```

## 실행 순서

```
1. 2-1 적용 → 테스트 → 커밋 (feat: remove link card)
2. 2-2 적용 → 테스트 → 커밋 (feat: force last card open-ended)
3. 2-3 적용 → 테스트 → 커밋 (fix: clarify humanize status)
4. 전체 dry-run 검증
```

각 Task 적용 후 `pytest tests/test_write_thread_validation.py`로 회귀 확인.

## 리서치 결과 (2026-08-14)

### 2-1 영향 분석

**write_thread() 반환값 변경 영향 범위:**

| 호출측 | 기존 사용 방식 | 변경 필요 |
|--------|-------------|----------|
| `main_v3.py:run_v3()` line 202 | `cards = write_thread(pitch, articles)` → 리스트 사용 | dict에서 `cards['cards']` 추출 필요 |
| `main_v3.py:save_draft()` line 213 | `save_draft(cards, pitch)` — cards로 저장 | dict['cards'] 전달 |
| `main_v3.py:validate_final_cards()` line 217 | `validate_final_cards(cards)` — 카드 리스트 검증 | dict['cards'] 전달 |
| `scripts/threads/v3/writer_v3.py` | `cards = write_thread(...)` → 리스트 | dict['cards'] 추출 |

**assemble_final() 현재 동작:**
- link_card 생성 → 6카드이면 마지막 교체, 아니면 append
- `_remove_duplicate_links()` 호출
- 카드 6 미만 시 가장 긴 카드 분할 (pad to 6)
- → 2-1에서는 링크 카드 생성 로직 삭제, pad 로직도 5카드 기준으로 변경

**publisher.py 현재 동작:**
- `publish_thread_chain(cards, article)` — cards 리스트를 연속 답글로 발행
- 각 카드마다 컨테이너 생성 → 발행 → reply_to_id 체이닝
- → 2-1에서는 5카드 발행 후 마지막(카드5 아님)에 링크 답글 발행, reply_to_id는 카드1 ID

### 2-2 변경 영향

- `_validate_card5_opens_reply` → `_validate_last_card_opens_reply`로 이름 변경
- cards[4] → cards[-1]로 변경하여 4/5카드 모두 대응 (다만 (5,5) 적용 시 5카드만 허용되므로 영향 제한적)
- 기존 카드5 검증 테스트도 `test_last_card_*`로 이름 변경 필요

### 2-3 변경 영향

- AI_KOREAN_PATTERNS 교체는 순수 패턴 리스트 교체로 함수 동작에 영향 없음
- humanize_cards() 존재 여부 확인 후 호출 경로 확인 필요 (현재 writer.py 내에서 호출되는지)

## 참고

- 2-5(launchd 스케줄 조정)는 별도 세션에서 3~5일 후 적용
- 2-4(답글 자동 응답), 2-6(A/B 인프라), 2-7(운영 가이드)는 별도 논의
