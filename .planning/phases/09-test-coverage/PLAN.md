# Phase 9: Test Coverage Expansion

## Goal
writers.py, crawler.py, pitch.py 핵심 함수 커버리지 확장 + integration 테스트 신규 → 206개 → 224개 (+18)

## Scope

### Task 1: writer.py 테스트 확장 (+6)
- `test_load_style_examples()` — 파일 존재/부재 시 폴백
- `test_build_system_prompt_D()` — 프롬프트 포함 키워드 검증
- `test_write_thread_success()` — 정상 쓰레드 생성 (mock LLM)
- `test_write_thread_validation_fail()` — 검증 실패 시 재시도
- `test_humanize_cards_preserves_count()` — 원본 카드 수 유지
- `test_assemble_final_without_url()` — URL 없을 때 원본 반환

### Task 2: crawler.py 테스트 확장 (+3)
- `test_log_failed_crawl_writes_file()` — 실패 기록 파일 쓰기
- `test_fetch_article_body_timeout()` — 타임아웃 시 빈 문자열 반환
- `test_fetch_article_body_empty()` — 빈 응답 시 빈 문자열 반환

### Task 3: pitch.py 테스트 확장 (+4)
- `test_parse_top_pitch_returns_first()` — 첫 번째 피치 반환
- `test_parse_top_pitch_empty_list()` — 빈 리스트 시 None 반환
- `test_regenerate_pitch_success()` — 재생성 성공 케이스
- `test_regenerate_pitch_failure()` — 재생성 실패 시 None 반환

### Task 4: integration 테스트 신규 (+5)
- `test_validate_final_output_with_real_cards()` — 실제 카드 샘플 검증
- `test_detect_and_clean_leak_pipeline()` — 탐지→삭제 파이프라인
- `test_writer_validation_chain()` — write_thread 검증 체인
- `test_pitch_to_writer_flow()` — 피치→쓰레드 전체 흐름
- `test_multiple_defense_layers()` — 다중 방어 레이어 테스트

## Success Criteria
- 224개 테스트 수집
- 223+ 통과 (기존 1 pre-existing 실패 유지)
- 커밋: "test: Phase 9 — test coverage expansion (+18)"
