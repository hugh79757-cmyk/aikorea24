---
date: 2026-09-17
type: fix
status: resolved
---

# 쓰레드 발행 실패 3대 원인 수정 (JSON 파싱 / 자기해설 누수 / 고유명사 오탐)

## What

쓰레드 발행이 일 12건 → 4~6건으로 급감. 원인 3개를 찾아 전부 수정.

## Why

8일치 로그 집계 (2026-09-10~17):

| 원인 | 건수 |
|---|---|
| `JSON/델리미터 파싱 실패 — 카드 생성 불가` | **124** |
| `카드 수 부족: 0개 (최소 5개 필요)` | 58 |
| `카드 구조 검증 실패` | 51 |
| `모든 기사가 제외됨 (크롤링 실패 이력)` | 41 |
| `Hook 고유명사(X)가 본문 카드에 없음` | 26 |

1. **JSON 파싱 실패 (최대 원인)** — LLM이 JSON 문자열 안에 날것의 개행(`\n`)을
   넣어서 `json.loads` strict 모드가 거부. 응답 내용 자체는 정상·고밀도였는데
   파서가 버리고 있었음. 원본 응답 덤프(`raw_parse_fail/`)로 확인.
2. **모델 자기해설 누수** — 카드 끝에 `카드는 여운을 남기는 마무리입니다.`,
   `발행되면 안 됩니다.` 같은 프롬프트 해설이 붙어 카드5가 9자로 잘리거나
   종결 검증 실패. `MODEL_MESSAGE_PATTERNS`가 전부 `^` 앵커라 카드 끝 누수를
   못 잡았음.
3. **Hook 고유명사 오탐** — 훅의 `OpenAI` vs 본문의 `오픈AI` (한국어 음차 표기)
   때문에 "사실 오류 가능"으로 26건 오탐 폐기. `GPT` 11건이 최다.

## Files changed

- `pipeline/threads/writer.py` — `json.loads(strict=False)`, `MODEL_SELF_COMMENTARY_PATTERNS`,
  raw dump, `validate_final_output(cards, article_body_text)`
- `pipeline/threads/validator.py` — `validate_final_output(cards, source_text=None)`,
  `_validate_hook_body_entity_consistency(cards, source_text=None)` 원문 대조 허용

## How

1. `json.loads(text, strict=False)` — 문자열 내 제어문자(개행/탭) 허용.
   파싱 실패 시 원본을 `scripts/threads/logs/raw_parse_fail/`에 덤프.
2. 파싱 직후 `_cleanup_source_attribution()`에서 자기해설 라인 제거
   (5개 regex: `여운을\s+남기는\s+마무리`, `카드입니다`, `발행되면\s+안\s+됩니다`,
   `검증\s+단계에서\s+걸러`, `걸러져야\s+합니다`).
3. `validate_final_output`에 optional `source_text` 추가 — 크롤링 원문에 실재하는
   엔티티면 음차 표기로 간주해 통과. 원문에도 없으면 여전히 차단
   (할루시네이션 방어 유지). 기존 호출부는 하위 호환.

## Verification

- 단위: 3케이스 assert 검증 — source 없음=차단 / source에 있음=허용 /
  할루시네이션 엔티티(`Wrtn`)=차단.
- 회귀: `pytest tests/` 472 passed / 17 failed. 실패 17건 전부 baseline 동일
  (`git stash` 후 재실행 → `comm -13` 신규 실패 0건).
- E2E: dry-run 5카드 생성 성공 → 실발행 성공 (루트 ID `18049321997805293`,
  카드 5/5 + 링크 답글). 발행 카드에 수치 5개 (220명 감축 / 페이지뷰 46% /
  주가 90% / 매출 1억 2890만 파운드 / 구독자 7만 5천 명) — 저밀도 아님.
- 커밋: `fbf2367f`

## 잔존 위험

- `contrast_writer.py:468`은 `source_text` 없이 기존 동작 유지 — 8카드
  contrast 포맷은 동일 오탐 잠재.
- 파서 4단계 폴백 중 델리미터 경로는 미수정.
