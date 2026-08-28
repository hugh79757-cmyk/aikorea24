---
date: 2026-08-28
type: config
status: resolved
---

# 쓰레드 발행 빈도 절반으로 조정 (12→6회/일)

## What
launchd 스케줄을 2시간 간격(12회/일)에서 4시간 간격(6회/일)으로 변경.
출근(08시)·퇴근(20시) 시간대 우선 배치.

## Why
발행 빈도 과다. 사용자 요청으로 절반으로 축소.

## Files changed
- `scripts/threads/threads-publisher.plist.template` — StartCalendarInterval 12→6 entries
- `~/Library/LaunchAgents/kr.aikorea24.threads-publisher.plist` — 배포 plist 동일 적용

## How
기존: 01,03,05,07,09,11,13,15,17,19,21,23시 (12회)
변경: 00,04,08,12,16,20시 (6회)
- 08시 = 출근 시간
- 20시 = 퇴근 시간
- 나머지 = 4시간 간격 균등 배치

launchctl unload/load 리로드 완료.

## Verification
`launchctl list | grep threads-publisher` → 서비스 정상 등록 확인.
