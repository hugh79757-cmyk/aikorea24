---
phase: quick-260913-hallucination-gate
subsystem: threads-pipeline
tags: [threads, hallucination, gate, cjk, refusal, burst-ending, kicker7]
requires: [260913-thread-quality-eval]
provides: [hallucination-3gate]
key-files:
  created:
    - tests/test_hallucination_gate.py
    - .planning/quick/260913-hallucination-gate/PLAN.md
  modified:
    - scripts/threads/main_v3.py
    - pipeline/threads/contrast/kicker7_writer.py
    - .planning/STATE.md
commits: [pending]
status: complete
---

# Quick 260913-hallucination-gate: 할루시네이션 발행 방어 게이트

## 원인 (코드 열람 검증)
1. `validate_final_cards`(main_v3.py) — v3+kicker7 공용 발행 게이트인데 CJK/거부문/파열 체크 없음
2. `write_kicker7_thread` — 생성 시점 검증 0개 (contrast_writer는 풀체인)
3. kicker7-publisher launchd disabled → 오염 k7 62개 적체 (신규 게이트로 7건 오염 확정)

## 수정 [PRODUCTION CODE]
- `main_v3.py::validate_final_cards` — 기존 검사 전부 유지, 신규 3종 추가 (시그니처/반환 불변):
  1. CJK 혼입: NFKC 정규화 후 한자[\u4e00-\u9fff]/일본어 가나 감지 ("大学和" 사고)
  2. LLM 거부문: 카드가 `^(죄송합니다|요청하신|충족할 수 없|I'm sorry|I cannot...)`로 시작 시 차단. prefix 판정 — 문장 중간 인용("미래는 피할 수 없습니다" k7_49238)은 통과 (오탐 해소)
  3. 어미 파열: 마지막 줄 끝 `[가-힣]{0,4}(다임|다이이|이이이|았다임|었다임...)$` 감지 ("한다임/왔다임/있다이이" 사고). 정상 "~임/~함/~음" 통과
- `kicker7_writer.py::write_kicker7_thread` — 2차 방어: 저장 직전 validate_final_cards 재사용, 오염(파열/혼입/거부문) 감지 시 None 반환(폐기). 기존 게이트 이슈(미완결 등)는 3차 발행 게이트에 위임 — 저장 허용

## 백로그 조치
- k7 대기 62개 재검증 → 신규 게이트 차단 7건 (한자 3: 資深×2, 力的, 大学和 / 카드수부족 4) → hold/ 이동. 대기 55개 잔여
- hold 27개 재검증 — 이동 7건과 일치, 추가 오염 없음

## kicker7-publisher 재개
- `launchctl print-disabled` → disabled 상태 확인 → `launchctl enable` + `bootstrap` → LOADED
- dry-run: 55개 중 PASS/ SKIP/ HOLD 루브릭 정상 동작 확인

## 테스트 [TEST CODE]
- `tests/test_hallucination_gate.py` 신규 6종: 파열 2, 정상 종결 오탐 0, CJK, 거부문, 인용문 오탐 0
- 회귀: `test_characterization_validate_final_cards` 8 passed (green 유지)
- 전체: 44 passed + 1 failed (`test_hook_entity_quote_marked_accepted` — git stash로 원복해도 동일 실패 = **기존 실패, 이번 수정 무관** [검증됨])

## 잔존 위험
- `nvidia-nemotron` "~했음" 나열체(D급)는 게이트 미차단 — 스타일 문제라 육안 검수 필요. 모델 제외는 소유자 결정
- contrast dry-run 초안(logs/drafts/contrast/)의 과거 거부문 2건은 미발행 상태로 방치 — 자동 발행 경로 없어 위험 낮음
- launchd 재개 후 다음 :30분 슬롯 실발행 — k7 PASS 건 5~6개 예상 발행, 발행 후 라이브 확인 권장
