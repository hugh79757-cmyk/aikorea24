---
date: 2026-07-15
type: fix
status: resolved
---

# Pipeline-runner가 blog-draft 직접 호출 (launchd 20:15 미실행 방지)

## What
blog-draft launchd job이 저녁 20:15 Bangkok time에 실행되지 않아 블로그 6편이 누락됨. `run_pipeline_with_notify.py`가 pipeline 성공 직후 `blog_draft_generator.py`를 직접 호출하도록 수정. 이미 발행된 글은 `deep_dive_url` 체크로 자동 스킵되므로 중복 안전.

## Why
macOS Sleep 상태에서 launchd `StartCalendarInterval` job이 skip되어 20:15 blog-draft가 실행되지 않음. pipeline-runner(20:00)는 정상 실행되었으므로, 그 직후 blog-draft를 함께 실행하면 이 문제를 회피 가능.

## Files changed
- `scripts/run_pipeline_with_notify.py` — pipeline 성공 시 blog-draft를 subprocess로 직접 호출 (line 108-121)

## How
pipeline 성공(`result.returncode == 0`) 시 `subprocess.run([sys.executable, blog_draft_script], ...)` 실행. Telegram 메시지에서 "Blog notification follows in 15 minutes" 문구 제거 (더 이상 15분 지연 불필요). launchd `kr.aikorea24.blog-draft`는 backup으로 유지 (이중 방어).

## Verification
- 저녁 블로그 6편 수동 생성 + 배포 완료 (12개 포스트 라이브)
- `python3 -c "import ast; ast.parse(...)"` syntax OK
- site rebuild + wrangler deploy → 12개 포스트 정상 표시
