# Quick: Threads 할루시네이션 발행 게이트 보강

## 문제
할루시네이션/오염 카드 발행 급증 (사용자 수동 삭제 4건+). 발행된 3건(50155/50016/50269) 파열 어미 포함.

## 원인 (코드 열람으로 검증)
1. `main_v3.py::validate_final_cards` (v3+kicker7 공용 발행 게이트) 결함 3종:
   - CJK(한자/일본어) 혼입 체크 없음 → "大学和" 통과
   - LLM 거부문("죄송합니다...") 체크 없음 → 거부문이 초안으로 저장
   - KR_COMPLETE_ENDINGS에 "임" 포함 → "한다임" 끝자 "임"=합법 종결로 판정
2. `kicker7_writer.py::write_kicker7_thread` 생성 시점 검증 0개 (contrast_writer는 풀체인 검증)
3. kicker7-publisher unload 상태 → k7 대기 43개 오염 가능 채로 적체

## 수정 (additive, non-destructive)
- [x] validate_final_cards에 3종 체크 추가 (기존 시그니처/반환 불변)
- [x] write_kicker7_thread에 생성 직후 검증 추가 (실패 시 None 반환 = 기존 실패 경로)
- [x] k7 백로그 재검증 — 오염 hold 이동
- [x] 게이트 테스트 작성
- [x] kicker7-publisher 재개
- [x] STATE.md 갱신 + 커밋

## 게이트 상세
validate_final_cards 신규 검사 (기존 검사 전부 유지):
1. CJK: NFKC 정규화 후 한자[\u4e00-\u9fff]/일본어[あ-ん ァ-ヶ] 발견 시 issue
2. LLM 거부문: "죄송합니다", "죄송하지만", "충족할 수 없", "요청하신", "cannot fulfill", "I'm sorry", "I cannot" 발견 시 issue
3. 파열 어미: 카드 마지막 줄 끝이 "한다임/왔다임/있다임/이다임/다임" 류 + "이이", "이이이" 연쇄 → issue. "임" 단독 종결은 유지 (정상 평어체 "~임" 보존 — 기존 green 테스트 보호)

파열 판정: 끝 2~5자가 `^[가-힣]다임$|^[가-힣](이|으|왔|했|한다)이{1,3}$` 패턴 = 파열. 정상 "~임"(2자 이상 어간+임)은 통과.
