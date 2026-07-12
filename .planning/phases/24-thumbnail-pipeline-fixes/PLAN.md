# PLAN.md — Phase 24: Thumbnail Pipeline Fixes

> Generated: 2026-07-12 by Sisyphus
> Research: RESEARCH.md (same dir)

## Goal
썸네일 파이프라인의 4가지 결함(재사용 버그 / 재시도 부재 / 깨진 참조 / repo drift)을
수정하고, 오늘 배포된 5건을 git과 동기화한다.

## Scope
- **In scope**: `auto_thumbnail.py` dedup+retry+placeholder, 호출자 2곳 안전화, drift 커밋, 3건 재생성
- **Out of scope**: 배포 방식(--commit-dirty) 변경, Pexels 대체 소스 추가, OG 이미지 디자인

## Requirements
- REQ-24-1: 동일 Pexels 사진이 연속/반복 선택되지 않아야 함 (dedup 강화)
- REQ-24-2: Pexels/다운로드 네트워크 실패 시 재시도(백오프) 적용
- REQ-24-3: Pexels 전면 실패 시 깨진 참조 대신 의도된 기본 placeholder 사용 (또는 image 필드 생략)
- REQ-24-4: 호출자가 표지 파일 존재를 확인한 뒤에만 `image:` frontmatter 기록
- REQ-24-5: live와 git 불일치 해소 (5 포스트 + 5 썸네일 커밋)
- REQ-24-6: 오늘 재사용 표지 3건 재생성

## Success Criteria
1. 신규 실행에서 동일 md5 썸네일이 반복 생성되지 않음 (단위 테스트/모의 확인)
2. `search_pexels`/`download_image`가 `@retry` 적용 (최소 3회, 지수 백오프)
3. Pexels 전면 실패 시 committed 기본 이미지(`public/images/_default_thumbnail.webp`)를 해당 slug dir에 복사 → `image:` 참조 항상 유효
4. `auto_deep_article.py`/`blog_draft_generator.py`가 파일 존재 시에만 `image:` 기록, 없으면 필드 생략
5. `git status`에서 07-12 포스트 5건 + 썸네일 5개가 추적됨 (커밋 완료)
6. `python -m py_compile` 통과, 기존 블로그 파이프라인 동작 유지
7. 사이트 `https://aikorea24.kr` HTTP 200 유지

## Tasks (Waves)

### Wave 1 — 코드 수정 (병렬 2 agent)
- **T1 (auto_thumbnail.py)**: dedup 강화 + `@retry` + 기본 placeholder
  - `search_pexels`/`download_image`에 `pipeline.infra.retry.retry` 적용
  - dedup: 모든 결과가 used면 `photos[0]` 즉시 재사용 말고, 대체 쿼리(DEEPSEEK_POOL 순환)로 미사용 사진 탐색; 그래도 없으면 명시 로그 후 `photos[0]`
  - 전면 실패 시 committed `public/images/_default_thumbnail.webp`를 `public/images/{slug}/thumbnail.webp`로 복사 후 경로 반환 (깨진 참조 제거)
  - import 경로: 기존 `from pipeline.infra.logger import get_scrubbed_logger` 패턴 유지
- **T2 (호출자 2곳)**: 파일 존재 확인 후 `image:` 기록
  - `auto_deep_article.py:288`, `blog_draft_generator.py:271`
  - `os.path.exists(PUBLIC_IMAGES_DIR / slug / "thumbnail.webp")` 확인 → 있으면 경로 삽입, 없으면 `image:` 필드 생략(또는 기본 placeholder 경로)

### Wave 2 — 동기화 + 재생성
- **T3 (drift 커밋)**: 5 포스트 + 5 썸네일 `git add` + 커밋 (운영, git-master 사용)
- **T4 (3건 재생성)**: 코드 수정 후 `auto_thumbnail.py`로 오늘 재사용 3 slug 재실행 (best-effort, Pexels 가용 시)

## Verification
- [ ] `python -m py_compile scripts/auto_thumbnail.py scripts/auto_deep_article.py scripts/blog_draft_generator.py`
- [ ] dedup 단위 검증: used_ids 모두 차단된 상황에서 대체 쿼리로 미사용 사진 선택되는지 (mock)
- [ ] placeholder 경로: Pexels 실패 모의 시 `_default_thumbnail.webp` 복사본 생성되는지
- [ ] 호출자: 파일 없을 때 `image:` 필드 생략되는지
- [ ] `git status` clean (추적 완료)
- [ ] `curl -s -o /dev/null -w "%{http_code}" https://aikorea24.kr` == 200

## Risks
- Pexels API 할당량/키 만료 시 T4 재생성 실패 → placeholder로 대체됨(깨진 참조 아님)
- `_default_thumbnail.webp` 신규 커밋 필요 (gitignore 대상 아님)
