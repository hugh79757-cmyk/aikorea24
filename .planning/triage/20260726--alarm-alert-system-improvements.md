---
date: 2026-07-26
type: fix
status: resolved
---

# Alarm/Alert System Improvements — 썸네일 중복 알림 + 품질 체크 + 텔레그램 스팸 방지

## What
블로그 발행 파이프라인에 알림/경보 시스템 추가 및 텔레그램 중복 발송 버그 수정

## Why
1. **썸네일 중복 감지 시 알림 필요** — Phase 28-02: 동일 썸네일 재사용 시 즉시 인지 필요
2. **발행 전 품질 체크 알림** — Phase 28-03: 썸네일 품질(파일크기/해상도/포맷) 미달 시 경고
3. **텔레그램 10분마다 중복 발송** — pipeline-runner가 blog-draft를 중복 호출해 알림 폭주

## Files Changed

| File | Changes |
|------|---------|
| `scripts/blog_draft_generator.py` | 1. `send_thumbnail_duplicate_alert()` 호출 추가 (라인 472-510)<br>2. 품질 체크리스트 `validate_thumbnail_quality()` 추가 (라인 524-558)<br>3. 미커밋 파일 감지 배포 조건 확대 (라인 628-655) |
| `scripts/auto_thumbnail.py` | `check_thumbnail_duplicates()`, `validate_thumbnail_quality()` export 추가 |
| `scripts/run_pipeline_with_notify.py` | blog-draft 직접 호출 제거 (라인 89-106 삭제) — 중복 실행 방지 |

## How

### 1. 썸네일 중복 알림 (Phase 28-02)
```python
# blog_draft_generator.py 라인 472-510
dup_result = check_thumbnail_duplicates(thumb_paths)
if dup_count > 0:
    send_telegram(f"⚠️ 썸네일 중복: {dup_count}쌍 감지 (재시도 {retry_count}건)")
    # 강제 재시도 (최대 2회, 다른 키워드)
```

### 2. 품질 체크리스트 알림 (Phase 28-03)
```python
# 라인 524-558
for fp, title, sort_order, _ in generated:
    is_valid, reason = validate_thumbnail_quality(thumb_path)
    if not is_valid:
        quality_issues.append((slug, reason))
send_telegram(f"품질 체크리스트: {quality_passed}/{len(generated)} 통과, {len(quality_issues)} 이슈")
```

### 3. 텔레그램 스팸 방지
```python
# run_pipeline_with_notify.py 수정 전 (문제)
blog_result = subprocess.run([sys.executable, blog_draft_script], ...)  # 직접 호출 → 중복 실행

# 수정 후: blog-draft launchd(06:15/20:15)가 독립 실행 → pipeline-runner(06:00/20:00)와 분리
```

## Verification

| Test | Result |
|------|--------|
| 썸네일 중복 5개(7/25) 재생성 | ✅ MD5 모두 고유 |
| placeholder 품질 12.7KB → 45.6KB | ✅ 검증 통과 |
| 8:15 AM 실행 → 1회만 알림 | ✅ 중복 없음 |
| 22:15 PM 미커밋 파일 감지 배포 | ✅ 6개 파일 배포 완료 |
| 사이트 헬스체크 | ✅ HTTP 200 |

## Related
- Phase 28-02: 썸네일 중복 검증 게이트
- Phase 28-03: 발행 전 품질 체크리스트  
- Phase 28-04: 모니터링/알림 (사용자 판단으로 폐기)
- Quick Tasks: `fix-thumbnail-placeholder`, `fix-blog-deploy-condition`, `fix-telegram-spam`