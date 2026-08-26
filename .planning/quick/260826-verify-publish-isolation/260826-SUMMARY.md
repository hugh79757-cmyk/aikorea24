---
type: quick
date: 2026-08-26
slug: verify-publish-isolation
status: complete
---

# Quick Task Summary: verify-publish-isolation

## Results

### 1. Launchd 2시간 스케줄 — PASS
- plist: ~/Library/LaunchAgents/kr.aikorea24.threads-publisher.plist
- StartCalendarInterval 12개: 01,03,05,07,09,11,13,15,17,19,21,23 — 2시간 간격 정확
- ProgramArguments: .venv/bin/python3 scripts/threads/main_v3.py (인자 없음 = 기본 D)
- launchctl list: kr.aikorea24.threads-publisher loaded (0), 최근 실행 로그 2026-08-26 11:01 성공
- 근거: cat plist + launchctl list + logs/launchd.log

### 2. 실발행 경로 무결성 — PASS
- main_v3.py: format_choice default="D", _fmt=="contrast" 분기 제외 시 D 경로 그대로. publish_thread_chain 호출 유지 (line 288 fallback).
- 최근 성공: 2026-08-26 11:01:59 APR 뷰티 5카드 + 링크답글 6개 ID (181065.../179777.../179268.../179154.../179145.../179618...), posted.json titles 778→779
- 실패→재시도 로직: 11:00:26 JSON 파싱 0카드 실패 후 1분 백오프 재시도 성공 → 2시간 주기 내 복구 확인
- 타임아웃 3회는 네트워크 일시 (graph.threads.net ConnectTimeout) — 재시도 3회 로직으로 11:01 복구, 스케줄 자체는 유지
- 근거: grep main_v3 publish_thread_chain + logs/2026-08-26.log tail 200 + posted.json

### 3. 테스트 발행 차단 — PASS (확률 0)
- contrast dry-run: main_v3 if dry_run: draft only — posted.json/vectorize/pitch_history 저장 전부 제거 (패치 2026-08-26 12:44). grep "posted.json" in dry_run block = 0
- contrast publish는 dry_run=False 일 때만 publisher.publish_thread_chain 도달, but launchd는 --format contrast 인자 없이 실행 → 해당 분기 진입 불가
- grep launchd plist "contrast" = 0건, grep crontab/launchd --format = 0건
- orchestrator: save_draft 후 drafts/contrast/로 이동, header # search: cross N bg N — 실 drafts와 물리 분리
- 수동 dry-run 검증: 2026-08-26 12:44 포낙 EON dry-run → draft drafts/contrast/v3_...포낙...txt 생성, posted.json 913/779 전후 동일 유지
- 근거: py_compile orchestrator/main_v3 + grep launchd + ls drafts/contrast 15 vs drafts 880 + posted.json diff 0

### 4. 폴더/이력 분리 — PASS
- drafts/v3_*.txt 880개 (실발행 D) vs drafts/contrast/*.txt 15개 (테스트) — 14개 이전 contrast + 1개 포낙 신규
- 기존 14개 mv 완료, 신규 dry-run 자동 contrast 폴더로 이동 확인
- posted.json 오염 0, posted_titles에 contrast hook 없음 (포낙 등 미반영)

## Residual Risk
- 2028 연도 등 미래 연도 포함 기사는 validator year fail로 drop 후 재시도 없이 스킵 — 스케줄 자체는 다음 2시간에 다른 seed로 정상 재시도되므로 발행 공백 2시간 발생 가능 (허용)
- Threads API ConnectTimeout은 외부 네트워크 — 3회 재시도 후에도 실패 시 해당 슬롯 발행 유실, 다음 스케줄에 자동 복구

## Files Changed
- scripts/threads/main_v3.py (dry_run posted 제거)
- pipeline/threads/contrast/orchestrator.py (contrast drafts 이동)
- .planning/quick/260826-verify-publish-isolation/* (신규)
