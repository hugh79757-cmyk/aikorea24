# Phase 31: 블로그 description 추출 버그 수정 — 첫 문장이 아닌 중간 문장 추출되는 버그

## Objective
블로그 포스트 frontmatter `description` 필드에서 본문의 **첫 번째 완전한 문장**을 추출하도록 수정.
현재 `_extract_first_sentence()` 함수가 `max_len - 50` 위치부터 검색하여 **첫 문장이 아닌 중간 문장**을 추출하는 버그 수정.

## Root Cause Analysis
**파일**: `scripts/blog_draft_generator.py` 라인 387
```python
m = _KOR_END_PATTERN.search(text, max_len - 50)  # 위치 250부터 검색 → 첫 문장 건너뜀
```

### 버그 동작 방식
1. 텍스트가 300자 초과 시 `max_len - 50` (위치 250)부터 종결어미 검색 시작
2. 첫 문장(보통 50-150자)은 건너뛰고 **중간 문장의 종결어미**에서 잘라냄
3. 결과: "이러한 배경에서, 구글 딥마인드가 개발한 알파폴드..." (중간 문장) 추출

### 정상 동작해야 할 것
- 텍스트 **처음(위치 0)**부터 첫 번째 한국어 종결어미(`.`, `!`, `?`, `습니다`, `입니다`, `했습니다`, `합니다`, `있습니다`, `였습니다`, `됩니다`, `봅니다`, `듣습니다`, `옵니다`, `갑니다`, `줍니다`, `삽니다`, `팝니다`, `만듭니다`, `생각합니다`, `느낍니다`, `알고 있습니다`, `모릅니다`, `임`, `음`, `이다`, `한다`, `했다`, `요`, `함`) 검색
- 첫 번째 종결어미 위치까지를 첫 문장으로 추출

## Files to Modify
- `scripts/blog_draft_generator.py`
  - `_extract_first_sentence()` 함수 수정 (라인 351-424)

## Plan

### Task 1: 버그 수정 — `_extract_first_sentence()` 로직 변경
- **변경 전**: `max_len - 50`부터 검색 (중간 문장 추출)
- **변경 후**: 위치 0부터 첫 번째 종결어미 검색 (첫 문장 추출)
- 검색 범위를 `text` 전체로 변경 (`_KOR_END_PATTERN.search(text, 0)`)

### Task 2: 안전장치 보강
- 첫 문장이 `max_len`(300자) 초과 시에만 안전장치로 `max_len`에서 자르기
- 첫 문장이 정상적으로 추출되면 길이 제한 없이 종결어미까지 포함

### Task 3: 회귀 방지 테스트 추가
- `scripts/validate_blog_posts.py` 또는 별도 테스트에 description 첫 문장 검증 로직 추가
- 첫 문장이 한국어 종결어미(`.`, `!`, `?`, `다`, `요`, `함`, `습니다`, `입니다`, `했습니다`, `합니다`, `있습니다`, `였습니다`, `됩니다`, `봅니다`, `듣습니다`, `옵니다`, `갑니다`, `줍니다`, `삽니다`, `팝니다`, `만듭니다`, `생각합니다`, `느낍니다`, `알고 있습니다`, `모릅니다`, `임`, `음`, `이다`, `한다`, `했다`, `요`, `함`)로 끝나는지 검증

### Task 4: 기존 포스트 백필 검증
- 이미 수정된 826개 포스트 중 `description`이 첫 문장이 아닌 것들 재수정
- `scripts/backfill_descriptions.py` 재실행으로 수정 사항 반영

## Acceptance Criteria
1. ✅ `_extract_first_sentence()`가 본문 **첫 문장**을 정확히 추출함
2. ✅ 알파폴드 포스트 description: `"유전자 편집 기술은 생명과학 분야에서 혁명적인 도구로 자리 잡았습니다"` (첫 문장)
3. ✅ 모든 포스트 description이 한국어 종결어미로 완결됨
4. ✅ 기존 826개 포스트 재검증 시 0개 truncation
5. ✅ 테스트 통과 (275/277 통과 유지)

## Test Plan
```bash
# 1. 단위 테스트
python3 -c "
from scripts.blog_draft_generator import _extract_first_sentence
body = '## 헤딩\n\n첫 번째 문장입니다. 두 번째 문장입니다.'
result = _extract_first_sentence(body)
assert result == '첫 번째 문장입니다.'
print('PASS:', result)
"

# 2. 알파폴드 포스트 검증
grep -A1 'description:' src/content/blog/2026-07-25-011-알파폴드-ai가-유전자-편집-단백질을-더-안전하게-재설계하는-방법과-미래-전망.md

# 3. 전체 검증
python3 scripts/validate_blog_posts.py
python3 -m pytest tests/ -v --tb=short
```

## Files Changed
| File | Change Type |
|------|-------------|
| `scripts/blog_draft_generator.py` | Bug fix: `_extract_first_sentence()` search from position 0 |
| `scripts/backfill_descriptions.py` | Re-run for re-backfill |
| `scripts/validate_blog_posts.py` | Add first-sentence validation |

## Risks & Mitigations
| Risk | Mitigation |
|------|------------|
| 첫 문장이 300자 초과 시 잘림 | `max_len` 안전장치 유지, 첫 문장이 정상적 길이(100자 내외)면 영향 없음 |
| 마크다운 링크/헤딩 제거 로직 부작용 | 기존 로직 유지, 첫 문장 추출 로직만 변경 |
| 기존 포스트 재수정 시 Git diff 노이즈 | `--commit-dirty=true`로 배포, 변경사항 최소화 |

## Timeline
- Task 1: 10분 (버그 수정)
- Task 2: 5분 (안전장치 검토)
- Task 3: 10분 (테스트 추가)
- Task 4: 10분 (백필 실행)
- Task 5: 5분 (배포 및 검증)

**Total: ~40분**