---
date: 2026-09-17
type: fix
status: resolved
---

# kicker7 초안 누적 차단 + 중복 경로 버그 수정

## What

파이프라인을 돌릴 때마다 kicker7 초안이 생성되어 디스크에 쌓이던 경로를
기본 비활성화. 동시에 초안 저장 경로가 CWD 상대경로라 `scripts/scripts/...`
중복 경로에 쌓이던 버그도 수정.

## Why

누적 원인은 발행 경로가 아니라 **생성 경로**였음. 경로 2개를 구분해야 함:

1. **발행 경로** — `scripts/threads/publish_kicker7_drafts.py`.
   launchd `kr.aikorea24.kicker7-publisher.plist.disabled` 로 **이미 비활성**
   (`.disabled` 확장자, `launchctl list` 미등록). 여기서는 문제 없었음.
2. **생성 경로** — `scripts/auto_news_selector.py` `main()` 말미의
   `route_person_stories(selected)` → `run_contrast_thread(...,
   writer_fn=write_kicker7_thread, ...)` → 초안 파일 저장.
   호출 체인: `kr.aikorea24.pipeline-runner.plist` →
   `scripts/run_pipeline_with_notify.py` (`cwd=PROJECT_DIR`) →
   `scripts/run_pipeline.py` `step_news_selection()` →
   `auto_news_selector.main()`.

즉 발행은 안 되는데 매 실행마다 초안만 쌓였음.

중복 경로 버그: `auto_news_selector.py` 원본 line 453이
`_pl.Path("scripts/threads/logs/drafts/kicker7_selector")` — CWD 상대경로.
CWD가 `scripts/`이면 `scripts/scripts/threads/...`로 생성됨.
실측 누적: 정상 경로 20개 + 중복 경로 59개 = 79개.

## Files changed

- `scripts/auto_news_selector.py` — 게이트 추가 + 절대경로 교체 (+8/-6)

## How

1. 게이트 (line ~561): `try: route_person_stories(selected) except ...` 블록을
   `if os.environ.get("KICKER7_ENABLED", "0") == "1":` 로 감쌈. 기본 비활성.
   `os`는 이미 import 되어 있음. 되살리려면 `KICKER7_ENABLED=1` 설정.
2. 절대경로 (line 453):
   `_pl.Path(PROJECT_DIR) / "scripts/threads/logs/drafts/kicker7_selector"`
   (`PROJECT_DIR` = `pipeline.infra.project_root()`, 파일 상단 line 27에 이미 정의).

## 누적 초안 삭제 (destructive protocol)

- 사전 카운트: 정상경로 20 + 중복경로 59 = 79
- 백업: `logs/backup_kicker7_drafts_20260917_221355.tar.gz` (168K, 165 entries)
- 실행: 두 디렉터리 `rm -rf`
- 사후: 정상경로 0, 중복경로 0, `scripts/scripts/threads/logs/drafts/` 빈 상태
- 로그: `logs/destructive_2026-09-17.log` — `FILE_DELETE kicker7_selector drafts
  | 사전=A20+B59=79 | 백업=... | 사후=A0+B0 | 보존확인=YES`

## Verification

- `python3 -m py_compile scripts/auto_news_selector.py` OK.
- 실동작: `python3 scripts/run_pipeline.py --skip-briefing --skip-email
  --skip-thumbnails --skip-deploy` 실행 →
  `선정 완료: 6개 기사`까지 진행, kicker7 로그 0건,
  `find scripts -path '*kicker7_selector*' -name 'k7_*.txt'` 결과 0개
  (BEFORE=0 AFTER=0).
- 커밋: `2d0fbbc9`

## 잔존 위험

- `publish_kicker7_drafts.py` 파일 자체는 남아 있음 (삭제 안 함). 게이트가
  생성까지 막으므로 이중 방어 상태. 되살릴 계획이 없으면 파일도 정리 가능.
- `KICKER7_ENABLED=1`로 되돌리면 중복 경로 버그는 수정됐으나 게이트 이전과
  동일한 생성량이 재개됨.
