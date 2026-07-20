---
date: 2026-07-20
type: fix
status: resolved
---

# Pipeline 경로 중복 버그 (scripts/scripts/)

## What
`run_pipeline_with_notify.py`에서 `SCRIPTS_DIR`이 `scripts/scripts/`로 중복되어 `run_pipeline.py`와 `blog_draft_generator.py`를 찾지 못하는 버그. 이로 인해 launchd 파이프라인(`kr.aikorea24.pipeline-runner`)이 매일 실행될 때:
- `run_pipeline.py` → `FileNotFoundError` (에러 캐치 → Telegram 알림만)
- `blog_draft_generator.py` → 아예 실행 안 됨

**영향**: 7/19, 7/20 블로그 발행 0건. 브리핑도 미발행.

## Why
과거 `PROJECT_DIR = '/Users/twinssn/Projects/aikorea24'` (하드코딩, 루트)였다가,
7/15 commit `4124a7b`에서 경로를 동적으로 바꾸면서 코드가:

```python
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
# → .../aikorea24/scripts/  (run_pipeline_with_notify.py는 scripts/ 아래)

SCRIPTS_DIR = os.path.join(PROJECT_DIR, 'scripts')
# → .../aikorea24/scripts/scripts/  ← 중복!
```

`__file__`이 이미 `scripts/` 디렉토리 라는 점을 간과하고 `scripts`를 한 번 더 붙임.

## Files changed
- `scripts/run_pipeline_with_notify.py` (Line 20): `SCRIPTS_DIR` 계산 수정

## How
`_PROJECT_DIR` (2단계 상위 = 루트)를 사용하여 `SCRIPTS_DIR = os.path.join(_PROJECT_DIR, 'scripts')`로 정정.
`_PROJECT_DIR`은 이미 `sys.path.insert(0, _PROJECT_DIR)`에서 사용 중이었음.

## Verification
- `python3 -c` 동적 경로 검증: SCRIPTS_DIR = .../aikorea24/scripts (정확)
- `run_pipeline.py` 존재 확인: `True`
- `blog_draft_generator.py` 존재 확인: `True`
- `npm run build` + `wrangler pages deploy` 성공
- 사이트 12개 블로그 포스트 라이브
