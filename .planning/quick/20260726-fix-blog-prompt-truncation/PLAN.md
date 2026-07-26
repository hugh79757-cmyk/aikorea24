# Quick Task: Fix Blog Prompt Truncation / Incomplete Sentences

## Description
블로그 글 생성 시 frontmatter `description` 필드가 250자 하드컷으로 잘려서 문장이 중간에 끊김. 예: "사서들이 중심이 된 이 워크숍의 배경에는 디"에서 중단. 본문은 정상인데 description만 잘림.

## Root Cause
`scripts/blog_draft_generator.py`의 `_save_file()` 함수 (라인 321-324):
```python
desc_raw = re.sub(r"^##?\s*(서론|들어가며|시작하며|개요)\s*[:：]?\s*", "", content)
desc_raw = re.sub(r"[#*>\n\s]+", " ", desc_raw)[:250].strip()  # 250자 하드컷
```
- 250자 딱 자르기 → 문장/단어 중간에서 잘림
- 한국어 종결어미(~다/~요/~함/~습니다 등) 고려 안 함

## Fix Plan
1. `_save_file()`에서 description 추출 시 문장 단위로 자르도록 수정
2. 한국어 종결어미 패턴(~다, ~요, ~함, ~습니다, ~입니다, ~했습니다, ~임, ~음, ~? 등) 기준으로 자르기
3. 마지막 문장이 완결되지 않으면 이전 문장까지만 포함

## Files to Modify
- `scripts/blog_draft_generator.py` - `_save_file()` 함수 내 description 추출 로직

## Acceptance Criteria
1. frontmatter description이 완결된 문장으로 끝남 (종결어미 포함)
2. 250자 제한은 유지하되 문장 경계에서 자름
3. 기존 블로그 포스트들(description 잘린 것들) 백필 스크립트 필요 시 작성