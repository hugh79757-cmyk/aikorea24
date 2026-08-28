---
date: 2026-08-28
type: fix
status: resolved
---

# Placeholder 사본이 OG 이미지로 노출되는 사고 + 기본 이미지 교체

## What
aikorea24.kr 블로그 발행 시 썸네일이 Pexels fallback placeholder(`news-keyword-og.webp`)의 사본으로 채워져, 결과적으로 "다른 프로젝트의 OG 이미지"로 보이는 사고. 8/27 발행 글(`2026-08-27-010-...`) 포함 2~3일 반복.

## Why
- Pexels/DeepSeek 키워드 추출 실패 → `process_thumbnail`의 폴백 체인 전부 소진 → `_use_default_thumbnail()`이 placeholder `news-keyword-og.webp`를 `{slug}/thumbnail.webp`로 복사
- 800x800 WebP, ≥15KB 품질 게이트는 통과 → 배포 차단 안 됨
- placeholder 자체가 옛 OG 기본 이미지(45670 bytes, MD5 `1de327e036fb85cd0c9a1e4fa0dd7c4a`)라, 카드뉴스/OG로 보임
- 2중 문제: (1) placeholder가 OG 의미의 이미지를 재활용, (2) placeholder 사본 검출 로직 없음

## Files changed
- `public/images/news-keyword-og.webp` — 교체 (1024x1024 JPEG → 800x800 WebP 42008 bytes, MD5 `1d5b76e3eb85e47ee01a903f0d628814`)
- `public/images/news-keyword-og.webp.bak` — 옛 파일 백업
- `scripts/auto_thumbnail.py` — `is_placeholder_copy()` 헬퍼 추가 (lazy MD5 캐시, placeholder 교체 시 프로세스 재시작 필요)
- `scripts/blog_draft_generator.py`:
  - import에 `is_placeholder_copy` 추가
  - `_add_image_to_frontmatter()`: placeholder 사본이면 `image:` 필드 주입 안 함 + 로그
  - `[5b]` 품질 게이트: placeholder 사본은 "이슈"로 카운트 (image 필드 생략됨 명시), `quality_passed`엔 포함 안 됨

## How
- placeholder를 의미중립적인 이미지로 교체 → 새 fallback 사본도 새 MD5로 변경됨
- 코드 가드: `_add_image_to_frontmatter` 진입 시 MD5 비교로 placeholder 사본이면 `image:` 필드 안 씀 → og:image 비움, SEO 메타 없음 상태로 노출
- 품질 게이트에 placeholder 검출 추가 → 텔레그램 알림에 이슈로 노출, 일부만 placeholder면 배포 진행

## Verification
- `md5 news-keyword-og.webp` = `1d5b76e3eb85e47ee01a903f0d628814` (옛 `1de327e0...`와 다름)
- 변환 결과: 800x800 WebP, 42008 bytes (≥15KB 통과)
- `python3 -c "from auto_thumbnail import is_placeholder_copy; print(is_placeholder_copy('public/images/news-keyword-og.webp'))"` → True
- 옛 placeholder 사본(8/27 010번) → False (MD5 다름, 정상 — 자동 갱신되진 않음)
- `py_compile` syntax OK (양쪽 파일)
- 다음 `wrangler pages deploy` 시 R2에 새 placeholder 업로드됨

## 잔존 위험
- 옛 placeholder 사본 thumbnail.webp 4건은 디스크에 그대로 (gitignore). md에서 `image:` 필드 제거했으므로 HTML/og:image 참조는 끊김. 다음 wrangler 배포 시 R2에 자연 덮어쓰기 됨 (dead object 일시 잔존 가능, 비용/혼동 미미).
- `_PLACEHOLDER_MD5_CACHE`가 프로세스 단위 캐시 → placeholder 파일 교체 후 같은 프로세스에서 재실행 시 stale MD5 반환. launchd 환경에선 매 실행 새 프로세스라 무관.
- `news-keyword-og.webp.backup` / `.bak` 파일 — 정리 완료 (삭제됨).

## 후속 정리 (2026-08-28 같은 세션)
- 옛 MD5(`1de327e0...`) 사본 4건 식별: 8/21-007, 8/24-002, 8/25-011, 8/27-010
- 각 md의 `image:` 필드 제거 완료 (re.subn, multiline, count=1)
- 백업 파일 `.backup` / `.bak` 삭제 완료
- 파일 자체는 자연 덮어쓰기 위해 디스크에 유지
