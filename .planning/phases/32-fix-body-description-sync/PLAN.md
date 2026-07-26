# Phase 32: 본문 도입단락-디스크립션 싱크 및 어미 절단 버그 수정

## Objective
블로그 포스트에서 **본문 도입단락(타이틀과 첫 H2 사이의 첫 단락)**과 **프론트메터 `description`**이 동일한 텍스트로 싱크되어 있으며, 둘 다 어미가 잘리는 버그를 수정.

## Root Cause Analysis

### 두 가지 복합 원인

| 원인 | 위치 | 현상 |
|------|------|------|
| **원인 1: Description 추출 버그** | `_extract_first_sentence()` 라인 387 | `max_len - 50`(위치 250)부터 검색하여 첫 문장 건너뛰고 중간 문장 추출 |
| **원인 2: 템플릿 중복 렌더링** | `src/pages/blog/[...id].astro` 라인 86-88 | `description`을 리드 단락으로 렌더링 + `<Content />`로 본문도 렌더링 → **동일 텍스트 중복 출력** |

### 실제 증상 (알파폴드 포스트 2026-07-25-011)

| 위치 | 현재 값 | 문제 |
|------|---------|------|
| Frontmatter `description` | "이러한 배경에서, 구글 딥마인드가 개발한 알파폴드 AlphaFold 인공지능이 새로운 해결책을 제시하고 있습니다" | **본문 2번째 문장**에서 추출됨 (버그) |
| 본문 첫 단락 | "유전자 편집 기술은 생명과학 분야에서 혁명적인 도구로 자리 잡았습니다..." | 정상 완결 |
| 템플릿 렌더링 | `<p>{description}</p>` + `<Content />` | **동일 텍스트 중복 출력** |

---

## Fix Plan

### Task 1: `_extract_first_sentence()` 검색 위치 0으로 변경 (완료됨 - Phase 31)
- [x] `max_len - 50` → `0` 변경으로 첫 문장부터 검색

### Task 2: 템플릿에서 리드 단락 렌더링 제거
- **파일**: `src/pages/blog/[...id].astro`
- **변경**: 라인 86-88 제거 (`<p>{post.data.description}</p>`)
- **이유**: 본문에 이미 도입 단락이 있음 → 중복 제거

### Task 3: SEOHead는 그대로 유지 (SEO 메타태그용)
- `description`은 `meta name="description"`, `og:description`, `twitter:description`, `schema.org description` 용도로만 사용
- 본문 렌더링에는 영향 없음

### Task 4: 기존 포스트 백필 재실행
- 수정된 `_extract_first_sentence()`로 826개 포스트 description 재생성

### Task 5: 검증 및 배포

---

## Acceptance Criteria

| 검증 항목 | 기준 |
|-----------|------|
| 알파폴드 포스트 description | "유전자 편집 기술은 생명과학 분야에서 혁명적인 도구로 자리 잡았습니다" (첫 문장) |
| 본문 첫 단락 | description과 동일 텍스트 (싱크됨) |
| 어미 절단 | 0건 (모든 description이 종결어미로 완결) |
| 중복 렌더링 | 0건 (리드 단락 제거로 중복 제거) |
| 테스트 통과 | 275/277 통과 유지 |

---

## Files to Modify

| 파일 | 변경 내용 |
|------|-----------|
| `src/pages/blog/[...id].astro` | 라인 86-88 리드 단락 렌더링 제거 |
| `scripts/blog_draft_generator.py` | `_extract_first_sentence()` 검색 위치 0 (이미 완료) |
| `scripts/backfill_descriptions.py` | 재실행으로 826개 포스트 재생성 |

---

## Risk Assessment

| 위험 | 완화 방안 |
|------|-----------|
| 리드 단락 제거로 디자인 변경 | 디자인은 기존 본문 첫 단락으로 자연스럽게 대체됨 |
| 기존 포스트 description 재생성 시 git diff 노이즈 | `--commit-dirty=true`로 일괄 커밋 |
| SEO meta 태그 누락 | `SEOHead`에서 `description` 프롭 계속 사용 → 안전 |

---

## Test Plan

```bash
# 1. 단위 테스트: 첫 문장 추출 검증
python3 -c "
from blog_draft_generator import _extract_first_sentence
body = '## 헤딩\n\n첫 번째 문장입니다. 두 번째 문장입니다.'
result = _extract_first_sentence(body)
assert result == '첫 번째 문장입니다.'
"

# 2. 알파폴드 포스트 검증
grep -A1 'description:' src/content/blog/2026-07-25-011-알파폴드-ai가-유전자-편집-단백질을-더-안전하게-재설계하는-방법과-미래-전망.md

# 3. 백필 실행
python3 scripts/backfill_descriptions.py --apply

# 4. 전체 검증
python3 scripts/validate_blog_posts.py
python3 -m pytest tests/ -v --tb=short
```

---

## Next Steps

1. `src/pages/blog/[...id].astro` 라인 86-88 제거
2. `scripts/backfill_descriptions.py --apply` 실행
3. `npm run build` → `wrangler pages deploy`
4. 라이브 사이트에서 알파폴드 포스트 확인