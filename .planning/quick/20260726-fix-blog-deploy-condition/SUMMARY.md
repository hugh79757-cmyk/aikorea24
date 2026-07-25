---
status: complete
completed_at: 2026-07-26T14:30:00+09:00
---

# Quick Task: fix-blog-deploy-condition

## Summary
Fixed the blog deployment condition bug in `blog_draft_generator.py` where deployment only triggered on newly generated posts (`if generated:`), missing existing untracked blog files.

## Changes Made
**File**: `scripts/blog_draft_generator.py` (lines 602-609)

**Before**:
```python
if generated:
    log("[6] Cloudflare Pages 배포 중...")
```

**After**:
```python
# 미커밋 블로그 파일 감지 (git status --porcelain)
untracked_blog_files = []
try:
    import subprocess
    git_status = subprocess.run(
        ["git", "status", "--porcelain", "src/content/blog/"],
        capture_output=True, text=True, timeout=10, cwd=PROJECT_DIR
    )
    if git_status.returncode == 0:
        for line in git_status.stdout.strip().split('\n'):
            if line and (line.startswith('??') or line.startswith('A ')):
                untracked_blog_files.append(line[3:].strip())
except Exception as e:
    log(f"  ⚠️ git status 확인 실패: {e}")

if generated or untracked_blog_files:
    log("[6] Cloudflare Pages 배포 중...")
    if untracked_blog_files:
        log(f"  📦 미커밋 블로그 파일 {len(untracked_blog_files)}개 감지 → 배포 실행")
```

## Effect
- Morning run (08:15): generates 6 posts → `generated` non-empty → deploys ✅
- Evening run (22:15): "이미 연결됨" for all 6 → `generated` empty BUT `untracked_blog_files` detects 6 files → **now deploys** ✅
- Prevents accumulation of undeployed blog posts (previously 19 posts stuck locally)

## Testing
- Syntax check: `python3 -m py_compile scripts/blog_draft_generator.py` → OK
- Git status detection verified: 6 untracked 7/25 blog files (007~012) detected