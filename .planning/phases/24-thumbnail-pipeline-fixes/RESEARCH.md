# RESEARCH.md — Phase 24: Thumbnail Pipeline Fixes

> Generated: 2026-07-12 by Sisyphus (resume-work investigation → plan)

## 문제 출처
`/gsd-resume-work` 세션 중 07-12 블로그 산출물(포스트 5건 + 썸네일 5개) 발견 →
배포 구조(`wrangler pages deploy --commit-dirty=true`) 및 썸네일 생성 로직(`auto_thumbnail.py`) 조사.

## 발견 사항 (Evidence)

### R1. 배포는 git push 자동배포가 아님 (drift 원인)
- `scripts/deploy.sh` 실제 배포: `npx wrangler pages deploy dist --project-name aikorea24 --branch main --commit-dirty=true`
- `--commit-dirty=true` → git 커밋/푸시 없이 로컬 빌드 직접 업로드
- 확인: `https://aikorea24.kr/blog/2026-07-12-a-i-로부터-...` → **HTTP 200** (커밋 안 됐는데 라이브)
- 결과: Cloudflare(live)에는 있으나 git(repo)에는 없는 파일 발생 → clean clone 재배포 시 증발 위험

### R2. Dedup 재사용 버그 (같은 표지 20+회)
- `auto_thumbnail.py:195-204`:
  ```python
  for photo in photos:
      if pid not in used_ids: chosen = photo; break
  if not chosen:
      chosen = photos[0]   # "모든 결과 사용됨 → 첫번째 재사용"
  ```
- `search_pexels("artificial intelligence")` 폴백이 항상 동일 #1 사진 반환 → dedup 놓치면 `photos[0]`로 매번 동일 사진 선택
- 증거: `find public/images -name thumbnail.webp -size 27958c` → **20+개가 동일 md5 `e7528de1...`**
- `config/pexels_used_ids.json`에 215개 id 있음(gitignore됨)에도 불구하고 재사용 → dedup 경로 미작동

### R3. 네트워크 재시도 없음
- `search_pexels()` (118-136): 예외 시 `return []` 즉시 포기
- `download_image()` (139-147): 예외 시 `return None` 즉시 포기
- 백오프/재시도 0회. 타임아웃 15s 실패 시 그 단계 포기
- `pipeline/infra/retry.py`에 `@retry(max_retries=3, delay=1.0, backoff=2.0)` 존재 → 미사용

### R4. 진짜 fallback placeholder 부재 → 깨진 참조
- `process_thumbnail()`가 Pexels 전면 실패 시 `return None` (표지 파일 미생성)
- 그런데 호출자들이 파일 존재 여부와 무관하게 frontmatter를 하드코딩:
  - `auto_deep_article.py:288` `thumbnail_path = f"/images/{slug}/thumbnail.webp"` → `inject_frontmatter_image()` 무조건 삽입
  - `blog_draft_generator.py:271` 동일하게 하드코딩
- 즉 Pexels 실패 → `image:` 필드가 존재하지 않는 파일을 가리킴 → 빈/깨진 썸네일

### R5. 오늘(07-12) 3건이 재사용 표지
- `e7528de1...` (27958B) 가 오늘 포스트 3건에서 확인 (오픈ai-gpt-5-6, a-i-로부터-안전한, 호주-저작권법)
- 2건(변동성이-큰, chatgpt가-가정으로)은 고유 Pexels 이미지 (정상)

## 호출 체인
```
run_pipeline.py:step_thumbnails(articles)   # 126
  → auto_thumbnail.process_thumbnail(url, slug, title, description)  # 145
      ↳ DeepSeek 키워드 → Pexels 검색 → 다운로드 → create_thumbnail()
      ↳ 실패 시 None 반환
  → rel_path 기록 (None 가능)
auto_deep_article.py:288  → 무조건 image: "/images/{slug}/thumbnail.webp" 삽입
blog_draft_generator.py:271 → 동일 하드코딩
```

## 관련 파일
| 파일 | 역할 |
|------|------|
| `scripts/auto_thumbnail.py` | Pexels 썸네일 생성 (수정 대상 R2/R3/R4) |
| `scripts/run_pipeline.py` | step_thumbnails (126-148) 오케스트레이션 |
| `scripts/auto_deep_article.py` | 블로그 생성 + image frontmatter (271/288, R4) |
| `scripts/blog_draft_generator.py` | 블로그 초안 + image frontmatter (271, R4) |
| `pipeline/infra/retry.py` | @retry 데코레이터 (R3에 재사용) |
| `config/pexels_used_ids.json` | used id 추적 (gitignore, R2) |
| `public/images/news-keyword-og.webp` | 기존 OG 기본 이미지 (R4 placeholder 후보) |
