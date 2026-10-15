---
name: aik24-manual-pipeline
description: aikorea24 파이프라인 수동 실행 전용. 트리거 문구: "파이프라인 수동 실행", "파이프라인 돌려줘", "수동으로 돌려". 수동 실행 시 이메일 발송 절대 금지.
---

# aik24-manual-pipeline — 파이프라인 수동 실행

## 절대 규칙 (MUST)

- **수동 실행에는 `--no-email`을 항상 붙인다.** 예외 없음.
- 이메일은 자동 스케줄 실행(인자 없이 실행되는 launchd/cron 경로)에서만 발송된다.
- `--no-email` 없이 파이프라인을 실행하는 것은 금지.

## 수동 실행 명령 (이 순서대로)

```bash
cd /Users/twinssn/Projects/aikorea24

# 1. 먼저 계획만 확인 (이메일 발송 없음, 부작용 없음)
.venv/bin/python3 scripts/run_pipeline.py --dry-run --no-email

# 2. 실제 수동 실행 (이메일 발송 안 함)
.venv/bin/python3 scripts/run_pipeline_with_notify.py --no-email [추가 인자...]
# 예: 뉴스 수집까지 다시 하려면
.venv/bin/python3 scripts/run_pipeline_with_notify.py --no-email --collect
```

## 금지 명령

```bash
# 금지 — 구독자에게 실제 이메일이 발송됨
.venv/bin/python3 scripts/run_pipeline_with_notify.py
.venv/bin/python3 scripts/run_pipeline.py
.venv/bin/python3 scripts/run_pipeline.py --dry-run   # dry-run이어도 --no-email 병행
```

## 이중 안전 구조 (코드 측)

1. `run_pipeline.py --no-email` → Step 5 이메일 단계 건너뜀 + `[pipeline] --no-email: 이메일 발송 건너뜀` 로그.
2. `--dry-run`은 Step 5 이전에 조기 반환되므로 이메일 코드에 도달하지 않음.
3. wrapper(`run_pipeline_with_notify.py`)는 인자를 그대로 전달하므로 `--no-email`이 내부까지 흐른다.

## 실행 후 확인

- 로그에 `[pipeline] --no-email: 이메일 발송 건너뜀` 2회(wrapper 1 + 내부 1) 출력됐는지 확인.
- `scripts/auto_email_sender.py`를 직접 실행하지 않았는지 확인.
- 완료 후 `docs/state.md` 맨 위에 스테이트먼트 1건 추가 (한 일 / 결과 / 잔존 위험 / 다음 행동).
