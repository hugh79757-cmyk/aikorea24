---
date: 2026-09-17
type: fix
status: resolved
---

# 크롤 본문 최소길이 게이트 — 크롤 실패 시 발행 중단

## What

네이버 스포츠 봇차단으로 15자짜리 껍데기만 크롤된 상태에서 발행 → 얇은 카드 +
죽은 링크가 쓰레드에 나감. 크롤 본문이 부족하면 발행을 중단하도록 게이트 추가.

## Why

2026-09-17 12:04 발행분 (국방AI) 확인:
- 카드 2~3이 거의 빈 상태 (09-01 초안과 대조 시 고유명사·수치 부재)
- 링크 답글의 원문 URL이 죽은 링크 — `curl` 결과 HTTP 200이지만 title
  `네이버 스포츠`, 본문 0자 (봇차단 셸)

원인 체인: 네이버 봇차단 → 15자 크롤 → 재생성 성공 판정 → 얇은 카드 발행.
기존 코드는 `if not crawled_body:` 만 검사 → 15자는 truthy라서 통과했음.
크롤 실패 시 `return ([top], set())` 로 D1 description 기반 원 피치를 발행하는
폴백이 있어, 데이터 없이 LLM이 할루시네이션으로 카드를 채울 여지가 있었음.

## Files changed

- `pipeline/threads/pitch.py` — `MIN_CRAWL_CHARS = 500` 상수, 게이트 조건 변경

## How

```python
if not crawled_body or len(crawled_body) < MIN_CRAWL_CHARS:
    _log(f'  🚫 크롤링 본문 부족({len(crawled_body or "")}자) → 발행 중단 (기사 {article_id_str})')
    return ([], {article_id_str} if article_id_str else set())
```

- 기존 D1 description 폴백 발행 삭제.
- 실패 기사 ID를 반환 세트에 넣어 실패 이력에 등록 → 재시도 방지.
- 정상 크롤 ~2700~6500자, 봇차단 껍데기 ~15자 → 500자 기준은 안전 마진.

## Verification

- `python3 -m py_compile pipeline/threads/pitch.py` OK.
- `pytest tests/test_write_thread_validation.py` 10/11 — 실패 1건
  (`test_hook_entity_quote_marked_accepted`)은 수정 stash 후에도 동일 실패 =
  baseline, 본 수정 무관.
- 실동작: 다음 실행 로그에서 `🚫 제외: N개 기사 (크롤링 실패 이력)` 확인
  (게이트가 실패 이력에 등록하는 경로).
- 커밋: `00405c84`

## 잔존 위험

- 크롤은 성공했지만 LLM 재생성 실패 시 D1 기반 원 피치로 폴백하는 경로는
  그대로 남아 있음 (별도 판단 필요).
