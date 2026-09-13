---
date: 2026-09-13
type: fix
status: resolved
---

# Kicker7 비활성화 + v3 스케줄 변경 + 블로그 배포 자동 설치

## What
1. kicker7-publisher 발행 비활성화 (발행 품질 7% 성공률)
2. v3 threads-publisher 스케줄 4h→2h 변경 (하루 12건)
3. blog_draft_generator에 node_modules 자동 설치 가드 추가

## Why
- kicker7: 55개 초안 중 4개만 발행(7%), 무근거 카드/화자실명누락 빈번
- v3: 하루 6건→12건으로 확대 필요
- 블로그 배포: node_modules 비어있으면 astro build 실패 반복

## Files changed
- `scripts/threads/publish_kicker7_drafts.py` — `--max` 인자 + `published_count` break
- `/Users/twinssn/Library/LaunchAgents/kr.aikorea24.threads-publisher.plist` — 4h→2h
- `/Users/twinssn/Library/LaunchAgents/kr.aikorea24.kicker7-publisher.plist` → `.disabled`
- `scripts/blog_draft_generator.py` — node_modules 자동 설치 가드 (npm install + npm run build)

## How
- kicker7: launchctl bootout + plist 이름 변경 (.disabled)
- v3: plist StartCalendarInterval 12시간대로 변경 (0,2,4,...,22)
- 블로그: build 전 `node_modules/.bin/astro` 존재 여부 확인, 없으면 npm install 자동 실행

## Verification
- kicker7: `launchctl list | grep kicker7` → unloaded 확인
- v3: `launchctl list | grep threads-publisher` → loaded, 다음 실행 12:00 확인
- 블로그: `npm run build` → astro 65.59s 성공, wrangler 배포 성공
