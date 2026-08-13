---
date: 2026-08-13
type: fix
status: resolved
---

# 6e16127 상태 복원 + 전체 LLM 무료 체인 전환

## What
블로그 발행 파이프라인의 모든 LLM 호출을 `model_router.chat_completion(model_override=None)` 무료 체인으로 통일하고, 코드를 8월 10일 정상 발행 시점(`6e16127`) 코드로 복원.

## Why
- Phase 28-05의 복잡한 프롬프트/검수 게이트가 블로그 발행 저해 (오늘 0건 발행)
- MiMo/GPT-4o-mini/DeepSeek 하드코딩 직접 호출 → 중앙 라우터(model_router)로 통일 필요
- 사용자가 "무료 LLM 체인 교체만 남기고 나머지는 과거로 원복" 요청

## Files changed
- `scripts/blog_draft_generator.py` — 6e16127 복원 (단순 프롬프트 구조, 단순 기사 조립: title+source+description)
- `scripts/auto_briefing.py` — 6e16127 복원 + MiMo 직접 호출 제거 → model_router 무료 체인
- `api_test/news_collector.py` — 6e16127 복원 + GPT-4o-mini 직접 호출 제거 → model_router 무료 체인 + sys.path 수정(PROJECT_DIR 추가)
- `scripts/auto_thumbnail.py` — 6e16127 복원 + DeepSeek 직접 호출 제거 → model_router 무료 체인 + OpenAI import 제거
- `scripts/threads/v3/model_router.py` — GPT-4o-mini 제거 유지, 무료 체인 상태 유지

## How
1. `git checkout 6e16127 --`로 4개 파일 복원
2. 각 파일에서 하드코딩 직접 호출을 `model_router.chat_completion(model_override=None)`으로 교체
   - auto_briefing.py: requests.post(MiMo) → chat_completion(model_override=None)
   - news_collector.py: openai.OpenAI(gpt-4o-mini) → chat_completion(model_override=None), sys.path.insert(0, PROJECT_DIR) 추가
   - auto_thumbnail.py: OpenAI(deepseek.com) → chat_completion(model_override=None), OpenAI import 제거, "DeepSeek 키워드 추출 중..." → "LLM 키워드 추출 중..." 로그 문구 변경
   - blog_draft_generator.py: 6e16127 상태에서 이미 model_router.chat_completion() 사용 중. model_override 미지정 → None으로 무료 체인 동작. 변경 불필요.
   - model_router.py: 무료 체인 유지, GPT-4o-mini 제거 상태 유지
3. 각 파일 구문 검사: python3 -m py_compile
4. 테스트 실행

## Verification
- **translate_to_korean**: Gemini-3.1-flash-lite 무료 체인으로 영문 제목 → 한국어 번역 성공
- **batch_translate**: 202건 번역 성공 (Gemini 무료 체인)
- **auto_briefing.py**: Gemini 무료 체인으로 브리핑 코멘트 생성, 브리핑 D1 저장 성공
- **blog_draft_generator.py**: Gemini 무료 체인으로 블로그 글 2226자 생성, deep_dive_url 연결 성공, 썸네일 생성, 블로그 검증 통과, Cloudflare Pages 배포 성공
- **auto_email_sender.py**: 이메일 발송 성공 (HTTP 201)
- **auto_thumbnail.py**: Gemini 무료 체인으로 키워드 추출 성공 ("machine learning"), Pexels 썸네일 생성 성공
- **전체 파이프라인**: news_collector(번역만) → auto_briefing → blog_draft_generator → auto_email_sender 순차 실행 성공

## Remaining / Known Issues
- **news_collector.py save_to_d1 D1 저장 실패**: wrangler 반환코드 check 방식 문제. INSERT OR IGNORE 중복 시 non-zero exit code → 저장 실패로 처리. 번역(LLM 체인)은 정상 동작하나 저장 단계 실패. pre-existing bug (6e16127 코드에도 존재). 별도 fix 필요.
- **기존 영어 DB title 레코드**: 8/12~13 등 일부 뉴스가 영어 title로 DB에 저장됨 (batch_translate가 과거에 OPENAI_KEY 없음으로 번역 스킵, INSERT OR IGNORE로 갱신 안 됨). news_collector.py 자동 실행(cron/launchd)도 미복원. 별도 UPDATE 스크립트 또는 실행 파이프라인 복원 필요.
- **news_collector.py stdout 버퍼링**: 실행 중 실시간 로그 안 보임. `python3 -u` 옵션 필요.
- **news_collector.py sys.path**: PROJECT_DIR 미포입 시 model_router의 `pipeline.infra` import 실패. sys.path.insert(0, PROJECT_DIR) 추가로 해결.

## commit
5b57349 feat: 6e16127 상태로 복원 + LLM 무료 체인 전환 (5 files, 116 insertions, 697 deletions)
