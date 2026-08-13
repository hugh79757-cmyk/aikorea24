---
date: 2026-08-09
type: diagnostic
status: resolved
---

# Vectorize dedup + threads JSON 파싱 + 프롬프트 릭 방어 — 진단/현황 기록

## What
Phase 13~15에서 정리된 threads 파이프라인 동작 방식과 현재 인베딩/인제스트 현황을 정리.
특히 `---` 구분자를 LLM에게 맡겼을 때 발생하는 카드 분리 실패와 프롬프트 릭 문제를
JSON-first 파싱으로 이전한 배경과 결과를 기록.

## Why
새 프로젝트/맥락 파악을 위해 현재 aikorea24 쓰레드 파이프라인이 "LLM이 `---`를
못 만들어서 프롬프트 릭이 발생"하는 문제를 어떻게 해결했는지 확인 필요.
Phase 13(`\n\n\n` 시도 후 실패) → Phase 14(JSON-first 전환) 흐름 및
Phase 15(Vectorize dedup + D1 save loss fix + fallback 복구)가 함께 동작하는
구조를 한눈에 볼 수 있게 기록.

## Files changed
- `pipeline/threads/writer.py`
- `scripts/threads/publisher.py`
- `pipeline/infra/vectorize_client.py`
- `scripts/threads/migrate_to_vectorize.py`
- `scripts/threads/main_v3.py`
- `pipeline/threads/crawler.py`
- `.planning/STATE.md`
- `.planning/ROADMAP.md`
- `.planning/triage/INDEX.md`

## How
1. **카드 구분 문제**: Phase 13에서 `---` → `\n\n\n` 전환을 시도했으나 카드 수 불일치로
   실패, `---` 복원 거부. Phase 14에서 JSON-first 파싱으로 전환.
   - `build_system_prompt_D()`에 JSON 출력 형식 명시 (`{"cards":[...]}`)
   - `write_thread()`에서 `response_format=json_schema` 전달해 API 수준 JSON 강제
   - `parse_cards_json_first()`로 JSON 우선 파싱 + 구분자 파싱 폴백 유지
2. **프롬프트 릭 방어**: `writer.py` `_strip_instruction_leak()`에서
   `- --- 구분자 정확히 유지` 같은 지시문 누출 줄을 제거.
3. **인베딩/중복제거**: `pipeline/infra/vectorize_client.py`가
   OpenAI `text-embedding-3-small`(1536d) 임베딩 → Cloudflare Vectorize
   `aikorea24-dedup` 인덱스 upsert. 유사도 임계 0.60.
   - `is_duplicate_with_vectorize()`가 제목+설명 임베딩으로 top_k=5 조회 후
     임계 이상이면 중복 제외.
   - `migrate_to_vectorize.py`로 기존 posted_article_meta 283건 일괄 마이그레이션.
4. **인제스트 흐름**: 크롤링(`crawler.py`, 2회 재시도, failed_crawls.json 24h TTL)
   → D1 저장(link 전범위 중복 체크) → posted.json 메타 관리 → 피치 생성 →
   쓰레드 작성(JSON 파싱) → Vectorize 인덱싱 → Threads API 발행.
5. **방어/안정화**: failed_articles.py 영구 실패 추적, batch_size=5 축소,
   DeepSeek → GPT-4o-mini 순차 fallback, `add_line_spacing()`의 `\n\n` 리터럴 방어.

## Verification
- Phase 14 이후 292/292 테스트 통과, E2E dry-run 성공.
- Phase 15 이후 2회 연속 dry-run 성공(6카드) + 실제 발행 성공 기록.
- Vectorize 인덱싱은 dry-run/실제 발행 후 자동 upsert, 실패해도 파이프라인 차단 없음.
- `.planning/STATE.md` Phase 13/14/15 섹션 + `.planning/ROADMAP.md`에 경로/결정 기록됨.
