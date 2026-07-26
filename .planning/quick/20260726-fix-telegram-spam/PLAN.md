# Quick Task: Fix Telegram Spam - Messages Every 10 Minutes

## Description
텔레그램 메시지가 블로그 발행 후 한 번만 와야 하는데 10분마다 반복 발송됨.
- 📭 [2026-07-26] 블로그 발행 - 모두 이미 연결됨 (6건)
- 🚀 [2026-07-26] 블로그 0건 배포 완료
- 이 두 메시지가 10분 간격으로 계속 옴

## Root Cause Candidates
1. **launchd 스케줄이 10분마다 실행되도록 설정됨** - plist의 StartCalendarInterval 확인 필요
2. **blog_draft_generator.py에서 중복 발송 로직** - send_telegram이 여러 번 호출되거나 조건 없이 호출됨
3. **파이프라인/다른 스크립트에서 동일 메시지 발송** - run_pipeline.py나 다른 스크립트에서 중복 호출

## Files to Investigate
- `/Users/twinssn/Library/LaunchAgents/kr.aikorea24.blog-draft.plist` - 스케줄 설정
- `scripts/blog_draft_generator.py` - send_telegram 호출 지점들
- `scripts/run_pipeline.py` - 파이프라인에서 블로그 발행 관련 로직

## Acceptance Criteria
1. launchd가 하루 2회(08:15, 22:15)만 실행되도록 확인/수정
2. 블로그 발행 시 텔레그램 메시지는 정확히 1회만 발송
3. "이미 연결됨" 케이스도 메시지는 1회만 발송