# Phase 28 Research: Thumbnail Pipeline DeepSeek Fix & Enhancement

## Problem Statement
**2026-07-25 발생**: 6개 블로그 포스트 중 5개(002~006번)가 **동일한 썸네일 이미지** 사용 (MD5: `8c93b87916afb3bc1e227bdda928b569`)

## Root Cause Analysis

### Code Path
```
blog_draft_generator.py:main()
  → generate_draft() × 6 articles
  → save_draft() → process_thumbnail() × 6
    → auto_thumbnail.py:process_thumbnail()
      → _extract_deepseek_keyword() → DeepSeek API 호출
      → search_pexels() → Pexels API 검색
      → _pick_unused_photo() → 미사용 사진 선택
      → (실패 시) 대체 쿼리 재시도
      → (최종 실패) photos[0] 재사용  ← **BUG HERE**
```

### Failure Sequence (7/25)
1. **DeepSeek API 5회 실패** (rate limit / timeout / network)
2. `_extract_deepseek_keyword()` 예외 → fallback: `"abstract technology"` (고정값, 라인 182)
3. `search_pexels("abstract technology")` → 결과 15개, **모두 used_ids에 이미 존재**
4. `_pick_unused_photo()` → `None` 반환
5. **대체 쿼리 루프** (라인 196-200): `DEEPSEEK_POOL[:3]` = `["abstract technology", "artificial intelligence", "big data"]`
   - 첫 번째가 원본과 동일 → 동일 결과
   - 나머지 두 개도 상위 결과는 이미 사용됨
6. **최종 폴백** (라인 202-205):
   ```python
   if not chosen:
       if photos:          # photos는 원본 검색 결과
           chosen = photos[0]  # 🐛 항상 첫 번째 사진 재사용!
   ```
7. 5개 기사 모두 동일한 `photos[0]` (Pexels ID 동일) 선택 → **동일 썸네일 생성**

### Why Article 001 Was Different?
- 001번 기사는 DeepSeek API **성공** → 고유 키워드 추출 → 고유 사진 선택
- 002~006번은 DeepSeek **실패** → 고정 fallback → 동일 경로 → 동일 결과

## Historical Context

### Thumbnail Pipeline Evolution
| Date | Commit | Change |
|------|--------|--------|
| 7/01 | 295f67d | og:image 추출 → **Pexels + DeepSeek** 전면 교체 |
| 7/12 | b49a09b | dedup 재사용 버그 수정, `@retry` 추가, placeholder 폴백 |
| 7/15 | 543c703 | blog_draft_generator에 Pexels 썸네일 통합 (auto_thumbnail 비활성화→내부 통합) |
| 7/20 | 080ea26 | `@retry` 데코레이터 제거 (불필요한 중복 호출) |

### Key Design Decisions (b49a09b)
- **사용된 사진 추적**: `config/pexels_used_ids.json` (현재 338개 ID 누적)
- **대체 쿼리**: `DEEPSEEK_POOL` 50개 중 상위 3개만 사용
- **Placeholder**: `public/images/news-keyword-og.webp` 복사 (깨진 참조 방지)
- **페이지네이션**: 미구현 (페이지당 15개, 1페이지만)

## Current State Assessment

### Used IDs Status
- **Total tracked**: 338 Pexels photo IDs
- **Pool size**: 50 keywords in `DEEPSEEK_POOL`
- **Per keyword results**: ~15 photos × 1 page = 15 candidates
- **Exhaustion risk**: HIGH — 338 used / (50 × 15) = 45% coverage, but popular keywords ("abstract technology", "artificial intelligence") heavily used

### DeepSeek API Reliability
- **Model**: `deepseek-chat` (via OpenAI-compatible endpoint)
- **Failure modes observed**: Rate limiting (429), Timeout, Network errors
- **No retry logic** in `_extract_deepseek_keyword()` (unlike Pexels search/download)
- **Temperature**: 0.3, **Max tokens**: 20 — very constrained

### Gaps Identified
1. **No retry for DeepSeek** — single attempt, immediate fallback
2. **Fixed fallback keyword** — eliminates diversity when API fails
3. **No pagination** — only page 1 searched, misses unused photos on pages 2+
4. **Alt queries include original** — wasted API calls
5. **Final fallback reuses photos[0]** — defeats dedup purpose
6. **No logging of decision path** — hard to debug production issues

## Proposed Solution Architecture

### Layer 1: DeepSeek Resilience (28-01)
- Add retry with exponential backoff to `_extract_deepseek_keyword()`
- On total failure: random choice from `DEEPSEEK_POOL` (not fixed string)
- Log: `deepseek_attempt=N keyword=X fallback=random`

### Layer 2: Pexels Search Breadth (28-01)
- `search_pexels(query, max_pages=3)` — iterate pages 1-3
- Accumulate all photos before dedup filtering
- Log: `keyword=X pages=Y total_candidates=N`

### Layer 3: Alternative Query Strategy (28-01)
- Exclude primary keyword from alt queries
- Apply same pagination to each alt query
- Stop early if unused photo found

### Layer 4: Safe Final Fallback (28-01)
- Replace `photos[0]` reuse → `_use_default_thumbnail(slug)`
- Placeholder is single committed file, no dedup conflict
- Log: `fallback=placeholder reason=all_exhausted`

### Layer 5: Observability (28-01 + 28-04)
- Structured logging at each decision point
- Phase 28-04: Telegram alert if duplicate thumbnail detected in batch

## Related Issues for Future Phases

### Phase 28-02: Generation-Time Validation Gate
- In `blog_draft_generator.py`: after all thumbnails generated, check for duplicates
- MD5 hash comparison across batch
- If duplicates: regenerate with forced different keywords / retry

### Phase 28-03: Image Quality Validation
- File size check (>10KB, <500KB)
- Dimensions check (800×800 WebP)
- Valid WebP header verification
- Corrupt file detection

### Phase 28-04: Monitoring & Alerts
- Telegram notification on batch duplicate detection
- Daily summary of thumbnail generation stats
- Used ID pool growth tracking

## References
- `scripts/auto_thumbnail.py` (current implementation)
- `scripts/blog_draft_generator.py` (caller, lines 432-442)
- `config/pexels_used_ids.json` (338 tracked IDs)
- `public/images/news-keyword-og.webp` (placeholder source)
- CHANGES.md entries: 2026-07-12 (b49a09b), 2026-07-15 (543c703)
- Triage: `.planning/triage/20260714--auto-thumbnail-deactivation.md`