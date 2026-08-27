# Phase 37 Context — Threads Contrast Writing Pivot

## Goal
기존에 `docs/manual-blog/prompts/01-extractor.md` + `02-curator.md` 로 설계된 대비 구조 7단락 블로그 글쓰기를, 코드로 구현하되 **블로그가 아니라 Threads (5-card Format D) 발행 파이프라인**에 적용. blog_draft_generator.py 신버전 구현 대신 Threads로 pivot.

## Background
- blog_draft_generator.py 839L 현재 버전: 1500자+ 3 H2 프롬프트만 있음, 신버전(대비·교차검증·상위주제·7단락 보도체) 미구현. docs/manual-blog/prompts 2개 파일 2026-08-26 추가됐으나 코드 연결 0, untracked 블로그 6건은 구포맷 유지.
- Threads 파이프라인: pipeline/threads/writer.py Format D (5 cards, --- 구분, 500자/card, ~임/~했음 종결, 빈줄 리듬, 열린 질문 카드5), pipeline/threads/pitch.py + validator + crawler 구조 존재. 기존 threads는 AI 뉴스 기사 1건 기반 짧은 브리핑형.
- 요구 pivot: contrast-writing skill 의 3+매체 교차검증 + 상위주제 배경기사 1건 연결 + 표면/근본 대비 논지 + 7단락 서사를 Threads 제약(5 cards, 500자/card, API limits) 안에 녹이기. 1:1 전체 길이 이식은 불가 → 매핑 필요.

## Scope
- 대상: pipeline/threads/* 확장, 필요시 pipeline/steps/* 오케스트레이션, model_router (무료 체인) 재사용
- 비대상: blog_draft_generator.py 신버전 구현 안 함 (기존 블로그 파이프는 현행 유지 또는 비활성화 판단은 Phase 밖)
- 입력: D1 news DB 기사 + 브리핑 items, 또는 keywords.json (기존 outline_generator 경로 재사용 여부 판단)

## Constraints
- 무료 LLM 폴백 체인 유지 (model_router.py tier_order), 유료 DeepSeek 최후수단만
- 3중 방어 원칙: pitch 생성 / thread 작성 후 / 발행 직전 검증 모두에 prompt-leak + korean + 한자 검사 유지 (validator.py)
- Threads API: 500자/card hard limit, hiragana/katakana 금지 (차단), 5 cards 구조 유지 (또는 대비 서사 매핑 시 기획 결정)
- D1 DRY: d1_client 재사용, 하드코딩 PROJECT_DIR 금지 (pipeline/infra/config.project_root)
- 테스트 회귀 없음: 기존 275 테스트 + Threads 모듈 테스트 green 유지

## Decisions Already Made
- 신버전 글쓰기는 블로그가 아니라 Threads로 구현
- 대비 스토리텔링 7단락을 Threads 5-card에 어떻게 압축/재배치할지, 교차검증 크롤링 소스를 어디서 가져올지는 Phase 설계에서 결정
- docs/manual-blog 2개 프롬프트는 Threads용으로 재해석 (원문 유지하되 카드 제약에 맞게 조정)

## Open Questions for Research
- 7단락 → 5카드 매핑 최선안 (병합 vs 생략 vs 7→5 재구성)
- 교차검증 3매체 크롤링 구현: 기존 crawler.py 재사용 가능? 추가 검색 API 필요?
- 배경기사 연결(상위주제) 검색 키워드 E 활용 시 D1 vs 외부 검색 중 무엇이 현실적?
- 추출기 A-F 구조를 코드 모델로 둘지 프롬프트 체인 2단계로 둘지
- 기존 pitch/narrative_pitcher 와의 중복 제거 (entity overlap dedup) 영향
