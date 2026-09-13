# PLAN: thread-quality-eval

## 목적
윈도우(2026-09-12 22:06 ~ 09-13 08:24 KST) 내 생성·발행된 스레드 초안 11건 전문 열람 + jisang 스킬 규격(평어체, 카드당 300자+, 12~15자/줄, 금지어) 기준 품질 평가 → writer LLM별 품질 등급화 → 체인 제외 후보 판정.

## 배경
전 퀵태스크(260913-thread-llm-audit)가 writer-LLM 매핑만 확정. 본 태스크는 실제 텍스트 품질 평가.

## 데이터 소스 (검증됨)
- 초안: `scripts/threads/logs/drafts/` + `drafts/contrast/` (11개 파일 cat으로 전문 확인)
- writer 모델: `scripts/threads/logs/launchd.log` "체인 성공" 라인 (각 초안 저장 직전) + `scripts/pipeline_runner.log`
- 발행 기록: `scripts/threads/posted.json` posted_article_meta
- 체인 설정: `config/models.yaml` (17 tiers + 유료 default)

## 작업
1. 11건 초안 전문 읽기 — 완료
2. jisang 규격 기반 품질 평가 (평어체/카드수/리듬/금지어/할루시네이션)
3. LLM별 등급 → 체인 제외 추천
4. SUMMARY.md 작성 + STATE.md 갱신 + 커밋

## 산출물
- `.planning/quick/260913-thread-quality-eval/SUMMARY.md`
- STATE.md Quick Tasks 테이블 1행 추가
